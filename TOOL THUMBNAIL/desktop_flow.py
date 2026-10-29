"""Direct Chrome controller. No installed extension or native-messaging port."""
import asyncio
import copy
import importlib.util
import json
import hashlib
from pathlib import Path
import re
import threading
import uuid
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CODE_ROOT = ROOT
spec = importlib.util.spec_from_file_location('studio_files', ROOT / 'chrome-extension/native-host/host.py')
file_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(file_module)


def is_flow(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and (parsed.hostname in ('flow.google.com', 'flow.google') or parsed.hostname == 'labs.google' and re.match(r'^/fx/(?:[^/]+/)?tools/flow(?:/|$)', parsed.path))


class DesktopFlow:
    def __init__(self, on_state, on_error):
        self.on_state, self.on_error = on_state, on_error
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.context = self.playwright = self.page = None
        self.profile = None
        self.state = {'history': [], 'limits': {}}
        self.files = file_module.Files()
        self.downloads = {}
        self.armed = None
        self.busy = False
        self.cancelled = False
        self.session_task = None
        self.reference_path = None
        self.opening = False
        self.recovery_ids = set()
        self.external_browser = None

    async def disconnect(self):
        if self.context and not self.external_browser:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        self.context = self.page = self.playwright = self.external_browser = None

    async def connect_existing(self, source):
        if self.busy or self.opening:
            raise ValueError('Chờ lượt hiện tại kết thúc trước khi kết nối Chrome.')
        self.opening = True
        try:
            from chrome_profile import discover_profiles
            folder = Path(source).resolve(strict=True)
            if str(folder) not in [p['path'] for p in discover_profiles(folder.parent)]:
                raise ValueError('Hồ sơ Chrome đã chọn không còn tồn tại. Quét lại hồ sơ.')
            active = folder.parent / 'DevToolsActivePort'
            try:
                lines = active.read_text(encoding='utf-8').splitlines()
                port = int(lines[0])
                path = lines[1].strip()
                if not 1 <= port <= 65535 or not re.fullmatch(r'/devtools/browser/[a-zA-Z0-9-]+', path):
                    raise ValueError()
            except (OSError, ValueError, IndexError):
                raise ValueError('Trong Chrome đang dùng, mở chrome://inspect/#remote-debugging và bật Allow remote debugging for this browser instance (Chrome 144+). Giữ Flow mở, sau đó bấm Kết nối Chrome đang mở và chọn Allow nếu Chrome hỏi. Không cần nhập phiên hoặc đăng nhập lại.')
            await self.disconnect()
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()
            try:
                browser = await self.playwright.chromium.connect_over_cdp(f'ws://127.0.0.1:{port}{path}', timeout=60000)
            except Exception:
                await self.disconnect()
                raise ValueError('Chưa kết nối được Chrome. Kiểm tra đã bật Remote debugging, rồi bấm Allow trong Chrome khi có yêu cầu kết nối. Tool không mở hồ sơ mới.')
            self.external_browser = browser
            self.connected_source = str(folder)
            self.profile = 'chrome-' + hashlib.sha256(str(folder).encode()).hexdigest()[:16]
            state_path = ROOT / 'desktop-data' / self.profile / 'state.json'
            self.state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'history': [], 'limits': {}}
            pages = [p for ctx in browser.contexts for p in ctx.pages if is_flow(p.url)]
            if not pages:
                raise ValueError('Đã kết nối Chrome hiện tại nhưng chưa có tab Flow. Bạn mở dự án Flow trong Chrome rồi kết nối lại.')
            self.context = pages[0].context
            self.external_pages = pages
            for page in pages:
                await page.evaluate('delete globalThis.__studioBridge')
                await page.expose_binding('__studioBridge', self.bridge)
                self.watch_page(page)
            self.page = pages[0] if len(pages) == 1 else None
            self.on_state({'running': False, 'logs': [f'Đã kết nối Chrome đang mở: {len(pages)} tab Flow. Chọn tab cần chạy. Không sao chép phiên đăng nhập.'], 'items': [], 'history': self.state['history'], 'limits': self.state['limits']})
            return [{'title': await p.title(), 'url': p.url, 'index': i} for i, p in enumerate(pages)]
        finally:
            self.opening = False

    async def select_existing_tab(self, index, expected_url=None):
        if self.busy or not self.external_browser:
            raise ValueError('Kết nối Chrome trước khi chọn tab.')
        pages = [p for ctx in self.external_browser.contexts for p in ctx.pages if is_flow(p.url)]
        if not 0 <= index < len(pages):
            raise ValueError('Tab đã thay đổi. Kết nối lại Chrome để chọn tab.')
        page = pages[index]
        if expected_url and page.url != expected_url:
            raise ValueError('Tab đã thay đổi. Kết nối lại Chrome để chọn đúng dự án.')
        if page not in self.external_pages:
            await page.evaluate('delete globalThis.__studioBridge')
            await page.expose_binding('__studioBridge', self.bridge)
            self.watch_page(page)
            self.external_pages.append(page)
        self.context = page.context
        self.page = page
        await page.bring_to_front()

    def submit(self, coroutine):
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        def completed(job):
            try:
                job.result()
            except Exception as error:
                self.on_error(str(error))
        future.add_done_callback(completed)
        return future

    def save_state(self):
        path = ROOT / 'desktop-data' / self.profile / 'state.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.state, ensure_ascii=False), encoding='utf-8')
        temp.replace(path)

    async def open(self, profile='account-1'):
        if self.opening:
            raise ValueError('Đang mở Chrome. Chờ kết nối xong.')
        self.opening = True
        try:
            await self._open(profile)
        finally:
            self.opening = False

    async def import_chrome_session(self, source, profile):
        if self.busy or self.opening:
            raise ValueError('Chờ lượt hiện tại hoặc thao tác mở Chrome kết thúc trước khi nhập hồ sơ.')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', profile):
            raise ValueError('Tên hồ sơ dùng chữ không dấu, số, dấu - hoặc _.')
        self.opening = True
        try:
            if self.context or self.external_browser:
                await self.disconnect()
            from chrome_profile import import_session
            await asyncio.to_thread(import_session, source, ROOT / 'desktop-data' / profile / 'chrome-profile')
            await self._open(profile)
            self.on_state({'running': False, 'logs': ['Đã nhập dữ liệu phiên Chrome. Kiểm tra đăng nhập trên Flow; Google có thể yêu cầu đăng nhập lại.'], 'items': [], 'history': self.state['history'], 'limits': self.state['limits']})
        finally:
            self.opening = False

    async def _open(self, profile):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', profile):
            raise ValueError('Tên hồ sơ dùng chữ không dấu, số, dấu - hoặc _.')
        if self.busy:
            raise ValueError('Dừng lượt hiện tại trước khi đổi hồ sơ.')
        if self.context and self.profile == profile:
            pages = [page for page in self.context.pages if is_flow(page.url)]
            page = pages[0] if pages else await self.context.new_page()
            if not pages:
                await page.goto('https://labs.google/fx/tools/flow', wait_until='domcontentloaded')
            await page.bring_to_front()
            return
        if self.context:
            await self.disconnect()
        from playwright.async_api import async_playwright
        if not self.playwright:
            self.playwright = await async_playwright().start()
        self.profile = profile
        path = ROOT / 'desktop-data' / profile
        path.mkdir(parents=True, exist_ok=True)
        state_path = path / 'state.json'
        self.state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'history': [], 'limits': {}}
        self.context = await self.playwright.chromium.launch_persistent_context(str(path / 'chrome-profile'), channel='chrome', headless=False, accept_downloads=True, no_viewport=True, args=['--profile-directory=Default'])
        await self.context.expose_binding('__studioBridge', self.bridge)
        self.context.on('page', self.watch_page)
        for page in self.context.pages:
            self.watch_page(page)
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        await self.page.goto('https://labs.google/fx/tools/flow', wait_until='domcontentloaded')
        self.on_state({'running': False, 'logs': ['Đã mở Chrome trực tiếp. Đăng nhập và mở đúng một dự án Flow.'], 'items': [], 'history': self.state['history'], 'limits': self.state['limits']})

    def watch_page(self, page):
        page.on('download', lambda download: asyncio.create_task(self.capture_download(page, download)))

    async def flow_page(self):
        if self.external_browser:
            if self.page and not self.page.is_closed() and is_flow(self.page.url):
                await self.page.bring_to_front()
                return self.page
            raise ValueError('Chọn tab Flow đang mở bằng nút Kết nối Chrome đang mở trước khi tạo ảnh.')
        if not self.context:
            raise ValueError('Bấm Mở Google Flow để mở cửa sổ Chrome do Desktop điều khiển. Tab Flow trong Chrome thường không tự kết nối với tool. Muốn dùng phiên có sẵn: chọn hồ sơ nguồn rồi bấm Nhập phiên từ Chrome.')
        pages = [page for page in self.context.pages if is_flow(page.url)]
        if not pages:
            page = await self.context.new_page()
            await page.goto('https://labs.google/fx/tools/flow', wait_until='domcontentloaded')
            await page.bring_to_front()
            raise ValueError(f'Đã mở Flow trong cửa sổ Chrome của Desktop (hồ sơ {self.profile}). Hãy đăng nhập nếu cần, mở một dự án rồi bấm Tạo ảnh lại. Flow đang mở trong Chrome thường thuộc cửa sổ khác, tool chưa điều khiển tab đó.')
        if len(pages) != 1:
            raise ValueError(f'Hồ sơ Desktop {self.profile} đang có {len(pages)} tab Flow. Giữ một tab dự án cần tạo ảnh và đóng các tab Flow còn lại trong cửa sổ Chrome của Desktop.')
        await pages[0].bring_to_front()
        return pages[0]

    async def inject(self, page):
        await page.evaluate((CODE_ROOT / 'desktop-runtime.js').read_text(encoding='utf-8'))
        for name in ['flow-errors.js', 'flow-models.js', 'flow-settings.js', 'flow-downloads.js', 'flow-clicks.js', 'content.js']:
            await page.evaluate((CODE_ROOT / 'chrome-extension' / name).read_text(encoding='utf-8'))

    async def request(self, page, message):
        return await page.evaluate('message => __studioRequest(message)', message)

    async def start(self, prompt, reference, model, count, output, options=None):
        if self.opening:
            raise ValueError('Chờ mở Chrome hoặc nhập hồ sơ xong trước khi tạo ảnh.')
        if self.busy:
            raise ValueError('Đang chạy một lượt. Không gửi chồng lên nhau.')
        if not prompt.strip():
            raise ValueError('Chưa nhập prompt.')
        destination = Path(output).resolve(strict=True)
        if not destination.is_dir():
            raise ValueError('Nơi lưu không phải thư mục.')
        page = await self.flow_page()
        if self.busy:
            raise ValueError('Một lượt khác vừa bắt đầu. Không gửi thêm.')
        self.cancelled = False
        self.page = page
        self.files = file_module.Files()
        self.files.directory = destination
        self.reference_path = str(Path(reference).resolve(strict=True)) if reference else None
        if self.reference_path:
            from PIL import Image
            image_path = Path(self.reference_path)
            if image_path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp') or not 0 < image_path.stat().st_size <= 20*1024*1024:
                self.busy = False
                raise ValueError('Chọn ảnh PNG/JPG/WebP tối đa 20 MB.')
            try:
                with Image.open(image_path) as image:
                    image.verify()
            except Exception:
                self.busy = False
                raise
        self.busy = True
        self.armed = None
        self.recovery_ids = set()
        self.session_task = asyncio.current_task()
        try:
            args = {'prompt': prompt, 'reference': {'path': self.reference_path, 'data': 'desktop', 'name': Path(reference).name} if reference else None,
                    'fileName': 'Desktop', 'cfg': {**(options or {}), 'observationDelayMs': 1200, 'verifySubmission': True, 'count': str(count), 'modelChoice': model, 'timeout': str((options or {}).get('timeout', '240')), 'clickMode': (options or {}).get('clickMode', 'native'), 'saveMode': 'windows', 'image': (options or {}).get('image', 'img')}}
            checkpoint = {'id': uuid.uuid4().hex, 'initialReload': True, 'nextAttempt': 1, 'args': args, 'attempts': []}
            project_url = page.url
            while checkpoint:
                if self.cancelled:
                    break
                self.next_checkpoint = None
                self.on_state({'running': True, 'logs': ['F5 Flow, chờ tải xong và thêm 2 giây…'], 'items': []})
                await page.reload(wait_until='load')
                await asyncio.sleep(2)
                if self.cancelled:
                    break
                if page.url != project_url or await self.flow_page() != page:
                    raise ValueError('Tab hoặc dự án Flow đã đổi. Đã dừng trước khi gửi.')
                await self.inject(page)
                result = await self.request(page, {'type': 'resumeRun', 'checkpoint': checkpoint})
                if not result.get('ok'):
                    raise ValueError(result.get('error', 'Không bắt đầu được lượt Desktop.'))
                while not self.cancelled:
                    status = await self.request(page, {'type': 'status', 'cfg': args['cfg']})
                    if self.next_checkpoint or not status.get('running'):
                        break
                    await asyncio.sleep(0.5)
                checkpoint = self.next_checkpoint
        finally:
            finish_message = 'Lượt Desktop đã kết thúc.'
            if not self.cancelled and self.state.get('history') and self.state['history'][0].get('status') in ('done', 'partial'):
                try:
                    await page.keyboard.press('Escape')
                    await asyncio.sleep(1.2)
                    await page.keyboard.press('Escape')
                    prompt_box = page.locator((options or {}).get('prompt') or 'textarea,[contenteditable="true"]').filter(visible=True)
                    if await prompt_box.count() != 1:
                        raise ValueError('Chưa thấy duy nhất ô prompt sau khi tải.')
                    await prompt_box.focus()
                    finish_message = 'Đã đóng bản xem và trở về ô prompt, sẵn sàng cho lượt tiếp theo.'
                except Exception:
                    finish_message = 'Ảnh đã lưu. Chưa xác nhận trở về ô prompt; đóng bản xem trên Flow trước lượt tiếp theo.'
            self.busy = False
            self.session_task = None
            self.on_state({'running': False, 'logs': [finish_message], 'items': [], 'history': self.state['history'], 'limits': self.state['limits'], 'finished': True})

    async def stop(self):
        self.cancelled = True
        if self.page and not self.page.is_closed():
            try:
                await self.request(self.page, {'type': 'stop'})
            except Exception:
                pass

    async def shutdown(self):
        await self.stop()
        if self.session_task:
            try:
                await asyncio.wait_for(asyncio.shield(self.session_task), timeout=3)
            except Exception:
                pass
        await self.disconnect()

    async def reset_limits(self):
        if self.busy:
            raise ValueError('Dừng trước khi đặt lại hạn mức.')
        self.state['limits'] = {}
        if self.profile:
            self.save_state()
        self.on_state({'running': False, 'logs': ['Đã đặt lại bằng chứng hạn mức sau khi đổi tài khoản.'], 'items': [], 'limits': {}})

    async def capture_download(self, page, download):
        entry = self.armed
        if not entry or page != self.page or entry.get('state') != 'waiting':
            return
        entry['state'] = 'saving'
        try:
            folder = ROOT / 'desktop-data' / self.profile / 'downloads'
            folder.mkdir(parents=True, exist_ok=True)
            suffix = Path(download.suggested_filename).suffix.lower()
            path = folder / (entry['token'] + (suffix if suffix in ('.png', '.jpg', '.jpeg', '.webp', '.avif') else '.jpg'))
            await download.save_as(path)
            entry.update(state='complete', filename=str(path), id=entry['token'])
        except Exception as error:
            entry.update(state='interrupted', error=str(error))

    async def bridge(self, source, message):
        page = source['page']
        if page != self.page or not is_flow(page.url):
            return {'error': 'Không nhận thao tác ngoài tab Flow đang chạy.'}
        try:
            kind = message['type']
            if kind == 'persist':
                state = copy.deepcopy(message['values'].get('lastRun', {}))
                state.update(history=self.state['history'], limits=self.state['limits'])
                state['running'] = self.busy
                self.on_state(state)
                return {'ok': True}
            if kind == 'readRecords':
                return {'history': self.state['history'], 'limits': self.state['limits']}
            if kind == 'saveHistory':
                row = message['run']
                self.state['history'] = ([row] + [r for r in self.state['history'] if r['id'] != row['id']])[:100]
                self.save_state()
                return {'ok': True}
            if kind == 'quotaHit':
                row = self.state['limits'].setdefault(message['model'], {'count': 0, 'events': []})
                event = f"{message.get('runId')}:{message.get('attempt')}"
                if event not in row['events']:
                    row['events'].append(event)
                    row['count'] += 1
                    row['disabled'] = row['count'] >= 3
                    self.save_state()
                return {'limits': self.state['limits']}
            if kind == 'recoverRun':
                cp = message['checkpoint']
                if cp['nextAttempt'] != 2 or self.next_checkpoint or cp['id'] in self.recovery_ids:
                    raise ValueError('Không phục hồi quá một lần.')
                self.recovery_ids.add(cp['id'])
                self.next_checkpoint = cp
                return {'ok': True}
            if kind == 'nativeEscape':
                await page.keyboard.press('Escape')
                return {'ok': True}
            if kind == 'nativeClick':
                await asyncio.sleep(1.2)
                point = await self.request(page, {'type': 'resolveClick', 'token': message['token']})
                if point.get('error'):
                    return {'error': point['error'], 'code': 'click_not_sent'}
                await page.mouse.move(point['x'], point['y'])
                await asyncio.sleep(0.1)
                verified = await self.request(page, {'type': 'resolveClick', 'token': message['token']})
                if verified != point:
                    return {'error': verified.get('error', 'Điểm bấm chưa ổn định.'), 'code': 'click_not_sent'}
                await page.mouse.click(point['x'], point['y'])
                return {'ok': True}
            if kind == 'desktopAttach':
                if not self.reference_path or message['reference'].get('path') != self.reference_path:
                    raise ValueError('Ảnh mẫu của lượt hiện tại đã thay đổi.')
                await self.attach_reference(page, self.reference_path)
                return {'ok': True}
            if kind == 'armFlowDownload':
                if self.armed:
                    raise ValueError('Đang chờ một ảnh tải.')
                token = uuid.uuid4().hex
                self.armed = {'token': token, 'state': 'waiting'}
                return {'ok': True, 'token': token}
            if kind in ('flowDownloadStatus', 'cancelFlowDownload', 'readFlowDownload'):
                entry = self.armed
                if not entry or entry['token'] != message['token']:
                    raise ValueError('Lượt tải không còn hiệu lực.')
                if kind == 'cancelFlowDownload':
                    self.armed = None
                    return {'ok': True}
                if kind == 'flowDownloadStatus':
                    return copy.deepcopy(entry)
                if entry.get('pair'):
                    return entry['pair']
                if entry['state'] != 'complete':
                    raise ValueError('Ảnh chưa tải xong.')
                original = entry.get('original')
                if not original:
                    original = self.files.import_image(message['path'], entry['filename'])
                    entry['original'] = original
                crop = self.files.crop_image(original['filename'], True)
                entry['pair'] = {**original, 'croppedFilename': crop['filename'], 'crop': {'width': crop['width'], 'height': crop['height']}}
                return entry['pair']
            if kind == 'writeImage':
                result = self.files.write(message['path'], message['data'])
                crop = self.files.crop_image(result['filename'], True)
                return {**result, 'croppedFilename': crop['filename']}
            if kind == 'downloadStatus':
                return self.downloads.get(message['id'], {'error': 'Không có lượt tải này.'})
            if kind == 'download':
                import base64
                url = message['url']
                token = uuid.uuid4().hex
                if url.startswith('data:image/'):
                    match = re.fullmatch(r'data:image/(png|jpeg|webp|avif);base64,([A-Za-z0-9+/=]+)', url)
                    if not match or len(url)>30*1024*1024:
                        raise ValueError('Dữ liệu ảnh tải không hợp lệ.')
                    data = base64.b64decode(match[2], validate=True)
                    ext = 'jpg' if match[1]=='jpeg' else match[1]
                elif urlparse(url).scheme == 'https':
                    response = await page.request.get(url, timeout=30000)
                    if not response.ok:
                        raise ValueError('Không đọc được ảnh gốc HTTPS.')
                    data = await response.body()
                    ext = {'image/jpeg':'jpg','image/png':'png','image/webp':'webp','image/avif':'avif'}.get(response.headers.get('content-type','').split(';')[0])
                    if not ext:
                        raise ValueError('URL tải không trả về ảnh.')
                else:
                    raise ValueError('Chỉ tải ảnh HTTPS hoặc data:image.')
                if not 0 < len(data) <= 20*1024*1024:
                    raise ValueError('Ảnh tải vượt 20 MB hoặc rỗng.')
                folder = ROOT / 'desktop-data' / self.profile / 'downloads'
                folder.mkdir(parents=True, exist_ok=True)
                filename = folder / (token+'.'+ext)
                filename.write_bytes(data)
                self.downloads[token] = {'state':'complete', 'filename':str(filename)}
                return {'id':token}
            raise ValueError('Lệnh Desktop chưa hỗ trợ: ' + kind)
        except Exception as error:
            return {'error': str(error), 'code': 'reference_unverified' if message.get('type') == 'desktopAttach' else None}

    async def attach_reference(self, page, path):
        pending = set()
        def started(request):
            if request.method in ('POST', 'PUT', 'PATCH') and (re.search(r'upload|storage|media|asset', request.url, re.I) or re.search(r'image/|multipart/', request.headers.get('content-type', ''), re.I)):
                pending.add(request)
        def finished(request):
            pending.discard(request)
        page.on('request', started)
        page.on('requestfinished', finished)
        page.on('requestfailed', finished)
        try:
            await self._attach_reference(page, path, pending)
        finally:
            page.remove_listener('request', started)
            page.remove_listener('requestfinished', finished)
            page.remove_listener('requestfailed', finished)
            try:
                await page.evaluate('globalThis.__studioUploadWatch?.observer.disconnect()')
            except Exception:
                pass

    async def _attach_reference(self, page, path, pending):
        """Real file upload and explicit asset-picker confirmation."""
        editor = page.locator('textarea,[contenteditable="true"]').filter(visible=True)
        if await editor.count() != 1:
            raise ValueError('Không xác định được duy nhất ô prompt.')
        box = await editor.bounding_box()
        before = await self.composer_images(page, box)
        inputs = page.locator('input[type=file][accept*="image"],input[type=file][accept*=".png"],input[type=file][accept*=".jpg"]')
        upload = page.get_by_role('button', name=re.compile(r'tải (nội dung|ảnh|hình ảnh|tệp)|upload', re.I)).filter(visible=True)
        if await inputs.count() != 1 and await upload.count() == 0:
            token = uuid.uuid4().hex
            candidates = await page.evaluate("""({box,token}) => {
              const visible=e=>e.getClientRects().length && !e.disabled;
              const rows=[...document.querySelectorAll('button,[role="button"]')].filter(visible).filter(e=>{
                const r=e.getBoundingClientRect();const text=(e.innerText || '').trim();const aria=e.getAttribute('aria-label') || '';
                return r.left>=box.x-30 && r.right<=box.x+150 && r.top>=box.y-30 && r.bottom<=box.y+box.height+180 &&
                  (/^(add|add_2|\\+|thêm)$/i.test(text) || /add|thêm/i.test(aria) || !text && !!e.querySelector('svg'));
              });if(rows.length===1)rows[0].setAttribute('data-studio-add',token);return rows.length;
            }""", {'box': box, 'token': token})
            if candidates != 1:
                raise ValueError(f'Không xác định được nút thêm ảnh cạnh prompt ({candidates} ứng viên).')
            await page.locator(f'[data-studio-add="{token}"]').click()
            await upload.first.wait_for(state='visible', timeout=10000)
        await asyncio.sleep(1.2)
        await page.evaluate("""() => {
            globalThis.__studioUploadWatch?.observer.disconnect();
            const identity=src=>globalThis.FlowDownloads?.identity?.(src) || src;
            const known=new Set([...document.images].map(e=>identity(e.currentSrc || e.src)).filter(Boolean));
            const recent=new Map();let sequence=0;
            const scan=()=>{for(const img of document.images){const src=identity(img.currentSrc || img.src);if(src && !known.has(src) && !recent.has(src))recent.set(src,++sequence);}};
            const observer=new MutationObserver(scan);
            observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['src','srcset']});
            globalThis.__studioUploadWatch={identity,known,recent,observer,scan};
        }""")
        if await inputs.count() == 1:
            await inputs.set_input_files(path)
        else:
            if await upload.count() != 1:
                raise ValueError('Không thấy duy nhất nút Tải nội dung lên.')
            async with page.expect_file_chooser(timeout=10000) as chooser:
                await upload.click()
            await (await chooser.value).set_files(path)
        deadline = asyncio.get_running_loop().time() + 300
        next_progress = 0
        quiet_since = None
        confirmed = False
        while asyncio.get_running_loop().time() < deadline:
            if self.cancelled:
                raise ValueError('Đã dừng tải ảnh mẫu.')
            now = asyncio.get_running_loop().time()
            busy = page.locator('[role="progressbar"],[aria-busy="true"]').filter(visible=True)
            uploading = page.get_by_text(re.compile(r'^(uploading|processing|đang tải(?: lên)?|đang xử lý)(?:[.\s…\d%]*)$', re.I)).filter(visible=True)
            loading = bool(pending) or await busy.count() > 0 or await uploading.count() > 0
            if loading:
                quiet_since = None
            elif quiet_since is None:
                quiet_since = now
            if now >= next_progress:
                text = f'Ảnh nguồn: {Path(path).name}. ' + ('Đang chờ Flow tải/xử lý; chưa chọn ảnh, chưa gửi prompt.' if loading else 'Đang chờ ảnh upload mới nhất xuất hiện; chưa gửi prompt.')
                try:
                    await self.request(page, {'type':'uploadProgress', 'text':text})
                except Exception:
                    pass
                next_progress = now + 10
            if loading or now - quiet_since < 2:
                await asyncio.sleep(0.5)
                continue
            add = page.get_by_role('button', name=re.compile(r'thêm vào câu lệnh|add to prompt', re.I))
            if await add.count() == 1 and await add.is_visible():
                if not confirmed and await add.is_enabled():
                    # Upload may leave an older asset selected in the picker.
                    # Select only an image visually matching the chosen file.
                    picker_token = uuid.uuid4().hex
                    await add.evaluate('''(button, token) => {
                        let node=button.parentElement;
                        while(node && node!==document.body && !(node.querySelector('img') && [...node.querySelectorAll('button')].some(e=>/upload|tải (nội dung|ảnh|tệp)/i.test(e.innerText || ''))))node=node.parentElement;
                        (node || document.body).setAttribute('data-studio-picker', token);
                    }''', picker_token, timeout=2000)
                    picker = page.locator(f'[data-studio-picker="{picker_token}"]')
                    matches = await picker.evaluate("""root => {
                        const watch=globalThis.__studioUploadWatch;
                        watch.scan();
                        const matches=[];
                        for(const img of root.querySelectorAll('img')) {
                            const r=img.getBoundingClientRect();
                            if(!img.complete || !img.naturalWidth || !img.getClientRects().length || r.width<40 || r.height<30)continue;
                            const src=img.currentSrc || img.src;
                            const sequence=watch.recent.get(watch.identity(src));
                            if(!sequence)continue;
                            const token=crypto.randomUUID?.() || String(Date.now())+'-'+Math.random().toString(16).slice(2);
                            img.setAttribute('data-studio-reference',token);
                            matches.push({token,src,sequence});
                        }
                        return matches.sort((a,b)=>b.sequence-a.sequence);
                    }""")
                    if not matches:
                        await asyncio.sleep(1)
                        continue
                    target = picker.locator(f'[data-studio-reference="{matches[0]["token"]}"]')
                    try:
                        await target.click(timeout=1500)
                    except Exception:
                        await asyncio.sleep(0.5)
                        continue
                    await asyncio.sleep(1.2)
                    try:
                        await self.request(page, {'type':'uploadProgress', 'text':'Upload đã xong. Đã chọn ảnh mới nhất của lần upload này; đang thêm vào prompt.'})
                    except Exception:
                        pass
                    # On the current Flow picker, selecting the image and
                    # pressing Enter commits it to the prompt. The Add button
                    # is only a fallback for versions where Enter leaves the
                    # picker open without attaching the image.
                    try:
                        await page.keyboard.press('Enter')
                    except Exception:
                        pass
                    await asyncio.sleep(1.2)
                    fresh_box = await editor.bounding_box()
                    attached = set(await self.composer_images(page, fresh_box)) - set(before)
                    if not attached and await add.count() == 1 and await add.is_visible() and await add.is_enabled():
                        try:
                            await add.click(timeout=2000)
                        except Exception:
                            # A click may have taken effect before the picker
                            # remounted. Verify the composer without clicking
                            # Add again, which could attach the image twice.
                            pass
                    confirmed = True
                    deadline = asyncio.get_running_loop().time() + 60
                    await asyncio.sleep(1.2)
                elif confirmed:
                    # The picker may remain open while Flow updates the
                    # composer. Observe the result; never repeat Enter/Add,
                    # since another activation can attach a duplicate.
                    fresh_box = await editor.bounding_box()
                    images = await self.composer_images(page, fresh_box)
                    new_images = set(images) - set(before)
                    if new_images:
                        if set(images) & set(before):
                            raise ValueError('Ô prompt vẫn còn ảnh cũ chưa bỏ, không khớp lượt upload hiện tại. Bỏ ảnh cũ trước khi chạy lại; chưa gửi.')
                        if len(new_images) != 1:
                            raise ValueError('Ô prompt có nhiều ảnh đính kèm mới. Chưa xác định duy nhất ảnh vừa thêm; chưa gửi.')
                        try:
                            await self.request(page, {'type':'uploadProgress', 'text':'Đã xác nhận ảnh vừa chọn được thêm vào ô prompt. Tiếp tục nhập prompt và tạo ảnh.'})
                        except Exception:
                            pass
                        return
            else:
                fresh_box = await editor.bounding_box()
                images = await self.composer_images(page, fresh_box)
                new_images = set(images) - set(before)
                if confirmed and new_images:
                    if set(images) & set(before):
                        raise ValueError('Ô prompt vẫn còn ảnh cũ chưa bỏ, không khớp lượt upload hiện tại. Bỏ ảnh cũ trước khi chạy lại; chưa gửi.')
                    if len(new_images) != 1:
                        raise ValueError('Ô prompt có nhiều ảnh đính kèm mới. Chưa xác định duy nhất ảnh vừa thêm; chưa gửi.')
                    try:
                        await self.request(page, {'type':'uploadProgress', 'text':'Đã xác nhận ảnh vừa chọn được thêm vào ô prompt. Tiếp tục nhập prompt và tạo ảnh.'})
                    except Exception:
                        pass
                    return
            await asyncio.sleep(0.25)
        raise ValueError('Chưa xác nhận ảnh mẫu: hết thời gian chờ ' + ('đính kèm sau khi thêm ảnh (60 giây).' if confirmed else 'Flow tải/xử lý ảnh và hiện đúng mẫu (5 phút).') + ' Chưa gửi prompt, không tự tải lại file.')

    async def composer_images(self, page, box):
        return await page.evaluate("""box => {
          const visible=e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden';
          const editor=[...document.querySelectorAll('textarea,[contenteditable="true"]')].find(e=>visible(e) && Math.abs(e.getBoundingClientRect().top-box.y)<5);
          let root=null;
          for(let node=editor?.parentElement;node && node!==document.body;node=node.parentElement){
            const r=node.getBoundingClientRect();
            if(r.height>500 || r.width>box.width+220)break;
            if(node.querySelector('button,[role="button"]') && node.querySelector('img')){root=node;break;}
          }
          return [...(root || document).querySelectorAll('img')].filter(e=>{
            const r=e.getBoundingClientRect();return visible(e) && !e.closest('[role="dialog"]') && e.complete && e.naturalWidth>0 && r.top>=box.y-160 && r.bottom<=box.y+box.height+40 && r.left>=box.x-40 && r.right<=box.x+box.width+40 && r.width>=40 && r.height>=30 && r.width<=260 && r.height<=260;
          }).map(e=>globalThis.FlowDownloads?.identity?.(e.currentSrc || e.src) || e.currentSrc || e.src);
        }""", box)
