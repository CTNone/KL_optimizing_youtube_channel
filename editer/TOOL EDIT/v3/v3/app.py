from __future__ import annotations

import json
import queue
import random
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from engine import (
    AUDIO_EXTS,
    IMAGE_EXTS,
    RenderEngine,
    RenderSettings,
    build_sequence,
    check_nvenc,
    check_qsv,
    find_binary,
    fmt_time,
    get_duration,
    load_preset,
    pretty_track_name,
    save_preset,
    scan_audio_files,
)

APP_NAME = "Quick Music Video Builder V2"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1180x860")
        self.minsize(1040, 760)

        self.image_path = tk.StringVar()
        self.music_folder = tk.StringVar()
        self.output_path = tk.StringVar()

        self.duration_choice = tk.StringVar(value="1 Hour")
        self.custom_minutes = tk.StringVar(value="60")

        self.normalize_enabled = tk.BooleanVar(value=True)
        self.loudness_target = tk.StringVar(value="-14")

        self.transition_mode = tk.StringVar(value="Crossfade")
        self.transition_seconds = tk.StringVar(value="2")

        # Safe defaults for the target low-RAM Intel UHD machine.
        self.visual_motion = tk.StringVar(value="Static")
        self.overlay_path = tk.StringVar()
        self.overlay_mode = tk.StringVar(value="Screen")
        self.overlay_opacity = tk.DoubleVar(value=0.45)

        self.encoder = tk.StringVar(value="Intel Quick Sync (h264_qsv)")
        self.output_profile = tk.StringVar(value="720p — Máy yếu (khuyến nghị)")
        self.seed = tk.IntVar(value=random.randint(100000, 999999))

        self.status = tk.StringVar(value="Sẵn sàng")
        self.progress = tk.DoubleVar(value=0)

        self.tracks: list[Path] = []
        self.track_display: list[str] = []
        self.slot_vars = [tk.StringVar() for _ in range(5)]

        self.ui_queue: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.engine: RenderEngine | None = None

        self._build_ui()
        self.after(100, self._drain_queue)

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text=APP_NAME, font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="Pre-editor cho video nhạc: playlist → audio processing → motion/overlay → MP4",
        ).pack(anchor="w", pady=(2, 10))

        files = ttk.LabelFrame(root, text="Project")
        files.pack(fill="x")
        files.columnconfigure(1, weight=1)

        self._path_row(files, 0, "Thumbnail:", self.image_path, self.choose_image, "Chọn ảnh")
        self._path_row(files, 1, "Folder nhạc:", self.music_folder, self.choose_music, "Chọn folder")
        self._path_row(files, 2, "Output MP4:", self.output_path, self.choose_output, "Chọn nơi lưu")

        self.track_count = ttk.Label(files, text="Chưa quét folder nhạc.")
        self.track_count.grid(row=3, column=1, sticky="w", padx=8, pady=(0, 7))

        tabs = ttk.Notebook(root)
        tabs.pack(fill="both", expand=True, pady=(10, 0))

        self.tab_audio = ttk.Frame(tabs, padding=10)
        self.tab_visual = ttk.Frame(tabs, padding=10)
        self.tab_output = ttk.Frame(tabs, padding=10)
        tabs.add(self.tab_audio, text="Audio & Playlist")
        tabs.add(self.tab_visual, text="Visual")
        tabs.add(self.tab_output, text="Output & Presets")

        self._build_audio_tab()
        self._build_visual_tab()
        self._build_output_tab()

        # Keep the primary action available while the user is reviewing any tab,
        # especially the playlist tab.
        action_row = ttk.Frame(root)
        action_row.pack(fill="x", pady=(10, 0))
        self.render_btn = ttk.Button(
            action_row,
            text="TẠO VIDEO V2",
            command=self.start_render,
        )
        self.render_btn.pack(side="right", ipadx=24, ipady=8)
        ttk.Label(
            action_row,
            text="Danh sách phát: 5 bài đã chọn → các bài còn lại ngẫu nhiên → lặp lại cùng thứ tự.",
        ).pack(side="left", pady=6)

        log_frame = ttk.LabelFrame(root, text="Progress / Log")
        log_frame.pack(fill="both", expand=False, pady=(10, 0))

        self.progress_bar = ttk.Progressbar(
            log_frame, variable=self.progress, maximum=100, mode="determinate"
        )
        self.progress_bar.pack(fill="x", padx=8, pady=(8, 4))

        status_row = ttk.Frame(log_frame)
        status_row.pack(fill="x", padx=8)
        ttk.Label(status_row, textvariable=self.status).pack(side="left")
        self.cancel_btn = ttk.Button(
            status_row, text="Hủy render", command=self.cancel_render, state="disabled"
        )
        self.cancel_btn.pack(side="right")

        self.log_text = tk.Text(
            log_frame, height=9, state="disabled", wrap="word", font=("Consolas", 9)
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    def _path_row(self, parent, row, label, var, command, btn_text):
        ttk.Label(parent, text=label, width=14).grid(row=row, column=0, sticky="w", padx=8, pady=5)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(parent, text=btn_text, command=command).grid(row=row, column=2, padx=8, pady=5)

    def _build_audio_tab(self):
        left = ttk.LabelFrame(self.tab_audio, text="5 bài đầu tiên")
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        ttk.Label(
            left,
            text="Vẫn giữ logic V1: 5 bài này đứng đầu mỗi vòng; phần còn lại random.",
            wraplength=480,
        ).pack(anchor="w", padx=10, pady=(8, 6))

        self.combos = []
        for i in range(5):
            row = ttk.Frame(left)
            row.pack(fill="x", padx=10, pady=4)
            ttk.Label(row, text=f"#{i+1}", width=4).pack(side="left")
            cb = ttk.Combobox(row, textvariable=self.slot_vars[i], state="readonly")
            cb.pack(side="left", fill="x", expand=True)
            self.combos.append(cb)

        row = ttk.Frame(left)
        row.pack(fill="x", padx=10, pady=8)
        ttk.Button(row, text="Tự điền 5 bài đầu", command=self.autofill).pack(side="left")
        ttk.Button(row, text="Xóa", command=self.clear_slots).pack(side="left", padx=6)
        ttk.Button(row, text="Shuffle random", command=self.new_seed).pack(side="right")

        seed_row = ttk.Frame(left)
        seed_row.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(seed_row, text="Playlist seed:").pack(side="left")
        ttk.Entry(seed_row, textvariable=self.seed, width=12).pack(side="left", padx=6)
        ttk.Button(seed_row, text="Preview playlist", command=self.preview_playlist).pack(side="right")

        right = ttk.LabelFrame(self.tab_audio, text="Audio processing")
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))

        grid = ttk.Frame(right)
        grid.pack(fill="x", padx=10, pady=8)
        grid.columnconfigure(1, weight=1)

        ttk.Label(grid, text="Duration:").grid(row=0, column=0, sticky="w", pady=5)
        dur = ttk.Combobox(
            grid,
            textvariable=self.duration_choice,
            state="readonly",
            values=[
                "5 Minutes",
                "10 Minutes",
                "20 Minutes",
                "30 Minutes",
                "1 Hour",
                "2 Hours",
                "3 Hours",
                "Custom",
            ],
        )
        dur.grid(row=0, column=1, sticky="ew", pady=5)
        dur.bind("<<ComboboxSelected>>", self._update_custom_minutes_state)

        ttk.Label(grid, text="Custom minutes:").grid(row=1, column=0, sticky="w", pady=5)
        self.custom_minutes_entry = ttk.Entry(grid, textvariable=self.custom_minutes)
        self.custom_minutes_entry.grid(row=1, column=1, sticky="ew", pady=5)
        self._update_custom_minutes_state()

        ttk.Checkbutton(
            grid,
            text="Audio loudness normalization",
            variable=self.normalize_enabled,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 3))

        ttk.Label(grid, text="Target LUFS:").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Combobox(
            grid,
            textvariable=self.loudness_target,
            state="readonly",
            values=["-14", "-16", "-18"],
        ).grid(row=3, column=1, sticky="ew", pady=5)

        ttk.Label(grid, text="Transition:").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Combobox(
            grid,
            textvariable=self.transition_mode,
            state="readonly",
            values=["None", "Fade", "Crossfade"],
        ).grid(row=4, column=1, sticky="ew", pady=5)

        ttk.Label(grid, text="Transition seconds:").grid(row=5, column=0, sticky="w", pady=5)
        ttk.Combobox(
            grid,
            textvariable=self.transition_seconds,
            state="readonly",
            values=["0", "1", "2", "3", "5"],
        ).grid(row=5, column=1, sticky="ew", pady=5)

        ttk.Label(
            right,
            text=(
                "Fade = fade đầu/cuối nhưng track không overlap.\n"
                "Crossfade = bài sau bắt đầu trước khi bài trước kết thúc; "
                "chapter timestamps tự tính theo overlap."
            ),
            wraplength=450,
        ).pack(anchor="w", padx=10, pady=(4, 10))

    def _build_visual_tab(self):
        motion = ttk.LabelFrame(self.tab_visual, text="Thumbnail motion")
        motion.pack(side="left", fill="both", expand=True, padx=(0, 6))

        ttk.Label(
            motion,
            text="Chuyển động rất chậm để phù hợp video nhạc dài.",
        ).pack(anchor="w", padx=10, pady=(8, 6))

        ttk.Label(motion, text="Motion:").pack(anchor="w", padx=10)
        ttk.Combobox(
            motion,
            textvariable=self.visual_motion,
            state="readonly",
            values=[
                "Static",
                "Slow Zoom",
                "Pan Left-Right",
                "Pan Up-Down",
                "Cinematic Drift",
            ],
        ).pack(fill="x", padx=10, pady=(2, 10))

        ttk.Label(
            motion,
            text=(
                "Slow Zoom và Cinematic Drift dùng chuyển động tuần hoàn rất chậm, "
                "không reset đột ngột sau vài chục giây."
            ),
            wraplength=470,
        ).pack(anchor="w", padx=10)

        overlay = ttk.LabelFrame(self.tab_visual, text="Snow / Rain MP4 Overlay")
        overlay.pack(side="left", fill="both", expand=True, padx=(6, 0))

        ttk.Label(overlay, text="Overlay MP4 (optional):").pack(anchor="w", padx=10, pady=(8, 2))
        row = ttk.Frame(overlay)
        row.pack(fill="x", padx=10)
        ttk.Entry(row, textvariable=self.overlay_path).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Chọn MP4", command=self.choose_overlay).pack(side="left", padx=(6, 0))
        ttk.Button(row, text="Xóa", command=lambda: self.overlay_path.set("")).pack(side="left", padx=(6, 0))

        ttk.Label(overlay, text="Blend mode:").pack(anchor="w", padx=10, pady=(10, 2))
        ttk.Combobox(
            overlay,
            textvariable=self.overlay_mode,
            state="readonly",
            values=["Screen", "Alpha"],
        ).pack(fill="x", padx=10)

        ttk.Label(overlay, text="Opacity:").pack(anchor="w", padx=10, pady=(10, 2))
        tk.Scale(
            overlay,
            variable=self.overlay_opacity,
            from_=0.05,
            to=1.0,
            resolution=0.05,
            orient="horizontal",
        ).pack(fill="x", padx=10)

        ttk.Label(
            overlay,
            text=(
                "Screen: phù hợp snow/rain/particles nền đen.\n"
                "Alpha: dùng khi overlay MP4 thực sự có alpha channel."
            ),
            wraplength=470,
        ).pack(anchor="w", padx=10, pady=(8, 10))

    def _build_output_tab(self):
        profile = ttk.LabelFrame(self.tab_output, text="Độ phân giải / Máy yếu")
        profile.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ttk.Label(profile, text="Output profile:").pack(anchor="w", padx=10, pady=(10, 2))
        ttk.Combobox(
            profile, textvariable=self.output_profile, state="readonly",
            values=[
                "720p — Máy yếu (khuyến nghị)",
                "1080p — Cân bằng",
                "1440p — Chất lượng cao",
            ],
        ).pack(fill="x", padx=10)
        ttk.Label(
            profile,
            text=("Với i3 / 4 GB RAM / Intel UHD: chọn 720p, Intel Quick Sync, "
                  "Static và tắt overlay để render ổn định nhất."),
            wraplength=290,
        ).pack(anchor="w", padx=10, pady=(10, 10))

        enc = ttk.LabelFrame(self.tab_output, text="Encoder")
        enc.pack(side="left", fill="both", expand=True, padx=6)

        ttk.Radiobutton(
            enc, text="Intel UHD — Quick Sync (khuyến nghị)", variable=self.encoder,
            value="Intel Quick Sync (h264_qsv)"
        ).pack(anchor="w", padx=10, pady=(10, 4))
        ttk.Radiobutton(
            enc, text="CPU — libx264 (dự phòng)", variable=self.encoder, value="CPU (libx264)"
        ).pack(anchor="w", padx=10, pady=4)
        ttk.Radiobutton(
            enc, text="NVIDIA — h264_nvenc", variable=self.encoder, value="NVIDIA NVENC"
        ).pack(anchor="w", padx=10, pady=4)
        ttk.Button(enc, text="Test Intel Quick Sync", command=self.test_qsv).pack(anchor="w", padx=10, pady=(8, 2))
        ttk.Button(enc, text="Test NVIDIA NVENC", command=self.test_nvenc).pack(anchor="w", padx=10, pady=8)

        ttk.Label(
            enc,
            text=(
                "Intel Quick Sync là GPU tích hợp Intel. Cả QSV/NVIDIA đều được "
                "encode thử trước khi render để tránh chờ lâu rồi mới lỗi."
            ),
            wraplength=470,
        ).pack(anchor="w", padx=10, pady=(0, 10))

        preset = ttk.LabelFrame(self.tab_output, text="Preset & Render")
        preset.pack(side="left", fill="both", expand=True, padx=(6, 0))

        ttk.Label(
            preset,
            text="Preset lưu các thiết lập edit, không lưu thumbnail/folder nhạc/output.",
            wraplength=470,
        ).pack(anchor="w", padx=10, pady=(10, 8))

        row = ttk.Frame(preset)
        row.pack(fill="x", padx=10)
        ttk.Button(row, text="Save Preset JSON", command=self.save_preset_ui).pack(side="left")
        ttk.Button(row, text="Load Preset JSON", command=self.load_preset_ui).pack(side="left", padx=8)

        ttk.Separator(preset).pack(fill="x", padx=10, pady=16)

        ttk.Label(
            preset,
            text=(
                "Output: 720p / 1080p / 1440p, 30 fps, H.264 / AAC 320 kbps.\n"
                "Sau render app tự tạo *_chapters.txt và verify duration/resolution/audio."
            ),
            wraplength=470,
        ).pack(anchor="w", padx=10, pady=(6, 10))

    def _log(self, msg):
        self.ui_queue.put(("log", msg))

    def _set_progress(self, pct, msg):
        self.ui_queue.put(("progress", pct, msg))

    def _drain_queue(self):
        try:
            while True:
                item = self.ui_queue.get_nowait()
                kind = item[0]
                if kind == "log":
                    self.log_text.configure(state="normal")
                    self.log_text.insert("end", item[1] + "\n")
                    self.log_text.see("end")
                    self.log_text.configure(state="disabled")
                elif kind == "progress":
                    self.progress.set(item[1])
                    self.status.set(item[2])
                elif kind == "render_done":
                    self.render_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    def choose_image(self):
        p = filedialog.askopenfilename(
            title="Chọn thumbnail",
            filetypes=[("Image", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All files", "*.*")],
        )
        if p:
            self.image_path.set(p)
            if not self.output_path.get():
                img = Path(p)
                self.output_path.set(str(img.with_name(img.stem + "_V2_2K.mp4")))

    def choose_music(self):
        p = filedialog.askdirectory(title="Chọn folder nhạc")
        if p:
            self.music_folder.set(p)
            self.scan_folder()

    def choose_output(self):
        p = filedialog.asksaveasfilename(
            title="Chọn nơi lưu video",
            defaultextension=".mp4",
            filetypes=[("MP4", "*.mp4")],
            initialfile=Path(self.output_path.get()).name if self.output_path.get() else "music_video_v2.mp4",
        )
        if p:
            self.output_path.set(p)

    def choose_overlay(self):
        p = filedialog.askopenfilename(
            title="Chọn Snow/Rain Overlay MP4",
            filetypes=[("Video", "*.mp4 *.mov *.mkv *.webm"), ("All files", "*.*")],
        )
        if p:
            self.overlay_path.set(p)

    def scan_folder(self):
        folder = Path(self.music_folder.get())
        if not folder.is_dir():
            messagebox.showerror("Lỗi", "Folder nhạc không tồn tại.")
            return
        self.tracks = scan_audio_files(folder)
        # Display relative path to avoid ambiguity for duplicate filenames.
        self.track_display = [str(p.relative_to(folder)) for p in self.tracks]
        for cb in self.combos:
            cb["values"] = self.track_display
        self.clear_slots()
        if len(self.tracks) >= 5:
            self.autofill()
        self.track_count.configure(text=f"Tìm thấy {len(self.tracks)} file audio.")
        self.new_seed()
        self._log(f"Đã quét folder: {folder}")
        self._log(f"Tìm thấy {len(self.tracks)} track.")

    def autofill(self):
        if len(self.track_display) >= 5:
            for i in range(5):
                self.slot_vars[i].set(self.track_display[i])

    def clear_slots(self):
        for v in self.slot_vars:
            v.set("")

    def new_seed(self):
        self.seed.set(random.randint(100000, 999999))
        self._log(f"Playlist seed mới: {self.seed.get()}")

    def duration_seconds(self) -> int:
        mapping = {
            "5 Minutes": 5 * 60,
            "10 Minutes": 10 * 60,
            "20 Minutes": 20 * 60,
            "30 Minutes": 30 * 60,
            "1 Hour": 60 * 60,
            "2 Hours": 2 * 60 * 60,
            "3 Hours": 3 * 60 * 60,
        }
        choice = self.duration_choice.get()
        if choice in mapping:
            return mapping[choice]
        try:
            minutes = int(self.custom_minutes.get())
        except ValueError:
            raise ValueError("Custom minutes phải là số nguyên.")
        if minutes < 1 or minutes > 720:
            raise ValueError("Custom duration cho phép từ 1 đến 720 phút.")
        return minutes * 60

    def _update_custom_minutes_state(self, _event=None):
        """Only allow a manual duration when the Custom option is selected."""
        state = "normal" if self.duration_choice.get() == "Custom" else "disabled"
        self.custom_minutes_entry.configure(state=state)

    def first_five_paths(self) -> list[Path]:
        if len(self.tracks) < 5:
            raise ValueError("Folder cần ít nhất 5 bài.")
        folder = Path(self.music_folder.get())
        vals = [v.get().strip() for v in self.slot_vars]
        if any(not v for v in vals):
            raise ValueError("Bạn phải chọn đủ 5 bài đầu tiên.")
        if len(set(vals)) != 5:
            raise ValueError("5 bài đầu không được trùng.")

        rel_map = {str(p.relative_to(folder)): p for p in self.tracks}
        try:
            return [rel_map[v] for v in vals]
        except KeyError:
            raise ValueError("Danh sách 5 bài không còn khớp folder. Hãy quét lại folder.")

    def current_settings(self) -> RenderSettings:
        mode = self.transition_mode.get()
        try:
            trans_sec = float(self.transition_seconds.get())
        except ValueError:
            trans_sec = 0
        if mode == "None":
            trans_sec = 0

        try:
            target = float(self.loudness_target.get())
        except ValueError:
            target = -14.0

        try:
            seed = int(self.seed.get())
        except Exception:
            seed = random.randint(100000, 999999)
            self.seed.set(seed)

        return RenderSettings(
            duration_seconds=self.duration_seconds(),
            normalization_enabled=self.normalize_enabled.get(),
            loudness_target=target,
            transition_mode=mode,
            transition_seconds=trans_sec,
            visual_motion=self.visual_motion.get(),
            overlay_path=self.overlay_path.get().strip(),
            overlay_mode=self.overlay_mode.get(),
            overlay_opacity=float(self.overlay_opacity.get()),
            encoder=self.encoder.get(),
            output_profile=self.output_profile.get(),
            random_seed=seed,
        )

    def apply_settings(self, s: RenderSettings):
        reverse_duration = {
            300: "5 Minutes",
            600: "10 Minutes",
            1200: "20 Minutes",
            1800: "30 Minutes",
            3600: "1 Hour",
            7200: "2 Hours",
            10800: "3 Hours",
        }
        if s.duration_seconds in reverse_duration:
            self.duration_choice.set(reverse_duration[s.duration_seconds])
        else:
            self.duration_choice.set("Custom")
            self.custom_minutes.set(str(max(1, s.duration_seconds // 60)))
        self._update_custom_minutes_state()

        self.normalize_enabled.set(s.normalization_enabled)
        self.loudness_target.set(str(int(s.loudness_target) if s.loudness_target.is_integer() else s.loudness_target))
        self.transition_mode.set(s.transition_mode)
        self.transition_seconds.set(str(int(s.transition_seconds) if s.transition_seconds.is_integer() else s.transition_seconds))
        self.visual_motion.set(s.visual_motion)
        self.overlay_path.set(s.overlay_path)
        self.overlay_mode.set(s.overlay_mode)
        self.overlay_opacity.set(s.overlay_opacity)
        self.encoder.set(s.encoder)
        self.output_profile.set(s.output_profile)
        self.seed.set(s.random_seed)

    def save_preset_ui(self):
        try:
            s = self.current_settings()
        except Exception as e:
            messagebox.showerror("Lỗi preset", str(e))
            return
        p = filedialog.asksaveasfilename(
            title="Lưu preset",
            defaultextension=".json",
            filetypes=[("JSON Preset", "*.json")],
            initialfile="music_video_preset_v2.json",
        )
        if p:
            save_preset(Path(p), s)
            self._log(f"Đã lưu preset: {p}")

    def load_preset_ui(self):
        p = filedialog.askopenfilename(
            title="Load preset",
            filetypes=[("JSON Preset", "*.json"), ("All files", "*.*")],
        )
        if not p:
            return
        try:
            s = load_preset(Path(p))
            self.apply_settings(s)
            self._log(f"Đã load preset: {p}")
        except Exception as e:
            messagebox.showerror("Lỗi preset", str(e))

    def validate_project(self):
        image = Path(self.image_path.get())
        folder = Path(self.music_folder.get())
        output = Path(self.output_path.get())

        if not image.is_file():
            raise ValueError("Chưa chọn thumbnail hợp lệ.")
        if not folder.is_dir():
            raise ValueError("Chưa chọn folder nhạc hợp lệ.")
        if len(self.tracks) < 5:
            raise ValueError("Folder cần ít nhất 5 file audio.")
        if not output.name:
            raise ValueError("Chưa chọn output.")
        if output.suffix.lower() != ".mp4":
            output = output.with_suffix(".mp4")
            self.output_path.set(str(output))
        output.parent.mkdir(parents=True, exist_ok=True)

        ffmpeg = find_binary("ffmpeg")
        ffprobe = find_binary("ffprobe")
        if not ffmpeg or not ffprobe:
            raise ValueError(
                "Không tìm thấy FFmpeg/FFprobe. Hãy đặt ffmpeg.exe và ffprobe.exe "
                "trong folder tools hoặc cài FFmpeg vào PATH."
            )

        first = self.first_five_paths()
        settings = self.current_settings()

        if settings.overlay_path and not Path(settings.overlay_path).is_file():
            raise ValueError("Overlay path không tồn tại.")

        return image, output, first, settings, ffmpeg, ffprobe

    def preview_playlist(self):
        try:
            image, output, first, settings, ffmpeg, ffprobe = self.validate_project()
        except Exception as e:
            messagebox.showerror("Chưa đủ thông tin", str(e))
            return

        self.status.set("Đang tính preview...")
        self.render_btn.configure(state="disabled")

        def work():
            try:
                durations = {}
                for i, p in enumerate(self.tracks, 1):
                    durations[p] = get_duration(ffprobe, p)
                    self._set_progress(
                        100 * i / max(1, len(self.tracks)),
                        f"Preview: đọc duration {i}/{len(self.tracks)}",
                    )

                seq, starts, cycles = build_sequence(
                    self.tracks,
                    first,
                    durations,
                    settings.duration_seconds,
                    settings.transition_mode,
                    settings.transition_seconds,
                    settings.random_seed,
                )

                self._log("===== PREVIEW PLAYLIST =====")
                self._log(f"Seed: {settings.random_seed}")
                self._log(f"Cycles: {cycles}")
                for i, (p, st) in enumerate(zip(seq, starts), 1):
                    if st >= settings.duration_seconds:
                        break
                    self._log(f"{i:03d}. {fmt_time(st, True)}  {p.name}")
                self._set_progress(0, "Preview xong.")
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Preview lỗi", str(e)))
                self._set_progress(0, "Preview lỗi.")
            finally:
                self.after(0, lambda: self.render_btn.configure(state="normal"))

        threading.Thread(target=work, daemon=True).start()

    def test_nvenc(self):
        ffmpeg = find_binary("ffmpeg")
        if not ffmpeg:
            messagebox.showerror("FFmpeg", "Không tìm thấy FFmpeg.")
            return

        self.status.set("Đang test NVIDIA NVENC...")

        def work():
            ok, msg = check_nvenc(ffmpeg)
            self._log("NVENC TEST: " + msg)
            self.after(
                0,
                lambda: messagebox.showinfo("NVENC OK", msg)
                if ok else messagebox.showerror("NVENC không hoạt động", msg)
            )
            self._set_progress(0, "Sẵn sàng")

        threading.Thread(target=work, daemon=True).start()

    def test_qsv(self):
        ffmpeg = find_binary("ffmpeg")
        if not ffmpeg:
            messagebox.showerror("FFmpeg", "Không tìm thấy FFmpeg.")
            return

        self.status.set("Đang test Intel Quick Sync...")

        def work():
            ok, msg = check_qsv(ffmpeg)
            self._log("INTEL QSV TEST: " + msg)
            self.after(
                0,
                lambda: messagebox.showinfo("Intel Quick Sync OK", msg)
                if ok else messagebox.showerror("Intel Quick Sync không hoạt động", msg),
            )
            self._set_progress(0, "Sẵn sàng")

        threading.Thread(target=work, daemon=True).start()

    def start_render(self):
        try:
            image, output, first, settings, ffmpeg, ffprobe = self.validate_project()
        except Exception as e:
            messagebox.showerror("Chưa đủ thông tin", str(e))
            return

        if self.worker and self.worker.is_alive():
            return

        self.progress.set(0)
        self.render_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.engine = RenderEngine(
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            progress_cb=self._set_progress,
            log_cb=self._log,
        )

        def work():
            try:
                self._log("===== BẮT ĐẦU RENDER V2 =====")
                self._log(f"Thumbnail: {image}")
                self._log(f"Output: {output}")
                self._log(f"Duration: {fmt_time(settings.duration_seconds, True)}")
                self._log(
                    f"Normalization: {'ON ' + str(settings.loudness_target) + ' LUFS' if settings.normalization_enabled else 'OFF'}"
                )
                self._log(
                    f"Transition: {settings.transition_mode} {settings.transition_seconds:g}s"
                )
                self._log(f"Motion: {settings.visual_motion}")
                self._log(f"Overlay: {settings.overlay_path or 'OFF'}")
                self._log(f"Encoder: {settings.encoder}")

                out, chapters, verify = self.engine.render_project(
                    image=image,
                    tracks=self.tracks,
                    first_five=first,
                    output=output,
                    settings=settings,
                )

                checks = (
                    f"Duration: {verify['duration']:.2f}s "
                    f"({'OK' if verify['duration_ok'] else 'CHECK'})\n"
                    f"Resolution: {verify['width']}×{verify['height']} "
                    f"({'OK' if verify['resolution_ok'] else 'CHECK'})\n"
                    f"Video: {verify['video_codec']} | Audio: {verify['audio_codec']} "
                    f"({'OK' if verify['audio_ok'] else 'CHECK'})"
                )
                self._log("===== VERIFY =====")
                self._log(checks.replace("\n", " | "))
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Render hoàn tất",
                        f"Video:\n{out}\n\nChapters:\n{chapters}\n\n{checks}",
                    ),
                )
            except Exception as e:
                self._log("LỖI: " + str(e))
                self.after(0, lambda: messagebox.showerror("Render lỗi", str(e)))
                self._set_progress(0, "Render lỗi / đã hủy.")
            finally:
                self.ui_queue.put(("render_done",))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def cancel_render(self):
        if self.engine:
            self.engine.cancel()
            self.status.set("Đang hủy...")


if __name__ == "__main__":
    App().mainloop()
