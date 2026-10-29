"""Adapters to existing tools; one persistent, cancellable local render worker."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from store import Store, DomainError, now, uid, fingerprint

def find_workspace():
    candidates = list(Path(__file__).resolve().parents) + list(Path(sys.executable).resolve().parents)
    for candidate in candidates:
        if (candidate / "TOOL Video Flow" / "launcher.py").is_file() and (candidate / "editer").is_dir():
            return candidate
    raise DomainError("Không tìm thấy workspace. Đặt CONTENT HUB cạnh TOOL Video Flow và editer.")

class Adapters:
    def __init__(self, store: Store, workspace: Path):
        self.store, self.workspace = store, Path(workspace).resolve()
        self.output_root = self.workspace / "TOOL Video Flow OUTPUT" / "Content Hub"
        self.editor_dir = self.workspace / "editer" / "TOOL EDIT" / "v3" / "v3"

    def status(self):
        return {"Video Flow": (self.workspace / "TOOL Video Flow" / "launcher.py").is_file(),
                "Tool Edit": (self.editor_dir / "flow_loop.py").is_file(),
                "FFmpeg": (self.editor_dir / "tools" / "ffmpeg.exe").is_file(),
                "FFprobe": (self.editor_dir / "tools" / "ffprobe.exe").is_file()}

    def python_command(self):
        if not getattr(sys, "frozen", False):
            return [sys.executable]
        import shutil
        if shutil.which("py"):
            return ["py", "-3"]
        if shutil.which("python"):
            return ["python"]
        raise DomainError("Mở tool source cần Python; dùng bản EXE editor nếu chưa cài Python.")

    def prepare_handoff(self, project_id, actor):
        project = self.store.project(project_id)
        assets = self.store.assets(project_id, latest=True)
        folder = self.output_root / "Projects" / project_id
        folder.mkdir(parents=True, exist_ok=True)
        bundle = {"schema_version": 1, "project": project, "assets": assets,
                  "instructions": "Chọn đúng input/prompt trong Studio; kết quả cần nhập lại và gắn đúng dự án."}
        (folder / "handoff.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "brief.txt").write_text(
            f"Kênh: {project['channel_name']}\nVideo: {project['title']}\n"
            f"Phong cách: {project['channel_style']}\n\n{project['brief']}\n", encoding="utf-8")
        if str(self.editor_dir) not in sys.path:
            sys.path.insert(0, str(self.editor_dir))
        from engine import RenderSettings
        from flow_loop import make_prompt
        clips = [a["path"] for a in assets if a["kind"] == "clip"]
        images = [a["path"] for a in assets if a["kind"] in ("thumbnail", "reference")]
        channel_music = self.store.channel_music(project["channel_id"])
        settings = RenderSettings(visual_source="Flow Loop", flow_clips=clips,
                                  flow_music_enabled=len(channel_music) >= 5,
                                  channel_profile=project["channel_name"], filter_channel_music=True,
                                  encoder="CPU (libx264)", output_profile="720p", visual_motion="Static")
        output = folder / "editor_output.mp4"
        (folder / "editor_project.json").write_text(json.dumps(
            {"schema_version": 1, "settings": settings.to_json_dict(), "image": images[0] if images else "",
             "music_folder": str(self.workspace / "editer" / "Nhạc jazz"),
             "output": str(output), "first_five": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "flow_prompt.txt").write_text(make_prompt("Custom", "Subtle", project["channel_style"]+". "+project["brief"]), encoding="utf-8")
        with self.store.transaction() as db:
            self.store.event(db, project_id, actor, "handoff_prepared", {"folder": str(folder)})
        return folder

    def launch(self, tool, project_id, actor):
        folder = self.prepare_handoff(project_id, actor)
        if tool == "studio":
            entry = self.workspace / "TOOL Video Flow" / "launcher.py"
            command = self.python_command() + [str(entry)]
        elif tool == "editor":
            entry = self.editor_dir / "dist" / "ToolEdit" / "ToolEdit.exe"
            if entry.is_file():
                command = [str(entry)]
            else:
                entry = self.editor_dir / "app.py"
                command = self.python_command() + [str(entry)]
        else:
            raise DomainError("Tool không hợp lệ.")
        if not entry.is_file():
            raise DomainError(f"Không tìm thấy: {entry}")
        project = self.store.project(project_id)
        env = os.environ.copy()
        env.update({"CONTENT_HUB_DATABASE": str(self.store.path),
                    "CONTENT_HUB_CHANNEL_ID": project["channel_id"],
                    "CONTENT_HUB_CHANNEL_NAME": project["channel_name"],
                    "CONTENT_HUB_PROJECT_ID": project_id,
                    "CONTENT_HUB_HANDOFF": str(folder / "handoff.json")})
        log = (folder / "tool-launch.log").open("a", encoding="utf-8")
        try:
            process = subprocess.Popen(command, cwd=entry.parent, stdout=log, stderr=log,
                                       env=env,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        finally:
            log.close()
        with self.store.transaction() as db:
            self.store.event(db, project_id, actor, "tool_open_requested",
                             {"tool": tool, "pid": process.pid, "note": "Khởi chạy không xác nhận sản xuất hoàn tất."})
        return folder

    def enqueue_render(self, project_id, seconds, resolution, overlap, actor, retry_of=None, music_enabled=False):
        import math
        if not 1 <= seconds <= 43200 or not isinstance(seconds, int):
            raise DomainError("Thời lượng từ 1 giây đến 12 giờ.")
        if resolution not in ("720p", "1080p", "1440p") or not math.isfinite(overlap) or not 0.1 <= overlap <= 3:
            raise DomainError("Độ phân giải hoặc overlap không hợp lệ.")
        assets = self.store.assets(project_id, latest=True)
        clips = [a for a in assets if a["kind"] == "clip"]
        music = [a for a in assets if a["kind"] == "music"] if music_enabled else []
        if music_enabled:
            project = self.store.project(project_id)
            assigned_music = []
            for track in self.store.channel_music(project["channel_id"]):
                info = fingerprint(Path(track["path"]))
                assigned_music.append({"id": track["id"], "kind": "music", "path": info["path"],
                                       "sha256": info["sha256"], "bytes": info["bytes"],
                                       "mtime_ns": info["mtime_ns"], "title": track["title"], "artist": track["artist"]})
            if len(assigned_music) >= 5 or not music:
                music = assigned_music
        if not clips:
            raise DomainError("Chưa nhập clip cho dự án.")
        if music_enabled and len(music) < 5:
            raise DomainError("Engine playlist hiện tại cần ít nhất 5 bài nhạc khác nhau.")
        payload = {"seconds": seconds, "resolution": resolution, "overlap": overlap,
                   "clips": clips, "music": music, "created_by": actor,
                   "project_revision": self.store.project(project_id)["revision"]}
        return self.store.create_job(project_id, payload, actor, retry_of)

    def retry(self, job_id, actor):
        job = self.store.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not job or job["state"] not in ("failed", "cancelled", "interrupted"):
            raise DomainError("Chỉ thử lại tác vụ lỗi, bị hủy hoặc gián đoạn.")
        old = json.loads(job["payload_json"])
        # Fresh snapshot: never silently reuse stale source hashes after user edits.
        return self.enqueue_render(job["project_id"], old["seconds"], old["resolution"], old["overlap"],
                                   actor, retry_of=job_id, music_enabled=bool(old.get("music")))


class RenderWorker:
    def __init__(self, store, adapters):
        self.store, self.adapters = store, adapters
        self.stop_event = threading.Event()
        self.current_id = None
        self.engine = None
        self.thread = None

    def start(self):
        self.store.recover_jobs()
        self.thread = threading.Thread(target=self.run, name="content-hub-render", daemon=True)
        self.thread.start()

    def cancel(self, job_id, actor):
        self.store.cancel_job(job_id, actor)
        if self.current_id == job_id and self.engine:
            self.engine.cancel()

    def shutdown(self):
        self.stop_event.set()
        if self.current_id and self.engine:
            self.engine.cancel()

    def run(self):
        while not self.stop_event.is_set():
            job = self.store.claim_job()
            if job:
                self.execute(job)
            else:
                self.stop_event.wait(0.5)

    def execute(self, job):
        self.current_id = job["id"]
        folder = self.adapters.output_root / "Renders" / job["project_id"] / job["id"]
        folder.mkdir(parents=True, exist_ok=True)
        last = [0.0]
        def progress(pct, message):
            current = time.monotonic()
            if current-last[0] > .5 or pct >= 100:
                self.store.job_progress(job["id"], pct, message)
                last[0] = current
            state = self.store.one("SELECT state FROM jobs WHERE id=?", (job["id"],))["state"]
            if self.stop_event.is_set() or state == "cancelling":
                if self.engine:
                    self.engine.cancel()
        def log(message):
            with (folder / "render.log").open("a", encoding="utf-8") as stream:
                stream.write(now() + " " + message + "\n")
        try:
            if str(self.adapters.editor_dir) not in sys.path:
                sys.path.insert(0, str(self.adapters.editor_dir))
            from engine import RenderSettings, find_binary
            from flow_loop import FlowLoopEngine
            payload = json.loads(job["payload_json"])
            for asset in payload["clips"] + payload["music"]:
                self.store.verify_asset(asset)
            ffmpeg, ffprobe = find_binary("ffmpeg"), find_binary("ffprobe")
            if not ffmpeg or not ffprobe:
                raise DomainError("Thiếu FFmpeg hoặc FFprobe trong editor.")
            self.engine = FlowLoopEngine(ffmpeg, ffprobe, progress, log)
            settings = RenderSettings(visual_source="Flow Loop", flow_clips=[a["path"] for a in payload["clips"]],
                                      duration_seconds=payload["seconds"], flow_crossfade=payload["overlap"],
                                      flow_music_enabled=bool(payload["music"]), encoder="CPU (libx264)",
                                      output_profile=payload["resolution"], visual_motion="Static")
            tracks = [Path(a["path"]) for a in payload["music"]]
            progress(0, "Kiểm tra nguồn và bắt đầu render")
            if self.engine.cancel_event.is_set():
                raise DomainError("Đã hủy trước khi render.")
            output = folder / "final.mp4"
            out, chapters, verify = self.engine.render_project(Path(), tracks, tracks[:5], output, settings)
            progress(99, "Đăng ký phiên bản thành phẩm")
            if self.engine.cancel_event.is_set():
                raise DomainError("Đã hủy; file render nếu có được giữ trong thư mục tác vụ.")
            asset_id = self.store.add_asset(job["project_id"], "final", out, "render-worker", "main",
                                            note=f"Render job {job['id']}")
            self.store.finish_job(job["id"], "succeeded", {"asset_id": asset_id, "output": str(out),
                                  "chapters": str(chapters) if chapters else "", "verification": verify})
        except Exception as error:
            state = self.store.one("SELECT state FROM jobs WHERE id=?", (job["id"],))["state"]
            cancelled = self.stop_event.is_set() or state == "cancelling" or (self.engine and self.engine.cancel_event.is_set())
            log(traceback.format_exc())
            self.store.finish_job(job["id"], "cancelled" if cancelled else "failed", error=str(error))
        finally:
            self.engine = None
            self.current_id = None


class InstanceLock:
    """Only one GUI owns recovery and queue consumption for each database."""
    def __init__(self, path):
        self.stream = open(path, "a+b")
        self.stream.seek(0, 2)
        if not self.stream.tell():
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise DomainError("Content Hub đang mở với database này. Dùng cửa sổ hiện tại.")

    def close(self):
        self.stream.close()
