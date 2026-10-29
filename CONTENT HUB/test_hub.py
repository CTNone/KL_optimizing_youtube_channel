import json
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from store import Store, DomainError, CHECKS, fingerprint, TZ
from services import Adapters, RenderWorker, InstanceLock, find_workspace

class DomainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hub tests tiếng Việt ")
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "hub.sqlite3")
        self.channel = self.store.save_channel("Winter Jazz", niche="Jazz")
        self.project = self.store.create_project(self.channel, "Snow café", "Giữ cảnh, tuyết ngoài trời", "Editor")
        self.actor = "Tester"

    def tearDown(self):
        self.temp.cleanup()

    def asset(self, kind, content=b"asset", slot=""):
        suffix = {"research":".csv", "thumbnail":".jpg", "clip":".mp4", "final":".mp4", "music":".wav"}[kind]
        path = self.root / (kind+suffix)
        path.write_bytes(content)
        return self.store.add_asset(self.project, kind, path, self.actor, slot)

    def step(self):
        p = self.store.project(self.project)
        return self.store.advance(self.project, p["revision"], self.actor)

    def to_edit(self):
        self.step()
        self.asset("research")
        self.step()
        self.asset("thumbnail")
        self.step()
        self.asset("clip")
        self.step()

    def to_review(self):
        self.to_edit()
        self.asset("final", slot="main")
        self.step()

    def approve(self):
        p = self.store.project(self.project)
        self.store.review(self.project, p["revision"], self.actor, True, CHECKS, "Đã xem preview")

    def test_channels_are_isolated(self):
        other = self.store.save_channel("Forest")
        self.store.create_project(other, "Forest calm")
        self.assertEqual(len(self.store.projects(self.channel)), 1)
        self.assertEqual(self.store.projects(self.channel)[0]["title"], "Snow café")

    def test_archive_prevents_new_project_without_deleting_old(self):
        self.store.save_channel("Winter Jazz", channel_id=self.channel, archived=True)
        with self.assertRaises(DomainError):
            self.store.create_project(self.channel, "New")
        self.assertEqual(len(self.store.projects(self.channel)), 1)

    def test_workflow_gates_and_atomic_audit(self):
        self.step()
        before = len(self.store.events(self.project))
        with self.assertRaises(DomainError):
            self.step()
        self.assertEqual(self.store.project(self.project)["stage"], "research")
        self.assertEqual(len(self.store.events(self.project)), before)

    def test_optimistic_concurrency(self):
        p = self.store.project(self.project)
        self.store.update_project(self.project, p["revision"], "Edited", "Brief", "Editor", "", self.actor)
        with self.assertRaises(DomainError):
            self.store.advance(self.project, p["revision"], self.actor)

    def test_versioning_deduplicates_same_file_and_preserves_history(self):
        first = self.asset("thumbnail", b"first")
        same = self.asset("thumbnail", b"first")
        second = self.asset("thumbnail", b"second")
        self.assertEqual(first, same)
        self.assertNotEqual(first, second)
        self.assertEqual(len(self.store.assets(self.project)), 2)
        self.assertEqual(self.store.assets(self.project, latest=True)[0]["version"], 2)

    def test_new_asset_after_approval_requires_new_review(self):
        self.to_review()
        self.approve()
        self.assertEqual(self.store.project(self.project)["stage"], "ready")
        self.asset("final", b"revised", "main")
        self.assertEqual(self.store.project(self.project)["stage"], "editing")

    def test_review_requires_all_checks_and_current_file(self):
        self.to_review()
        p = self.store.project(self.project)
        with self.assertRaises(DomainError):
            self.store.review(self.project, p["revision"], self.actor, True, CHECKS[:2], "")
        (self.root / "final.mp4").write_bytes(b"externally modified")
        with self.assertRaises(DomainError):
            self.approve()
        self.assertEqual(self.store.project(self.project)["stage"], "review")

    def test_rejection_and_rework(self):
        self.to_review()
        p = self.store.project(self.project)
        with self.assertRaises(DomainError):
            self.store.review(self.project, p["revision"], self.actor, False, [], "")
        self.store.review(self.project, p["revision"], self.actor, False, [], "Điểm nối bị bóng đôi")
        self.assertEqual(self.store.project(self.project)["stage"], "editing")

    def test_publish_gates_and_metrics(self):
        self.to_review()
        self.approve()
        p = self.store.project(self.project)
        future = (datetime.now(TZ)+timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        self.store.advance(self.project, p["revision"], self.actor, future)
        blocked = self.root / "new_final.mp4"
        blocked.write_bytes(b"changed")
        with self.assertRaises(DomainError):
            self.store.add_asset(self.project, "final", blocked, self.actor)
        p = self.store.project(self.project)
        with self.assertRaises(DomainError):
            self.store.advance(self.project, p["revision"], self.actor, youtube_url="https://youtube.com.evil.example/watch?v=x")
        self.store.advance(self.project, p["revision"], self.actor, youtube_url="https://youtu.be/example_id")
        self.store.add_metrics(self.project, 100, 200, 1000, 5, self.actor)
        with self.assertRaises(DomainError):
            self.store.add_metrics(self.project, 100, float("nan"), 1000, 5, self.actor)
        self.assertEqual(self.store.export_bundle(self.project)["metrics"][0]["views"], 100)

    def test_render_excludes_parallel_jobs_and_recovers_interruption(self):
        self.to_edit()
        first = self.store.create_job(self.project, {"seconds": 6}, self.actor)
        with self.assertRaises(DomainError):
            self.store.create_job(self.project, {}, self.actor)
        job = self.store.claim_job()
        self.assertEqual(job["id"], first)
        self.store.recover_jobs()
        self.assertEqual(self.store.jobs()[0]["state"], "interrupted")
        second = self.store.create_job(self.project, {}, self.actor, retry_of=first)
        self.store.cancel_job(second, self.actor)
        self.assertIsNone(self.store.claim_job())

    def test_busy_job_blocks_review(self):
        self.to_edit()
        self.asset("final", slot="main")
        self.store.create_job(self.project, {}, self.actor)
        with self.assertRaises(DomainError):
            self.step()

    def test_database_backup_is_consistent(self):
        destination = self.root / "backup.sqlite3"
        self.store.backup(destination)
        copied = Store(destination)
        self.assertEqual(copied.project(self.project)["title"], "Snow café")
        with self.assertRaises(DomainError):
            self.store.backup(self.store.path)

    def test_one_instance_per_database(self):
        path = self.root / "instance.lock"
        lock = InstanceLock(path)
        try:
            with self.assertRaises(DomainError):
                InstanceLock(path)
        finally:
            lock.close()


class RenderIntegrationTests(unittest.TestCase):
    setUp = DomainTests.setUp
    tearDown = DomainTests.tearDown
    asset = DomainTests.asset
    step = DomainTests.step
    to_edit = DomainTests.to_edit
    def test_real_render_registers_asset_and_preserves_provenance(self):
        workspace = find_workspace()
        adapters = Adapters(self.store, workspace)
        ffmpeg = adapters.editor_dir / "tools" / "ffmpeg.exe"
        if not ffmpeg.is_file():
            self.skipTest("FFmpeg not available")
        self.to_edit()
        clip = self.root / "clip.mp4"
        subprocess.run([str(ffmpeg), "-y", "-v", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=320x180:rate=24:duration=2", "-c:v", "libx264", str(clip)], check=True)
        self.store.add_asset(self.project, "clip", clip, self.actor)
        job_id = adapters.enqueue_render(self.project, 5, "720p", .4, self.actor)
        worker = RenderWorker(self.store, adapters)
        worker.execute(self.store.claim_job())
        job = self.store.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        self.assertEqual(job["state"], "succeeded", job["error"])
        result = json.loads(job["result_json"])
        self.assertTrue(Path(result["output"]).is_file())
        self.assertTrue(result["verification"]["frames_ok"])
        final = next(a for a in self.store.assets(self.project, latest=True) if a["kind"] == "final")
        self.assertEqual(final["id"], result["asset_id"])
        self.assertIn(job_id, final["note"])
        bundle = self.store.export_bundle(self.project)
        self.assertTrue(any(e["action"] == "render_succeeded" for e in bundle["events"]))


if __name__ == "__main__":
    unittest.main()
