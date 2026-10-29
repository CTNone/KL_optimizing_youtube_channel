from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Callable, Optional

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

FPS = 30
AUDIO_RATE = 48000
AUDIO_BITRATE = "320k"

ProgressCallback = Callable[[float, str], None]
LogCallback = Callable[[str], None]


@dataclass
class RenderSettings:
    duration_seconds: int = 3600
    normalization_enabled: bool = True
    loudness_target: float = -14.0
    transition_mode: str = "Crossfade"
    transition_seconds: float = 2.0
    visual_motion: str = "Slow Zoom"
    overlay_path: str = ""
    overlay_mode: str = "Screen"
    overlay_opacity: float = 0.45
    encoder: str = "CPU (libx264)"
    output_profile: str = "1440p — Chất lượng cao"
    random_seed: int = 123456
    visual_source: str = "Thumbnail"
    flow_clips: list[str] = field(default_factory=list)
    flow_crossfade: float = 0.8
    flow_trim_start: float = 0.0
    flow_trim_end: float = 0.0
    flow_music_enabled: bool = True
    flow_style: str = "Winter / Snow"
    flow_intensity: str = "Subtle"
    flow_instruction: str = ""
    channel_profile: str = "HEARTHLUNE"
    filter_channel_music: bool = False

    def to_json_dict(self) -> dict:
        data = asdict(self)
        data["schema_version"] = 4
        return data

    @classmethod
    def from_json_dict(cls, data: dict) -> "RenderSettings":
        return cls(
            duration_seconds=int(data.get("duration_seconds", 3600)),
            normalization_enabled=bool(data.get("normalization_enabled", True)),
            loudness_target=float(data.get("loudness_target", -14.0)),
            transition_mode=str(data.get("transition_mode", "Crossfade")),
            transition_seconds=float(data.get("transition_seconds", 2.0)),
            visual_motion=str(data.get("visual_motion", "Slow Zoom")),
            overlay_path=str(data.get("overlay_path", "")),
            overlay_mode=str(data.get("overlay_mode", "Screen")),
            overlay_opacity=float(data.get("overlay_opacity", 0.45)),
            encoder=str(data.get("encoder", "CPU (libx264)")),
            output_profile=str(data.get("output_profile", "1440p — Chất lượng cao")),
            random_seed=int(data.get("random_seed", 123456)),
            visual_source=str(data.get("visual_source", "Thumbnail")),
            flow_clips=list(data.get("flow_clips", [])),
            flow_crossfade=float(data.get("flow_crossfade", 0.8)),
            flow_trim_start=float(data.get("flow_trim_start", 0)),
            flow_trim_end=float(data.get("flow_trim_end", 0)),
            flow_music_enabled=bool(data.get("flow_music_enabled", True)),
            flow_style=str(data.get("flow_style", "Winter / Snow")),
            flow_intensity=str(data.get("flow_intensity", "Subtle")),
            flow_instruction=str(data.get("flow_instruction", "")),
            channel_profile=str(data.get("channel_profile", "HEARTHLUNE")),
            filter_channel_music=bool(data.get("filter_channel_music", False)),
        )


def video_dimensions(settings: RenderSettings) -> tuple[int, int]:
    """Return a conservative output size chosen by the user."""
    profile = settings.output_profile.lower()
    if profile.startswith("720"):
        return 1280, 720
    if profile.startswith("1080"):
        return 1920, 1080
    return 2560, 1440


def resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def no_window_flag() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def find_binary(name: str) -> Optional[str]:
    exe = f"{name}.exe" if os.name == "nt" else name
    candidates = [
        resource_path("tools", exe),
        Path(__file__).resolve().parent / "tools" / exe,
    ]
    for p in candidates:
        if p.exists():
            return str(p)

    found = shutil.which(name)
    return found


def scan_audio_files(folder: Path) -> list[Path]:
    tracks = [
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS
    ]
    tracks.sort(key=lambda p: (p.name.lower(), str(p).lower()))
    return tracks


def pretty_track_name(path: Path) -> str:
    name = path.stem.replace("_", " ").strip()
    return re.sub(r"\s+", " ", name)


def fmt_time(seconds: float, always_hours: bool = False) -> str:
    total = max(0, int(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h or always_hours:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def ffconcat_escape(path: Path) -> str:
    s = str(path.resolve()).replace("\\", "/")
    return s.replace("'", "'\\''")


def get_duration(ffprobe: str, path: Path) -> float:
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    cp = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=no_window_flag(),
    )
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or f"Không đọc được thời lượng: {path}")
    try:
        return float(cp.stdout.strip())
    except ValueError:
        raise RuntimeError(f"FFprobe trả về duration không hợp lệ: {path}")


def build_sequence(
    tracks: list[Path],
    first_five: list[Path],
    durations: dict[Path, float],
    target_seconds: int,
    transition_mode: str,
    transition_seconds: float,
    seed: int,
) -> tuple[list[Path], list[float], int]:
    """Return sequence, chapter-start seconds, number of cycles.

    Playlist behavior:
    - the selected first five tracks always lead the playlist
    - all remaining tracks are shuffled once from ``seed``
    - that complete playlist is repeated unchanged until target duration is covered
    """
    if len(first_five) != 5 or len(set(first_five)) != 5:
        raise ValueError("Cần đúng 5 bài đầu tiên và không được trùng nhau.")

    first_set = {p.resolve() for p in first_five}
    remaining_base = [p for p in tracks if p.resolve() not in first_set]
    rng = random.Random(seed)
    remaining = list(remaining_base)
    rng.shuffle(remaining)
    playlist_cycle = list(first_five) + remaining

    is_crossfade = transition_mode.lower() == "crossfade" and transition_seconds > 0

    if is_crossfade:
        too_short = [p for p in tracks if durations[p] <= transition_seconds + 0.25]
        if too_short:
            names = ", ".join(p.name for p in too_short[:5])
            raise ValueError(
                "Crossfade dài hơn hoặc gần bằng duration của một số track. "
                f"Hãy giảm crossfade. Ví dụ: {names}"
            )

    sequence: list[Path] = []
    starts: list[float] = []
    cycles = 0
    current_end = 0.0

    while current_end < target_seconds:
        if not playlist_cycle:
            break

        cycles += 1
        for p in playlist_cycle:
            if not sequence:
                start = 0.0
            else:
                prev = sequence[-1]
                prev_start = starts[-1]
                overlap = transition_seconds if is_crossfade else 0.0
                start = prev_start + durations[prev] - overlap

            sequence.append(p)
            starts.append(start)
            current_end = start + durations[p]
            if current_end >= target_seconds:
                break

    if not sequence:
        raise ValueError("Không tạo được playlist.")

    return sequence, starts, cycles


def write_chapters(
    output_video: Path,
    sequence: list[Path],
    starts: list[float],
    target_seconds: int,
) -> Path:
    chapter_path = output_video.with_name(output_video.stem + "_chapters.txt")
    lines = []
    for p, start in zip(sequence, starts):
        if start >= target_seconds:
            break
        lines.append(f"{fmt_time(start)} {pretty_track_name(p)}")
    chapter_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return chapter_path


def save_preset(path: Path, settings: RenderSettings) -> None:
    path.write_text(
        json.dumps(settings.to_json_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_preset(path: Path) -> RenderSettings:
    data = json.loads(path.read_text(encoding="utf-8"))
    return RenderSettings.from_json_dict(data)


def check_nvenc(ffmpeg: str) -> tuple[bool, str]:
    """Actual one-frame encode test, not just checking encoder name."""
    null_sink = "NUL" if os.name == "nt" else "/dev/null"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-f", "lavfi",
        "-i", "color=c=black:s=128x128:r=1:d=1",
        "-frames:v", "1",
        "-c:v", "h264_nvenc",
        "-f", "null",
        null_sink,
    ]
    cp = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=no_window_flag(),
    )
    if cp.returncode == 0:
        return True, "NVENC hoạt động: FFmpeg đã encode thử thành công 1 frame."
    msg = cp.stderr.strip() or "FFmpeg không thể khởi tạo h264_nvenc."
    return False, msg


def check_qsv(ffmpeg: str) -> tuple[bool, str]:
    """Actual Intel Quick Sync test; encoder listing alone is insufficient."""
    null_sink = "NUL" if os.name == "nt" else "/dev/null"
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=black:s=128x128:r=1:d=1",
        "-frames:v", "1", "-c:v", "h264_qsv", "-f", "null", null_sink,
    ]
    cp = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", creationflags=no_window_flag(),
    )
    if cp.returncode == 0:
        return True, "Intel Quick Sync hoạt động: FFmpeg đã encode thử thành công 1 frame."
    msg = cp.stderr.strip() or "FFmpeg không thể khởi tạo Intel Quick Sync (h264_qsv)."
    return False, msg


class RenderEngine:
    def __init__(
        self,
        ffmpeg: str,
        ffprobe: str,
        progress_cb: Optional[ProgressCallback] = None,
        log_cb: Optional[LogCallback] = None,
    ):
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.progress_cb = progress_cb or (lambda pct, msg: None)
        self.log_cb = log_cb or (lambda msg: None)
        self.cancel_event = threading.Event()
        self.current_process: Optional[subprocess.Popen] = None

    def cancel(self) -> None:
        self.cancel_event.set()
        p = self.current_process
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass

    def _check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise RuntimeError("Đã hủy theo yêu cầu.")

    def _log(self, msg: str) -> None:
        self.log_cb(msg)

    def _progress(self, pct: float, msg: str) -> None:
        self.progress_cb(max(0.0, min(100.0, pct)), msg)

    def probe_durations(self, tracks: list[Path]) -> dict[Path, float]:
        durations: dict[Path, float] = {}
        total = max(1, len(tracks))
        for i, p in enumerate(tracks, 1):
            self._check_cancel()
            durations[p] = get_duration(self.ffprobe, p)
            self._progress(2 + 8 * i / total, f"Đọc duration {i}/{total}: {p.name}")
        return durations

    def _run_simple(self, cmd: list[str], purpose: str) -> None:
        self._check_cancel()
        self.current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=no_window_flag(),
        )
        stdout, stderr = self.current_process.communicate()
        rc = self.current_process.returncode
        self.current_process = None
        self._check_cancel()
        if rc != 0:
            detail = (stderr or stdout or "").strip()
            raise RuntimeError(f"{purpose} thất bại.\n\n{detail[-5000:]}")

    def _run_with_ffmpeg_progress(
        self,
        cmd: list[str],
        duration_seconds: float,
        pct_start: float,
        pct_end: float,
        label: str,
    ) -> None:
        self._check_cancel()
        full_cmd = list(cmd)
        # Insert global progress output before final output path.
        full_cmd[-1:-1] = ["-progress", "pipe:1", "-nostats"]

        self.current_process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=no_window_flag(),
        )

        stderr_lines: list[str] = []

        def read_stderr():
            if not self.current_process or not self.current_process.stderr:
                return
            for line in self.current_process.stderr:
                line = line.rstrip()
                if line:
                    stderr_lines.append(line)
                    if len(stderr_lines) > 80:
                        stderr_lines.pop(0)

        err_thread = threading.Thread(target=read_stderr, daemon=True)
        err_thread.start()

        if self.current_process.stdout:
            for line in self.current_process.stdout:
                if self.cancel_event.is_set():
                    try:
                        self.current_process.terminate()
                    except Exception:
                        pass
                    break

                line = line.strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                seconds = None

                if key in ("out_time_us", "out_time_ms"):
                    try:
                        seconds = float(value) / 1_000_000.0
                    except ValueError:
                        pass
                elif key == "out_time":
                    try:
                        hh, mm, ss = value.split(":")
                        seconds = int(hh) * 3600 + int(mm) * 60 + float(ss)
                    except Exception:
                        pass

                if seconds is not None and duration_seconds > 0:
                    ratio = max(0.0, min(1.0, seconds / duration_seconds))
                    pct = pct_start + (pct_end - pct_start) * ratio
                    self._progress(
                        pct,
                        f"{label}: {ratio * 100:5.1f}% "
                        f"({fmt_time(seconds, True)} / {fmt_time(duration_seconds, True)})",
                    )

        rc = self.current_process.wait()
        err_thread.join(timeout=1.0)
        if self.current_process.stdout:
            self.current_process.stdout.close()
        if self.current_process.stderr:
            self.current_process.stderr.close()
        self.current_process = None
        self._check_cancel()

        if rc != 0:
            detail = "\n".join(stderr_lines[-40:])
            raise RuntimeError(f"{label} thất bại.\n\n{detail[-5000:]}")

    def preprocess_tracks(
        self,
        unique_tracks: list[Path],
        durations: dict[Path, float],
        settings: RenderSettings,
        temp_dir: Path,
    ) -> dict[Path, Path]:
        """Normalize / resample each used source exactly once into short-path FLAC."""
        processed: dict[Path, Path] = {}
        total = max(1, len(unique_tracks))

        for i, src in enumerate(unique_tracks):
            self._check_cancel()
            dst = temp_dir / f"t{i:03d}.flac"

            filters = []
            if settings.normalization_enabled:
                target = settings.loudness_target
                filters.append(
                    f"loudnorm=I={target}:LRA=11:TP=-1.5"
                )
            filters.append("aresample=48000")
            # loudnorm can emit oversized frames in newer FFmpeg builds.
            # FLAC block sizes must remain <= 65535 samples.
            filters.append("asetnsamples=n=4608:p=0")

            if (
                settings.transition_mode.lower() == "fade"
                and settings.transition_seconds > 0
            ):
                d = settings.transition_seconds
                dur = durations[src]
                if dur <= d * 2 + 0.5:
                    raise ValueError(
                        f"Track quá ngắn để fade {d:g}s ở cả đầu/cuối: {src.name}"
                    )
                filters.append(f"afade=t=in:st=0:d={d:g}")
                filters.append(f"afade=t=out:st={max(0, dur-d):.6f}:d={d:g}")

            cmd = [
                self.ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel", "error",
                "-i", str(src),
                "-vn",
                "-af", ",".join(filters),
                "-ar", str(AUDIO_RATE),
                "-ac", "2",
                "-c:a", "flac",
                "-sample_fmt", "s16",
                str(dst),
            ]
            self._run_simple(cmd, f"Chuẩn hóa audio: {src.name}")
            processed[src] = dst

            pct = 10 + 25 * (i + 1) / total
            mode = (
                f"{settings.loudness_target:g} LUFS"
                if settings.normalization_enabled else "Normalization OFF"
            )
            self._progress(pct, f"Audio {i+1}/{total}: {src.name} — {mode}")

        return processed

    def build_final_audio(
        self,
        sequence: list[Path],
        processed: dict[Path, Path],
        settings: RenderSettings,
        temp_dir: Path,
    ) -> Path:
        self._check_cancel()
        out_audio = temp_dir / "final_audio.m4a"
        target = settings.duration_seconds

        if (
            settings.transition_mode.lower() == "crossfade"
            and settings.transition_seconds > 0
            and len(sequence) > 1
        ):
            cmd = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "warning"]
            for p in sequence:
                cmd += ["-i", str(processed[p])]

            d = settings.transition_seconds
            lines = []
            prev_label = "[0:a]"
            for i in range(1, len(sequence)):
                out_label = f"[a{i}]"
                lines.append(
                    f"{prev_label}[{i}:a]"
                    f"acrossfade=d={d:g}:c1=tri:c2=tri{out_label}"
                )
                prev_label = out_label

            script = temp_dir / "acrossfade_filter.txt"
            script.write_text(";\n".join(lines), encoding="utf-8")

            # FFmpeg 9 removed the legacy ``-filter_complex_script`` option.
            # Prefixing an option with ``-/`` tells modern FFmpeg to read its
            # value from a file, keeping long playlist graphs off the command line.
            cmd += [
                "-/filter_complex", str(script),
                "-map", prev_label,
                "-t", str(target),
                "-c:a", "aac",
                "-b:a", AUDIO_BITRATE,
                "-ar", str(AUDIO_RATE),
                "-ac", "2",
                str(out_audio),
            ]
        else:
            concat_file = temp_dir / "playlist.ffconcat"
            with concat_file.open("w", encoding="utf-8", newline="\n") as f:
                f.write("ffconcat version 1.0\n")
                for p in sequence:
                    f.write(f"file '{ffconcat_escape(processed[p])}'\n")

            cmd = [
                self.ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel", "warning",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-t", str(target),
                "-c:a", "aac",
                "-b:a", AUDIO_BITRATE,
                "-ar", str(AUDIO_RATE),
                "-ac", "2",
                str(out_audio),
            ]

        self._run_with_ffmpeg_progress(
            cmd,
            duration_seconds=target,
            pct_start=35,
            pct_end=55,
            label="Ghép audio",
        )
        return out_audio

    def _base_visual_filter(self, motion: str, width: int, height: int) -> str:
        # Work on an overscaled 16:9 canvas so slow motion has crop headroom.
        pre_width = (width * 11 // 10) // 2 * 2
        pre_height = (height * 11 // 10) // 2 * 2
        pre = (
            f"scale={pre_width}:{pre_height}:force_original_aspect_ratio=increase,"
            f"crop={pre_width}:{pre_height},setsar=1"
        )
        motion_key = motion.lower().strip()

        if motion_key == "static":
            return (
                f"{pre},scale={width}:{height},fps={FPS},"
                "setpts=PTS-STARTPTS"
            )

        if motion_key == "slow zoom":
            return (
                f"{pre},zoompan="
                "z='1.0175+0.0175*sin(on/900)':"
                "x='iw/2-(iw/zoom/2)':"
                "y='ih/2-(ih/zoom/2)':"
                f"d=1:s={width}x{height}:fps={FPS},"
                "setpts=PTS-STARTPTS"
            )

        if motion_key == "pan left-right":
            return (
                f"{pre},zoompan="
                "z='1.045':"
                "x='(iw-iw/zoom)*(0.5+0.5*sin(on/1800))':"
                "y='ih/2-(ih/zoom/2)':"
                f"d=1:s={width}x{height}:fps={FPS},"
                "setpts=PTS-STARTPTS"
            )

        if motion_key == "pan up-down":
            return (
                f"{pre},zoompan="
                "z='1.045':"
                "x='iw/2-(iw/zoom/2)':"
                "y='(ih-ih/zoom)*(0.5+0.5*sin(on/1800))':"
                f"d=1:s={width}x{height}:fps={FPS},"
                "setpts=PTS-STARTPTS"
            )

        # Cinematic Drift
        return (
            f"{pre},zoompan="
            "z='1.035+0.008*sin(on/2100)':"
            "x='(iw-iw/zoom)*(0.5+0.42*sin(on/1700))':"
            "y='(ih-ih/zoom)*(0.5+0.35*cos(on/2300))':"
            f"d=1:s={width}x{height}:fps={FPS},"
            "setpts=PTS-STARTPTS"
        )

    def _visual_filter_complex(self, settings: RenderSettings, has_overlay: bool) -> str:
        width, height = video_dimensions(settings)
        base = self._base_visual_filter(settings.visual_motion, width, height)
        if not has_overlay:
            return f"[0:v]{base},format=yuv420p[vout]"

        opacity = max(0.0, min(1.0, settings.overlay_opacity))
        ov_prepare = (
            f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},fps={FPS},setpts=PTS-STARTPTS"
        )

        if settings.overlay_mode.lower() == "alpha":
            return (
                f"[0:v]{base}[base];"
                f"{ov_prepare},format=rgba,colorchannelmixer=aa={opacity:.4f}[ov];"
                "[base][ov]overlay=0:0:shortest=0,format=yuv420p[vout]"
            )

        # Screen is ideal for snow/rain/light particles on a dark/black background.
        return (
            f"[0:v]{base},format=gbrp[base];"
            f"{ov_prepare},format=gbrp[ov];"
            f"[base][ov]blend=all_mode=screen:all_opacity={opacity:.4f},"
            "format=yuv420p[vout]"
        )

    def render_video(
        self,
        image: Path,
        final_audio: Path,
        output: Path,
        settings: RenderSettings,
    ) -> None:
        has_overlay = bool(settings.overlay_path)
        overlay = Path(settings.overlay_path) if has_overlay else None

        cmd = [
            self.ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel", "warning",
            "-filter_threads", "1",
            "-loop", "1",
            "-framerate", str(FPS),
            "-i", str(image),
        ]

        if has_overlay:
            if not overlay or not overlay.is_file():
                raise ValueError(f"Không tìm thấy overlay MP4: {settings.overlay_path}")
            cmd += [
                "-stream_loop", "-1",
                "-i", str(overlay),
            ]

        audio_input_idx = 2 if has_overlay else 1
        cmd += ["-i", str(final_audio)]

        filter_complex = self._visual_filter_complex(settings, has_overlay)
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", f"{audio_input_idx}:a:0",
            "-r", str(FPS),
            "-pix_fmt", "yuv420p",
        ]

        if settings.encoder.lower().startswith("nvidia"):
            cmd += [
                "-c:v", "h264_nvenc",
                "-preset", "p5",
                "-cq", "19",
                "-b:v", "0",
            ]
        elif settings.encoder.lower().startswith("intel"):
            cmd += [
                "-c:v", "h264_qsv",
                "-preset", "veryfast",
                "-global_quality", "25",
                "-look_ahead", "0",
            ]
        else:
            # Two encoder threads leave Windows responsive on 4 GB / dual-core PCs.
            low_resource = settings.output_profile.lower().startswith("720")
            cmd += [
                "-c:v", "libx264",
                "-preset", "ultrafast" if low_resource else "veryfast",
                "-crf", "23" if low_resource else "19",
                "-threads", "2",
            ]

        cmd += [
            "-c:a", "copy",
            "-t", str(settings.duration_seconds),
            "-movflags", "+faststart",
            str(output),
        ]

        self._run_with_ffmpeg_progress(
            cmd,
            duration_seconds=settings.duration_seconds,
            pct_start=55,
            pct_end=99,
            label="Render video",
        )

    def verify_output(self, output: Path, target_seconds: int, settings: RenderSettings) -> dict:
        cmd = [
            self.ffprobe,
            "-v", "error",
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,width,height",
            "-of", "json",
            str(output),
        ]
        cp = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=no_window_flag(),
        )
        if cp.returncode != 0:
            raise RuntimeError("Không verify được file output.\n" + cp.stderr.strip())

        data = json.loads(cp.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
        streams = data.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        result = {
            "duration": duration,
            "video_codec": video_stream.get("codec_name") if video_stream else None,
            "width": video_stream.get("width") if video_stream else None,
            "height": video_stream.get("height") if video_stream else None,
            "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
            "duration_ok": abs(duration - target_seconds) <= 1.0,
            "resolution_ok": bool(
                video_stream
                and video_stream.get("width") == video_dimensions(settings)[0]
                and video_stream.get("height") == video_dimensions(settings)[1]
            ),
            "audio_ok": audio_stream is not None,
        }
        return result

    def render_project(
        self,
        image: Path,
        tracks: list[Path],
        first_five: list[Path],
        output: Path,
        settings: RenderSettings,
    ) -> tuple[Path, Path, dict]:
        self.cancel_event.clear()
        output.parent.mkdir(parents=True, exist_ok=True)

        if settings.encoder.lower().startswith("nvidia"):
            self._progress(1, "Kiểm tra NVIDIA NVENC...")
            ok, msg = check_nvenc(self.ffmpeg)
            if not ok:
                raise RuntimeError(
                    "Bạn đang chọn NVIDIA NVENC nhưng kiểm tra encode thất bại.\n\n"
                    + msg
                )
            self._log(msg)
        elif settings.encoder.lower().startswith("intel"):
            self._progress(1, "Kiểm tra Intel Quick Sync...")
            ok, msg = check_qsv(self.ffmpeg)
            if not ok:
                raise RuntimeError("Bạn đang chọn Intel Quick Sync nhưng kiểm tra encode thất bại.\n\n" + msg)
            self._log(msg)

        self._progress(2, "Đang đọc thông tin audio...")
        durations = self.probe_durations(tracks)

        sequence, starts, cycles = build_sequence(
            tracks=tracks,
            first_five=first_five,
            durations=durations,
            target_seconds=settings.duration_seconds,
            transition_mode=settings.transition_mode,
            transition_seconds=settings.transition_seconds,
            seed=settings.random_seed,
        )

        self._log("===== PLAYLIST =====")
        self._log(f"Seed: {settings.random_seed}")
        self._log(f"Target: {fmt_time(settings.duration_seconds, True)}")
        self._log(f"Số lượt track: {len(sequence)} | Số vòng playlist: {cycles}")
        for i, (p, start) in enumerate(zip(sequence, starts), 1):
            if start >= settings.duration_seconds:
                break
            self._log(f"{i:03d}. {fmt_time(start, True)}  {p.name}")

        chapters = write_chapters(
            output_video=output,
            sequence=sequence,
            starts=starts,
            target_seconds=settings.duration_seconds,
        )
        self._log(f"Chapter file: {chapters}")

        with tempfile.TemporaryDirectory(prefix="qmvb_v2_") as td:
            temp_dir = Path(td)

            # Only process unique sources that actually appear in the target sequence.
            seen = set()
            unique_tracks = []
            for p in sequence:
                rp = p.resolve()
                if rp not in seen:
                    seen.add(rp)
                    unique_tracks.append(p)

            self._progress(10, "Chuẩn hóa audio...")
            processed = self.preprocess_tracks(
                unique_tracks=unique_tracks,
                durations=durations,
                settings=settings,
                temp_dir=temp_dir,
            )

            self._progress(35, "Ghép audio timeline...")
            final_audio = self.build_final_audio(
                sequence=sequence,
                processed=processed,
                settings=settings,
                temp_dir=temp_dir,
            )

            self._progress(55, "Bắt đầu render video...")
            self.render_video(
                image=image,
                final_audio=final_audio,
                output=output,
                settings=settings,
            )

        self._progress(99.5, "Đang kiểm tra output...")
        verify = self.verify_output(output, settings.duration_seconds, settings)
        self._progress(100, "Hoàn tất.")
        return output, chapters, verify
