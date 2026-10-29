import asyncio,json,os
from pathlib import Path
from playwright.async_api import async_playwright
async def main():
    lines=(Path(os.environ['LOCALAPPDATA'])/'Google/Chrome/User Data/DevToolsActivePort').read_text().splitlines()
    async with async_playwright() as p:
        browser=await p.chromium.connect_over_cdp('ws://127.0.0.1:'+lines[0]+lines[1],timeout=8000)
        for ctx in browser.contexts:
            for page in ctx.pages:
                if 'tools/flow' in page.url or 'flow.google' in page.url:
                    result=await page.evaluate('''()=>({buttons:[...document.querySelectorAll('button,[role=button],[role=combobox],[role=menuitem],[role=option]')].filter(e=>e.getClientRects().length).filter(e=>/Nano|Veo|Hình ảnh|Video|settings|tune/.test(e.textContent||'')).map(e=>({html:e.outerHTML.slice(0,1800),box:{x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y}})),editors:document.querySelectorAll('textarea,[contenteditable=true]').length})''')
                    print(json.dumps(result,ensure_ascii=True))
asyncio.run(main())
