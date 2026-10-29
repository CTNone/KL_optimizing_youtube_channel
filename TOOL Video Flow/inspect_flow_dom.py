import asyncio, os, json
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
 endpoint=(Path(os.environ['LOCALAPPDATA'])/'Google/Chrome/User Data/DevToolsActivePort').read_text().splitlines()
 async with async_playwright() as pw:
  browser=await pw.chromium.connect_over_cdp('ws://127.0.0.1:'+endpoint[0]+endpoint[1],timeout=15000)
  for context in browser.contexts:
   for page in context.pages:
    from urllib.parse import urlparse
    parsed=urlparse(page.url)
    print('Tab:',parsed.hostname,parsed.path)
    if not (parsed.hostname in ('flow.google.com','flow.google') or parsed.hostname=='labs.google' and 'flow' in parsed.path):continue
    result=await page.evaluate('''()=>({videos:[...document.querySelectorAll('video')].map(v=>({html:v.outerHTML,visible:!!v.getClientRects().length,ready:v.readyState,error:v.error?.code})),cards:[...document.querySelectorAll('img')].filter(i=>i.getClientRects().length).map(i=>{let p=i;for(let n=0;n<4&&p.parentElement;n++)p=p.parentElement;return p.outerHTML}).slice(-20),buttons:[...document.querySelectorAll('button')].filter(e=>e.getClientRects().length).map(e=>({text:e.textContent,aria:e.getAttribute('aria-label')}))})''')
    Path('flow-dom-diagnostic.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Saved live Flow DOM diagnostic; videos:',len(result['videos']),'image containers:',len(result['cards']))
    print('Video states:',[(v['visible'],v['ready'],v.get('error')) for v in result['videos']])
    await page.evaluate(Path('video_controls.js').read_text(encoding='utf-8'))
    detection=await page.evaluate('()=>({detected:VideoControls.results(),ancestors:[...document.querySelectorAll("video")].map(v=>{let p=v;const a=[];for(let i=0;i<7&&p;i++,p=p.parentElement)a.push({tag:p.tagName,cls:p.className,videoCount:p.querySelectorAll("video").length,progress:p.querySelectorAll("[role=progressbar],[aria-busy=true]").length,text:(p.textContent||"").slice(0,200)});return a})})')
    Path('flow-detection-diagnostic.json').write_text(json.dumps(detection,ensure_ascii=False,indent=2),encoding='utf-8')
    current=await page.evaluate("()=>VideoControls.results().map(v=>({key:v.key,prompts:v.prompts}))")
    print(json.dumps(current,ensure_ascii=True))

asyncio.run(main())
