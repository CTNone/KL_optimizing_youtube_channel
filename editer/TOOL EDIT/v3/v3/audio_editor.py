from __future__ import annotations

import base64
import json
import os
import queue
import random
import subprocess
import tempfile
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from engine import find_binary, get_duration, no_window_flag, scan_audio_files
from music_library import SharedMusicCatalog

APP_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = next((p for p in APP_ROOT.parents if (p / "OPEN_CONTENT_HUB.bat").is_file()), APP_ROOT.parents[4])
OUTPUT_ROOT = WORKSPACE_ROOT / "OUTPUT TỔNG" / "Editor"
SETTINGS_PATH = OUTPUT_ROOT / "tool_edit_settings.json"


def _format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _parse_duration(value: str, source_duration: float) -> float:
    value = value.strip()
    if not value:
        return source_duration
    try:
        if ":" in value:
            parts = [float(part) for part in value.split(":")]
            if len(parts) == 2:
                hours, minutes, seconds = 0, parts[0], parts[1]
            elif len(parts) == 3:
                hours, minutes, seconds = parts
            else:
                raise ValueError
            if hours < 0 or minutes < 0 or seconds < 0 or minutes >= 60 and len(parts) == 3 or seconds >= 60:
                raise ValueError
            requested = hours * 3600 + minutes * 60 + seconds
        else:
            requested = float(value)
    except ValueError as exc:
        raise ValueError("Thời lượng cần nhập dạng MM:SS, HH:MM:SS hoặc số giây.") from exc
    if requested <= 3:
        raise ValueError("Thời lượng xuất phải lớn hơn 3 giây để tạo fade-out.")
    if requested > source_duration + 0.001:
        raise ValueError(
            f"Thời lượng xuất ({_format_duration(requested)}) không được dài hơn video gốc "
            f"({_format_duration(source_duration)})."
        )
    return min(requested, source_duration)
def _run(command: list[str]) -> None:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", creationflags=no_window_flag())
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[-3000:] or "FFmpeg xử lý thất bại.")


def _show_error(title: str, details: str, parent=None) -> None:
    """Show complete exception details in a scrollable, copyable window."""
    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        log_path = OUTPUT_ROOT / "tool_edit_error.log"
    except OSError:
        log_path = Path(tempfile.gettempdir()) / "tool_edit_error.log"
    try:
        log_path.write_text(details, encoding="utf-8")
    except OSError:
        log_path = Path(tempfile.gettempdir()) / "tool_edit_error.log"
        log_path.write_text(details, encoding="utf-8")

    window = tk.Toplevel(parent) if parent is not None else tk.Tk()
    window.title(title)
    window.geometry("900x580")
    window.minsize(680, 400)
    window.columnconfigure(0, weight=1)
    window.rowconfigure(1, weight=1)
    ttk.Label(window, text=f"Đã lưu đầy đủ thông tin lỗi tại:\n{log_path}", padding=10).grid(
        row=0, column=0, sticky="ew")
    body = ttk.Frame(window, padding=(10, 0, 10, 8))
    body.grid(row=1, column=0, sticky="nsew")
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)
    text_box = tk.Text(body, wrap="none", font=("Consolas", 9), undo=False)
    y_scroll = ttk.Scrollbar(body, orient="vertical", command=text_box.yview)
    x_scroll = ttk.Scrollbar(body, orient="horizontal", command=text_box.xview)
    text_box.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
    text_box.grid(row=0, column=0, sticky="nsew")
    y_scroll.grid(row=0, column=1, sticky="ns")
    x_scroll.grid(row=1, column=0, sticky="ew")
    text_box.insert("1.0", details)
    text_box.configure(state="disabled")
    buttons = ttk.Frame(window, padding=10)
    buttons.grid(row=2, column=0, sticky="e")

    def copy_details():
        window.clipboard_clear()
        window.clipboard_append(details)
        window.update()

    ttk.Button(buttons, text="Sao chép lỗi", command=copy_details).pack(side="left", padx=5)
    ttk.Button(buttons, text="Mở file log", command=lambda: os.startfile(str(log_path))).pack(side="left", padx=5)
    ttk.Button(buttons, text="Đóng", command=window.destroy).pack(side="left", padx=5)
    if parent is not None:
        window.transient(parent)
        window.grab_set()
    window.focus_force()


class AudioMixEngine:
    """Mix an existing video with normalized music and optionally scheduled effects."""

    def __init__(self, ffmpeg: str, ffprobe: str, progress, log):
        self.ffmpeg, self.ffprobe = ffmpeg, ffprobe
        self.progress, self.log = progress, log
        self.cancelled = threading.Event()

    def cancel(self):
        self.cancelled.set()

    def render(self, video: Path, tracks: list[Path], opening: list[Path], effects: list[Path],
               output: Path, include_original_audio: bool = True,
               requested_duration: float | None = None):
        # The music and effect folders can change after the UI scan. Catch stale
        # paths before probing or invoking FFmpeg so users can refresh the lists.
        sources = list(dict.fromkeys([video, *tracks, *opening, *effects]))
        missing = [path for path in sources if not path.is_file()]
        if missing:
            details = "\n".join(str(path) for path in missing[:10])
            if len(missing) > 10:
                details += f"\n… và {len(missing) - 10} file khác"
            raise FileNotFoundError(
                "Không tìm thấy file đầu vào sau đây:\n\n"
                f"{details}\n\n"
                "Hãy kiểm tra file hoặc thư mục nhạc/sound effect, rồi bấm Làm mới trước khi xuất."
            )
        source_duration = get_duration(self.ffprobe, video)
        if source_duration <= 3:
            raise ValueError("Video cần dài hơn 3 giây để áp dụng fade-out.")
        duration = source_duration if requested_duration is None else float(requested_duration)
        if duration <= 3:
            raise ValueError("Thời lượng xuất phải lớn hơn 3 giây để áp dụng fade-out.")
        if duration > source_duration + 0.001:
            raise ValueError(
                f"Thời lượng xuất ({_format_duration(duration)}) không được dài hơn video gốc "
                f"({_format_duration(source_duration)})."
            )
        duration = min(duration, source_duration)
        with tempfile.TemporaryDirectory(prefix="tool_edit_audio_") as temp_name:
            temp = Path(temp_name)
            self.progress(2, "Đọc thời lượng video và chuẩn hóa nhạc…")
            normalized: dict[Path, Path] = {}
            durations: dict[Path, float] = {}
            unique_tracks = list(dict.fromkeys(tracks))

            def prepare_track(source: Path) -> None:
                if source in normalized:
                    return
                self._check()
                dest = temp / f"track_{len(normalized):04d}.flac"
                normalized_raw = temp / f"normalized_{len(normalized):04d}.flac"
                filt = ("silenceremove=start_periods=1:start_duration=0.08:start_threshold=-55dB:"
                        "stop_periods=1:stop_duration=0.08:stop_threshold=-55dB,"
                        "loudnorm=I=-14:TP=-1.5:LRA=11,asetpts=PTS-STARTPTS")
                _run([self.ffmpeg, "-y", "-v", "error", "-i", str(source), "-af", filt,
                      "-ar", "48000", "-ac", "2", "-c:a", "flac", str(normalized_raw)])
                # Run silence trimming once more on the encoded intermediate.
                # Some source files carry leading timestamps that can otherwise
                # reappear as padding when the concat demuxer reads the FLAC.
                _run([self.ffmpeg, "-y", "-v", "error", "-i", str(normalized_raw), "-af",
                      "silenceremove=start_periods=1:start_duration=0.08:start_threshold=-50dB:"
                      "stop_periods=1:stop_duration=0.08:stop_threshold=-50dB,asetpts=PTS-STARTPTS",
                      "-ar", "48000", "-ac", "2", "-c:a", "flac", str(dest)])
                d = get_duration(self.ffprobe, dest)
                if d < 0.25:
                    raise ValueError(f"Không còn đủ âm thanh sau khi cắt khoảng trống: {source.name}")
                normalized[source] = dest
                durations[source] = d
                self.progress(3 + 32 * len(normalized) / max(1, len(unique_tracks)),
                              f"Chuẩn hóa bài nhạc: {source.name}")

            remaining = [p for p in tracks if p not in opening]
            if not remaining:
                remaining = list(opening)
            rng = random.SystemRandom()
            sequence: list[Path] = []
            timeline = 0.0
            while timeline < duration:
                pool = list(remaining)
                rng.shuffle(pool)
                cycle = list(opening) + pool
                if not cycle:
                    raise ValueError("Chưa chọn bài nhạc.")
                for path in cycle:
                    prepare_track(path)
                    sequence.append(path)
                    timeline += durations[path] + 1.0
                    if timeline >= duration:
                        break
            self.progress(37, "Ghép playlist và khoảng nghỉ 1 giây…")

            pieces: list[Path] = []
            for i, path in enumerate(sequence):
                pieces.append(normalized[path])
                if i < len(sequence) - 1:
                    silence = temp / f"gap_{i:04d}.flac"
                    _run([self.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                          "anullsrc=r=48000:cl=stereo", "-t", "1", "-c:a", "flac", str(silence)])
                    pieces.append(silence)
            concat_file = temp / "playlist.txt"
            concat_lines = []
            for piece in pieces:
                escaped = piece.as_posix().replace("'", "'\\''")
                concat_lines.append(f"file '{escaped}'\n")
            concat_file.write_text("".join(concat_lines), encoding="utf-8")
            raw_audio = temp / "playlist_raw.flac"
            base_audio = temp / "base.flac"
            _run([self.ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                  "-c:a", "flac", str(raw_audio)])
            # A demuxer can preserve a non-zero start timestamp as leading
            # silence. Remove it from the assembled playlist and reset PTS
            # before this track becomes the looping source for the video.
            _run([self.ffmpeg, "-y", "-v", "error", "-i", str(raw_audio), "-af",
                  "silenceremove=start_periods=1:start_duration=0.08:start_threshold=-50dB,"
                  "asetpts=PTS-STARTPTS", "-ar", "48000", "-ac", "2", "-c:a", "flac", str(base_audio)])
            clean_duration = get_duration(self.ffprobe, base_audio)
            if clean_duration < 0.25:
                raise ValueError("Playlist nhạc sau khi ghép gần như im lặng. Hãy thử bài mở đầu khác.")

            self._check()
            rng = random.SystemRandom()
            schedule: list[tuple[Path, float]] = []
            if effects:
                cursor = rng.randint(60, 300)
                while cursor < duration - 2:
                    schedule.append((rng.choice(effects), float(cursor)))
                    cursor += rng.randint(60, 300)

            cmd = [self.ffmpeg, "-y", "-v", "error", "-i", str(video),
                   "-stream_loop", "-1", "-i", str(base_audio)]
            for effect, _ in schedule:
                cmd += ["-i", str(effect)]
            filters = [f"[1:a]asetpts=PTS-STARTPTS,atrim=0:{duration:.6f},"
                       f"afade=t=out:st={duration-3:.6f}:d=3[music]"]
            current = "music"
            original_audio_used = False
            if include_original_audio and self._has_audio(video):
                filters.append(f"[0:a:0]aresample=48000,asetpts=PTS-STARTPTS,"
                               f"atrim=duration={duration:.6f},volume=0.35[original]")
                filters.append("[music][original]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[withoriginal]")
                current = "withoriginal"
                original_audio_used = True
            for index, (_, at) in enumerate(schedule):
                label = f"fx{index}"
                filters.append(f"[{index+2}:a]asetpts=PTS-STARTPTS,atrim=duration=10,volume=0.16,"
                               f"adelay={int(at*1000)}|{int(at*1000)}[{label}]")
                next_label = f"mix{index}"
                filters.append(f"[{current}][{label}]amix=inputs=2:duration=first:dropout_transition=0[{next_label}]")
                current = next_label
            filters.append(f"[{current}]atrim=duration={duration:.6f},alimiter=limit=0.95[outa]")
            cmd += ["-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[outa]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-t", f"{duration:.6f}",
                    "-movflags", "+faststart", str(output)]
            self.progress(45, "Ghép âm thanh vào video…")
            _run(cmd)
            self._verify_output_audio(output)
            self.progress(100, "Hoàn tất")
            return output, len(sequence), len(schedule), original_audio_used

    def _has_audio(self, video: Path) -> bool:
        result = subprocess.run(
            [self.ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index",
             "-of", "csv=p=0", str(video)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            creationflags=no_window_flag(),
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def _verify_output_audio(self, output: Path) -> None:
        if not self._has_audio(output):
            raise RuntimeError("File xuất không có track âm thanh; Tool Edit chưa xác nhận thành công.")
        sample_seconds = min(30.0, get_duration(self.ffprobe, output))
        result = subprocess.run(
            [self.ffmpeg, "-hide_banner", "-v", "info", "-i", str(output), "-vn", "-t",
             f"{sample_seconds:.3f}", "-af", "volumedetect", "-f", "null", os.devnull],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            creationflags=no_window_flag(),
        )
        if result.returncode:
            raise RuntimeError("Không kiểm tra được âm thanh trong file xuất: " + result.stderr[-1200:])
        mean_line = next((line for line in result.stderr.splitlines() if "mean_volume:" in line), "")
        try:
            mean_volume = float(mean_line.split("mean_volume:", 1)[1].split("dB", 1)[0].strip())
        except (IndexError, ValueError):
            raise RuntimeError("Không đọc được mức âm thanh của file xuất; hãy kiểm tra lại trước khi dùng.")
        if mean_volume <= -55:
            raise RuntimeError(
                f"30 giây đầu của file xuất gần như im lặng ({mean_volume:.1f} dB). "
                "File chưa được xác nhận hoàn tất. Kiểm tra bài mở đầu và bấm Làm mới thư viện nhạc."
            )

    def _check(self):
        if self.cancelled.is_set():
            raise RuntimeError("Đã hủy xử lý.")


class App(tk.Tk):
    def __init__(self, load_default_library: bool = True):
        super().__init__()
        self.title("Tool Edit · Âm thanh cho video")
        self.geometry("1050x760")
        self.minsize(900, 650)
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        self.catalog = SharedMusicCatalog()
        self.settings = self._load_settings()
        self.music_folder = tk.StringVar(value=self.settings.get("music_folder", ""))
        self.video_path = tk.StringVar()
        self.video_duration = 0.0
        self.duration_text = tk.StringVar()
        self.source_duration_text = tk.StringVar(value="Chưa chọn video")
        self.include_original_audio = tk.BooleanVar(value=False)
        self.effect_folder = tk.StringVar(value=self.settings.get("effect_folder", ""))
        self.output_path = tk.StringVar(value=str(OUTPUT_ROOT / "video_hoan_thien.mp4"))
        self.status = tk.StringVar(value="Chọn video và thư mục nhạc để bắt đầu.")
        self.progress = tk.DoubleVar(value=0)
        self.tracks: list[Path] = []
        self.opening: list[Path] = []
        self.effects: list[Path] = []
        self.aliases: dict[str, str] = {}
        self.busy = False
        self.preview_window = None
        self.preview_label = None
        self.preview_photo = None
        self.preview_process = None
        self.preview_queue = None
        self.preview_reader = None
        self._ui()
        if load_default_library:
            self._load_music_folder_default()
        self.after(150, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close_app)

    def _load_settings(self) -> dict:
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _remember_folder(self, key: str, folder: str | Path) -> None:
        path = str(Path(folder).resolve())
        self.settings[key] = path
        try:
            OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            self.status.set(f"Không lưu được thư mục gần nhất: {exc}")

    def report_callback_exception(self, exc_type, exc, tb):
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        _show_error("Tool Edit gặp lỗi", details, self)

    def _ui(self):
        viewport = ttk.Frame(self)
        viewport.pack(fill="both", expand=True)
        canvas = self.main_canvas = tk.Canvas(viewport, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        root = ttk.Frame(canvas, padding=18)
        content_id = canvas.create_window((0, 0), window=root, anchor="nw")

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_content_width(event):
            canvas.itemconfigure(content_id, width=event.width)

        root.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", fit_content_width)
        ttk.Label(root, text="TOOL EDIT", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(root, text="Ghép nhạc đồng mức vào video đã dựng sẵn", font=("Segoe UI", 11)).pack(anchor="w", pady=(0, 14))
        video = ttk.LabelFrame(root, text="1 · Video thành phẩm của bạn", padding=10); video.pack(fill="x", pady=5)
        ttk.Entry(video, textvariable=self.video_path).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(video, text="Chọn video…", command=self._choose_video).pack(side="right")
        ttk.Button(video, text="Xem trước", command=self._open_preview).pack(side="right", padx=5)
        duration_row = ttk.Frame(video); duration_row.pack(fill="x", pady=(8, 0))
        ttk.Label(duration_row, text="Thời lượng xuất (MM:SS / HH:MM:SS):").pack(side="left")
        self.duration_entry = ttk.Entry(duration_row, textvariable=self.duration_text, width=14)
        self.duration_entry.pack(side="left", padx=6)
        ttk.Label(duration_row, textvariable=self.source_duration_text).pack(side="left")
        ttk.Checkbutton(video, text="Giữ âm thanh gốc của video khi xuất (tắt ô này để bỏ tiếng gốc)",
                        variable=self.include_original_audio).pack(anchor="w", pady=(8, 0))
        music = ttk.LabelFrame(root, text="2 · Thư viện nhạc", padding=10); music.pack(fill="both", expand=True, pady=5)
        row = ttk.Frame(music); row.pack(fill="x")
        ttk.Entry(row, textvariable=self.music_folder).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Chọn thư mục…", command=self._choose_music_folder).pack(side="left", padx=5)
        ttk.Button(row, text="Làm mới", command=self._scan_music).pack(side="left")
        ttk.Label(music, text="Chọn 3–5 bài mở đầu. Nhấp đúp một bài để nghe; dùng nút bên dưới để thêm/bỏ khỏi danh sách.").pack(anchor="w", pady=6)
        self.music_tree = ttk.Treeview(music, columns=("duration", "opening"), show="tree headings", height=9, selectmode="browse")
        self.music_tree.heading("#0", text="Bài nhạc"); self.music_tree.heading("duration", text="Thời lượng"); self.music_tree.heading("opening", text="Mở đầu")
        self.music_tree.column("#0", width=520); self.music_tree.column("duration", width=100, anchor="center"); self.music_tree.column("opening", width=100, anchor="center")
        self.music_tree.pack(fill="both", expand=True)
        self.music_tree.bind("<Double-1>", self._preview_music)
        controls = ttk.Frame(music); controls.pack(fill="x", pady=(7, 0))
        ttk.Button(controls, text="Nghe bài đang chọn", command=self._preview_music).pack(side="left")
        ttk.Button(controls, text="Thêm / bỏ bài mở đầu", command=self._toggle_opening).pack(side="left", padx=6)
        self.opening_label = ttk.Label(controls, text="Đã chọn 0/5 bài mở đầu"); self.opening_label.pack(side="right")
        fx = ttk.LabelFrame(root, text="3 · Sound effect (tùy chọn)", padding=10); fx.pack(fill="x", pady=5)
        row = ttk.Frame(fx); row.pack(fill="x")
        ttk.Entry(row, textvariable=self.effect_folder).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Chọn kho…", command=self._choose_effect_folder).pack(side="left", padx=5)
        ttk.Button(row, text="Làm mới", command=self._scan_effects).pack(side="left")
        self.effect_tree = ttk.Treeview(fx, columns=("path",), show="tree", height=3, selectmode="browse")
        self.effect_tree.heading("#0", text="Tên hiển thị · nhấp đúp để đổi"); self.effect_tree.pack(fill="x", pady=(6, 0))
        self.effect_tree.bind("<Double-1>", self._rename_effect)
        ttk.Label(fx, text="Một hiệu ứng ngẫu nhiên được phát mỗi 1–5 phút; âm lượng hiệu ứng được hạ để không lấn nhạc.").pack(anchor="w", pady=(5, 0))
        out = ttk.LabelFrame(root, text="4 · Xuất video", padding=10); out.pack(fill="x", pady=5)
        row = ttk.Frame(out); row.pack(fill="x")
        ttk.Entry(row, textvariable=self.output_path).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Nơi lưu…", command=self._choose_output).pack(side="left", padx=5)
        self.start_btn = ttk.Button(row, text="Bắt đầu ghép", command=self._start); self.start_btn.pack(side="right")
        self.bar = ttk.Progressbar(out, variable=self.progress, maximum=100); self.bar.pack(fill="x", pady=(8, 2))
        ttk.Label(root, textvariable=self.status).pack(anchor="w", pady=(5, 0))

    def _load_music_folder_default(self):
        saved = self.music_folder.get()
        if saved and Path(saved).is_dir():
            self._scan_music()
            return
        try:
            rows = self.catalog.library_rows("")
            paths = [Path(r["path"]) for r in rows if r.get("path")]
            if paths:
                folder = str(Path(os.path.commonpath([str(p.parent) for p in paths])))
                self.music_folder.set(folder)
                self._remember_folder("music_folder", folder)
        except Exception:
            pass
        if self.music_folder.get(): self._scan_music()

    def _choose_video(self):
        initialdir = self.settings.get("video_folder")
        p = filedialog.askopenfilename(initialdir=initialdir if initialdir and Path(initialdir).is_dir() else None,
                                       filetypes=[("Video", "*.mp4 *.mov *.mkv *.webm *.avi *.m4v")])
        if p:
            self.video_path.set(p)
            self._remember_folder("video_folder", Path(p).parent)
            try:
                self.video_duration = get_duration(find_binary("ffprobe"), Path(p))
                self.duration_text.set(_format_duration(self.video_duration))
                self.source_duration_text.set(f"Video gốc: {_format_duration(self.video_duration)}")
            except Exception as exc:
                self.video_duration = 0.0
                self.source_duration_text.set("Không đọc được thời lượng video")
                messagebox.showerror("Không đọc được video", str(exc), parent=self)

    def _open_preview(self):
        video = Path(self.video_path.get())
        ffmpeg = find_binary("ffmpeg")
        if not video.is_file():
            return messagebox.showerror("Thiếu video", "Hãy chọn video cần xem trước.", parent=self)
        if not ffmpeg:
            return messagebox.showerror("Thiếu FFmpeg", "Không tìm thấy ffmpeg trong tools hoặc PATH.", parent=self)
        if self.preview_window is not None and self.preview_window.winfo_exists():
            self.preview_window.lift()
            self._restart_preview()
            return

        window = self.preview_window = tk.Toplevel(self)
        window.title(f"Xem trước · {video.name}")
        window.geometry("760x500")
        window.minsize(600, 400)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)
        ttk.Label(window, text="Xem trước video · không phát tiếng", padding=8).grid(row=0, column=0, sticky="w")
        self.preview_label = ttk.Label(window, text="Đang mở video…", anchor="center")
        self.preview_label.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        controls = ttk.Frame(window, padding=8)
        controls.grid(row=2, column=0, sticky="e")
        ttk.Button(controls, text="Phát lại từ đầu", command=self._restart_preview).pack(side="left", padx=4)
        ttk.Button(controls, text="Đóng", command=self._close_preview).pack(side="left", padx=4)
        window.protocol("WM_DELETE_WINDOW", self._close_preview)
        self._restart_preview()

    def _restart_preview(self):
        if self.preview_process is not None and self.preview_process.poll() is None:
            self.preview_process.terminate()
        video = Path(self.video_path.get())
        ffmpeg = find_binary("ffmpeg")
        if not video.is_file() or not ffmpeg or self.preview_window is None:
            return
        self.preview_queue = queue.Queue(maxsize=2)
        self.preview_label.configure(text="Đang giải mã video…", image="")
        self.preview_photo = None
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-re", "-i", str(video), "-an",
                   "-vf", "fps=15,scale=640:-2:flags=fast_bilinear", "-f", "image2pipe", "-vcodec", "ppm", "pipe:1"]
        try:
            self.preview_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                                    creationflags=no_window_flag())
        except OSError as exc:
            return messagebox.showerror("Không thể mở video", str(exc), parent=self.preview_window)
        work_queue = self.preview_queue
        process = self.preview_process

        def offer(item):
            try:
                work_queue.put_nowait(item)
            except queue.Full:
                try:
                    work_queue.get_nowait()
                    work_queue.put_nowait(item)
                except (queue.Empty, queue.Full):
                    pass

        def read_frames():
            try:
                stream = process.stdout
                def read_exact(length):
                    data = bytearray()
                    while len(data) < length:
                        block = stream.read(length - len(data))
                        if not block:
                            break
                        data.extend(block)
                    return bytes(data)

                def read_token():
                    token = bytearray()
                    while True:
                        char = stream.read(1)
                        if not char:
                            return None
                        if char == b"#":
                            while char not in (b"\n", b""):
                                char = stream.read(1)
                            continue
                        if not char.isspace():
                            token.extend(char)
                            break
                    while True:
                        char = stream.read(1)
                        if not char or char.isspace():
                            break
                        token.extend(char)
                    return bytes(token)

                while stream:
                    magic = read_token()
                    if magic is None:
                        break
                    width_token, height_token, maxval_token = read_token(), read_token(), read_token()
                    if magic != b"P6" or not width_token or not height_token or maxval_token != b"255":
                        raise RuntimeError("FFmpeg trả về khung hình PPM không hợp lệ.")
                    width, height = int(width_token), int(height_token)
                    rgb = read_exact(width * height * 3)
                    if len(rgb) != width * height * 3:
                        raise RuntimeError("Khung hình xem trước bị cắt giữa chừng.")
                    ppm = f"P6\n{width} {height}\n255\n".encode("ascii") + rgb
                    offer(("frame", ppm))
                offer(("done", process.wait()))
            except Exception as exc:
                offer(("error", str(exc)))

        self.preview_reader = threading.Thread(target=read_frames, daemon=True)
        self.preview_reader.start()
        self._poll_preview()

    def _poll_preview(self):
        window = self.preview_window
        if window is None or not window.winfo_exists():
            return
        work_queue = self.preview_queue
        if work_queue is not None:
            while True:
                try:
                    kind, value = work_queue.get_nowait()
                except queue.Empty:
                    break
                if kind == "frame":
                    photo_data = base64.b64encode(value).decode("ascii")
                    try:
                        self.preview_photo = tk.PhotoImage(data=photo_data, format="ppm")
                        self.preview_label.configure(image=self.preview_photo, text="")
                    except tk.TclError as exc:
                        self.preview_label.configure(text=f"Không thể hiển thị khung hình:\n{exc}", image="")
                        if self.preview_process is not None and self.preview_process.poll() is None:
                            self.preview_process.terminate()
                elif kind == "error":
                    self.preview_label.configure(text=f"Không xem được video:\n{value}", image="")
                elif kind == "done":
                    self.preview_process = None
                    if value and self.preview_photo is None:
                        self.preview_label.configure(text="Không thể phát video. Hãy kiểm tra file và định dạng.", image="")
        window.after(35, self._poll_preview)

    def _close_preview(self):
        process = self.preview_process
        self.preview_process = None
        if process is not None and process.poll() is None:
            process.terminate()
        window = self.preview_window
        self.preview_window = None
        self.preview_queue = None
        self.preview_photo = None
        if window is not None and window.winfo_exists():
            window.destroy()

    def _close_app(self):
        self._close_preview()
        self.destroy()

    def _choose_music_folder(self):
        current = self.music_folder.get() or self.settings.get("music_folder")
        p = filedialog.askdirectory(title="Chọn thư mục nhạc của Music Manager",
                                    initialdir=current if current and Path(current).is_dir() else None)
        if p:
            self.music_folder.set(p)
            self._remember_folder("music_folder", p)
            self._scan_music()

    def _scan_music(self):
        try: self.tracks = scan_audio_files(Path(self.music_folder.get()))
        except Exception: self.tracks = []
        self.opening = [p for p in self.opening if p in self.tracks]
        self.music_tree.delete(*self.music_tree.get_children())
        for i, path in enumerate(self.tracks):
            iid = f"m{i}"; self.music_tree.insert("", "end", iid=iid, text=path.name, values=("", "✓" if path in self.opening else ""))
            self.music_tree.item(iid, tags=(str(path),))
        self._update_opening()
        self.status.set(f"Đã tìm thấy {len(self.tracks)} bài nhạc.")

    def _selected_music(self):
        selected = self.music_tree.selection()
        if not selected: return None
        tags = self.music_tree.item(selected[0], "tags")
        return Path(tags[0]) if tags else None

    def _preview_music(self, _event=None):
        path = self._selected_music()
        if path and path.is_file(): os.startfile(str(path))

    def _toggle_opening(self):
        path = self._selected_music()
        if not path: return
        if path in self.opening: self.opening.remove(path)
        elif len(self.opening) < 5: self.opening.append(path)
        else: messagebox.showinfo("Danh sách mở đầu", "Chỉ chọn tối đa 5 bài.", parent=self)
        self._scan_music()

    def _update_opening(self):
        self.opening_label.configure(text=f"Đã chọn {len(self.opening)}/5 bài mở đầu")

    def _choose_effect_folder(self):
        current = self.effect_folder.get() or self.settings.get("effect_folder")
        p = filedialog.askdirectory(title="Chọn thư mục sound effect",
                                    initialdir=current if current and Path(current).is_dir() else None)
        if p:
            self.effect_folder.set(p)
            self._remember_folder("effect_folder", p)
            self._scan_effects()

    def _scan_effects(self):
        self.effects = scan_audio_files(Path(self.effect_folder.get())) if self.effect_folder.get() else []
        self.aliases = {}
        store = OUTPUT_ROOT / "sound_effect_names.json"
        try: self.aliases = json.loads(store.read_text(encoding="utf-8"))
        except Exception: pass
        self.effect_tree.delete(*self.effect_tree.get_children())
        for i, path in enumerate(self.effects):
            key = str(path.resolve()); self.effect_tree.insert("", "end", iid=f"fx{i}", text=self.aliases.get(key, path.name), tags=(key,))
        self.status.set(f"Đã tìm thấy {len(self.effects)} sound effect.")

    def _rename_effect(self, event=None):
        item = self.effect_tree.identify_row(event.y) if event else (self.effect_tree.selection() or [None])[0]
        if not item: return
        path = self.effect_tree.item(item, "tags")[0]
        name = simpledialog.askstring("Đổi tên hiển thị", "Tên hiển thị cho sound effect:", initialvalue=self.effect_tree.item(item, "text"), parent=self)
        if name is None: return
        name = name.strip()
        if name: self.aliases[path] = name
        else: self.aliases.pop(path, None)
        (OUTPUT_ROOT / "sound_effect_names.json").write_text(json.dumps(self.aliases, ensure_ascii=False, indent=2), encoding="utf-8")
        self.effect_tree.item(item, text=name or Path(path).name)

    def _choose_output(self):
        initialdir = self.settings.get("output_folder", str(OUTPUT_ROOT))
        if not Path(initialdir).is_dir():
            initialdir = str(OUTPUT_ROOT)
        p = filedialog.asksaveasfilename(initialdir=initialdir, initialfile=Path(self.output_path.get()).name,
                                         defaultextension=".mp4", filetypes=[("MP4", "*.mp4")])
        if p:
            self.output_path.set(p)
            self._remember_folder("output_folder", Path(p).parent)

    def _start(self):
        if self.busy: return
        video = Path(self.video_path.get())
        output = Path(self.output_path.get())
        if not video.is_file(): return messagebox.showerror("Thiếu video", "Hãy chọn video đã dựng sẵn.", parent=self)
        try:
            source_duration = get_duration(find_binary("ffprobe"), video)
            requested_duration = _parse_duration(self.duration_text.get(), source_duration)
        except Exception as exc:
            return messagebox.showerror("Thời lượng không hợp lệ", str(exc), parent=self)
        if len(self.tracks) < 3: return messagebox.showerror("Thiếu nhạc", "Thư viện cần ít nhất 3 bài.", parent=self)
        if not 3 <= len(self.opening) <= 5: return messagebox.showerror("Danh sách mở đầu", "Chọn thủ công từ 3 đến 5 bài mở đầu.", parent=self)
        if not find_binary("ffmpeg") or not find_binary("ffprobe"): return messagebox.showerror("Thiếu FFmpeg", "Cần ffmpeg và ffprobe trong tools hoặc PATH.", parent=self)
        if video.resolve() == output.resolve(): return messagebox.showerror("Nơi lưu không hợp lệ", "Không ghi đè video nguồn.", parent=self)
        self.busy = True; self.start_btn.configure(state="disabled"); self.progress.set(0)
        queue = self._queue = __import__("queue").Queue()
        engine = self._engine = AudioMixEngine(find_binary("ffmpeg"), find_binary("ffprobe"),
                                                lambda pct, msg: queue.put(("progress", pct, msg)),
                                                lambda msg: queue.put(("log", msg)))
        def work():
            try:
                result = engine.render(video, self.tracks, self.opening, self.effects, output,
                                       self.include_original_audio.get(), requested_duration)
                queue.put(("done", result))
            except Exception as exc: queue.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        if hasattr(self, "_queue"):
            while not self._queue.empty():
                item = self._queue.get()
                if item[0] == "progress": self.progress.set(item[1]); self.status.set(item[2])
                elif item[0] == "done":
                    _, (path, count, effects, source_audio) = item; self.busy = False; self.start_btn.configure(state="normal")
                    self.status.set(f"Hoàn tất · {count} lượt bài · {effects} sound effect")
                    audio_text = "đã trộn âm thanh gốc" if source_audio else "không trộn âm thanh gốc"
                    messagebox.showinfo("Đã xuất video", f"Video đã lưu tại:\n{path}\n\nSố lượt bài nhạc: {count}\nSound effect: {effects}\nÂm thanh video: {audio_text}", parent=self)
                elif item[0] == "error":
                    self.busy = False; self.start_btn.configure(state="normal"); self.status.set("Xử lý chưa hoàn tất")
                    messagebox.showerror("Không thể xuất video", item[1], parent=self)
        self.after(150, self._poll)


def main():
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--self-check":
        app = App(load_default_library=False); app.withdraw(); app.update_idletasks()
        Path(sys.argv[2]).write_text(json.dumps({"ui": "OK", "ffmpeg": find_binary("ffmpeg"),
                                                 "ffprobe": find_binary("ffprobe"), "workflow": "audio-mix"}, indent=2), encoding="utf-8")
        app.destroy(); return
    app = None
    try:
        app = App()
        app.mainloop()
    except Exception:
        _show_error("Tool Edit không thể khởi động", traceback.format_exc(), app)
