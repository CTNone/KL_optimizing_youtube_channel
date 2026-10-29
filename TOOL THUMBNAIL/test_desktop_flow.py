import asyncio
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, AsyncMock
from PIL import Image
import desktop_flow


def controller(root):
    value = object.__new__(desktop_flow.DesktopFlow)
    value.profile = 'test-account'
    value.state = {'history': [], 'limits': {}}
    value.page = type('Page', (), {'url': 'https://flow.google.com/project/test'})()
    value.files = desktop_flow.file_module.Files()
    value.files.directory = root
    value.on_state = lambda state: None
    value.armed = None
    value.next_checkpoint = None
    value.busy = False
    value.opening = False
    value.external_browser = None
    value.playwright = None
    value.cancelled = False
    value.recovery_ids = set()
    return value


class DesktopTests(unittest.IsolatedAsyncioTestCase):
    async def test_unconfirmed_submission_never_downloads_or_resubmits(self):
        from playwright.async_api import async_playwright
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            engine = controller(root)
            engine.downloads = {}
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(channel='chrome', headless=True)
                engine.context = await browser.new_context(accept_downloads=True, viewport={'width':1200,'height':850})
                await engine.context.expose_binding('__studioBridge', engine.bridge)
                page = await engine.context.new_page()
                engine.watch_page(page)
                await page.goto((Path(__file__).parent / 'tests/desktop-flow-fixture.html').as_uri() + '?noSubmit=1')
                fixture_url = page.url
                with patch.object(desktop_flow, 'ROOT', root), patch.object(desktop_flow, 'is_flow', lambda url: url == fixture_url):
                    await asyncio.wait_for(engine.start('Not acknowledged', None, 'Nano Banana 2 Lite', 1, root), 30)
                self.assertEqual(await page.evaluate('window.sendCount'), 1)
                self.assertEqual(engine.state['history'][0]['status'], 'submission_uncertain')
                self.assertEqual(engine.state['history'][0]['attempts'][0]['files'], [])
                self.assertEqual(engine.downloads, {})
                await browser.close()

    async def test_attach_existing_chrome_and_disconnect_preserves_browser(self):
        from playwright.async_api import async_playwright
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            user_data = root / 'User Data'
            source = user_data / 'Default'
            source.mkdir(parents=True)
            (source / 'Preferences').write_text('{}')
            engine = controller(root)
            engine.context = None
            engine.downloads = {}
            async with async_playwright() as owner:
                context = await owner.chromium.launch_persistent_context(str(user_data), channel='chrome', headless=True, viewport={'width':1200,'height':850}, args=['--remote-debugging-port=0'])
                page = context.pages[0]
                await page.goto((Path(__file__).parent / 'tests/desktop-flow-fixture.html').as_uri())
                fixture_url = page.url
                with patch.object(desktop_flow, 'ROOT', root), patch.object(desktop_flow, 'is_flow', lambda url: url == fixture_url):
                    tabs = await engine.connect_existing(source)
                    self.assertEqual(len(tabs), 1)
                    self.assertEqual((await engine.flow_page()).url, fixture_url)
                    await asyncio.wait_for(engine.start('Existing-session prompt', None, 'Nano Banana 2 Lite', 1, root), 30)
                    self.assertEqual(engine.state['history'][0]['status'], 'done', str(engine.state['history']))
                    self.assertEqual(len(engine.state['history'][0]['attempts'][0]['files']), 2)
                    await engine.disconnect()
                    self.assertFalse(page.is_closed())
                    self.assertEqual(await page.evaluate('2+2'), 4)
                    await engine.connect_existing(source)
                    records = await engine.page.evaluate("__studioBridge({type:'readRecords'})")
                    self.assertIsInstance(records, dict)
                    await engine.disconnect()
                await context.close()

    async def test_missing_flow_opens_tool_window_without_submitting(self):
        engine = controller(Path(__file__).parent)
        page = type('Page', (), {})()
        page.goto = AsyncMock()
        page.bring_to_front = AsyncMock()
        engine.context = type('Context', (), {'pages': [], 'new_page': AsyncMock(return_value=page)})()
        with self.assertRaisesRegex(ValueError, 'Đã mở Flow'):
            await engine.flow_page()
        page.goto.assert_awaited_once_with('https://labs.google/fx/tools/flow', wait_until='domcontentloaded')
        page.bring_to_front.assert_awaited_once()

    async def test_complete_desktop_run_without_extension(self):
        from playwright.async_api import async_playwright
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            engine = controller(root)
            snapshots = []
            engine.on_state = lambda state: snapshots.append(copy.deepcopy(state))
            engine.downloads = {}
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(channel='chrome', headless=True)
                engine.context = await browser.new_context(accept_downloads=True, viewport={'width':1200,'height':850})
                await engine.context.expose_binding('__studioBridge', engine.bridge)
                page = await engine.context.new_page()
                engine.watch_page(page)
                await page.goto((Path(__file__).parent / 'tests/desktop-flow-fixture.html').as_uri() + '?replacePreview=1')
                fixture_url=page.url
                with patch.object(desktop_flow, 'ROOT', root), patch.object(desktop_flow, 'is_flow', lambda url: url == fixture_url):
                    await asyncio.wait_for(engine.start('One desktop prompt',None,'Nano Banana 2 Lite',1,root,{'aspectRatio':'16:9'}),30)
                self.assertEqual(await page.evaluate('window.sendCount'),1)
                self.assertEqual(await page.locator('#ratios [aria-checked=true]').inner_text(), '16:9')
                self.assertEqual(engine.state['history'][0]['status'],'done',str(snapshots))
                paths=engine.state['history'][0]['attempts'][0]['files']
                self.assertEqual(len(paths),2)
                with Image.open(paths[0]) as original:
                    self.assertEqual(original.size,(2048,1536))
                with Image.open(paths[1]) as cropped:
                    self.assertEqual(cropped.size,(2048,1152))
                await browser.close()

    async def test_reload_settle_single_recovery_and_cancel(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            engine = controller(root)
            engine.page.reload = AsyncMock()
            engine.flow_page = AsyncMock(return_value=engine.page)
            engine.inject = AsyncMock()
            dispatched = []
            async def request(page, message):
                if message['type'] == 'resumeRun':
                    cp = message['checkpoint']
                    dispatched.append(cp['nextAttempt'])
                    if cp['nextAttempt'] == 1:
                        engine.next_checkpoint = {**cp, 'nextAttempt': 2}
                    return {'ok': True}
                return {'running': False}
            engine.request = request
            with patch('desktop_flow.asyncio.sleep', new_callable=AsyncMock) as sleep:
                await engine.start('prompt', None, 'Nano Banana 2 Lite', 2, root)
                self.assertEqual(dispatched, [1, 2])
                self.assertEqual(engine.page.reload.await_count, 2)
                self.assertEqual(sleep.await_args_list[0].args, (2,))
                self.assertFalse(engine.busy)
            async def cancel_during_reload(**kwargs):
                engine.cancelled = True
            engine.page.reload = cancel_during_reload
            dispatched.clear()
            with patch('desktop_flow.asyncio.sleep', new_callable=AsyncMock):
                await engine.start('cancel', None, 'Nano Banana 2 Lite', 1, root)
            self.assertEqual(dispatched, [])
            self.assertFalse(engine.busy)

    async def test_quota_history_download_pair_and_retry(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            with patch.object(desktop_flow, 'ROOT', root):
                engine = controller(root)
                source = {'page': engine.page}
                for attempt in (1, 1, 2):
                    await engine.bridge(source, {'type': 'quotaHit', 'model': 'Lite', 'runId': 'run', 'attempt': attempt})
                self.assertEqual(engine.state['limits']['Lite']['count'], 2)
                self.assertFalse(engine.state['limits']['Lite']['disabled'])
                await engine.bridge(source, {'type': 'quotaHit', 'model': 'Lite', 'runId': 'run', 'attempt': 3})
                self.assertTrue(engine.state['limits']['Lite']['disabled'])
                image = root / 'source.jpg'
                Image.new('RGB', (2048, 1536), 'red').save(image)
                await engine.bridge(source, {'type': 'armFlowDownload'})
                token = engine.armed['token']
                engine.armed.update(state='complete', filename=str(image))
                request = {'type': 'readFlowDownload', 'token': token, 'path': 'run_123/0001_01.jpg'}
                first = await engine.bridge(source, request)
                self.assertTrue(first['ok'])
                self.assertEqual((await engine.bridge(source, request))['filename'], first['filename'])
                self.assertEqual(len(list((root / 'run_123').iterdir())), 2)
                with Image.open(first['croppedFilename']) as cropped:
                    self.assertEqual(cropped.size, (2048, 1152))
                row = {'id': 'one', 'prompt': 'test', 'status': 'done'}
                await engine.bridge(source, {'type': 'saveHistory', 'run': row})
                await engine.bridge(source, {'type': 'saveHistory', 'run': row})
                self.assertEqual(len(engine.state['history']), 1)
                await engine.reset_limits()
                self.assertEqual(engine.state['limits'], {})

    async def test_upload_real_browser_svg_plus_and_asset_confirmation(self):
        from playwright.async_api import async_playwright
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            image = root / 'market.jpg'
            Image.new('RGB', (640, 360), 'blue').save(image)
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(channel='chrome', headless=True)
                page = await browser.new_page(viewport={'width': 1200, 'height': 850})
                browser_errors=[]
                page.on('pageerror', lambda error: browser_errors.append(str(error)))
                await page.set_content('''<style>textarea{position:absolute;left:300px;top:650px;width:650px;height:50px}#plus{position:absolute;left:310px;top:710px}#preview{position:absolute;left:320px;top:580px;width:80px;height:50px;object-fit:cover;filter:brightness(.5)}</style>
                  <textarea></textarea><button id="plus" onclick="document.querySelector('#upload').hidden=false"><svg width="20" height="20"><path d="M10 0V20M0 10H20"/></svg></button>
                  <button id="upload" hidden onclick="const f=document.createElement('input');f.type='file';f.accept='image/*';f.onchange=()=>{document.body.setAttribute('aria-busy','true');window.uploadDone=false;setTimeout(()=>{window.uploadDone=true;document.body.removeAttribute('aria-busy')},1500);window.uploadName=f.files[0].name;const asset=document.createElement('img');asset.src=window.URL.createObjectURL(f.files[0]);asset.alt='Flow renamed this upload';asset.onclick=()=>window.selectedUpload=asset.src;asset.style.width='160px';asset.style.height='90px';document.body.append(asset);const add=document.createElement('button');add.innerText='Thêm vào câu lệnh';add.onclick=()=>{window.confirmedWhileUploading=!window.uploadDone;const img=document.createElement('img');img.id='preview';img.src=window.wrongReference || window.URL.createObjectURL(f.files[0]);document.body.append(img);add.remove();asset.remove()};document.body.append(add)};document.body.append(f);f.click()">Tải nội dung lên</button>''')
                engine = controller(root)
                try:
                    await asyncio.wait_for(engine.attach_reference(page, str(image)), 20)
                except Exception:
                    print('LOCAL FIXTURE:', await page.evaluate("({uploadName:window.uploadName,images:[...document.images].map(e=>({src:e.src,w:e.naturalWidth,rect:e.getBoundingClientRect().toJSON()})),buttons:[...document.querySelectorAll('button')].map(e=>e.innerText)})"))
                    print('PAGE ERRORS:',browser_errors)
                    raise
                self.assertEqual(await page.evaluate('window.uploadName'), 'market.jpg')
                self.assertFalse(await page.evaluate('window.confirmedWhileUploading'))
                self.assertTrue(await page.evaluate('!!window.selectedUpload'))
                self.assertEqual(await page.locator('#preview').count(), 1)
                self.assertEqual(await page.get_by_role('button', name='Thêm vào câu lệnh').count(), 0)
                # Current Flow can close the picker and attach on asset click.
                # The old controller then timed out waiting for the Add button.
                await page.locator('#preview').evaluate('(e)=>e.remove()')
                await page.locator('input[type=file]').evaluate_all('(items)=>items.forEach(e=>e.remove())')
                original_upload = await page.locator('#upload').get_attribute('onclick')
                await page.locator('#upload').evaluate(
                    '(e, code)=>e.setAttribute("onclick", code)',
                    original_upload.replace('asset.onclick=()=>window.selectedUpload=asset.src',
                        "asset.onclick=()=>{window.selectedUpload=asset.src;add.click()}"))
                await asyncio.wait_for(engine.attach_reference(page, str(image)), 20)
                self.assertEqual(await page.locator('#preview').count(), 1)
                self.assertEqual(await page.get_by_role('button', name='Thêm vào câu lệnh').count(), 0)
                await page.locator('#upload').evaluate('(e, code)=>e.setAttribute("onclick", code)', original_upload)
                # A picker adding the wrong old image must fail before sending.
                import base64, io
                wrong = io.BytesIO()
                Image.new('RGB', (640, 360), 'red').save(wrong, format='PNG')
                await page.evaluate('(src)=>window.wrongReference=src', 'data:image/png;base64,' + base64.b64encode(wrong.getvalue()).decode())
                await page.locator('input[type=file]').evaluate_all('(items)=>items.forEach(e=>e.remove())')
                with self.assertRaisesRegex(ValueError, 'không khớp'):
                    await asyncio.wait_for(engine.attach_reference(page, str(image)), 20)
                # The desktop runtime exposes the same content-script protocol
                # without an installed extension.
                engine.page = page
                messages = []
                async def bridge(source, message):
                    messages.append(message)
                    return {'ok': True}
                await page.expose_binding('__studioBridge', bridge)
                await page.evaluate((Path(__file__).parent / 'desktop-runtime.js').read_text())
                await page.evaluate("chrome.runtime.onMessage.addListener((m,s,reply)=>reply({id:s.id,type:m.type}));")
                result = await page.evaluate("__studioRequest({type:'status'})")
                self.assertEqual(result, {'id': 'desktop-studio', 'type': 'status'})
                await page.evaluate("chrome.runtime.sendMessage({type:'readRecords'})")
                self.assertEqual(messages[-1]['type'], 'readRecords')
                await browser.close()


if __name__ == '__main__':
    unittest.main()

