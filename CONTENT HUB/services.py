"""Adapters to the existing research, music and Flow tools."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from store import Store, DomainError


def find_workspace():
    candidates = list(Path(__file__).resolve().parents) + list(Path(sys.executable).resolve().parents)
    for candidate in candidates:
        if (candidate / "TOOL Video Flow" / "launcher.py").is_file() and (candidate / "editer").is_dir():
            return candidate
    raise DomainError("Không tìm thấy workspace. Đặt CONTENT HUB cạnh TOOL Video Flow và editer.")


class Adapters:
    def __init__(self, store: Store, workspace: Path):
        self.store, self.workspace = store, Path(workspace).resolve()
        self.output_root = self.workspace / "OUTPUT TỔNG" / "Content Hub"

    def status(self):
        return {"NCTT": (self.workspace / "TOOL NCTT" / "app.py").is_file(),
                "Music Manager": (self.workspace / "editer" / "Nhạc jazz" / "Music_Manager" / "app.py").is_file()}

    def python_command(self):
        if not getattr(sys, "frozen", False):
            return [sys.executable]
        import shutil
        if shutil.which("py"):
            return ["py", "-3"]
        if shutil.which("python"):
            return ["python"]
        raise DomainError("Mở tool source cần Python; hãy cài Python 3.10+.")

    def prepare_handoff(self, project_id, actor):
        project = self.store.project(project_id)
        assets = self.store.assets(project_id, latest=True)
        channel_assets = self.store.channel_assets(project["channel_id"])
        channel_latest = {}
        for asset in channel_assets:
            key = (asset["kind"], asset["slot"])
            if key not in channel_latest or asset["version"] > channel_latest[key]["version"]:
                channel_latest[key] = asset
        assets.extend(channel_latest.values())
        folder = self.output_root / "Projects" / project_id
        folder.mkdir(parents=True, exist_ok=True)
        bundle = {"schema_version": 3, "project": project, "assets": assets,
                  "instructions": "Mỗi dự án là một video/mix trong album (nếu có). Dùng Google Flow Agent trên website; nhập kết quả về đúng video/mix."}
        (folder / "handoff.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "brief.txt").write_text(
            f"Kênh: {project['channel_name']}\nAlbum/playlist: {project.get('album_name') or 'Chưa gắn'}\n"
            f"Video/mix: {project['title']}\nPhong cách: {project['channel_style']}\n\n"
            f"Brief album:\n{project.get('album_brief') or '(không có)'}\n\n"
            f"Brief video/mix:\n{project['brief']}\n", encoding="utf-8")
        flow_brief = " ".join(
            text for value in (project.get("album_brief"), project.get("brief"))
            if (text := str(value or "").strip())
        )
        channel_style = str(project.get("channel_style") or "").strip()
        prompt_context = ". ".join(part for part in (channel_style, flow_brief) if part)
        image_hint = next((a["path"] for a in assets if a["kind"] in ("thumbnail", "reference")), "")
        (folder / "flow_prompt.txt").write_text(
            "Tạo video/mix cho kênh YouTube với phong cách hình ảnh và âm thanh nhất quán.\n"
            f"Kênh: {project['channel_name']}\n"
            f"Video/mix: {project['title']}\n"
            f"Bối cảnh: {prompt_context or '(không có)'}\n"
            "Ưu tiên hình ảnh tĩnh hoặc chuyển động rất nhẹ, vòng lặp mượt, không chữ trong ảnh.\n"
            + (f"Ảnh tham chiếu: {image_hint}\n" if image_hint else ""),
            encoding="utf-8")
        with self.store.transaction() as db:
            self.store.event(db, project_id, actor, "handoff_prepared", {"folder": str(folder)})
        return folder

    def launch(self, tool, project_id, actor):
        folder = self.prepare_handoff(project_id, actor)
        if tool == "studio":
            entry = self.workspace / "TOOL NCTT" / "app.py"
            command = self.python_command() + [str(entry), "--research-only"]
        elif tool == "music":
            entry = self.workspace / "editer" / "Nhạc jazz" / "Music_Manager" / "app.py"
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
        if project.get("album_id"):
            env["CONTENT_HUB_ALBUM_ID"] = project["album_id"]
        log = (folder / "tool-launch.log").open("a", encoding="utf-8")
        try:
            process = subprocess.Popen(command, cwd=entry.parent, stdout=log, stderr=log,
                                       env=env,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        finally:
            log.close()
        with self.store.transaction() as db:
            self.store.event(db, project_id, actor, "tool_open_requested",
                             {"tool": tool, "pid": process.pid,
                              "note": "Khởi chạy không xác nhận sản xuất hoàn tất."})
        return folder


class InstanceLock:
    """Only one GUI owns a database at a time."""
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
