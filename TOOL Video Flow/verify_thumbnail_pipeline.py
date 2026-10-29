import asyncio,sys
from pathlib import Path
from playwright.async_api import async_playwright
HTML='''<style>textarea{position:absolute;top:400px;left:40px;width:650px;height:80px}#trigger{position:absolute;top:490px;left:400px}#panel{position:absolute;top:20px;left:400px}#send{position:absolute;top:490px;left:710px}</style><textarea onclick="panel.hidden=true"></textarea><button id="trigger" onclick="panel.hidden=!panel.hidden">Hình ảnh x1</button><button id="send" aria-label="Generate" onclick="window.sent=(window.sent||0)+1">→</button><div id="panel" hidden><button role="combobox">Nano Banana 2 Lite</button><div id="ratios"><button onclick="pick(this)">16:9</button><button onclick="pick(this)">4:3</button><button aria-pressed="true" onclick="pick(this)">1:1</button><button onclick="pick(this)">3:4</button><button onclick="pick(this)">9:16</button></div><div id="counts"><button aria-pressed="true" onclick="pick(this);summary(this)">x1</button><button onclick="pick(this);summary(this)">x2</button><button onclick="pick(this);summary(this)">x3</button><button onclick="pick(this);summary(this)">x4</button></div></div><script>function pick(e){for(const s of e.parentElement.children)s.setAttribute('aria-pressed','false');e.setAttribute('aria-pressed','true')}function summary(e){trigger.textContent='Hình ảnh '+e.textContent}</script>'''
async def main():
 async with async_playwright() as pw:
  b=await pw.chromium.launch(channel='chrome',headless=True);p=await b.new_page();await p.set_content(HTML)
  for f in ['video_controls.js','thumbnail-models.js','thumbnail-settings.js']:await p.evaluate(Path(f).read_text(encoding='utf-8'))
  result=await p.evaluate('''async()=>{
   const editor=()=>document.querySelector('textarea');
   const settings={editor,order:['Nano Banana 2 Lite'],click:async e=>e.click(),sleep:ms=>new Promise(r=>setTimeout(r,ms)),check:()=>{},dismiss:async()=>editor().click()};
   const model=await FlowModels.chooseBest({...settings,blocked:{}});
   const cfg={count:'2',aspectRatio:'3:4'};
   await FlowModels.prepare(settings);
   const ratio=await FlowSettings.applyRatio({...settings,cfg});
   const count=await FlowSettings.apply({...settings,cfg});
   const actual=await FlowModels.prepare(settings);
   editor().click();return {model,ratio,count,actual:actual.name};
  }''')
  assert result=={'model':'Nano Banana 2 Lite','ratio':'3:4','count':2,'actual':'Nano Banana 2 Lite'},result
  await p.locator('textarea').fill('test thumbnail prompt')
  send=await p.evaluate("()=>VideoControls.send('thumbnail-send')");assert send['count']==1,send
  await p.locator('[data-video-control="thumbnail-send"]').click();assert await p.evaluate('window.sent')==1
  print('PASS: image composer opens settings without settings label, portal model, ratio 3:4, x2, prompt filled and submitted once')
  await b.close()
asyncio.run(main())
