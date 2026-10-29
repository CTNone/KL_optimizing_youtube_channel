"""Video automation sharing Chrome connection and reference upload with Thumbnail."""
import asyncio
import json
import re
import time
import traceback
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from desktop_flow import DesktopFlow
from video_storage import atomic_json, validate_video, record_download

ROOT = Path(__file__).resolve().parent

class StudioFlow(DesktopFlow):
    def report(self, message, running=True):
        self.on_state({'running': running, 'logs': [message], 'items': []})

    def check_video(self):
        if self.cancelled:
            raise asyncio.CancelledError()

    async def pause(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check_video()
            await asyncio.sleep(min(.25, max(0, end-time.monotonic())))

    async def unique(self, page, pattern):
        await page.evaluate((ROOT / 'video_controls.js').read_text(encoding='utf-8-sig'))
        token = uuid.uuid4().hex
        result = await page.evaluate('({pattern,token})=>VideoControls.find(pattern,token)', {'pattern':pattern,'token':token})
        if result['count'] != 1:
            raise ValueError(f"Không xác định duy nhất lựa chọn Flow: {pattern} ({result['count']} ứng viên: {result.get('labels', [])}). Chưa gửi prompt.")
        return page.locator(f'[data-video-control="{token}"]')

    async def open_video_settings(self, page):
        await page.evaluate((ROOT / 'video_controls.js').read_text(encoding='utf-8-sig'))
        for _ in range(60):
            self.check_video()
            # The settings portal may already be open. Never toggle it closed.
            opened = await page.evaluate("()=>VideoControls.find('^(?:Video)$','mode-video-visible').count===1 && VideoControls.find('^(?:Hình ảnh|Images?)$','mode-image-visible').count===1")
            if opened:
                return
            token=uuid.uuid4().hex
            result=await page.evaluate('(token)=>VideoControls.trigger(token)', token)
            if result['count']==1:
                await self.pause(1.2)
                await page.locator(f'[data-video-control="{token}"]').click()
                for _ in range(40):
                    self.check_video()
                    if await page.evaluate("()=>VideoControls.find('^(?:Video|Hình ảnh)$','video-settings-ready').count"):
                        return
                    await self.pause(.25)
                raise ValueError('Đã bấm mở cài đặt nhưng Flow chưa hiển thị bảng lựa chọn. Chưa gửi prompt.')
            await self.pause(.25)
        raise ValueError(f"Không tìm được duy nhất nút cài đặt cạnh ô prompt: {result}. Chưa gửi prompt.")

    async def video_send_button(self, page):
        await page.evaluate((ROOT / 'video_controls.js').read_text(encoding='utf-8-sig'))
        for _ in range(60):
            self.check_video()
            token=uuid.uuid4().hex
            result=await page.evaluate('(token)=>VideoControls.send(token)',token)
            if result['count']==1:
                return page.locator(f'[data-video-control="{token}"]')
            await self.pause(.25)
        raise ValueError(f"Chưa xác định duy nhất nút gửi video cạnh ô prompt: {result}. Chưa gửi prompt.")

    async def choose(self, page, pattern):
        self.check_video()
        loc = await self.unique(page, pattern)
        await self.pause(1.2)
        await loc.click()
        await self.pause(.6)
        # Match Thumbnail: verify semantic selected state, otherwise unique active background among peers.
        if not await loc.evaluate('''e => {
            if(e.getAttribute('aria-selected')==='true'||e.getAttribute('aria-checked')==='true'||e.getAttribute('aria-pressed')==='true'||['on','active','checked'].includes(e.getAttribute('data-state')))return true;
            const peers=[...e.parentElement.children].filter(x=>x.getClientRects().length && x.matches('button,[role=radio],[role=option]'));
            const color=getComputedStyle(e).backgroundColor;
            return peers.length>1 && !['transparent','rgba(0, 0, 0, 0)'].includes(color) && peers.filter(x=>getComputedStyle(x).backgroundColor===color).length===1;
        }'''):
            raise ValueError('Flow chưa xác nhận lựa chọn: ' + pattern + '. Chưa gửi prompt.')

    async def select_generation_mode(self, page, mode):
        await self.open_video_settings(page)
        pattern=r'^(?:Hình ảnh|Images?)$' if mode=='image' else r'^Video$'
        await self.choose(page,pattern)
        self.report('Đã xác nhận chế độ '+('Hình ảnh cho Thumbnail.' if mode=='image' else 'Video.'))

    async def inject(self, page):
        await super().inject(page)
        for filename in ('video_controls.js','thumbnail-models.js','thumbnail-settings.js'):
            await page.evaluate((ROOT/filename).read_text(encoding='utf-8-sig'))

    async def request(self, page, message):
        # Thumbnail reloads for every attempt. Switch mode before its model/ratio/count logic.
        if message.get('type')=='resumeRun':
            await self.select_generation_mode(page,'image')
            await page.keyboard.press('Escape')
        return await super().request(page,message)

    async def configure_video(self, page, model, mode, ratio, count):
        await self.select_generation_mode(page,'video')
        await self.choose(page, r'^(?:' + ('Thành phần|Ingredients' if mode == 'Thành phần' else 'Khung hình|Frames') + r')$')
        await self.choose(page, '^' + re.escape(ratio) + '$')
        token=uuid.uuid4().hex
        options=await page.evaluate('({model,token})=>VideoControls.models(model,"options",token)', {'model':model,'token':token})
        if not options['count']:
            dropdown = await self.unique(page, r'Veo\s*\d')
            await dropdown.click()
        for _ in range(40):
            self.check_video()
            options=await page.evaluate('({model,token})=>VideoControls.models(model,"options",token)', {'model':model,'token':token})
            if options['count']==1:
                break
            await self.pause(.25)
        else:
            raise ValueError(f"Chưa tìm được mô hình {model} trong menu Flow: {options}. Chưa gửi prompt.")
        await page.locator(f'[data-video-control="{token}"]').click()
        for _ in range(40):
            selected=await page.evaluate('({model,token})=>VideoControls.models(model,"selected",token)', {'model':model,'token':token})
            if selected['count']==1:
                break
            await self.pause(.25)
        else:
            raise ValueError(f'Flow chưa xác nhận mô hình {model} sau khi chọn. Chưa gửi prompt.')
        await self.choose(page, r'^x' + str(count) + '$')
        await page.keyboard.press('Escape')
        self.report(f'Đã xác nhận Video · {mode} · {ratio} · {model} · x{count}')

    async def start_error_monitor(self, page, prompt):
        await page.evaluate("""prompt => {
            if(typeof globalThis.FlowErrors?.watch !== 'function')
                throw new Error('Bộ theo dõi lỗi Flow chưa được nạp. Chưa gửi prompt.');
            globalThis.__videoErrors?.disconnect();
            globalThis.__videoErrors=FlowErrors.watch({
                prompt,
                ignoreExisting:true,
                visible:e=>!!e?.getClientRects().length && getComputedStyle(e).visibility!=='hidden'
            });
            globalThis.__videoErrors.check();
        }""", prompt)

    async def check_flow_error(self, page):
        await page.evaluate('()=>globalThis.__videoErrors?.check()')

    async def videos(self, page, include_hidden=False):
        await page.evaluate((ROOT / 'video_controls.js').read_text(encoding='utf-8-sig'))
        return await page.evaluate('(hidden)=>VideoControls.results(hidden)', include_hidden)

    async def wait_for_videos(self, page, before, count, timeout=1200, prompt=None):
        deadline=time.monotonic()+timeout
        stable=[];last_log=0
        while time.monotonic()<deadline:
            self.check_video()
            await self.check_flow_error(page)
            rows=[v for v in await self.videos(page) if v.get('key',v['src']) not in before and v.get('posterKey') not in before]
            # Flow's virtual grid can mount an old completed card after submission.
            # Exact prompt labels disambiguate those cards; never count them as new outputs.
            if prompt and any(v.get('prompts') for v in rows):
                normalized=' '.join(prompt.split())
                rows=[v for v in rows if normalized in v.get('prompts',[])]
            current=sorted({v['src'] for v in rows})
            stable=current
            if len(stable)==count:
                self.report(f'Video đã hoàn tất: {count}/{count}. Mở clip và tải ngay…')
                break
            if time.monotonic()-last_log>=15:
                self.report(f'Đang chờ video hoàn tất: {len(stable)}/{count}');last_log=time.monotonic()
            await self.pause(.25)
        else:raise ValueError('Hết thời gian chờ video; không tạo lại. Kiểm tra kết quả trên Flow.')
        return stable


    async def return_to_composer(self, page, original_url=None):
        if original_url and '/edit/' in page.url:
            await page.goto(original_url,wait_until='domcontentloaded')
        for _ in range(20):
            await page.keyboard.press('Escape')
            await asyncio.sleep(.2)
            dialogs=page.locator('[role=dialog],[data-state=open],.cdk-overlay-pane').filter(visible=True)
            for i in range(await dialogs.count()):
                dialog=dialogs.nth(i)
                if await dialog.locator('video').count():
                    closes=dialog.get_by_role('button',name=re.compile(r'^(close|đóng|close_small|×|✕)$',re.I)).filter(visible=True)
                    if await closes.count()==1:await closes.click()
            editor=page.locator('textarea,[contenteditable=true]').filter(visible=True)
            if await editor.count()==1 and not await page.locator('[role=dialog] video,[data-state=open] video,.cdk-overlay-pane video').filter(visible=True).count():
                await editor.focus()
                return True
        if original_url and page.url!=original_url:
            from desktop_flow import is_flow
            if is_flow(original_url) and is_flow(page.url):
                await page.goto(original_url,wait_until='domcontentloaded')
                editor=page.locator('textarea,[contenteditable=true]').filter(visible=True)
                if await editor.count()==1:
                    await editor.focus()
                    return True
        self.report('Chưa xác nhận trở về giao diện tạo trên Flow.',False)
        return False

    async def download_video(self, page, source, folder, index):
        if '/edit/' in page.url:
            await page.goto(page.url.split('/edit/')[0],wait_until='domcontentloaded')
            await self.pause(1)
        original_url=page.url
        self.last_download_warning=None
        # Mirror Thumbnail: each asset starts and ends outside its preview.
        await page.keyboard.press('Escape')
        await page.keyboard.press('Escape')
        await self.pause(.3)
        try:
            return await self._download_video(page,source,folder,index)
        finally:
            try:
                if not await self.return_to_composer(page,original_url):
                    self.last_download_warning='File đã lưu; chưa xác nhận trở về giao diện tạo.'
            except Exception as error:
                self.last_download_warning='File đã lưu; lỗi đóng bản xem: '+str(error)

    async def _download_video(self, page, source, folder, index):
        await page.evaluate((ROOT / 'video_controls.js').read_text(encoding='utf-8-sig'))
        import hashlib
        identity=await page.evaluate('(source)=>VideoControls.videoIdentity(source)',source)
        stem=f'{index:02d}_{hashlib.sha256(identity.encode()).hexdigest()[:12]}'
        intent_path=folder/f'download-intent-{index:02d}.json'
        for existing in folder.glob(stem+'.*'):
            if existing.suffix.lower() not in ('.mp4','.webm','.mov','.mkv'):continue
            try:
                metadata=json.loads(existing.with_suffix(existing.suffix+'.json').read_text(encoding='utf-8'))
                if metadata['source']==identity:
                    verified=validate_video(existing)
                    if metadata.get('sha256') and metadata['sha256']!=verified['sha256']:
                        raise ValueError('File đã lưu bị thay đổi; không sử dụng cache.')
                    self.report(f'Video {index} đã được lưu; phục hồi lịch sử trên file có sẵn.')
                    return str(existing),metadata['resolution']
            except (OSError,ValueError,KeyError):pass
        token=uuid.uuid4().hex
        preview_path=folder/f'preview-{index:02d}.json'
        known_preview=None
        if preview_path.exists():
            saved=json.loads(preview_path.read_text(encoding='utf-8'))
            if saved.get('source')==identity and saved.get('url','').startswith(page.url.split('/edit/')[0]+'/edit/'):
                known_preview=saved['url']
        widths=[0]
        if known_preview:
            self.report(f'Mở lại đúng bản xem đã xác nhận của video {index}…')
            await page.goto(known_preview,wait_until='domcontentloaded')
        else:
            for _ in range(40):
                self.check_video()
                target=await page.evaluate('({source,token})=>VideoControls.openClip(source,token)',{'source':source,'token':token})
                if target['count']==1:break
                await self.pause(.25)
            if target['count']!=1:
                diagnostic=await page.evaluate("()=>({url:location.href,tiles:[...document.querySelectorAll('flow-video-tile')].map(e=>e.outerHTML)})")
                atomic_json(ROOT/'live-card-diagnostic.json',diagnostic)
                raise ValueError('Không thấy duy nhất card/thumbnail của clip cần tải. Không tạo lại video.')
            widths=[target['width']]
            self.report(f'Mở lần lượt video {index} để tải…')
            card_url=page.url
            await page.locator(f'[data-video-control="{token}"]').click()
            for _ in range(40):
                self.check_video()
                preview=await page.evaluate('({source,width,height})=>VideoControls.preview(source,width,height)', {'source':source,'width':target['width'],'height':target['height']})
                if preview['verified'] or page.url!=card_url and '/edit/' in page.url:break
                await self.pause(.25)
            else:
                raise ValueError('Bản xem chưa khớp video cần tải. Dừng để tránh tải nhầm; không tạo lại video.')
            if '/edit/' in page.url:
                atomic_json(preview_path,{'source':identity,'url':page.url})
        # Separate tokens keep the thumbnail and download button unambiguous in overlays.
        token=uuid.uuid4().hex
        # Navigation creates a new document: reinstall local controls.
        await page.evaluate((ROOT / 'video_controls.js').read_text(encoding='utf-8-sig'))
        for _ in range(40):
            self.check_video()
            result=await page.evaluate('({source,token,width})=>VideoControls.downloadControl(source,token,true,width)', {'source':source,'token':token,'width':max(widths)})
            if result['count']==1:break
            await self.pause(.25)
        if result['count']!=1:
            raise ValueError(f"Chưa thấy duy nhất nút tải trong card/bản xem của đúng video: {result}. Video đã tạo; dùng Tải lại kết quả, không tạo lại.")
        await page.locator(f'[data-video-control="{token}"]').click()
        resolution_token=uuid.uuid4().hex
        for _ in range(40):
            self.check_video()
            resolution=await page.evaluate('(token)=>VideoControls.resolutions(token)',resolution_token)
            if resolution['count']==1:break
            await self.pause(.25)
        else:
            diagnostic=await page.evaluate("()=>({url:location.href,menus:[...document.querySelectorAll('[role=menu],.cdk-overlay-pane')].filter(e=>e.getClientRects().length).map(e=>e.outerHTML),body:document.body.innerText.slice(-8000)})")
            atomic_json(ROOT/'live-resolution-diagnostic.json',diagnostic)
            raise ValueError(f"Chưa xác định duy nhất mức tải cao nhất trong menu Flow: {resolution}. Video đã tạo, không tạo lại.")
        label=resolution['label']
        choice=page.locator(f'[data-video-control="{resolution_token}"]')
        self.report('Tải video ở mức cao nhất khả dụng: '+label)
        atomic_json(intent_path,{'source':identity,'resolution':label,'requestedAt':datetime.now(timezone(timedelta(hours=7))).isoformat()})
        # One request only; report progress while Flow prepares an upscale/download.
        async def request_download():
            async with page.expect_download(timeout=900000) as pending:
                await choice.click()
            return await pending.value
        pending_task=asyncio.create_task(request_download())
        started=time.monotonic()
        try:
            while not pending_task.done():
                self.check_video()
                await asyncio.wait({pending_task},timeout=5)
                if not pending_task.done():
                    self.report(f'Flow đang chuẩn bị file {label} · {int(time.monotonic()-started)} giây. Không gửi/tải lại.')
            download=await pending_task
        finally:
            if not pending_task.done():
                pending_task.cancel()
                await asyncio.gather(pending_task,return_exceptions=True)
        suffix=Path(download.suggested_filename).suffix.lower()
        if suffix not in ('.mp4','.webm','.mov','.mkv'):
            raise ValueError('Flow trả về file không phải video: '+download.suggested_filename)
        target=folder / (stem+suffix)
        temporary=target.with_suffix(target.suffix+'.part')
        for attempt in range(3):
            try:
                await download.save_as(temporary)
                metadata=validate_video(temporary)
                temporary.replace(target)
                break
            except Exception as error:
                if attempt==2:raise
                self.report(f'File đã tải từ Flow; thử lưu lại dữ liệu cũ ({attempt+2}/3), không tải/generate lại.')
                await self.pause(.5)
        atomic_json(target.with_suffix(target.suffix+'.json'), {'source':identity,'resolution':label,**metadata})
        intent_path.unlink(missing_ok=True)
        await page.keyboard.press('Escape')
        return str(target),label

    async def start_video(self, prompt, reference, model, mode, ratio, count, folder):
        if self.busy or self.opening:
            raise ValueError('Chờ lượt hiện tại hoặc kết nối Chrome hoàn tất.')
        if not prompt.strip() or not reference:
            raise ValueError('Video cần đúng một ảnh và prompt.')
        page=await self.flow_page()
        self.busy=True;self.cancelled=False;self.page=page
        self.session_task=asyncio.current_task()
        folder=Path(folder)
        record={'id':uuid.uuid4().hex,'time':datetime.now(timezone(timedelta(hours=7))).isoformat(),'prompt':prompt,'image':str(reference),'model':model,'mode':mode,'ratio':ratio,'count':count,'status':'Đang chuẩn bị','stage':'prepare','submitted':False,'submitAttempted':False,'files':[],'resolutions':[]}
        path=folder/'video.json'
        def save():
            record['updatedAt']=datetime.now(timezone(timedelta(hours=7))).isoformat()
            atomic_json(path,record)
        submitted=False
        try:
            save()
            self.report('F5 Flow; chờ tải xong và thêm 2 giây…')
            await page.reload(wait_until='domcontentloaded')
            await self.pause(2)
            await self.inject(page)
            record['stage']='settings';save()
            await self.configure_video(page,model,mode,ratio,count)
            record['stage']='upload';save()
            await self.attach_reference(page,str(reference))
            editor=page.locator('textarea,[contenteditable=true]').filter(visible=True)
            if await editor.count()!=1:raise ValueError('Không xác định duy nhất ô prompt video.')
            await editor.fill(prompt)
            baseline=await self.videos(page,include_hidden=True)
            before={v.get('key',v['src']) for v in baseline}
            snapshot=await page.evaluate('()=>VideoControls.snapshot()')
            if isinstance(snapshot,list):before.update(snapshot)
            record['baselineKeys']=sorted(before);save()
            send=await self.video_send_button(page)
            record['stage']='preflight';save()
            await self.start_error_monitor(page,prompt)
            await self.pause(1.2)
            await self.check_flow_error(page)
            record['stage']='submit';record['submitAttempted']=True;save()
            # From this point onward a failed click can have reached Flow.
            submitted=True
            await send.click()
            record['submitted']=True;save()
            # Never retry a submission whose outcome is uncertain.
            acknowledged=False
            for _ in range(40):
                self.check_video()
                await self.check_flow_error(page)
                text=await editor.input_value() if await editor.evaluate('(e)=>e.tagName')=='TEXTAREA' else await editor.inner_text()
                if not text.strip() or await send.is_disabled():acknowledged=True;break
                await self.pause(.5)
            if not acknowledged:raise ValueError('Chưa xác nhận Flow nhận lệnh; không tự gửi lại.')
            record['status']='Đang tạo';record['stage']='wait';save()
            self.report('Flow đã nhận lệnh. Chờ video mới hoàn tất, không gửi lại…')
            stable=await self.wait_for_videos(page,before,count,prompt=prompt)
            record['resultSources']=stable
            record['stage']='download';save()
            for index,source in enumerate(stable,1):
                self.check_video()
                filename,resolution=await self.download_video(page,source,folder,index)
                record_download(record,index,source,filename,resolution)
                if getattr(self,'last_download_warning',None):record.setdefault('warnings',[]).append(self.last_download_warning)
                save()
            record['status']='Hoàn tất';record['stage']='complete';save()
            self.report('Đã tải đủ video ở độ phân giải cao nhất khả dụng.',False)
        except asyncio.CancelledError:
            record['status']='Đã dừng · kiểm tra Flow' if submitted else 'Đã dừng';save()
            self.report(record['status'],False)
        except Exception as error:
            record['status']='Một phần' if record['files'] else 'Lỗi'
            record['error']=str(error)
            record['errorType']=type(error).__name__
            record['traceback']=traceback.format_exc()
            record['submissionUncertain']=submitted and not record['submitted'];save()
            self.report(str(error),False)
            raise
        finally:
            try:
                await page.evaluate('()=>globalThis.__videoErrors?.disconnect()')
            except Exception:
                pass
            self.busy=False;self.session_task=None
            self.on_state({'running':False,'logs':[record.get('error') or record['status']],'finished':True})

    async def available_video_results(self):
        page=await self.flow_page()
        rows=await self.videos(page)
        return list({row['src']:row for row in rows}.values())

    async def download_existing_record(self, record_path):
        if self.busy:
            task=self.session_task
            if not task or task.get_coro().__name__!='start_video':
                raise ValueError('Đang tải hoặc tạo ảnh. Chờ lượt hiện tại hoàn tất.')
            await self.stop()
        await self.retry_video_download(record_path)

    async def retry_video_download(self, record_path, sources=None):
        if self.busy or self.opening:
            raise ValueError('Chờ lượt hiện tại hoàn tất trước khi tải lại.')
        path=Path(record_path).resolve(strict=True)
        record=json.loads(path.read_text(encoding='utf-8'))
        sources=sources or record.get('resultSources', [])
        page=await self.flow_page()
        pinned_previews=False
        if sources:
            await page.evaluate((ROOT / 'video_controls.js').read_text(encoding='utf-8-sig'))
            identities=await page.evaluate('(sources)=>sources.map(VideoControls.videoIdentity)',sources)
            pinned_previews=True
            for index,identity in enumerate(identities,1):
                try:
                    preview=json.loads((path.parent/f'preview-{index:02d}.json').read_text(encoding='utf-8'))
                    if preview.get('source')!=identity or not preview.get('url','').startswith(page.url.split('/edit/')[0]+'/edit/'):
                        pinned_previews=False;break
                except (OSError,ValueError):
                    pinned_previews=False;break
        if sources and not pinned_previews:
            rows=await self.videos(page)
            if rows:
                identities=await page.evaluate('(sources)=>sources.map(VideoControls.videoIdentity)',sources)
                by_key={row.get('key',row['src']):row['src'] for row in rows}
                if all(key in by_key for key in identities):
                    sources=[by_key[key] for key in identities]
                else:
                    # Signed URLs or preview variants may expire/change after restarting.
                    prompt=' '.join(record['prompt'].split())
                    matched=[row for row in rows if prompt in row.get('prompts',[]) and row.get('key',row['src']) not in record.get('baselineKeys',[]) and row.get('posterKey') not in record.get('baselineKeys',[])]
                    if len(matched)==int(record['count']):sources=[row['src'] for row in matched]
        if not sources:
            rows=await self.videos(page)
            prompt=' '.join(record['prompt'].split())
            matched=[row for row in rows if prompt in row.get('prompts',[]) and row.get('key',row['src']) not in record.get('baselineKeys',[]) and row.get('posterKey') not in record.get('baselineKeys',[])]
            if len(matched)!=int(record['count']):
                raise ValueError(f"Chưa thấy đúng {record['count']} clip có prompt của lượt này trên Flow. Mở đúng dự án/clip rồi bấm Tải lại. Không tạo mới.")
            sources=[row['src'] for row in matched]
        if len(sources)!=int(record['count']):
            raise ValueError('Số clip của lượt đã tạo không khớp lịch sử. Không gửi prompt mới.')
        self.busy=True;self.cancelled=False;self.page=page
        self.session_task=asyncio.current_task()
        def save():
            record['updatedAt']=datetime.now(timezone(timedelta(hours=7))).isoformat()
            atomic_json(path,record)
        try:
            await self.inject(page)
            record['resultSources']=sources
            record['status']='Đang tải lại';save()
            self.report('Đang tải lại video đã tạo; không gửi prompt mới…')
            files=record.setdefault('files',[])
            for index,source in enumerate(sources,1):
                self.check_video()
                if index<=len(files) and files[index-1] and Path(files[index-1]).is_file():
                    try:
                        validate_video(files[index-1])
                        continue
                    except (OSError,ValueError):
                        pass
                filename,resolution=await self.download_video(page,source,path.parent,index)
                record_download(record,index,source,filename,resolution)
                if getattr(self,'last_download_warning',None):record.setdefault('warnings',[]).append(self.last_download_warning)
                save()
            record['status']='Hoàn tất';record['stage']='complete'
            record.pop('error',None);record.pop('traceback',None);save()
            self.report('Đã tải kết quả có sẵn. Không gửi lại prompt.',False)
        except asyncio.CancelledError:
            record['status']='Đã dừng tải';save()
        except Exception as error:
            record['status']='Một phần' if record.get('files') else 'Lỗi tải'
            record['error']=str(error);save()
            raise
        finally:
            self.busy=False;self.session_task=None
            self.on_state({'running':False,'logs':[record.get('error') or record['status']],'finished':True})

    async def stop(self):
        if self.session_task and self.session_task.get_coro().__name__ in ('start_video','retry_video_download'):
            self.cancelled=True
            task=self.session_task
            task.cancel()
            if task is not asyncio.current_task():
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            return
        await super().stop()

def resolution_rank(label):
    if not re.search(r'\b(?:\d{3,4}\s*p|[248]\s*k)\b', label,re.I):return 0
    values=[int(v) for v in re.findall(r'(\d{3,4})\s*p\b',label,re.I)]
    values += [int(v)*540 for v in re.findall(r'\b([248])\s*k\b',label,re.I)]
    return max(values,default=0)
