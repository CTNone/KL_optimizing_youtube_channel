import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'TOOL Video Flow'))
spec = importlib.util.spec_from_file_location('review_video_flow', ROOT / 'video_flow.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

HTML = '''<style>body{min-height:850px}.sidebar{height:300px;width:160px}.menu{position:absolute;top:230px;left:380px;width:380px;background:#222;padding:12px}.row{display:flex;height:44px}.row button{flex:1;background:#333;color:white}.row button[aria-selected=true]{background:white;color:black}textarea{position:absolute;top:550px;left:240px;width:700px;height:50px}#summary{position:absolute;top:620px;left:800px}</style>
<div class="sidebar"><button>Hình ảnh</button><button>Video</button></div>
<textarea></textarea><button id="summary" onclick="document.querySelector('#settings').hidden=!document.querySelector('#settings').hidden">Video · 720p · 8 giây x1</button>
<div id="settings" class="menu"></div>
<script>
window.mode='video';window.kind='Khung hình';window.ratio='16:9';window.clicks=0;
function row(labels, selected, action){const wrap=document.createElement('div');wrap.className='row';for(const name of labels){const button=document.createElement('button');button.textContent=name;button.setAttribute('aria-selected',String(name===selected));button.onclick=()=>{action(name);setTimeout(render,20)};wrap.append(button)}return wrap;}
function render(){const root=document.querySelector('#settings');root.replaceChildren();root.append(row(['Hình ảnh','Video'],mode==='image'?'Hình ảnh':'Video',name=>{window.mode=name==='Video'?'video':'image';window.clicks++}));if(mode==='video')root.append(row(['Khung hình','Thành phần'],kind,name=>window.kind=name));root.append(row(['16:9','9:16'],ratio,name=>window.ratio=name));for(const text of [mode==='video'?'Veo 3.1 - Lite':'Nano Banana 2 Lite','x1']){const button=document.createElement('button');button.textContent=text;root.append(button)}
}render();
</script>'''


class ModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_video_model_appears_late_and_selection_closes_settings(self):
        from playwright.async_api import async_playwright
        controller=module.StudioFlow.__new__(module.StudioFlow)
        controller.cancelled=False
        controller.on_state=lambda state:None
        async with async_playwright() as playwright:
            browser=await playwright.chromium.launch(channel='chrome',headless=True)
            page=await browser.new_page(viewport={'width':1200,'height':850})
            await page.set_content(HTML)
            await page.evaluate((ROOT/'video_controls.js').read_text(encoding='utf-8'))
            await page.evaluate('''()=>{
              window.kind='Thành phần';render();
              const root=document.querySelector('#settings');root.hidden=false;
              const model=[...root.querySelectorAll('button')].find(e=>/Veo/.test(e.textContent));
              model.textContent='Đang tải mô hình';
              [...root.querySelectorAll('button')].find(e=>e.textContent==='x1').remove();
              const counts=document.createElement('div');counts.className='row';
              for(const name of ['x1','x2','x3','x4']){
                const b=document.createElement('button');b.textContent=name;b.setAttribute('aria-selected',String(name==='x2'));
                b.onclick=()=>{for(const peer of counts.children)peer.setAttribute('aria-selected',String(peer===b))};counts.append(b);
              }root.append(counts);
              setTimeout(()=>model.textContent='Omni 1.1 Flash',2500);
              model.onclick=()=>{
                const menu=document.createElement('div');menu.setAttribute('role','menu');
                const row=document.createElement('button');row.setAttribute('role','menuitem');row.textContent='Veo 3.1 - Lite';
                row.onclick=()=>{model.textContent=row.textContent;menu.remove();root.hidden=true};menu.append(row);root.append(menu);
              };
            }''')
            await controller.configure_video(page,'Veo 3.1 - Lite','Thành phần','16:9',1)
            await controller.open_video_settings(page)
            self.assertEqual((await page.evaluate("()=>VideoControls.models('Veo 3.1 - Lite','selected','check')"))['count'],1)
            self.assertTrue((await page.evaluate("()=>VideoControls.find('^x1$','count-check')"))['selected'])
            await browser.close()

    async def test_repeated_switch_with_duplicate_sidebar_and_remounted_menu(self):
        from playwright.async_api import async_playwright
        controller = module.StudioFlow.__new__(module.StudioFlow)
        controller.cancelled = False
        controller.on_state = lambda state: None
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel='chrome', headless=True)
            page = await browser.new_page(viewport={'width':1200,'height':850})
            await page.set_content(HTML)
            await page.evaluate((ROOT / 'video_controls.js').read_text(encoding='utf-8'))
            await page.locator('#settings').evaluate('(e)=>e.hidden=true')
            for _ in range(2):
                await controller.select_generation_mode(page, 'image')
                self.assertEqual(await page.evaluate('window.mode'), 'image')
                await controller.select_generation_mode(page, 'video')
                self.assertEqual(await page.evaluate('window.mode'), 'video')
                await controller.choose(page, r'^Thành phần$')
                self.assertEqual(await page.evaluate('window.kind'), 'Thành phần')
                await controller.choose(page, r'^9:16$')
                self.assertEqual(await page.evaluate('window.ratio'), '9:16')
            clicks = await page.evaluate('window.clicks')
            await controller.select_generation_mode(page, 'video')
            self.assertEqual(await page.evaluate('window.clicks'), clicks)
            await page.evaluate("document.querySelectorAll('#settings .row:first-child button').forEach(e=>{e.style.backgroundColor=getComputedStyle(e).backgroundColor;e.removeAttribute('aria-selected')})")
            self.assertTrue(await page.evaluate("VideoControls.mode('video','css-video').selected"))
            self.assertFalse(await page.evaluate("VideoControls.mode('image','css-image').selected"))
            await controller.select_generation_mode(page, 'image')
            self.assertEqual(await page.evaluate('window.mode'), 'image')
            await page.evaluate("document.querySelectorAll('#settings .row:first-child button').forEach(e=>{const click=e.onclick;e.onclick=()=>{click();document.querySelector('#settings').hidden=true}})")
            await controller.select_generation_mode(page, 'video')
            self.assertEqual(await page.evaluate('window.mode'), 'video')
            self.assertTrue(await page.locator('#settings').is_visible())
            await browser.close()


if __name__ == '__main__':
    unittest.main()
