import asyncio,os,json
from pathlib import Path
from playwright.async_api import async_playwright
async def main():
 lines=(Path(os.environ['LOCALAPPDATA'])/'Google/Chrome/User Data/DevToolsActivePort').read_text().splitlines()
 async with async_playwright() as pw:
  b=await pw.chromium.connect_over_cdp('ws://127.0.0.1:'+lines[0]+lines[1],timeout=15000)
  pages=[p for c in b.contexts for p in c.pages if 'flow.google' in p.url]
  if not pages:raise ValueError('No Flow tab')
  p=pages[0];await p.keyboard.press('Escape');await p.keyboard.press('Escape')
  if '/edit/' not in p.url:
   targets=p.locator('flow-video-tile img.thumbnail').filter(visible=True)
   await targets.first.click();await asyncio.sleep(1)
  info=await p.evaluate('''()=>({url:location.href,players:[...document.querySelectorAll('video')].filter(e=>e.getClientRects().length).map(v=>({src:v.currentSrc||v.src,width:v.getBoundingClientRect().width,parent:v.parentElement.parentElement.outerHTML})),buttons:[...document.querySelectorAll('button')].filter(e=>e.getClientRects().length).map(e=>({text:e.textContent,aria:e.getAttribute('aria-label'),html:e.outerHTML}))})''')
  Path('flow-preview-audit.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'url':info['url'],'players':[(v['width']) for v in info['players']],'buttons':[(v['text'],v['aria']) for v in info['buttons']]},ensure_ascii=True)[:8000])
  import re
  downloads=p.get_by_role('button',name=re.compile(r'^T\u1ea3i.*xu\u1ed1ng$',re.I)).filter(visible=True)
  print('DOWNLOAD count',await downloads.count())
  if await downloads.count()==1:
   await downloads.click();await asyncio.sleep(.7)
   menu=await p.evaluate('''()=>[...document.querySelectorAll('[role=menu],.cdk-overlay-pane')].filter(e=>e.getClientRects().length).map(e=>e.outerHTML)''')
   Path('flow-download-menu-audit.json').write_text(json.dumps(menu,ensure_ascii=False,indent=2),encoding='utf-8')
   print('MENU',ascii(' '.join(menu))[:12000])
  await p.keyboard.press('Escape');await p.keyboard.press('Escape')
  if '/edit/' in p.url:await p.goto(p.url.split('/edit/')[0],wait_until='domcontentloaded')
asyncio.run(main())
