"""Browser integration test of actual monitor, submit, result wait and download."""
import asyncio, json, sys
from pathlib import Path
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'TOOL THUMBNAIL'))
from playwright.async_api import async_playwright
from video_flow import StudioFlow

HTML='''<style>textarea{width:650px;height:80px}video{display:block;width:200px;height:100px}#results{margin-top:20px}</style>
<div><textarea></textarea><button aria-label="Generate" onclick="generate()">→</button></div><div id="results"></div>
<script>
let clicks=0;
function generate(){clicks++;document.querySelector('textarea').value='';
 for(let i=1;i<=2;i++){
 let card=document.createElement('div');card.innerHTML=`<video></video><button hidden onclick="this.nextElementSibling.hidden=false"><span class="material-symbols-outlined">file_download</span></button><div hidden><button onclick="downloadFile(${i},720)">720p</button><button onclick="downloadFile(${i},1080)">1080p</button><button onclick="downloadFile(${i},2160)">4K</button></div>`;
 document.getElementById('results').appendChild(card);const v=card.querySelector('video');
 v.setAttribute('src',location.origin+'/result/'+i+'.mp4');v.onclick=()=>{v.style.width='600px';card.querySelector('button').hidden=false};Object.defineProperties(v,{error:{get:()=>null},readyState:{get:()=>0},duration:{get:()=>NaN},currentSrc:{get:()=>''}});
 }
}
function downloadFile(i,r){const a=document.createElement('a');a.href='/download/'+i+'_'+r+'.mp4';a.download=i+'_'+r+'.mp4';document.body.appendChild(a);a.click();a.remove();for(const v of document.querySelectorAll('video'))v.style.width='200px';for(const n of document.querySelectorAll('#results>div>div'))n.hidden=true;}
</script>'''

async def main():
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(channel='chrome',headless=True)
  context=await browser.new_context(accept_downloads=True)
  from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
  import threading
  requests=[]
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):
    if '/download/' in self.path:requests.append(self.path)
    body=(b'\x00\x00\x00\x18ftypmp42'+b'\x00'*64) if '/download/' in self.path else HTML.encode()
    self.send_response(200)
    self.send_header('Content-Type','video/mp4' if '/download/' in self.path else 'text/html; charset=utf-8')
    if '/download/' in self.path:self.send_header('Content-Disposition','attachment; filename="video.mp4"')
    self.send_header('Content-Length',str(len(body)))
    self.end_headers();self.wfile.write(body)
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
  threading.Thread(target=server.serve_forever,daemon=True).start()
  page=await context.new_page();await page.goto(f'http://127.0.0.1:{server.server_port}/')
  await page.expose_function('__studioBridge',lambda message:{'ok':True})
  controller=StudioFlow.__new__(StudioFlow)
  controller.busy=False;controller.opening=False;controller.cancelled=False
  states=[];controller.on_state=states.append
  controller.flow_page=AsyncMock(return_value=page)
  # Settings and upload are covered separately; this test exercises everything after them.
  controller.configure_video=AsyncMock();controller.attach_reference=AsyncMock()
  folder=Path('_browser_video_test');folder.mkdir(exist_ok=True)
  try:
   await controller.start_video('thêm hiệu ứng tuyết rơi mạnh.','reference.jpg','Veo 3.1 - Lite','Thành phần','16:9',2,folder)
   record=json.loads((folder/'video.json').read_text(encoding='utf-8'))
   assert record['status']=='Hoàn tất',record
   assert record['submitted'] and len(record['files'])==2
   assert record['resolutions']==['4K','4K'],record
   assert len(requests)==2
   cached=await controller.download_video(page,record['resultSources'][0],folder,1)
   assert cached[0]==record['files'][0]
   assert len(requests)==2,requests
   assert await page.evaluate('clicks')==1
   assert all(Path(file).is_file() for file in record['files'])
   assert not controller.busy and controller.session_task is None
   assert await page.evaluate("document.activeElement.tagName")=="TEXTAREA"
   await page.evaluate("()=>document.querySelector('#results>div').setAttribute('aria-busy','true')")
   assert len(await controller.videos(page))==1
   await page.evaluate("()=>document.querySelector('#results>div').removeAttribute('aria-busy')")
   print('PASS: actual FlowErrors.watch API, one submit, two fresh results, highest-resolution downloads, atomic history, cleanup')
   # Cancel while waiting for Flow to prepare a file: no orphan download task.
   await page.evaluate('()=>{window.downloadFile=()=>{}}')
   cancel_folder=Path('_browser_cancel_test');cancel_folder.mkdir(exist_ok=True)
   ready=asyncio.Event()
   original_report=controller.report
   def report(message,running=True):
    original_report(message,running)
    if message.startswith('Tải video ở mức'):ready.set()
   controller.report=report
   task=asyncio.create_task(controller.download_video(page,record['resultSources'][0],cancel_folder,1))
   try:
    await asyncio.wait_for(ready.wait(),5)
    await asyncio.sleep(.1)
    task.cancel()
    try:await task
    except asyncio.CancelledError:pass
    assert not [t for t in asyncio.all_tasks() if 'request_download' in t.get_coro().__qualname__]
    assert await page.evaluate('document.activeElement.tagName')=='TEXTAREA'
    print('PASS: cancellation during download wait cleans child task and restores composer')
   finally:
    controller.report=original_report
    for file in cancel_folder.iterdir():file.unlink()
    cancel_folder.rmdir()
   # Existing generation errors are ignored; new errors and existing credit failures are actionable.
   await page.evaluate("()=>{let e=document.createElement('div');e.setAttribute('role','alert');e.textContent='Generation failed';document.body.appendChild(e)}")
   await controller.start_error_monitor(page,'prompt')
   await controller.check_flow_error(page)
   await page.evaluate("()=>{let e=document.createElement('div');e.setAttribute('role','alert');e.textContent='Insufficient credits';document.body.appendChild(e)}")
   await asyncio.sleep(.05)
   try:await controller.check_flow_error(page)
   except Exception as error:assert 'credit' in str(error).lower()
   else:raise AssertionError('New credit error was not detected')
   await page.evaluate('()=>__videoErrors.disconnect()')
   print('PASS: old error ignored and new credit failure detected')
  finally:
   for path in folder.iterdir():
    if path.is_file():path.unlink()
   folder.rmdir()
   await browser.close()
   server.shutdown();server.server_close()

asyncio.run(main())
