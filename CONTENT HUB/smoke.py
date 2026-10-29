"""Release smoke: isolated DB + synthetic media; no external AI service."""
import json
import subprocess
from pathlib import Path
from store import Store, uid
from services import Adapters, RenderWorker

def run(workspace, report_path):
    folder = workspace / "CONTENT HUB" / "data" / "release_checks" / uid()
    folder.mkdir(parents=True)
    store = Store(folder / "smoke.sqlite3")
    adapters = Adapters(store, workspace)
    from engine import find_binary
    ffmpeg = find_binary("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Packaged FFmpeg missing")
    clip = folder / "synthetic.mp4"
    subprocess.run([ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=320x180:rate=24:duration=2", "-c:v", "libx264", str(clip)],
                   check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    channel = store.save_channel("RELEASE TEST")
    pid = store.create_project(channel, "Synthetic render", brief="Local release verification")
    brief = folder / "research.txt"
    brief.write_text("Synthetic local fixture", encoding="utf-8")
    image = folder / "thumbnail.jpg"
    subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(clip), "-frames:v", "1", str(image)],
                   check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    for kind, path in [("research", brief), ("thumbnail", image), ("clip", clip)]:
        store.add_asset(pid, kind, path, "release-check")
    for _ in range(4):
        project = store.project(pid)
        store.advance(pid, project["revision"], "release-check")
    job_id = adapters.enqueue_render(pid, 6, "720p", .4, "release-check")
    worker = RenderWorker(store, adapters)
    worker.execute(store.claim_job())
    job = store.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    result = {"state": job["state"], "error": job["error"], "result": json.loads(job["result_json"]),
              "database": str(store.path), "ffmpeg": ffmpeg}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if job["state"] != "succeeded":
        raise RuntimeError(job["error"])
