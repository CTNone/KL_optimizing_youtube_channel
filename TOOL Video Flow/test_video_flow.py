"""Tests for selected settings, highest resolution and no duplicate submissions."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'TOOL THUMBNAIL'))
import unittest
import asyncio
import tempfile
from unittest.mock import AsyncMock, patch
from video_flow import StudioFlow, resolution_rank

class ModeDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_thumbnail_model_is_verified_before_resume(self):
        from desktop_flow import DesktopFlow
        c=StudioFlow.__new__(StudioFlow);page=AsyncMock();events=[]
        c.select_generation_mode=AsyncMock(side_effect=lambda p,m:events.append('mode'))
        c.pause=AsyncMock()
        c.select_thumbnail_model=AsyncMock(side_effect=lambda p,m:events.append(m))
        c.on_state=lambda state:None
        c.open_video_settings=AsyncMock(side_effect=lambda p:events.append('settings ready'))
        with patch.object(DesktopFlow,'request',AsyncMock(side_effect=lambda p,m:events.append('resume'))):
            await c.request(page,{'type':'resumeRun','checkpoint':{'args':{'cfg':{'modelChoice':'Nano Banana 2 Lite'}}}})
        self.assertEqual(events,['mode','Nano Banana 2 Lite','settings ready','resume'])

    async def test_thumbnail_model_failure_prevents_prompt_submission(self):
        from desktop_flow import DesktopFlow
        c=StudioFlow.__new__(StudioFlow);c.select_generation_mode=AsyncMock();c.pause=AsyncMock()
        c.select_thumbnail_model=AsyncMock(side_effect=ValueError('model not confirmed'))
        with patch.object(DesktopFlow,'request',AsyncMock()) as dispatch:
            with self.assertRaisesRegex(ValueError,'model not confirmed'):
                await c.request(AsyncMock(),{'type':'resumeRun','checkpoint':{'args':{'cfg':{'modelChoice':'Nano Banana 2 Lite'}}}})
            dispatch.assert_not_awaited()

    async def test_thumbnail_selects_image_before_resume(self):
        from desktop_flow import DesktopFlow
        c=StudioFlow.__new__(StudioFlow);page=AsyncMock();events=[]
        async def mode(p,m):events.append(m)
        async def dispatch(p,message):events.append(message['type']);return {'ok':True}
        c.select_generation_mode=AsyncMock(side_effect=mode)
        c.pause=AsyncMock()
        with patch.object(DesktopFlow,'request',AsyncMock(side_effect=dispatch)):
            await c.request(page,{'type':'resumeRun'})
            await c.request(page,{'type':'status'})
        self.assertEqual(events,['image','resumeRun','status'])
        c.select_generation_mode.assert_awaited_once_with(page,'image')
        page.keyboard.press.assert_not_awaited()
        c.pause.assert_awaited_once_with(.6)

    async def test_thumbnail_mode_failure_prevents_resume(self):
        from desktop_flow import DesktopFlow
        c=StudioFlow.__new__(StudioFlow);c.select_generation_mode=AsyncMock(side_effect=ValueError('mode not confirmed'))
        with patch.object(DesktopFlow,'request',AsyncMock()) as dispatch:
            with self.assertRaisesRegex(ValueError,'mode not confirmed'):
                await c.request(AsyncMock(),{'type':'resumeRun'})
            dispatch.assert_not_awaited()

class RankTests(unittest.TestCase):
    def test_highest(self):
        self.assertGreater(resolution_rank('4K'), resolution_rank('1080p'))
        self.assertGreater(resolution_rank('1080p'), resolution_rank('720p'))
        self.assertEqual(resolution_rank('Download original'),0)
        self.assertEqual(resolution_rank('x4'),0)

class StorageTests(unittest.TestCase):
    def setUp(self):
        import uuid
        self.folder=Path('_storage_test_'+uuid.uuid4().hex[:8]);self.folder.mkdir()
    def tearDown(self):
        for file in self.folder.iterdir():file.unlink()
        self.folder.rmdir()
    def test_reject_html_download(self):
        from video_storage import validate_video
        path=self.folder/'fake.mp4';path.write_bytes(b'<html>Forbidden download</html>')
        with self.assertRaisesRegex(ValueError,'cấu trúc video'):validate_video(path)
    def test_video_header_and_checksum(self):
        from video_storage import validate_video
        path=self.folder/'real.mp4';path.write_bytes(b'\x00\x00\x00\x18ftypmp42'+b'\x00'*64)
        info=validate_video(path)
        self.assertEqual(info['bytes'],path.stat().st_size)
        self.assertEqual(len(info['sha256']),64)
    def test_missing_first_slot_does_not_duplicate_second(self):
        from video_storage import record_download
        row={'files':['missing.mp4','second.mp4'],'resolutions':['720p','4K']}
        record_download(row,1,'first-src','first-fixed.mp4','1080p')
        self.assertEqual(row['files'],['first-fixed.mp4','second.mp4'])
    def test_atomic_history(self):
        from video_storage import atomic_json
        import json
        path=self.folder/'history.json'
        atomic_json(path,{'status':'old'});atomic_json(path,{'status':'new'})
        self.assertEqual(json.loads(path.read_text())['status'],'new')
        self.assertFalse(path.with_suffix('.json.tmp').exists())

class RunTests(unittest.IsolatedAsyncioTestCase):
    async def test_uncertain_send_does_not_retry(self):
        controller=StudioFlow.__new__(StudioFlow)
        controller.busy=False;controller.opening=False;controller.cancelled=False
        controller.on_state=lambda state:None
        controller.flow_page=AsyncMock()
        page=controller.flow_page.return_value
        page.reload=AsyncMock()
        page.evaluate=AsyncMock()
        editor=AsyncMock()
        editor.count.return_value=1
        editor.evaluate.return_value='TEXTAREA'
        editor.input_value.return_value='unchanged prompt'
        class Locator:
            def filter(self,**kwargs):return editor
        page.locator=lambda selector:Locator()
        send=AsyncMock();send.is_disabled.return_value=False
        controller.unique=AsyncMock(return_value=send)
        controller.video_send_button=AsyncMock(return_value=send)
        controller.inject=AsyncMock();controller.configure_video=AsyncMock()
        controller.attach_reference=AsyncMock();controller.videos=AsyncMock(return_value=[])
        controller.pause=AsyncMock()
        folder=Path('_video_test_run');folder.mkdir(exist_ok=True)
        with self.assertRaisesRegex(ValueError,'không tự gửi lại'):
            await controller.start_video('prompt','reference.jpg','Veo 3.1 - Lite','Thành phần','16:9',1,folder)
        self.assertEqual(send.click.await_count,1)
        self.assertFalse(controller.busy)
        import json
        self.assertTrue(json.loads((folder/'video.json').read_text(encoding='utf-8'))['submitted'])
        (folder/'video.json').unlink();folder.rmdir()

class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import uuid
        self.folder=Path('_video_unit_'+uuid.uuid4().hex[:8]);self.folder.mkdir()
        c=self.controller=StudioFlow.__new__(StudioFlow)
        c.busy=False;c.opening=False;c.cancelled=False;c.on_state=lambda state:None
        self.page=AsyncMock();c.flow_page=AsyncMock(return_value=self.page)
        editor=AsyncMock();editor.count.return_value=1;editor.evaluate.return_value='TEXTAREA';editor.input_value.return_value=''
        class Locator:
            def filter(self,**kwargs):return editor
        self.page.locator=lambda selector:Locator()
        self.send=AsyncMock();self.send.is_disabled.return_value=False
        c.video_send_button=AsyncMock(return_value=self.send)
        c.inject=AsyncMock();c.configure_video=AsyncMock();c.attach_reference=AsyncMock()
        c.start_error_monitor=AsyncMock();c.check_flow_error=AsyncMock();c.pause=AsyncMock()
        c.videos=AsyncMock(return_value=[])
        c.wait_for_videos=AsyncMock(return_value=['first','second'])
        c.download_video=AsyncMock(side_effect=[('first.mp4','4K'),('second.mp4','4K')])

    async def asyncTearDown(self):
        for file in self.folder.iterdir():file.unlink()
        self.folder.rmdir()

    async def run_video(self):
        await self.controller.start_video('prompt','reference.jpg','Veo 3.1 - Lite','Thành phần','16:9',2,self.folder)

    def record(self):
        import json
        return json.loads((self.folder/'video.json').read_text(encoding='utf-8'))

    async def test_monitor_failure_before_click(self):
        self.controller.start_error_monitor.side_effect=ValueError('monitor failed')
        with self.assertRaisesRegex(ValueError,'monitor failed'):await self.run_video()
        self.send.click.assert_not_awaited()
        row=self.record()
        self.assertFalse(row['submitted']);self.assertFalse(row['submitAttempted'])
        self.assertFalse(self.controller.busy)

    async def test_success(self):
        await self.run_video()
        self.send.click.assert_awaited_once()
        row=self.record()
        self.assertEqual(row['status'],'Hoàn tất')
        self.assertEqual(len(row['files']),2)
        self.assertTrue(row['submitted'])
        self.assertIsNone(self.controller.session_task)

    async def test_partial_download_keeps_first(self):
        self.controller.download_video.side_effect=[('first.mp4','4K'),ValueError('download failed')]
        with self.assertRaisesRegex(ValueError,'download failed'):await self.run_video()
        row=self.record()
        self.assertEqual(row['status'],'Một phần');self.assertEqual(row['files'],['first.mp4'])
        self.send.click.assert_awaited_once()

    async def test_retry_download_never_submits(self):
        await self.run_video()
        row=self.record();row['files']=[];row['resolutions']=[];row['status']='Lỗi tải'
        import json
        path=self.folder/'video.json';path.write_text(json.dumps(row),encoding='utf-8')
        self.send.click.reset_mock()
        self.controller.download_video=AsyncMock(side_effect=[('first.mp4','4K'),('second.mp4','4K')])
        await self.controller.retry_video_download(path)
        self.send.click.assert_not_awaited()
        self.assertEqual(self.record()['status'],'Hoàn tất')
        self.assertEqual(len(self.record()['files']),2)

    async def test_old_results_do_not_complete_new_run(self):
        self.controller.videos=AsyncMock(return_value=[{'src':'old-video','key':'old-key'}])
        with self.assertRaisesRegex(ValueError,'Hết thời gian'):
            await StudioFlow.wait_for_videos(self.controller,self.page,{'old-key'},1,timeout=.005)
        self.controller.download_video.assert_not_awaited()

    async def test_completed_result_downloads_without_stability_delay(self):
        self.controller.videos=AsyncMock(return_value=[{'src':'finished','key':'new','prompts':['prompt']}])
        self.controller.pause=AsyncMock()
        selected=await StudioFlow.wait_for_videos(self.controller,self.page,set(),1,prompt='prompt')
        self.assertEqual(selected,['finished'])
        self.controller.pause.assert_not_awaited()
        self.controller.videos.assert_awaited_once()

    async def test_virtual_old_clip_is_excluded_by_exact_prompt(self):
        self.controller.videos=AsyncMock(return_value=[
            {'src':'new-video','key':'new-key','prompts':['tuyết rơi.']},
            {'src':'old-video','key':'old-key','prompts':['tuyết rơi mạnh.']}
        ])
        async def pause(seconds):await asyncio.sleep(.05)
        self.controller.pause=pause
        selected=await StudioFlow.wait_for_videos(self.controller,self.page,set(),1,timeout=3,prompt='tuyết rơi.')
        self.assertEqual(selected,['new-video'])

    async def test_legacy_download_matches_prompt_without_file_picker(self):
        import json
        path=self.folder/'video.json'
        path.write_text(json.dumps({'prompt':'prompt','count':1,'submitted':True,'status':'Đang tạo','files':[],'resolutions':[]}),encoding='utf-8')
        self.controller.videos=AsyncMock(return_value=[
            {'src':'correct-video','prompts':['prompt']},
            {'src':'old-video','prompts':['other prompt']}
        ])
        self.controller.download_video=AsyncMock(return_value=('correct.mp4','1080p'))
        await self.controller.download_existing_record(path)
        self.send.click.assert_not_awaited()
        self.assertEqual(self.record()['resultSources'],['correct-video'])
        self.assertEqual(self.record()['status'],'Hoàn tất')

    async def test_cancel_after_submit(self):
        self.controller.wait_for_videos.side_effect=asyncio.CancelledError()
        await self.run_video()
        self.assertEqual(self.record()['status'],'Đã dừng · kiểm tra Flow')
        self.assertFalse(self.controller.busy)
        self.controller.download_video.assert_not_awaited()

    async def test_click_failure_is_uncertain(self):
        self.send.click.side_effect=ValueError('click failed')
        with self.assertRaisesRegex(ValueError,'click failed'):await self.run_video()
        row=self.record()
        self.assertTrue(row['submitAttempted']);self.assertFalse(row['submitted'])
        self.assertTrue(row['submissionUncertain'])
        self.send.click.assert_awaited_once()

if __name__=='__main__':unittest.main()
