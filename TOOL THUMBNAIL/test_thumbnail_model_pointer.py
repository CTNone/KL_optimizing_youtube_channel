import unittest
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
HTML = '''<style>textarea{position:absolute;top:500px;left:250px;width:650px;height:50px}#summary{position:absolute;top:570px;left:700px}#settings{position:absolute;top:250px;left:700px}button{padding:12px}</style>
<textarea></textarea><button id="summary">Nano Banana Pro x1</button>
<div id="settings" hidden><button id="model" role="combobox">Nano Banana Pro</button><div id="options" role="menu" hidden></div></div>
<script>
window.model='Nano Banana Pro';window.opens=[];window.testClickSequence=0;
summary.addEventListener('pointerdown',()=>{opens.push('settings');setTimeout(()=>settings.hidden=false,80)});
document.querySelector('#model').addEventListener('pointerdown',()=>{opens.push('models');setTimeout(()=>options.hidden=false,80)});
for(const name of ['Nano Banana Pro','Nano Banana 2.1','Nano Banana 2 Lite']){const row=document.createElement('button');row.setAttribute('role','menuitem');row.textContent=name;row.onclick=()=>{window.model=name;summary.textContent=name+' x1';document.querySelector('#model').textContent=name;options.hidden=true};options.append(row)}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){settings.hidden=true;options.hidden=true}});
</script>'''


class ModelPointerTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_layers_require_pointer_events_and_verify_selected_model(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(channel='chrome', headless=True)
            page = await browser.new_page(viewport={'width':1200,'height':850})
            await page.set_content(HTML)
            await page.locator('#summary').evaluate('(e)=>e.click()')
            self.assertFalse(await page.locator('#settings').is_visible())
            self.assertEqual(await page.evaluate('window.opens'), [])
            await page.evaluate((ROOT / 'mode-review/thumbnail-models.js').read_text(encoding='utf-8'))
            await page.expose_binding('nativeModelClick', lambda source, token: source['page'].locator('[data-test-click="'+token+'"]').click(timeout=2000))
            await page.expose_binding('closeModels', lambda source: source['page'].keyboard.press('Escape'))
            # This callback follows content.js: model rows use DOM activation,
            # other controls use the Chrome mouse. No real prompt is submitted.
            script = '''async wanted => FlowModels.chooseBest({editor:()=>document.querySelector('textarea'),order:[wanted],blocked:{},check(){},sleep:ms=>new Promise(r=>setTimeout(r,ms)),dismiss:()=>closeModels(),click:async e=>{if(FlowModels.isOption(e)||FlowModels.isControl(e)){e.click();return}const token=String(++window.testClickSequence);e.setAttribute('data-test-click',token);await nativeModelClick(token)}})'''
            for wanted in ['Nano Banana 2 Lite','Nano Banana 2.1','Nano Banana Pro']:
                self.assertEqual(await page.evaluate(script, wanted), wanted)
                self.assertEqual(await page.evaluate('window.model'), wanted)
                self.assertFalse(await page.locator('#settings').is_visible())
            self.assertEqual(await page.evaluate('window.opens'), ['settings','models'] * 3)
            # Already selected means no unnecessary reopening or clicking.
            self.assertEqual(await page.evaluate(script, 'Nano Banana Pro'), 'Nano Banana Pro')
            self.assertEqual(await page.evaluate('window.opens.length'), 6)
            # Real integration leaves mode settings open. Its model button
            # may have no combobox role, and the composer remains visible.
            await page.evaluate('''()=>{
              settings.hidden=false;
              document.querySelector('#model').removeAttribute('role');
              const row=document.createElement('div');row.style.display='flex';
              for(const name of ['Hình ảnh','Video']){const b=document.createElement('button');b.textContent=name;row.append(b)}
              settings.prepend(row);
              const count=document.createElement('button');count.textContent='x1';settings.append(count);
              window.opens=[];
            }''')
            await page.evaluate((ROOT / 'mode-review/video_controls.js').read_text(encoding='utf-8'))
            self.assertEqual(await page.evaluate(script, 'Nano Banana 2 Lite'), 'Nano Banana 2 Lite')
            self.assertEqual(await page.evaluate('window.opens'), ['models'])
            await page.evaluate('''()=>{
              settings.hidden=false;
              const ratios=document.createElement('div');
              for(const name of ['16:9','4:3','1:1','3:4','9:16']){
                const b=document.createElement('button');b.textContent=name;b.setAttribute('aria-selected',String(name==='16:9'));
                b.addEventListener('pointerdown',()=>{for(const peer of ratios.children)peer.setAttribute('aria-selected',String(peer===b))});ratios.append(b);
              }
              settings.append(ratios);
            }''')
            self.assertEqual(await page.evaluate(script,'Nano Banana 2 Lite'),'Nano Banana 2 Lite')
            self.assertTrue(await page.locator('#settings').is_visible())
            await page.evaluate((ROOT.parent / 'TOOL Video Flow/thumbnail-settings.js').read_text(encoding='utf-8-sig'))
            ratio=await page.evaluate('''async ()=>FlowSettings.applyRatio({editor:()=>document.querySelector('textarea'),cfg:{aspectRatio:'4:3',count:'1'},check(){},sleep:ms=>new Promise(r=>setTimeout(r,ms)),click:async e=>{const token=String(++window.testClickSequence);e.setAttribute('data-test-click',token);await nativeModelClick(token)}})''')
            self.assertEqual(ratio,'4:3')
            self.assertEqual(await page.evaluate("()=>FlowSettings.apply({editor:()=>document.querySelector('textarea'),cfg:{count:'1'},check(){},sleep:async()=>{},click:async()=>{throw new Error('Count already correct')}})"),1)
            await page.set_content(HTML)
            await page.evaluate((ROOT / 'mode-review/thumbnail-models.js').read_text(encoding='utf-8'))
            await page.evaluate('''()=>{
              crypto.randomUUID=()=>String(++window.testClickSequence);
              for(const row of options.children){const handler=row.onclick;row.onclick=null;row.addEventListener('pointerdown',handler)}
            }''')
            # Actual Desktop selector uses locator.click for both triggers
            # and option rows that only respond to pointer events.
            from test_mode_switch import module
            controller=module.StudioFlow.__new__(module.StudioFlow)
            controller.cancelled=False
            controller.state={'limits':{}}
            controller.on_state=lambda state:None
            await controller.select_thumbnail_model(page,'Nano Banana 2 Lite')
            self.assertEqual(await page.evaluate('window.model'),'Nano Banana 2 Lite')
            await browser.close()


if __name__ == '__main__':
    unittest.main()
