import asyncio, sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd().parent/'TOOL THUMBNAIL'))
from playwright.async_api import async_playwright
from video_flow import StudioFlow

async def main():
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(channel='chrome',headless=True)
        page=await browser.new_page()
        await page.set_content('''<textarea></textarea><button onclick="document.getElementById('panel').hidden=false">Video · 720p · 8 giây x1</button><div id="panel" hidden>
        <div><button onclick="select(this)">Hình ảnh</button><button onclick="select(this)">Video</button></div>
        <div><button onclick="select(this)">Khung hình</button><button onclick="select(this)">Thành phần</button></div>
        <div><button onclick="select(this)">16:9</button><button onclick="select(this)">9:16</button></div>
        <button id="model" onclick="this.hidden=true;document.getElementById('option').hidden=false">Veo 3.1 - Lite</button>
        <button role="option" id="option" hidden onclick="this.hidden=true;document.getElementById('model').hidden=false">Veo 3.1 - Lite</button>
        <div><button onclick="select(this)">x1</button><button onclick="select(this)">x2</button><button onclick="select(this)">x3</button><button onclick="select(this)">x4</button></div></div>
        <script>function select(e){for(const x of e.parentElement.children)x.setAttribute('aria-pressed','false');e.setAttribute('aria-pressed','true')}</script>''')
        controller=StudioFlow.__new__(StudioFlow)
        controller.cancelled=False;controller.on_state=lambda s:None
        async def pause(seconds): pass
        controller.pause=pause
        await controller.configure_video(page,'Veo 3.1 - Lite','Thành phần','9:16',4)
        # Regression: image mode, icon-only settings, multiline and split count labels.
        for label in ['Hình ảnh · Nano Banana 2 Lite', '<span class="material-symbols-outlined">tune</span><span>Cài đặt</span>', 'Video<br>720p · 8 giây<br>x1', 'x1']:
            await page.evaluate('(label)=>{document.getElementById("panel").hidden=true;document.querySelector("body > button").innerHTML=label}',label)
            await controller.configure_video(page,'Veo 3.1 - Lite','Thành phần','9:16',4)
        await page.evaluate('()=>{document.querySelector("#panel button").innerHTML="<span class=material-symbols-outlined>image</span>Hình ảnh";document.querySelectorAll("#panel button")[1].innerHTML="<span class=material-symbols-outlined>videocam</span>Video"}')
        await controller.configure_video(page,'Veo 3.1 - Lite','Thành phần','9:16',4)
        await page.evaluate("""()=>{
            document.getElementById('option').outerHTML='<div id="models" hidden><div onclick="pickModel()"><span>Veo 3.1 – Lite</span><div>10 tín dụng · Tạo video nhanh</div></div><div>Veo 3.1 - Fast<div>20 tín dụng</div></div></div>';
            document.getElementById('model').onclick=()=>{document.getElementById('model').hidden=true;setTimeout(()=>document.getElementById('models').hidden=false,100)};
            window.pickModel=()=>{document.getElementById('models').hidden=true;document.getElementById('model').hidden=false;document.getElementById('model').innerHTML='Veo 3.1 — Lite <span class="material-symbols-outlined">expand_more</span>'};
        }""")
        # Use real waits for delayed menu rendering.
        async def wait(seconds):
            await asyncio.sleep(min(seconds,.1))
        controller.pause=wait
        await controller.configure_video(page,'Veo 3.1 - Lite','Thành phần','9:16',4)
        assert await page.get_by_role('button',name='9:16',exact=True).get_attribute('aria-pressed')=='true'
        assert await page.get_by_role('button',name='x4',exact=True).get_attribute('aria-pressed')=='true'
        print('PASS: real Chrome selected and verified video settings')
        await page.set_content("""<style>textarea{position:absolute;left:30px;top:90px;width:650px;height:60px}button{position:absolute;width:40px;height:40px;border:0;border-radius:50%}#clear{left:710px;top:20px;background:#333;color:white}#add{left:35px;top:165px;background:#333}#send{left:711px;top:165px;background:white}</style><textarea>tạo hiệu ứng tuyết rơi.</textarea><button id="clear">×</button><button id="add">+</button><button id="send"><svg width="24" height="24"><path d="M4 12h16M14 6l6 6-6 6"/></svg></button>""")
        await page.evaluate((Path('video_controls.js')).read_text(encoding='utf-8'))
        result=await page.evaluate("()=>VideoControls.send('test-send')")
        assert result['count']==1,result
        assert await page.locator('[data-video-control="test-send"]').get_attribute('id')=='send'
        await page.evaluate("()=>document.getElementById('send').disabled=true")
        assert (await page.evaluate("()=>VideoControls.send('disabled-send')"))['count']==0
        await page.evaluate("()=>{const s=document.getElementById('send');s.disabled=false;s.innerHTML='<span class=material-symbols-outlined>arrow_forward</span>';s.style.background='#333'}")
        result=await page.evaluate("()=>VideoControls.send('icon-send')")
        assert result['count']==1,result
        await page.locator('[data-video-control="icon-send"]').click()
        print('PASS: SVG-only send, clear/add excluded, disabled send excluded, raw arrow icon')
        for blocked in ['<button disabled>4K</button>', '<div role="menuitem" aria-disabled="true"><div>4K</div></div>', '<button>4K <span class="material-symbols-outlined">lock</span> Upgrade</button>']:
            await page.set_content('<div role="menu"><button>720p</button><button>1080p</button>'+blocked+'</div>')
            await page.evaluate(Path('video_controls.js').read_text(encoding='utf-8'))
            result=await page.evaluate("()=>VideoControls.resolutions('allowed')")
            assert result['count']==1 and result['rank']==1080,result
        print('PASS: account restrictions exclude disabled, inherited disabled and locked upgrade options')
        # Real Angular menu: a disabled 4K sibling must not disqualify 1080p.
        import json
        actual=json.loads(Path('live-resolution-diagnostic.json').read_text(encoding='utf-8'))
        await page.set_content(actual['menus'][0])
        await page.evaluate(Path('video_controls.js').read_text(encoding='utf-8'))
        result=await page.evaluate("()=>VideoControls.resolutions('angular')")
        assert result['count']==1 and result['rank']==1080,result
        assert await page.locator('[data-video-control="angular"]').get_attribute('role')=='menuitem'
        print('PASS: actual Flow Angular menu selects 1080p; disabled 4K and GIF excluded')
        marker=json.loads(Path('REAL_FLOW_TEST.json').read_text(encoding='utf-8'))
        record=json.loads(Path(marker['record']).read_text(encoding='utf-8'))
        sample=record['files'][0]
        await page.route('https://flow-content.google/video/test',lambda route:route.fulfill(path=sample,content_type='video/mp4'))
        await page.set_content('<flow-grid-tile-container><flow-video-tile style="display:block"><video hidden src="https://flow-content.google/video/test"></video><img class="thumbnail" src="https://flow-content.google/image/test" style="width:100px;height:100px"></flow-video-tile><span>snow</span></flow-grid-tile-container>')
        await page.evaluate(Path('video_controls.js').read_text(encoding='utf-8'))
        rows=await page.evaluate('()=>VideoControls.results()')
        assert len(rows)==1 and 'snow' in rows[0]['prompts'],rows
        await page.evaluate("()=>document.querySelector('video').src='https://flow.google.com/asb/changed-proxy'")
        result=await page.evaluate("()=>VideoControls.openClip('https://flow-content.google/video/test','remembered')")
        assert result['count']==1,result
        print('PASS: hidden completed video and changed playback proxy retain exact clip selection')
        await page.set_content('<flow-grid-tile-container><flow-video-tile style="display:block"><img class="thumbnail" style="width:100px;height:100px" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aS1kAAAAASUVORK5CYII="><div role="progressbar" aria-valuenow="99" aria-valuemax="100"></div><span class="footer-title">snow</span></flow-video-tile></flow-grid-tile-container>')
        await page.evaluate("async()=>{await document.querySelector('img').decode()}")
        await page.evaluate(Path('video_controls.js').read_text(encoding='utf-8'))
        assert await page.evaluate('()=>VideoControls.results().length')==0
        await page.evaluate("()=>document.querySelector('[role=progressbar]').setAttribute('aria-valuenow','100')")
        rows=await page.evaluate('()=>VideoControls.results()')
        assert len(rows)==1 and rows[0]['readyState']==0,rows
        result=await page.evaluate("source=>VideoControls.openClip(source,'poster-only')",rows[0]['src'])
        assert result['count']==1,result
        print('PASS: thumbnail-only completion at 100% opens immediately without mounting a player; 99% rejected')
        await page.set_content("""<textarea></textarea><button id="trigger" onclick="document.getElementById('modes').hidden=false">Video · 720p · 8 giây x1</button><div id="modes" hidden><div><button id="image-mode" aria-pressed="false" onclick="switchMode('image')"><mat-icon>image</mat-icon>Hình ảnh</button><button id="video-mode" aria-pressed="true" onclick="switchMode('video')"><mat-icon>videocam</mat-icon>Video</button></div><div id="next-settings">Veo 3.1 - Lite</div></div><script>function switchMode(mode){document.getElementById('image-mode').setAttribute('aria-pressed',String(mode==='image'));document.getElementById('video-mode').setAttribute('aria-pressed',String(mode==='video'));document.getElementById('next-settings').textContent=mode==='image'?'Nano Banana 2 Lite':'Veo 3.1 - Lite';document.getElementById('trigger').textContent=mode==='image'?'Hình ảnh · Nano Banana 2 Lite x1':'Video · 720p · 8 giây x1';}</script>""")
        for mode,model in [('image','Nano Banana 2 Lite'),('video','Veo 3.1 - Lite'),('image','Nano Banana 2 Lite')]:
            await controller.select_generation_mode(page,mode)
            assert await page.locator('#'+mode+'-mode').get_attribute('aria-pressed')=='true'
            assert await page.locator('#next-settings').inner_text()==model
        print('PASS: Video -> Image -> Video -> Image explicitly switches before model settings, including already open menu')
        await browser.close()
asyncio.run(main())
