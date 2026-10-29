"""Render a real imported Flow clip without modifying its source."""
import argparse
import json
import sys
from pathlib import Path
from engine import RenderSettings, find_binary
from flow_loop import FlowLoopEngine

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--seconds", type=int, default=3600)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    output_root = root / "TOOL Video Flow OUTPUT"
    source = args.source or sorted((output_root / "Video").rglob("*.mp4"))[-1]
    folder = output_root / "Editor" / "demo_flow"
    folder.mkdir(parents=True, exist_ok=True)
    settings = RenderSettings(visual_source="Flow Loop", flow_clips=[str(source)],
                              flow_music_enabled=False, encoder="CPU (libx264)",
                              output_profile="720p", duration_seconds=args.seconds)
    engine = FlowLoopEngine(find_binary("ffmpeg"), find_binary("ffprobe"), log_cb=print)
    preview = folder / "flow_preview_3_cycles.mp4"
    engine.preview(settings, preview)
    output = folder / f"flow_demo_{args.seconds}s.mp4"
    _, _, verify = engine.render_project(Path(), [], [], output, settings)
    project = {"schema_version": 1, "settings": settings.to_json_dict(),
               "image": "", "music_folder": "", "output": str(output), "first_five": []}
    (folder / "demo_project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"preview": str(preview), "output": str(output), "verify": verify}, ensure_ascii=False))
