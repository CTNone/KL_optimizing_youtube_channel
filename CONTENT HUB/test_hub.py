import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from store import Store, DomainError, CHECKS, fingerprint, TZ
from services import InstanceLock
from demo import seed
from youtube_analytics import YouTubeAnalyticsClient

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
        published = self.store.project(self.project)
        self.assertEqual(published["stage"], "published")
        self.assertTrue(published["published_at"])
        self.store.add_metrics(self.project, 100, 200, 1000, 5, self.actor)
        with self.assertRaises(DomainError):
            self.store.add_metrics(self.project, 100, float("nan"), 1000, 5, self.actor)
        self.assertEqual(self.store.export_bundle(self.project)["metrics"][0]["views"], 100)

    def test_manual_stage_is_audited_and_allows_free_jump(self):
        self.store.set_stage(self.project, "thumbnail", self.actor)
        project = self.store.project(self.project)
        self.assertEqual(project["stage"], "thumbnail")
        event = self.store.events(self.project)[0]
        detail = json.loads(event["detail_json"])
        self.assertTrue(detail["manual"])
        self.assertTrue(detail["override"])
        self.store.set_stage(self.project, "idea", self.actor)
        self.assertEqual(self.store.project(self.project)["stage"], "idea")

    def test_channel_youtube_id_is_validated_and_unique(self):
        youtube_id = "UC" + "a" * 22
        channel = self.store.save_channel("Analytics One", youtube_channel_id=youtube_id)
        self.assertEqual(self.store.channel(channel)["youtube_channel_id"], youtube_id)
        with self.assertRaises(DomainError):
            self.store.save_channel("Analytics Two", youtube_channel_id=youtube_id)
        with self.assertRaises(DomainError):
            self.store.save_channel("Analytics Three", youtube_channel_id="not-a-channel-id")

    def test_analytics_snapshots_and_channel_scoped_delete(self):
        first = self.store.save_channel("Analytics One", youtube_channel_id="UC" + "a" * 22)
        second = self.store.save_channel("Analytics Two", youtube_channel_id="UC" + "b" * 22)
        self.store.save_channel_analytics_snapshot(first, {"views": 10, "ctr": 0.05}, self.actor)
        self.store.save_channel_analytics_snapshot(second, {"views": 20, "ctr": 0.06}, self.actor)
        self.assertEqual(len(self.store.channel_metric_snapshots(first)), 1)
        removed = self.store.delete_analytics_data(self.actor, self.store.channel(first)["youtube_channel_id"])
        self.assertEqual(removed, 1)
        self.assertEqual(self.store.channel_metric_snapshots(first), [])
        self.assertEqual(len(self.store.channel_metric_snapshots(second)), 1)

    def test_delete_project_snapshots_before_removal(self):
        self.store.delete_project(self.project, self.actor)
        with self.assertRaises(DomainError):
            self.store.project(self.project)
        event = self.store.events()[0]
        self.assertEqual(event["action"], "video_project_deleted")
        self.assertTrue(json.loads(event["detail_json"])["project"]["title"])

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


class AnalyticsParsingTests(unittest.TestCase):
    def test_reach_summary_weights_ctr_by_impressions(self):
        summary = YouTubeAnalyticsClient._reach_summary([
            {"date": date(2026, 11, 20), "impressions": 1000, "ctr_percent": 4.0},
            {"date": date(2026, 11, 21), "impressions": 3000, "ctr_percent": 8.0},
        ])
        self.assertAlmostEqual(summary["ctr"], 0.07)
        self.assertEqual(summary["impressions"], 4000)
        self.assertEqual(summary["ctr_start_date"], "2026-11-20")
        self.assertEqual(summary["ctr_data_through"], "2026-11-21")

    def test_reach_summary_without_impressions_is_empty(self):
        summary = YouTubeAnalyticsClient._reach_summary([])
        self.assertIsNone(summary["ctr"])
        self.assertEqual(summary["impressions"], 0)
        self.assertIsNone(summary["ctr_data_through"])


class DemoSeedTests(unittest.TestCase):
    def test_demo_seed_has_multichannel_hierarchy_and_is_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="hub demo ") as temporary:
            root = Path(temporary)
            store = Store(root / "demo.sqlite3")
            seed(store, root)
            seed(store, root)

            channels = store.channels()
            albums = [album for channel in channels for album in store.albums(channel["id"])]
            projects = store.projects()
            self.assertEqual(len(channels), 3)
            self.assertEqual(len(albums), 6)
            self.assertEqual(len(projects), 12)
            self.assertEqual(sum(album["video_count"] for album in albums), 12)
            self.assertTrue((root / "OUTPUT TỔNG" / "Content Hub" / "Demo Assets" / "demo_thumbnail.png").is_file())


if __name__ == "__main__":
    unittest.main()
