import asyncio,json,os
from pathlib import Path
from playwright.async_api import async_playwright
async def main():
 e=(Path(os.environ['LOCALAPPDATA'])/'Google/Chrome/User Data/DevToolsActivePort').read_text().splitlines()
 async with async_playwright() as pw:
  b=await pw.chromium.connect_over_cdp('ws://127.0.0.1:'+e[0]+e[1],timeout=15000)
  p=next(p for c in b.contexts for p in c.pages if '/project/' in p.url)
  d=await p.evaluate('()=>({url:location.href,body:document.body.innerText.slice(-9000),menus:[...document.querySelectorAll("[role=menu],.cdk-overlay-pane")].filter(e=>e.getClientRects().length).map(e=>e.outerHTML)})')
  Path('live-download-after-choice.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps(d,ensure_ascii=True)[:14000])
asyncio.run(main())
