"""Real FFmpeg integration tests. Run: py -m unittest test_flow_loop -v."""
import json
import subprocess
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path

from engine import RenderSettings, find_binary
from flow_loop import FlowLoopEngine, probe_video


class FlowLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ffmpeg, cls.ffprobe = find_binary("ffmpeg"), find_binary("ffprobe")
        if not cls.ffmpeg or not cls.ffprobe:
            raise unittest.SkipTest("FFmpeg/FFprobe required")
        cls.folder = tempfile.TemporaryDirectory(prefix="loop tests tiếng Việt ", dir=Path(__file__).parent)
        cls.root = Path(cls.folder.name)
        cls.clips = []
        for i, fps in enumerate((24, 25)):
            p = cls.root / f"clip {i}.mp4"
            subprocess.run([cls.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                            f"testsrc2=size=320x180:rate={fps}:duration=2",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)], check=True)
            cls.clips.append(str(p))
        cls.settings = RenderSettings(visual_source="Flow Loop", flow_clips=cls.clips,
                                      flow_crossfade=0.4, duration_seconds=6,
                                      flow_music_enabled=False, encoder="CPU (libx264)", output_profile="720p")

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def engine(self):
        return FlowLoopEngine(self.ffmpeg, self.ffprobe)

    def test_single_clip_preview_has_three_exact_cycles(self):
        output = self.root / "preview.mp4"
        report = self.engine().preview(replace(self.settings, flow_clips=self.clips[:1]), output)
        self.assertEqual(report["loop_frames"], 48)
        self.assertEqual(int(probe_video(self.ffprobe, output)["nb_frames"]), 144)
        # Decode frames and prove repeated cycles, including the closing seam, are identical.
        data = subprocess.check_output([self.ffmpeg, "-v", "error", "-i", str(output),
                                        "-vf", "scale=32:18", "-pix_fmt", "gray", "-f", "rawvideo", "-"])
        size = 32*18*48
        self.assertEqual(data[:size], data[size:2*size])
        self.assertEqual(data[:size], data[2*size:])

    def test_multi_clip_export_exact_frames_and_no_audio(self):
        output = self.root / "silent.mp4"
        _, chapters, verify = self.engine().render_project(Path(), [], [], output, self.settings)
        self.assertIsNone(chapters)
        self.assertTrue(verify["frames_ok"])
        self.assertIsNone(verify["audio_codec"])
        report = json.loads((self.root / "silent_loop" / "render_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["loop_frames"], 96)
        self.assertEqual(report["closing_seam"], "last_to_first")
        # Decode whole output; container checks alone do not catch broken concat bitstreams.
        subprocess.run([self.ffmpeg, "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"], check=True)

    def test_music_pipeline_and_chapters(self):
        tracks = []
        for i in range(5):
            p = self.root / f"tone {i}.wav"
            subprocess.run([self.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                            f"sine=frequency={220+i*50}:duration=2", str(p)], check=True)
            tracks.append(p)
        settings = replace(self.settings, flow_music_enabled=True, transition_seconds=0.3,
                           normalization_enabled=True)
        output = self.root / "music.mp4"
        _, chapters, verify = self.engine().render_project(Path(), tracks, tracks, output, settings)
        self.assertTrue(verify["audio_ok"])
        self.assertTrue(chapters.is_file())
        self.assertIn("00:00", chapters.read_text(encoding="utf-8"))
        subprocess.run([self.ffmpeg, "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"], check=True)

    def test_validation_and_source_protection(self):
        engine = self.engine()
        with self.assertRaises(ValueError):
            engine.validate_sources(replace(self.settings, flow_crossfade=1.2), self.root / "other.mp4")
        with self.assertRaises(ValueError):
            engine.validate_sources(replace(self.settings, flow_trim_end=10), self.root / "other.mp4")
        with self.assertRaises(ValueError):
            engine.preview(self.settings, Path(self.clips[0]))
        old = self.root / "existing.mp4"
        old.write_bytes(b"keep existing output")
        with self.assertRaises(ValueError):
            engine.render_project(Path(), [], [], old, replace(self.settings, flow_clips=["missing.mp4"]))
        self.assertEqual(old.read_bytes(), b"keep existing output")

    def test_preset_backward_compatibility(self):
        self.assertEqual(RenderSettings.from_json_dict({"schema_version": 3}).visual_source, "Thumbnail")
        loaded = RenderSettings.from_json_dict(self.settings.to_json_dict())
        self.assertEqual(loaded, self.settings)

    def test_cancel_preserves_existing_output(self):
        output = self.root / "cancelled.mp4"
        output.write_bytes(b"original")
        engine = self.engine()
        errors = []
        def work():
            try:
                engine.preview(self.settings, output)
            except RuntimeError as e:
                errors.append(str(e))
        worker = threading.Thread(target=work)
        worker.start()
        deadline = time.monotonic() + 10
        while engine.current_process is None and worker.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        engine.cancel()
        worker.join(15)
        self.assertFalse(worker.is_alive())
        self.assertTrue(errors)
        self.assertEqual(output.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
