"""Authorized real Flow integration check. Never resubmits an existing test."""
import asyncio,json,sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'TOOL THUMBNAIL'))
from chrome_profile import discover_profiles
from video_flow import StudioFlow
from history_view import dated_output,register_video_folder
ROOT=Path(__file__).resolve().parent

def state(value):
    for message in value.get('logs',[]):print(json.dumps({'log':message},ensure_ascii=True),flush=True)

def error(value):print(json.dumps({'error':str(value)},ensure_ascii=True),flush=True)

async def main():
 c=StudioFlow(state,error)
 try:
  profiles=discover_profiles()
  if not profiles:raise ValueError('No local Chrome profile')
  print('Connecting existing Chrome...',flush=True)
  tabs=await c.connect_existing(profiles[0]['path'])
  project=[i for i,t in enumerate(tabs) if '/project/' in t['url']]
  if not project:raise ValueError('Open a Flow project in existing Chrome')
  await c.select_existing_tab(project[0],tabs[project[0]]['url'])
  marker=ROOT/'REAL_FLOW_TEST.json'
  if marker.exists():
   saved=json.loads(marker.read_text(encoding='utf-8'))
   path=Path(saved['record'])
   if path.exists():
    row=json.loads(path.read_text(encoding='utf-8'))
    if row.get('submitAttempted') or row.get('submitted'):
     print('Recovering existing test only; no new submission.',flush=True)
     import importlib,video_flow
     for attempt in range(6):
      try:
       c.__class__=importlib.reload(video_flow).StudioFlow
       await c.retry_video_download(path)
       return
      except Exception as failure:
       print(json.dumps({'downloadFailure':str(failure),'attempt':attempt+1},ensure_ascii=True),flush=True)
       page=await c.flow_page()
       snapshot=await page.evaluate('()=>({url:location.href,buttons:[...document.querySelectorAll("button")].filter(e=>e.getClientRects().length).map(e=>({text:e.textContent,aria:e.getAttribute("aria-label")})),menus:[...document.querySelectorAll("[role=menu],.cdk-overlay-pane")].filter(e=>e.getClientRects().length).map(e=>e.outerHTML)})')
       (ROOT/'real-download-failure.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
       if attempt==5:raise
       print('Holding connection for selector repair; retry download only in 20 seconds.',flush=True)
       await asyncio.sleep(20)

    if '--retry-before-submit' not in sys.argv:
     raise ValueError('Previous test stopped before submit. Explicit --retry-before-submit required.')
  source=ROOT.parent/'TOOL Video Flow OUTPUT/Video/2026-10-07/12-38-14_2c9e31c6/video.json'
  row=json.loads(source.read_text(encoding='utf-8'))
  settings=json.loads((ROOT/'video-settings.json').read_text(encoding='utf-8'))
  folder=dated_output(settings['output'],'Video')
  image=folder/('input'+Path(row['image']).suffix)
  shutil.copy2(row['image'],image)
  register_video_folder(ROOT,folder)
  marker.write_text(json.dumps({'record':str(folder/'video.json'),'source':str(source)},ensure_ascii=False,indent=2),encoding='utf-8')
  print('Test folder:',ascii(str(folder)),flush=True)
  await c.start_video(row['prompt'],image,row['model'],row['mode'],row['ratio'],1,folder)
 finally:
  await c.disconnect()
  c.loop.call_soon_threadsafe(c.loop.stop)

asyncio.run(main())
