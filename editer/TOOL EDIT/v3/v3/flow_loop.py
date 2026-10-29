"""Bounded-memory, frame-aligned cyclic ambient video builder."""
from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

from engine import (FPS, RenderEngine, RenderSettings, video_dimensions,
                    ffconcat_escape, no_window_flag, check_nvenc, check_qsv,
                    build_sequence, write_chapters)

STYLES = {
    "Winter / Snow": "gentle snowfall outdoors only; keep indoor areas still",
    "Rainy Cafe / Lofi": "soft rainfall outdoors and small droplets on existing window glass",
    "Autumn / Leaves": "occasional falling leaves outdoors and very gentle movement of existing foliage",
    "Forest / Meditation": "slow thin mist outdoors and slight movement of existing leaves",
    "Fireplace": "gentle flames in the existing fireplace and restrained local firelight",
    "Ocean / Water": "small natural ripples on existing water, without changing the shoreline",
    "Custom": "only the motion explicitly described in the additional instruction",
}


def make_prompt(style: str, intensity: str, instruction: str = "") -> str:
    return (
        "Use the supplied image as the exact visual reference. Create an 8-second ambient animation "
        "with a completely locked camera. Preserve the original composition, perspective, architecture, "
        "furniture, object positions, colors and exposure throughout. "
        f"Animate only {STYLES.get(style, STYLES['Custom'])}. Motion intensity: {intensity.lower()}. "
        "Apply effects only where the reference scene supports them; do not introduce missing objects. "
        "Keep all other regions still. Maintain gentle consistent motion suitable for seamless looping, "
        "with an ending visually compatible with the beginning. No zoom, pan, camera shake, cuts, "
        "new people, text, global lighting changes, fade in or fade to black. "
        "Keep the original 16:9 framing. No soundtrack. "
        + (f"Additional motion instruction: {instruction.strip()}" if instruction.strip() else "")
    ).strip()


def probe_video(ffprobe: str, path: Path) -> dict:
    cp = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,duration,nb_frames,avg_frame_rate:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=no_window_flag(),
    )
    if cp.returncode:
        raise ValueError(f"Không đọc được clip {path.name}: {cp.stderr[-2000:]}")
    data = json.loads(cp.stdout)
    if not data.get("streams"):
        raise ValueError(f"Không có video stream: {path.name}")
    info = data["streams"][0]
    info["duration"] = float(info.get("duration", data.get("format", {}).get("duration", 0)))
    return info


class FlowLoopEngine(RenderEngine):
    def _progress(self, pct: float, msg: str) -> None:
        if getattr(self, "audio_phase", False):
            pct = 30 + max(0, min(55, pct)) * 40 / 55
        super()._progress(pct, msg)

    def _codec(self, settings: RenderSettings) -> list[str]:
        if settings.encoder.lower().startswith("nvidia"):
            return ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19", "-b:v", "0"]
        if settings.encoder.lower().startswith("intel"):
            return ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "25", "-look_ahead", "0"]
        low = settings.output_profile.lower().startswith("720")
        cap = "4M" if low else "8M" if settings.output_profile.startswith("1080") else "16M"
        buffer = "8M" if low else "16M" if settings.output_profile.startswith("1080") else "32M"
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23" if low else "20",
                "-maxrate", cap, "-bufsize", buffer, "-threads", "2"]

    def _cmd(self) -> list[str]:
        return [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "warning",
                "-filter_threads", "1", "-filter_complex_threads", "1"]

    def validate_sources(self, settings: RenderSettings, output: Path) -> list[dict]:
        if not settings.flow_clips:
            raise ValueError("Thêm ít nhất một clip Google Flow.")
        if len(settings.flow_clips) > 24:
            raise ValueError("Mỗi loop hỗ trợ tối đa 24 clip; hãy chia thành các dự án nhỏ hơn.")
        values = [settings.flow_crossfade, settings.flow_trim_start, settings.flow_trim_end]
        if any(not math.isfinite(v) for v in values) or not 0.1 <= settings.flow_crossfade <= 3:
            raise ValueError("Hòa trộn phải từ 0.1 đến 3 giây, các giá trị cắt phải hữu hạn.")
        if min(settings.flow_trim_start, settings.flow_trim_end) < 0:
            raise ValueError("Thời gian cắt đầu/cuối phải >= 0.")
        if not isinstance(settings.duration_seconds, int) or not 1 <= settings.duration_seconds <= 43200:
            raise ValueError("Thời lượng xuất phải từ 1 giây đến 12 giờ.")
        result = []
        for item in settings.flow_clips:
            self._check_cancel()
            path = Path(item).resolve()
            if not path.is_file():
                raise ValueError(f"Không tìm thấy clip: {path}")
            if path == output.resolve():
                raise ValueError("Output không được trùng clip nguồn.")
            info = probe_video(self.ffprobe, path)
            # Padding preserves the entire composition rather than cropping reference objects.
            if abs(info["width"] / info["height"] - 16 / 9) > 0.03:
                self._log(f"Lưu ý: {path.name} không phải 16:9; sẽ thêm viền để giữ nguyên bố cục.")
            frames = math.floor((info["duration"] - settings.flow_trim_start - settings.flow_trim_end) * FPS + 1e-6)
            overlap = round(settings.flow_crossfade * FPS)
            if frames <= 2 * overlap + 1:
                raise ValueError(f"{path.name}: clip sau cắt phải dài hơn hai lần thời gian hòa trộn.")
            result.append({"path": str(path), "frames": frames, "source_duration": info["duration"]})
        return result

    def build_master(self, settings: RenderSettings, output: Path, temp: Path) -> dict:
        """Each block is clip[d:L-d] followed by tail -> next head. Final wraps to first."""
        sources = self.validate_sources(settings, output)
        for prefix, checker in [("nvidia", check_nvenc), ("intel", check_qsv)]:
            if settings.encoder.lower().startswith(prefix):
                ok, message = checker(self.ffmpeg)
                if not ok:
                    raise RuntimeError(message + "\nChọn CPU trong tab Output để thử lại.")
        width, height = video_dimensions(settings)
        overlap = round(settings.flow_crossfade * FPS)
        d = overlap / FPS
        normalized = []
        for i, source in enumerate(sources):
            dest = temp / f"source_{i:03d}.mp4"
            filters = (f"trim=start={settings.flow_trim_start}:duration={source['frames']/FPS},"
                       f"setpts=PTS-STARTPTS,fps={FPS},"
                       f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                       f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p")
            self._run_with_ffmpeg_progress(
                self._cmd() + ["-i", source["path"], "-map", "0:v:0", "-an", "-vf", filters,
                               "-frames:v", str(source["frames"])] + self._codec(settings) + [str(dest)],
                source["frames"] / FPS, 2 + 13*i/len(sources), 2 + 13*(i+1)/len(sources),
                f"Chuẩn hóa clip {i+1}/{len(sources)}")
            actual = probe_video(self.ffprobe, dest)
            source["frames"] = int(actual["nb_frames"])
            if source["frames"] <= 2 * overlap + 1:
                raise ValueError("Clip thực tế quá ngắn sau chuẩn hóa.")
            normalized.append(dest)
        blocks = []
        for i, source in enumerate(sources):
            frames = source["frames"]
            count = frames - overlap
            offset = (frames - 2 * overlap) / FPS
            next_i = (i + 1) % len(sources)
            graph = (
                f"[0:v]trim=start_frame={overlap}:end_frame={frames},setpts=PTS-STARTPTS[a];"
                f"[1:v]trim=end_frame={overlap},setpts=PTS-STARTPTS[b];"
                f"[a][b]xfade=transition=fade:duration={d}:offset={offset},"
                "format=yuv420p[v]"
            )
            block = temp / f"block_{i:03d}.mp4"
            self._run_with_ffmpeg_progress(
                self._cmd() + ["-i", str(normalized[i]), "-i", str(normalized[next_i]),
                               "-filter_complex", graph, "-map", "[v]", "-an", "-frames:v", str(count)]
                + self._codec(settings) + [str(block)], count/FPS,
                15 + 15*i/len(sources), 15 + 15*(i+1)/len(sources),
                f"Nối {i+1} → {next_i+1} (kể cả cuối → đầu)")
            blocks.append(block)
        concat = temp / "blocks.ffconcat"
        concat.write_text("ffconcat version 1.0\n" + "".join(
            f"file '{ffconcat_escape(p)}'\n" for p in blocks), encoding="utf-8")
        self._run_simple(self._cmd() + ["-f", "concat", "-safe", "0", "-i", str(concat),
                                       "-map", "0:v:0", "-c:v", "copy", "-an", "-movflags", "+faststart",
                                       str(output)], "Tạo loop master")
        total_frames = sum(s["frames"] - overlap for s in sources)
        master_info = probe_video(self.ffprobe, output)
        if int(master_info["nb_frames"]) != total_frames:
            raise RuntimeError("Loop master không đủ số khung hình dự kiến.")
        return {"sources": sources, "loop_frames": total_frames, "loop_seconds": total_frames/FPS,
                "overlap_seconds": d, "closing_seam": "last_to_first", "fps": FPS}

    def preview(self, settings: RenderSettings, output: Path) -> dict:
        self.cancel_event.clear()
        output.parent.mkdir(parents=True, exist_ok=True)
        self.validate_sources(settings, output)
        with tempfile.TemporaryDirectory(prefix="flow_preview_", dir=output.parent) as folder:
            temp = Path(folder)
            master = temp / "master.mp4"
            report = self.build_master(settings, master, temp)
            preview = temp / "preview.mp4"
            self._run_with_ffmpeg_progress(
                self._cmd() + ["-stream_loop", "2", "-i", str(master), "-map", "0:v:0",
                               "-an", "-c:v", "copy", "-frames:v", str(report["loop_frames"]*3),
                               "-movflags", "+faststart", str(preview)],
                report["loop_seconds"]*3, 30, 99, "Xuất preview ba vòng")
            self._check_cancel()
            os.replace(preview, output)
        self._progress(100, "Preview ba vòng đã sẵn sàng.")
        return report

    def render_video(self, image: Path, final_audio: Path | None, output: Path,
                     settings: RenderSettings) -> None:
        cmd = self._cmd() + ["-stream_loop", "-1", "-i", str(self.master_path)]
        if final_audio:
            cmd += ["-i", str(final_audio)]
        cmd += ["-map", "0:v:0", "-c:v", "copy", "-frames:v", str(settings.duration_seconds*FPS)]
        if final_audio:
            cmd += ["-map", "1:a:0", "-c:a", "copy"]
        else:
            cmd += ["-an"]
        cmd += ["-t", str(settings.duration_seconds), "-movflags", "+faststart", str(output)]
        self._run_with_ffmpeg_progress(cmd, settings.duration_seconds, 70, 99, "Lặp master và ghép âm thanh")

    def verify_output(self, output: Path, target_seconds: int, settings: RenderSettings) -> dict:
        result = super().verify_output(output, target_seconds, settings)
        result["audio_ok"] = bool(result["audio_codec"]) == settings.flow_music_enabled
        result["duration_ok"] = abs(result["duration"] - target_seconds) <= 0.08
        info = probe_video(self.ffprobe, output)
        result["frames_ok"] = int(info.get("nb_frames", 0)) == target_seconds*FPS
        if not all(result[key] for key in ("duration_ok", "resolution_ok", "audio_ok", "frames_ok")):
            raise RuntimeError(f"Output chưa đạt kiểm tra: {result}")
        return result

    def render_project(self, image: Path, tracks: list[Path], first_five: list[Path],
                       output: Path, settings: RenderSettings) -> tuple[Path, Path | None, dict]:
        self.cancel_event.clear()
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        self.validate_sources(settings, output)
        protected = [Path(p).resolve() for p in settings.flow_clips] + [p.resolve() for p in tracks]
        if output in protected or (image.is_file() and output == image.resolve()):
            raise ValueError("Output không được trùng file nguồn.")
        chapters = None
        with tempfile.TemporaryDirectory(prefix="flow_render_", dir=output.parent) as folder:
            temp = Path(folder)
            self.master_path = temp / "master.mp4"
            report = self.build_master(settings, self.master_path, temp)
            staged = temp / "final.mp4"
            if settings.flow_music_enabled:
                # Reuse audio methods without resetting cancellation or repeating the GPU test.
                self.audio_phase = True
                try:
                    durations = self.probe_durations(tracks)
                    sequence, starts, _ = build_sequence(
                        tracks, first_five, durations, settings.duration_seconds,
                        settings.transition_mode, settings.transition_seconds, settings.random_seed)
                    staged_chapters = write_chapters(staged, sequence, starts, settings.duration_seconds)
                    unique = list(dict.fromkeys(sequence))
                    processed = self.preprocess_tracks(unique, durations, settings, temp)
                    audio = self.build_final_audio(sequence, processed, settings, temp)
                finally:
                    self.audio_phase = False
                self.render_video(image, audio, staged, settings)
                verify = self.verify_output(staged, settings.duration_seconds, settings)
                chapters = output.with_name(output.stem + "_chapters.txt")
            else:
                self.render_video(image, None, staged, settings)
                verify = self.verify_output(staged, settings.duration_seconds, settings)
            self._check_cancel()
            os.replace(staged, output)
            if chapters:
                os.replace(staged_chapters, chapters)
            assets = output.with_name(output.stem + "_loop")
            assets.mkdir(exist_ok=True)
            os.replace(self.master_path, assets / "loop_master.mp4")
            report.update({"settings": settings.to_json_dict(), "output": str(output),
                           "reference_image": str(image) if image.is_file() else "",
                           "suggested_prompt": make_prompt(settings.flow_style, settings.flow_intensity, settings.flow_instruction),
                           "verification": verify,
                           "visual_review": "Review three cycles; crossfade cannot repair camera drift or scene morphing."})
            (assets / "render_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self._progress(100, "Hoàn tất và đã kiểm tra video.")
        return output, chapters, verify
