from __future__ import annotations

import json
import os
import queue
import random
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from engine import (
    AUDIO_EXTS,
    IMAGE_EXTS,
    RenderEngine,
    RenderSettings,
    check_nvenc,
    check_qsv,
    find_binary,
    fmt_time,
    load_preset,
    save_preset,
)
from flow_loop import FlowLoopEngine
from music_library import SharedMusicCatalog


APP_NAME = "Tool Edit · Tạo video"
APP_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = next(
    (parent for parent in Path(__file__).resolve().parents if (parent / "OPEN_CONTENT_HUB.bat").is_file()),
    Path(__file__).resolve().parents[4],
)
# Keep the exact output location used by the existing editor so old projects stay visible.
OUTPUT_ROOT = WORKSPACE_ROOT / "editer" / "TOOL Video Flow OUTPUT" / "Editor"
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
VIDEO_MODES = {"Flow Loop", "Footage Montage"}
DURATIONS = {
    "30 phút": 30 * 60,
    "1 giờ": 60 * 60,
    "2 giờ": 2 * 60 * 60,
    "3 giờ": 3 * 60 * 60,
    "Tùy chỉnh": None,
}
PROFILES = {
    "720p · 1280 × 720": "720p — Máy yếu (khuyến nghị)",
    "1080p · 1920 × 1080": "1080p — Cân bằng",
    "2K · 2560 × 1440": "1440p — Chất lượng cao",
}


class App(tk.Tk):
    """Simple three-step editor UI backed by the existing render engines."""

    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1500, screen_w - 24)}x{min(950, screen_h - 80)}+12+12")
        self.minsize(min(980, screen_w - 24), min(680, screen_h - 80))
        self.state("zoomed")

        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        self.catalog = SharedMusicCatalog()
        self.music_rows: list[dict] = []
        self.filtered_rows: list[dict] = []
        self.track_labels: dict[str, Path] = {}
        self.tracks: list[Path] = []
        self.flow_clips: list[str] = []
        self.worker: threading.Thread | None = None
        self.engine: RenderEngine | FlowLoopEngine | None = None
        self.ui_queue: queue.Queue = queue.Queue()
        self.current_page = 0
        self._loading_filters = False
        self._loading_tree = False

        channel_names = self.catalog.channel_names()
        preferred_channel = os.environ.get("CONTENT_HUB_CHANNEL_NAME", "").strip()
        default_channel = preferred_channel if preferred_channel in channel_names else (channel_names[0] if channel_names else "Tất cả kênh")

        self.mode = tk.StringVar(value="image")
        self.image_path = tk.StringVar()
        self.channel = tk.StringVar(value=default_channel)
        self.search = tk.StringVar()
        self.artist_filter = tk.StringVar(value="Tất cả nghệ sĩ")
        self.genre_filter = tk.StringVar(value="Tất cả thể loại")
        self.instrument_filter = tk.StringVar(value="Tất cả nhạc cụ")
        self.vocal_filter = tk.StringVar(value="Tất cả")
        self.mood_filter = tk.StringVar(value="Tất cả không khí")
        self.status_filter = tk.StringVar(value="Đã kiểm tra")
        self.only_selected = tk.BooleanVar(value=False)
        self.include_music = tk.BooleanVar(value=True)
        self.duration_choice = tk.StringVar(value="1 giờ")
        self.custom_minutes = tk.StringVar(value="60")
        self.output_profile = tk.StringVar(value="720p · 1280 × 720")
        self.output_path = tk.StringVar(value=str(OUTPUT_ROOT / "video_moi.mp4"))
        self.encoder = tk.StringVar(value="Intel Quick Sync (h264_qsv)")
        self.crossfade = tk.StringVar(value="1.0")
        self.flow_trim_start = tk.StringVar(value="0")
        self.flow_trim_end = tk.StringVar(value="0")
        self.normalize = tk.BooleanVar(value=True)
        self.loudness = tk.StringVar(value="-16")
        self.transition_mode = tk.StringVar(value="Crossfade")
        self.transition_seconds = tk.StringVar(value="2")
        self.visual_motion = tk.StringVar(value="Slow Zoom")
        self.overlay_path = tk.StringVar()
        self.overlay_mode = tk.StringVar(value="Screen")
        self.overlay_opacity = tk.DoubleVar(value=0.45)
        self.seed = tk.IntVar(value=random.randint(100000, 999999))
        self.status = tk.StringVar(value="Sẵn sàng")
        self.progress = tk.DoubleVar(value=0)
        self.first_five_vars = [tk.StringVar() for _ in range(5)]

        self._build_ui(channel_names)
        self._refresh_music()
        self._refresh_flow_dates()
        self.after(100, self._drain_queue)

    def _build_ui(self, channel_names: list[str]):
        self.style = ttk.Style(self)
        self.style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"), padding=(14, 8))
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="TOOL EDIT", font=("Segoe UI", 22, "bold")).pack(side="left")
        ttk.Label(header, text="Tạo video nền bằng Loop hoặc footage + nhạc từ Music Manager").pack(side="left", padx=18)
        ttk.Button(header, text="Content Hub", command=self.open_content_hub).pack(side="right", padx=4)
        ttk.Button(header, text="Music Manager", command=self.open_music_manager).pack(side="right", padx=4)
        ttk.Button(header, text="Mở dự án", command=self.load_project_ui).pack(side="right", padx=4)
        ttk.Button(header, text="Lưu dự án", command=self.save_project_ui).pack(side="right", padx=4)

        self.step_label = ttk.Label(root, text="BƯỚC 1 / 3  ·  Nguồn hình ảnh", font=("Segoe UI", 11, "bold"))
        self.step_label.grid(row=1, column=0, sticky="w", pady=(12, 4))
        self.pages_host = ttk.Frame(root)
        self.pages_host.grid(row=2, column=0, sticky="nsew")
        self.pages_host.rowconfigure(0, weight=1)
        self.pages_host.columnconfigure(0, weight=1)

        self.pages = [ttk.Frame(self.pages_host), ttk.Frame(self.pages_host), ttk.Frame(self.pages_host)]
        for page in self.pages:
            page.grid(row=0, column=0, sticky="nsew")
        self._build_source_page(self.pages[0])
        self._build_music_page(self.pages[1], channel_names)
        self._build_output_page(self.pages[2])

        footer = ttk.Frame(root)
        footer.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(1, weight=1)
        self.back_btn = ttk.Button(footer, text="← Quay lại", command=lambda: self.show_page(self.current_page - 1))
        self.back_btn.grid(row=0, column=0, sticky="w")
        self.status_label = ttk.Label(footer, textvariable=self.status)
        self.status_label.grid(row=0, column=1, sticky="w", padx=12)
        self.cancel_btn = ttk.Button(footer, text="Hủy render", command=self.cancel_render, state="disabled")
        self.cancel_btn.grid(row=0, column=2, sticky="e", padx=(0, 8))
        self.next_btn = ttk.Button(footer, text="Tiếp tục →", command=self.next_page, style="Accent.TButton")
        self.next_btn.grid(row=0, column=3, sticky="e", ipadx=18, ipady=6)
        self.progress_bar = ttk.Progressbar(footer, variable=self.progress, maximum=100)
        self.progress_bar.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0))

        self.show_page(0)

    def _build_source_page(self, page: ttk.Frame):
        page.columnconfigure(0, weight=1)
        page.rowconfigure(4, weight=1)
        ttk.Label(page, text="Tạo video nền dài theo từng bước", font=("Segoe UI", 17, "bold")).grid(
            row=0, column=0, sticky="w", pady=(10, 8)
        )
        self.welcome_text = ttk.Label(
            page,
            text="Ghép nhạc từ Music Manager với ảnh hoặc video. Video xuất đúng khung ngang 16:9.",
            font=("Segoe UI", 12),
        )
        self.welcome_text.grid(row=1, column=0, sticky="w", pady=(8, 14))
        self.start_video_button = ttk.Button(
            page, text="Tạo video mới", command=self._start_video_flow, style="Accent.TButton"
        )
        self.start_video_button.grid(row=2, column=0, sticky="w", ipadx=20, ipady=10)
        choices = ttk.Frame(page)
        self.source_choices = choices
        choices.grid(row=1, column=0, sticky="ew")
        options = [
            ("image", "Ảnh nền loop", "Một ảnh, có thể thêm chuyển động hoặc overlay."),
            ("loop", "Video Loop", "Các clip cùng bối cảnh, nối vòng mượt từ cuối về đầu."),
            ("footage", "Ghép footage", "Nối nhiều cảnh khác nhau làm nền cho video dài."),
        ]
        for col, (value, title, hint) in enumerate(options):
            choices.columnconfigure(col, weight=1)
            card = ttk.LabelFrame(choices, text=title, padding=10)
            card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
            ttk.Radiobutton(card, text="Chọn cách này", variable=self.mode, value=value,
                            command=self._update_source_mode).pack(anchor="w")
            ttk.Label(card, text=hint, wraplength=270).pack(anchor="w", pady=(6, 0))

        self.source_image_box = ttk.LabelFrame(page, text="Ảnh nền", padding=12)
        self.source_video_box = ttk.LabelFrame(page, text="Danh sách clip", padding=12)
        self.source_image_box.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        self.source_video_box.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        self.source_image_box.columnconfigure(0, weight=1)
        ttk.Label(self.source_image_box, text="Chọn ảnh làm nền 16:9. Ảnh khác tỷ lệ sẽ được căn giữa, không kéo méo.").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        ttk.Entry(self.source_image_box, textvariable=self.image_path).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(self.source_image_box, text="Chọn ảnh…", command=self.choose_image).grid(row=1, column=1)

        self.source_video_box.columnconfigure(0, weight=1)
        self.source_video_box.rowconfigure(1, weight=1)
        self.mode_hint = ttk.Label(self.source_video_box, text="Clip nguồn sẽ được chuẩn hóa 16:9, giữ nguyên khung hình và bỏ tiếng gốc.")
        self.mode_hint.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        list_frame = ttk.Frame(self.source_video_box)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1); list_frame.columnconfigure(0, weight=1)
        self.clip_list = tk.Listbox(list_frame, height=10, selectmode="extended", exportselection=False)
        self.clip_list.grid(row=0, column=0, sticky="nsew")
        clip_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.clip_list.yview)
        clip_scroll.grid(row=0, column=1, sticky="ns")
        self.clip_list.configure(yscrollcommand=clip_scroll.set)
        clip_buttons = ttk.Frame(self.source_video_box)
        clip_buttons.grid(row=1, column=1, sticky="ns", padx=(10, 0))
        ttk.Button(clip_buttons, text="Thêm video…", command=self.add_video_files).pack(fill="x", pady=3)
        ttk.Button(clip_buttons, text="Thêm thư mục…", command=self.add_video_folder).pack(fill="x", pady=3)
        ttk.Button(clip_buttons, text="Nạp từ Flow theo ngày", command=self.add_flow_day).pack(fill="x", pady=3)
        ttk.Button(clip_buttons, text="↑ Lên", command=lambda: self.move_clip(-1)).pack(fill="x", pady=(14, 3))
        ttk.Button(clip_buttons, text="↓ Xuống", command=lambda: self.move_clip(1)).pack(fill="x", pady=3)
        ttk.Button(clip_buttons, text="Bỏ khỏi danh sách", command=self.remove_clips).pack(fill="x", pady=(14, 3))

        flow_row = ttk.Frame(self.source_video_box)
        flow_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(flow_row, text="Video Flow theo ngày:").pack(side="left")
        self.flow_date_var = tk.StringVar()
        self.flow_date_combo = ttk.Combobox(flow_row, textvariable=self.flow_date_var, state="readonly", width=15)
        self.flow_date_combo.pack(side="left", padx=8)
        ttk.Button(flow_row, text="Làm mới", command=self._refresh_flow_dates).pack(side="left")
        ttk.Label(flow_row, text="Hòa trộn cảnh (giây):").pack(side="left", padx=(20, 6))
        ttk.Combobox(flow_row, textvariable=self.crossfade, state="readonly", values=("0.5", "0.8", "1.0", "1.5", "2.0", "3.0"), width=7).pack(side="left")
        ttk.Label(flow_row, text="Cắt đầu / cuối clip:").pack(side="left", padx=(18, 6))
        ttk.Entry(flow_row, textvariable=self.flow_trim_start, width=5).pack(side="left")
        ttk.Label(flow_row, text="/ ").pack(side="left")
        ttk.Entry(flow_row, textvariable=self.flow_trim_end, width=5).pack(side="left")
        ttk.Label(flow_row, text="giây").pack(side="left", padx=(4, 0))
        ttk.Label(self.source_video_box, text="Tối đa 24 clip mỗi dự án. Bạn có thể đổi thứ tự trước khi dựng; tiếng gốc clip không dùng.",
                  foreground="#555").grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._update_source_mode()
        self.source_choices.grid_remove()
        self.source_image_box.grid_remove()
        self.source_video_box.grid_remove()

    def _start_video_flow(self):
        self.welcome_text.grid_remove()
        self.start_video_button.grid_remove()
        self.next_btn.grid()
        self.source_choices.grid(row=1, column=0, sticky="ew")
        if self.mode.get() == "image":
            self.source_image_box.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        else:
            self.source_video_box.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        self.step_label.configure(text="BƯỚC 1 / 3  ·  Chọn kiểu video và nguồn hình")

    def _build_music_page(self, page: ttk.Frame, channel_names: list[str]):
        page.columnconfigure(0, weight=1); page.rowconfigure(2, weight=1)
        ttk.Label(page, text="Chọn playlist nhạc", font=("Segoe UI", 17, "bold")).grid(row=0, column=0, sticky="w", pady=(10, 4))
        ttk.Label(page, text="Mặc định dùng playlist của kênh. Bộ lọc giúp thu hẹp danh sách; bài chưa kiểm tra bị loại trừ.").grid(
            row=1, column=0, sticky="w", pady=(0, 8)
        )
        filters = ttk.LabelFrame(page, text="Lọc kho Music Manager", padding=10)
        filters.grid(row=2, column=0, sticky="nsew")
        filters.columnconfigure(1, weight=1); filters.columnconfigure(3, weight=1); filters.rowconfigure(3, weight=1)
        ttk.Label(filters, text="Kênh playlist").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.channel_combo = ttk.Combobox(filters, textvariable=self.channel, state="readonly",
                                          values=("Tất cả kênh", *channel_names))
        self.channel_combo.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=4)
        self.channel_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_music())
        ttk.Button(filters, text="Làm mới kho", command=self._refresh_music).grid(row=0, column=2, sticky="w", pady=4)
        status_combo = ttk.Combobox(filters, textvariable=self.status_filter, state="readonly",
                                    values=("Đã kiểm tra", "Tất cả trạng thái", "Chưa kiểm tra", "Cần ghi công", "Không cần ghi công"),
                                    width=22)
        status_combo.grid(row=0, column=3, sticky="e", pady=4)
        status_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_music())

        ttk.Label(filters, text="Tìm tên bài / nghệ sĩ").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        search_entry = ttk.Entry(filters, textvariable=self.search)
        search_entry.grid(row=1, column=1, sticky="ew", padx=(0, 14), pady=4)
        ttk.Label(filters, text="Nghệ sĩ").grid(row=1, column=2, sticky="w", padx=(0, 8), pady=4)
        self.artist_combo = ttk.Combobox(filters, textvariable=self.artist_filter, state="readonly")
        self.artist_combo.grid(row=1, column=3, sticky="ew", pady=4)

        facets = ttk.Frame(filters)
        facets.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(4, 8))
        for col in range(8): facets.columnconfigure(col, weight=1 if col % 2 else 0)
        facet_specs = [
            ("Thể loại", self.genre_filter, "Tất cả thể loại", "genre"),
            ("Nhạc cụ", self.instrument_filter, "Tất cả nhạc cụ", "instrument"),
            ("Giọng hát", self.vocal_filter, "Tất cả", "vocal"),
            ("Không khí", self.mood_filter, "Tất cả không khí", "mood"),
        ]
        self.facet_combos = {}
        for idx, (label, variable, all_label, key) in enumerate(facet_specs):
            ttk.Label(facets, text=label).grid(row=0, column=idx * 2, sticky="w", padx=(0, 6))
            combo = ttk.Combobox(facets, textvariable=variable, state="readonly", width=18, values=(all_label,))
            combo.grid(row=0, column=idx * 2 + 1, sticky="ew", padx=(0, 12))
            combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_music())
            self.facet_combos[key] = combo
        self.artist_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_music())
        self.search.trace_add("write", lambda *_: self._refresh_music())
        self.status_filter.trace_add("write", lambda *_: self._refresh_music())

        table_frame = ttk.Frame(filters)
        table_frame.grid(row=3, column=0, columnspan=4, sticky="nsew")
        table_frame.rowconfigure(0, weight=1); table_frame.columnconfigure(0, weight=1)
        cols = ("title", "artist", "status", "genre", "instrument", "vocal", "mood")
        self.music_table = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended")
        for col, label, width in zip(cols, ("Tên bài", "Nghệ sĩ", "Ghi công", "Thể loại", "Nhạc cụ", "Giọng hát", "Không khí"),
                                     (250, 180, 170, 130, 130, 110, 150)):
            self.music_table.heading(col, text=label); self.music_table.column(col, width=width, minwidth=75, stretch=True)
        ybar = ttk.Scrollbar(table_frame, orient="vertical", command=self.music_table.yview)
        xbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.music_table.xview)
        self.music_table.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.music_table.grid(row=0, column=0, sticky="nsew"); ybar.grid(row=0, column=1, sticky="ns"); xbar.grid(row=1, column=0, sticky="ew")
        self.music_table.bind("<<TreeviewSelect>>", lambda _e: self._sync_music_selection())
        self.music_table.bind("<Double-1>", lambda _e: self.preview_selected_track())

        music_actions = ttk.Frame(filters)
        music_actions.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(music_actions, text="Chỉ dùng những bài đang chọn trong bảng", variable=self.only_selected,
                        command=self._sync_music_selection).pack(side="left")
        self.music_count = ttk.Label(music_actions, text="")
        self.music_count.pack(side="left", padx=12)
        ttk.Button(music_actions, text="Nghe thử bài đang chọn", command=self.preview_selected_track).pack(side="right")
        ttk.Button(music_actions, text="Mở Music Manager để phân loại", command=self.open_music_manager).pack(side="right", padx=6)
        self.include_music_check = ttk.Checkbutton(page, text="Ghép playlist nhạc với video", variable=self.include_music)
        self.include_music_check.grid(row=4, column=0, sticky="w", pady=(8, 0))
        self._update_source_mode()

        start_frame = ttk.LabelFrame(page, text="Tuỳ chọn: ghim 5 bài mở đầu", padding=8)
        start_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(start_frame, text="Nếu chưa đổi, Editor tự lấy 5 bài đầu của danh sách đã lọc.").grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 4))
        self.first_five_combos = []
        for i, var in enumerate(self.first_five_vars):
            ttk.Label(start_frame, text=f"{i + 1}.").grid(row=1, column=i * 2, sticky="e", padx=(4, 3))
            combo = ttk.Combobox(start_frame, textvariable=var, state="readonly", width=24)
            combo.grid(row=1, column=i * 2 + 1, sticky="ew", padx=(0, 8))
            self.first_five_combos.append(combo)

    def _build_output_page(self, page: ttk.Frame):
        page.columnconfigure(0, weight=1); page.rowconfigure(4, weight=1)
        ttk.Label(page, text="Thời lượng và chất lượng", font=("Segoe UI", 17, "bold")).grid(row=0, column=0, sticky="w", pady=(10, 8))
        basics = ttk.LabelFrame(page, text="Thiết lập video", padding=14)
        basics.grid(row=1, column=0, sticky="ew")
        basics.columnconfigure(1, weight=1); basics.columnconfigure(3, weight=1)
        ttk.Label(basics, text="Thời lượng").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        duration = ttk.Combobox(basics, textvariable=self.duration_choice, state="readonly", values=tuple(DURATIONS), width=20)
        duration.grid(row=0, column=1, sticky="ew", padx=(0, 24), pady=6)
        duration.bind("<<ComboboxSelected>>", self._duration_changed)
        ttk.Label(basics, text="Phút tuỳ chỉnh").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=6)
        self.custom_minutes_entry = ttk.Entry(basics, textvariable=self.custom_minutes, width=12)
        self.custom_minutes_entry.grid(row=0, column=3, sticky="w", pady=6)
        self._duration_changed()
        ttk.Label(basics, text="Độ phân giải").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Combobox(basics, textvariable=self.output_profile, state="readonly", values=tuple(PROFILES), width=24).grid(
            row=1, column=1, sticky="ew", padx=(0, 24), pady=6
        )
        ttk.Label(basics, text="Tỷ lệ khung hình").grid(row=1, column=2, sticky="w", padx=(0, 8), pady=6)
        ttk.Label(basics, text="16:9 · tự căn khung, không kéo méo hình").grid(row=1, column=3, sticky="w", pady=6)
        ttk.Label(basics, text="Lưu video vào").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(basics, textvariable=self.output_path).grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 8), pady=6)
        ttk.Button(basics, text="Chọn nơi lưu…", command=self.choose_output).grid(row=2, column=3, sticky="w", pady=6)

        advanced = ttk.LabelFrame(page, text="Nâng cao (có thể để mặc định)", padding=14)
        advanced.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        advanced.columnconfigure(1, weight=1); advanced.columnconfigure(3, weight=1)
        ttk.Label(advanced, text="Encoder").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Combobox(advanced, textvariable=self.encoder, state="readonly", values=(
            "Intel Quick Sync (h264_qsv)", "CPU (libx264)", "NVIDIA NVENC"
        )).grid(row=0, column=1, sticky="ew", padx=(0, 18), pady=5)
        ttk.Checkbutton(advanced, text="Chuẩn hoá âm lượng", variable=self.normalize).grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Combobox(advanced, textvariable=self.loudness, state="readonly", values=("-14", "-16", "-18"), width=8).grid(row=0, column=3, sticky="w")
        ttk.Label(advanced, text="Chuyển bài nhạc").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Combobox(advanced, textvariable=self.transition_mode, state="readonly", values=("Crossfade", "Fade", "None")).grid(
            row=1, column=1, sticky="ew", padx=(0, 18), pady=5
        )
        ttk.Label(advanced, text="Thời gian chuyển (giây)").grid(row=1, column=2, sticky="w", padx=(0, 8), pady=5)
        ttk.Combobox(advanced, textvariable=self.transition_seconds, state="readonly", values=("1", "2", "3", "5")).grid(
            row=1, column=3, sticky="w", pady=5
        )
        ttk.Label(advanced, text="Chuyển động ảnh").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Combobox(advanced, textvariable=self.visual_motion, state="readonly", values=("Static", "Slow Zoom", "Pan Left-Right", "Pan Up-Down", "Cinematic Drift")).grid(
            row=2, column=1, sticky="ew", padx=(0, 18), pady=5
        )
        ttk.Label(advanced, text="Overlay tuyết / mưa").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Entry(advanced, textvariable=self.overlay_path).grid(row=3, column=1, sticky="ew", padx=(0, 8), pady=5)
        ttk.Button(advanced, text="Chọn MP4…", command=self.choose_overlay).grid(row=3, column=2, sticky="w", pady=5)
        ttk.Combobox(advanced, textvariable=self.overlay_mode, state="readonly", values=("Screen", "Alpha"), width=10).grid(row=3, column=3, sticky="w", pady=5)
        ttk.Label(advanced, text="Độ trong overlay").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=5)
        tk.Scale(advanced, variable=self.overlay_opacity, from_=0.05, to=1.0, resolution=0.05, orient="horizontal").grid(
            row=4, column=1, sticky="ew", padx=(0, 18), pady=5
        )
        ttk.Button(advanced, text="Lưu preset…", command=self.save_preset_ui).grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Button(advanced, text="Mở preset…", command=self.load_preset_ui).grid(row=5, column=1, sticky="w", padx=(0, 18), pady=(8, 0))
        ttk.Button(advanced, text="Test Intel Quick Sync", command=self.test_qsv).grid(row=5, column=2, sticky="w", pady=(8, 0))
        ttk.Button(advanced, text="Test NVIDIA", command=self.test_nvenc).grid(row=5, column=3, sticky="w", pady=(8, 0))

        self.summary_frame = ttk.LabelFrame(page, text="Kiểm tra trước khi tạo", padding=12)
        self.summary_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.summary = ttk.Label(self.summary_frame, text="Bấm Tiếp tục để xem tóm tắt dự án.", justify="left")
        self.summary.pack(anchor="w")
        log_frame = ttk.LabelFrame(page, text="Tiến trình", padding=8)
        log_frame.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        log_frame.columnconfigure(0, weight=1); log_frame.rowconfigure(1, weight=1)
        self.log_text = tk.Text(log_frame, height=8, state="disabled", wrap="word", font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)

    def show_page(self, index: int):
        self.current_page = max(0, min(2, index))
        is_welcome = self.current_page == 0 and not self.source_choices.winfo_manager()
        if is_welcome:
            self.welcome_text.grid()
            self.start_video_button.grid()
            self.next_btn.grid_remove()
        else:
            self.next_btn.grid()
        self.pages[self.current_page].tkraise()
        labels = ("Nguồn hình ảnh", "Chọn nhạc", "Thời lượng và xuất")
        if not is_welcome:
            self.step_label.configure(text=f"BƯỚC {self.current_page + 1} / 3  ·  {labels[self.current_page]}")
        else:
            self.step_label.configure(text="BẮT ĐẦU  ·  Tạo video mới")
        self.back_btn.configure(state="normal" if self.current_page else "disabled")
        self.next_btn.configure(text="TẠO VIDEO" if self.current_page == 2 else "Tiếp tục →")
        if self.current_page == 2:
            self.update_summary()

    def next_page(self):
        if self.current_page < 2:
            if self.current_page == 0 and not self._validate_sources(show_errors=True):
                return
            if self.current_page == 1 and not self._validate_music(show_errors=True):
                return
            self.show_page(self.current_page + 1)
        else:
            self.start_render()

    def _update_source_mode(self):
        mode = self.mode.get()
        if mode == "image":
            self.source_image_box.tkraise()
        else:
            self.source_video_box.tkraise()
            if mode == "loop":
                self.mode_hint.configure(text="Chọn clip cùng bối cảnh; Editor nối vòng cuối → đầu. Có thể nạp clip đã xuất từ Google Flow.")
            else:
                self.mode_hint.configure(text="Chọn các cảnh theo thứ tự muốn phát; Editor nối thành một vòng footage dài rồi ghép nhạc.")
        if mode == "image" and not self.image_path.get():
            self.status.set("Chọn một ảnh nền để tiếp tục.")
        else:
            self.status.set("Sẵn sàng")
        if hasattr(self, "include_music_check"):
            if mode == "image":
                self.include_music.set(True)
                self.include_music_check.configure(state="disabled")
            else:
                self.include_music_check.configure(state="normal")

    def _duration_changed(self, _event=None):
        state = "normal" if self.duration_choice.get() == "Tùy chỉnh" else "disabled"
        self.custom_minutes_entry.configure(state=state)

    def choose_image(self):
        path = filedialog.askopenfilename(title="Chọn ảnh nền", filetypes=[("Ảnh", "*.jpg *.jpeg *.png *.webp *.bmp")])
        if path:
            self.image_path.set(path)
            self._set_default_output(Path(path).stem)

    def add_video_files(self):
        paths = filedialog.askopenfilenames(title="Chọn video", filetypes=[("Video", "*.mp4 *.mov *.mkv *.webm *.avi *.m4v")])
        self._append_clips(paths)

    def add_video_folder(self):
        folder = filedialog.askdirectory(title="Chọn thư mục video")
        if not folder:
            return
        paths = sorted((p for p in Path(folder).rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS),
                       key=lambda p: str(p).casefold())
        self._append_clips(str(p) for p in paths)

    def _append_clips(self, paths):
        for raw in paths:
            path = str(Path(raw).resolve())
            if path not in self.flow_clips:
                self.flow_clips.append(path)
        if len(self.flow_clips) > 24:
            self.flow_clips = self.flow_clips[:24]
            messagebox.showinfo("Giới hạn clip", "Mỗi vòng hỗ trợ tối đa 24 clip; danh sách đã lấy 24 clip đầu.", parent=self)
        if self.flow_clips:
            if self.mode.get() == "image":
                self.mode.set("footage")
            self._set_default_output(Path(self.flow_clips[0]).stem)
        self._refresh_clip_list()
        self._update_source_mode()

    def _refresh_clip_list(self):
        self.clip_list.delete(0, "end")
        for index, clip in enumerate(self.flow_clips, 1):
            self.clip_list.insert("end", f"{index:02d}. {Path(clip).name}")

    def remove_clips(self):
        for index in reversed(self.clip_list.curselection()):
            del self.flow_clips[index]
        self._refresh_clip_list()

    def move_clip(self, delta: int):
        selected = self.clip_list.curselection()
        if len(selected) != 1:
            return
        old = selected[0]; new = old + delta
        if 0 <= new < len(self.flow_clips):
            self.flow_clips[old], self.flow_clips[new] = self.flow_clips[new], self.flow_clips[old]
            self._refresh_clip_list(); self.clip_list.selection_set(new)

    def _flow_video_root(self) -> Path:
        candidates = [
            WORKSPACE_ROOT / "TOOL Video Flow OUTPUT" / "Video",
            WORKSPACE_ROOT / "TOOL Video Flow" / "OUTPUT" / "Video",
            WORKSPACE_ROOT.parent / "TOOL Video Flow OUTPUT" / "Video",
        ]
        return next((path for path in candidates if path.is_dir()), candidates[0])

    def _refresh_flow_dates(self):
        root = self._flow_video_root()
        dates = sorted((p.name for p in root.iterdir() if p.is_dir()), reverse=True) if root.is_dir() else []
        self.flow_date_combo.configure(values=dates)
        if dates and self.flow_date_var.get() not in dates:
            self.flow_date_var.set(dates[0])
        elif not dates:
            self.flow_date_var.set("")

    def add_flow_day(self):
        folder = self._flow_video_root() / self.flow_date_var.get()
        if not self.flow_date_var.get() or not folder.is_dir():
            messagebox.showinfo("Video Flow", "Chưa có thư mục clip Flow cho ngày này.", parent=self)
            return
        paths = sorted((p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS),
                       key=lambda p: (p.parent.name.casefold(), p.name.casefold()))
        self._append_clips(str(p) for p in paths)
        if paths:
            self.mode.set("loop"); self._update_source_mode()
            self.status.set(f"Đã nạp {min(len(paths), 24)} clip từ Flow ngày {self.flow_date_var.get()}.")

    def _set_default_output(self, stem: str):
        if not self.output_path.get() or Path(self.output_path.get()).name == "video_moi.mp4":
            safe_stem = "".join(c if c.isalnum() or c in "-_ " else "_" for c in stem).strip() or "video_moi"
            self.output_path.set(str(OUTPUT_ROOT / f"{safe_stem}_video.mp4"))

    def _refresh_music(self):
        if not hasattr(self, "music_table") or self._loading_filters:
            return
        self._loading_filters = True
        channel = self.channel.get()
        self.music_rows = self.catalog.library_rows("" if channel == "Tất cả kênh" else channel)
        for key, variable, all_label in (
            ("artist", self.artist_filter, "Tất cả nghệ sĩ"),
            ("genre", self.genre_filter, "Tất cả thể loại"),
            ("instrument", self.instrument_filter, "Tất cả nhạc cụ"),
            ("vocal", self.vocal_filter, "Tất cả"),
            ("mood", self.mood_filter, "Tất cả không khí"),
        ):
            values = sorted({value for row in self.music_rows for value in self._split_values(row.get(key)) if value}, key=str.casefold)
            combo = self.artist_combo if key == "artist" else self.facet_combos[key]
            combo.configure(values=(all_label, *values))
            if variable.get() not in (all_label, *values):
                variable.set(all_label)
        self._loading_filters = False
        self._apply_music_filters()

    @staticmethod
    def _split_values(value) -> list[str]:
        return [part.strip() for part in str(value or "").split(",") if part.strip()]

    def _apply_music_filters(self):
        query = self.search.get().strip().casefold()
        artist = self.artist_filter.get()
        genre = self.genre_filter.get()
        instrument = self.instrument_filter.get()
        vocal = self.vocal_filter.get()
        mood = self.mood_filter.get()
        status = self.status_filter.get()
        result = []
        for row in self.music_rows:
            if query and query not in f"{row.get('title', '')} {row.get('artist', '')}".casefold():
                continue
            if artist != "Tất cả nghệ sĩ" and row.get("artist") != artist:
                continue
            if genre != "Tất cả thể loại" and genre not in self._split_values(row.get("genre")):
                continue
            if instrument != "Tất cả nhạc cụ" and instrument not in self._split_values(row.get("instrument")):
                continue
            if vocal != "Tất cả" and vocal not in self._split_values(row.get("vocal")):
                continue
            if mood != "Tất cả không khí" and mood not in self._split_values(row.get("mood")):
                continue
            track_status = row.get("status") or "Chưa kiểm tra"
            if status == "Đã kiểm tra" and track_status == "Chưa kiểm tra":
                continue
            if status == "Chưa kiểm tra" and track_status != "Chưa kiểm tra":
                continue
            if status == "Cần ghi công" and track_status != "Cần ghi công":
                continue
            if status == "Không cần ghi công" and track_status != "Không cần ghi công":
                continue
            result.append(row)
        self.filtered_rows = result
        self._loading_tree = True
        self.music_table.delete(*self.music_table.get_children())
        for row in result:
            self.music_table.insert("", "end", iid=row["id"], values=(
                row.get("title", ""), row.get("artist", ""), row.get("status", "Chưa kiểm tra"),
                row.get("genre", ""), row.get("instrument", ""), row.get("vocal", ""), row.get("mood", ""),
            ))
        self._loading_tree = False
        self._sync_music_selection()

    def _sync_music_selection(self):
        if not hasattr(self, "music_table"):
            return
        if self.only_selected.get():
            selected = set(self.music_table.selection())
            selected_rows = [row for row in self.filtered_rows if str(row["id"]) in selected]
        else:
            selected_rows = self.filtered_rows
        self.tracks = [Path(row["path"]) for row in selected_rows if Path(row["path"]).is_file()]
        labels = []
        self.track_labels = {}
        for row in selected_rows:
            path = Path(row["path"])
            label = f"{row.get('title', path.stem)} — {row.get('artist', '')}"
            if label in self.track_labels:
                label += f" [{path.parent.name}]"
            self.track_labels[label] = path
            labels.append(label)
        for combo, var in zip(self.first_five_combos, self.first_five_vars):
            combo.configure(values=labels)
            if var.get() not in labels:
                var.set("")
        current = [var.get() for var in self.first_five_vars if var.get()]
        if len(self.tracks) >= 5 and len(current) < 5:
            for var, label in zip(self.first_five_vars, labels):
                var.set(label)
        self.music_count.configure(text=f"{len(self.tracks)} bài sẽ dùng · {len(self.filtered_rows)} kết quả đang lọc")

    def preview_selected_track(self):
        selected = self.music_table.selection()
        row = next((item for item in self.filtered_rows if str(item["id"]) in selected), None)
        if row is None:
            messagebox.showinfo("Nghe thử", "Chọn một bài trong danh sách trước.", parent=self)
            return
        try:
            os.startfile(str(row["path"]))
        except OSError as exc:
            messagebox.showerror("Không mở được nhạc", str(exc), parent=self)

    def _validate_music(self, show_errors: bool = False) -> bool:
        valid = len(self.tracks) >= 5
        if not valid and show_errors:
            message = "Playlist cần ít nhất 5 bài. Hãy chọn kênh khác, bỏ bớt bộ lọc hoặc phân loại thêm nhạc trong Music Manager."
            messagebox.showinfo("Playlist chưa đủ bài", message, parent=self)
        return valid

    def duration_seconds(self) -> int:
        choice = self.duration_choice.get()
        if DURATIONS.get(choice) is not None:
            return int(DURATIONS[choice])
        try:
            minutes = int(self.custom_minutes.get())
        except ValueError as exc:
            raise ValueError("Thời lượng tuỳ chỉnh phải là số phút nguyên.") from exc
        if not 1 <= minutes <= 720:
            raise ValueError("Thời lượng tuỳ chỉnh phải từ 1 đến 720 phút.")
        return minutes * 60

    def first_five_paths(self) -> list[Path]:
        labels = [var.get() for var in self.first_five_vars]
        if len(labels) != 5 or any(not value for value in labels) or len(set(labels)) != 5:
            raise ValueError("Chọn đủ 5 bài mở đầu khác nhau.")
        try:
            return [self.track_labels[value] for value in labels]
        except KeyError as exc:
            raise ValueError("Bộ lọc nhạc đã thay đổi. Hãy kiểm tra lại 5 bài mở đầu.") from exc

    def current_settings(self) -> RenderSettings:
        try:
            transition_seconds = float(self.transition_seconds.get())
            crossfade = float(self.crossfade.get())
            trim_start = float(self.flow_trim_start.get())
            trim_end = float(self.flow_trim_end.get())
            seed = int(self.seed.get())
            loudness = float(self.loudness.get())
        except ValueError as exc:
            raise ValueError("Một thiết lập nâng cao chưa đúng định dạng.") from exc
        if self.transition_mode.get() == "None":
            transition_seconds = 0
        source_mode = {"image": "Thumbnail", "loop": "Flow Loop", "footage": "Footage Montage"}[self.mode.get()]
        return RenderSettings(
            duration_seconds=self.duration_seconds(),
            normalization_enabled=self.normalize.get(),
            loudness_target=loudness,
            transition_mode=self.transition_mode.get(),
            transition_seconds=transition_seconds,
            encoder=self.encoder.get(),
            output_profile=PROFILES[self.output_profile.get()],
            random_seed=seed,
            visual_motion=self.visual_motion.get(),
            overlay_path=self.overlay_path.get().strip(),
            overlay_mode=self.overlay_mode.get(),
            overlay_opacity=float(self.overlay_opacity.get()),
            visual_source=source_mode,
            flow_clips=list(self.flow_clips),
            flow_crossfade=crossfade,
            flow_trim_start=trim_start,
            flow_trim_end=trim_end,
            flow_music_enabled=self.include_music.get(),
            channel_profile=self.channel.get(),
            filter_channel_music=self.channel.get() != "Tất cả kênh",
        )

    def update_summary(self):
        mode_name = {"image": "Ảnh nền loop", "loop": "Video Loop", "footage": "Ghép footage"}[self.mode.get()]
        channel = self.channel.get()
        count = len(self.tracks) if self.include_music.get() else 0
        try:
            duration_text = fmt_time(self.duration_seconds(), True)
        except ValueError:
            duration_text = "Chưa hợp lệ · kiểm tra thời lượng"
        summary = (
            f"Kiểu video: {mode_name}\n"
            f"Nguồn: {Path(self.image_path.get()).name if self.mode.get() == 'image' else f'{len(self.flow_clips)} clip'}\n"
            f"Nhạc: {count} bài · Kênh: {channel}\n"
            f"Thời lượng: {duration_text} · 16:9 · {self.output_profile.get()}\n"
            f"Tệp xuất: {self.output_path.get()}"
        )
        if not self.include_music.get():
            summary = summary.replace(f"Nhạc: {count} bài", "Nhạc: tắt")
        self.summary.configure(text=summary)

    def _render_inputs(self):
        if not self._validate_sources(show_errors=True):
            return None
        needs_music = self.include_music.get()
        if needs_music and not self._validate_music(show_errors=True):
            return None
        output = Path(self.output_path.get().strip())
        if not output.name:
            messagebox.showinfo("Chưa chọn tệp", "Chọn nơi lưu video trước khi tạo.", parent=self)
            return None
        if output.suffix.lower() != ".mp4":
            output = output.with_suffix(".mp4")
            self.output_path.set(str(output))
        media_paths = [Path(self.image_path.get())] if self.mode.get() == "image" else [Path(p) for p in self.flow_clips]
        media_paths.extend(self.tracks if needs_music else [])
        if any(output.resolve() == p.resolve() for p in media_paths):
            messagebox.showerror("Tệp xuất trùng nguồn", "Chọn nơi lưu khác với ảnh, video hoặc nhạc nguồn.", parent=self)
            return None
        if self.mode.get() == "image" and self.overlay_path.get().strip() and not Path(self.overlay_path.get()).is_file():
            messagebox.showerror("Overlay không tồn tại", "Chọn một file MP4 overlay hợp lệ hoặc xóa đường dẫn.", parent=self)
            return None
        ffmpeg, ffprobe = find_binary("ffmpeg"), find_binary("ffprobe")
        if not ffmpeg or not ffprobe:
            messagebox.showerror("Thiếu FFmpeg", "Đặt ffmpeg.exe và ffprobe.exe trong thư mục tools hoặc cài FFmpeg vào PATH.", parent=self)
            return None
        try:
            settings = self.current_settings()
            first = self.first_five_paths() if needs_music else []
        except Exception as exc:
            messagebox.showerror("Thiết lập chưa hợp lệ", str(exc), parent=self)
            return None
        output.parent.mkdir(parents=True, exist_ok=True)
        return output, settings, first, ffmpeg, ffprobe

    def start_render(self):
        if self.worker and self.worker.is_alive():
            return
        inputs = self._render_inputs()
        if not inputs:
            return
        output, settings, first, ffmpeg, ffprobe = inputs
        if output.exists() and not messagebox.askyesno("Ghi đè video", f"Tệp đã tồn tại. Thay thế?\n\n{output}", parent=self):
            return
        if self.mode.get() == "image":
            engine_class = RenderEngine
            image = Path(self.image_path.get())
        else:
            engine_class = FlowLoopEngine
            image = Path()
        self.engine = engine_class(ffmpeg=ffmpeg, ffprobe=ffprobe, progress_cb=self._set_progress, log_cb=self._log)
        self.next_btn.configure(state="disabled")
        self.back_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.status.set("Đang chuẩn bị…")
        self.show_page(2)

        def work():
            try:
                self._log("===== BẮT ĐẦU TẠO VIDEO =====")
                self._log(f"Kiểu video: {settings.visual_source}")
                self._log(f"Thời lượng: {fmt_time(settings.duration_seconds, True)}")
                self._log(f"Đầu ra: {output}")
                selected_tracks = list(self.tracks) if settings.flow_music_enabled else []
                result = self.engine.render_project(
                    image=image,
                    tracks=selected_tracks,
                    first_five=first,
                    output=output,
                    settings=settings,
                )
                out, chapters, verify = result
                self.ui_queue.put(("done", out, chapters, verify))
            except Exception as exc:
                self.ui_queue.put(("error", "Tạo video lỗi", str(exc)))
            finally:
                self.ui_queue.put(("render_done",))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _set_progress(self, percent: float, message: str):
        self.ui_queue.put(("progress", percent, message))

    def _log(self, message: str):
        self.ui_queue.put(("log", message))

    def _drain_queue(self):
        try:
            while True:
                item = self.ui_queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    self.progress.set(item[1]); self.status.set(item[2])
                elif kind == "log":
                    self.log_text.configure(state="normal"); self.log_text.insert("end", item[1] + "\n")
                    self.log_text.see("end"); self.log_text.configure(state="disabled")
                elif kind == "error":
                    self.status.set("Có lỗi · xem chi tiết bên dưới")
                    messagebox.showerror(item[1], item[2], parent=self)
                elif kind == "done":
                    _kind, output, chapters, verify = item
                    self.status.set("Hoàn tất · video đã được kiểm tra")
                    self._log(f"Video: {output}")
                    self._log(f"Chapter: {chapters or 'Không dùng nhạc'}")
                    self._log(f"Kiểm tra: {verify.get('width')}×{verify.get('height')} · {verify.get('duration', 0):.1f}s")
                    messagebox.showinfo("Tạo video xong", f"Video:\n{output}\n\nChapters:\n{chapters or 'Không dùng nhạc'}", parent=self)
                elif kind == "encoder":
                    _kind, ok, title, detail = item
                    messagebox.showinfo(f"{title}: {'sẵn sàng' if ok else 'không dùng được'}", detail, parent=self)
                elif kind == "render_done":
                    self.next_btn.configure(state="normal"); self.back_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    def _validate_sources(self, show_errors: bool = False) -> bool:
        mode = self.mode.get()
        if mode == "image":
            path = Path(self.image_path.get())
            valid = path.is_file() and path.suffix.lower() in IMAGE_EXTS
            message = "Chọn một ảnh nền hợp lệ."
        else:
            valid = bool(self.flow_clips) and all(Path(path).is_file() and Path(path).suffix.lower() in VIDEO_EXTS for path in self.flow_clips)
            message = "Thêm ít nhất một clip video hợp lệ."
            if len(self.flow_clips) > 24:
                valid = False; message = "Mỗi dự án hỗ trợ tối đa 24 clip."
        if not valid and show_errors:
            messagebox.showinfo("Thiếu nguồn hình", message, parent=self)
        return valid

    def save_project_ui(self):
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(
            title="Lưu dự án Tool Edit", initialdir=str(OUTPUT_ROOT), initialfile="du_an_video.json",
            defaultextension=".json", filetypes=[("Dự án Tool Edit", "*.json")],
        )
        if not path:
            return
        try:
            settings = self.current_settings()
            payload = {
                "schema_version": 2,
                "settings": settings.to_json_dict(),
                "image": self.image_path.get(),
                "music_folder": str(self.catalog.music_root),
                "output": self.output_path.get(),
                "first_five": [item.get() for item in self.first_five_vars],
                "channel": self.channel.get(),
                "filters": {"artist": self.artist_filter.get(), "genre": self.genre_filter.get(),
                            "instrument": self.instrument_filter.get(), "vocal": self.vocal_filter.get(),
                            "mood": self.mood_filter.get(), "status": self.status_filter.get()},
                "selected_tracks": [str(path) for path in self.tracks],
            }
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status.set(f"Đã lưu dự án: {Path(path).name}")
        except Exception as exc:
            messagebox.showerror("Không lưu được dự án", str(exc), parent=self)

    def load_project_ui(self):
        path = filedialog.askopenfilename(title="Mở dự án Tool Edit", filetypes=[("Dự án JSON", "*.json")])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            settings = RenderSettings.from_json_dict(data["settings"])
            mode_by_source = {"Thumbnail": "image", "Flow Loop": "loop", "Footage Montage": "footage"}
            self.mode.set(mode_by_source.get(settings.visual_source, "image"))
            self.image_path.set(data.get("image", ""))
            self.flow_clips = list(settings.flow_clips)
            self._refresh_clip_list(); self._update_source_mode()
            self.output_path.set(data.get("output", str(OUTPUT_ROOT / "video_moi.mp4")))
            self.duration_choice.set(next((key for key, seconds in DURATIONS.items() if seconds == settings.duration_seconds), "Tùy chỉnh"))
            if self.duration_choice.get() == "Tùy chỉnh":
                self.custom_minutes.set(str(max(1, settings.duration_seconds // 60)))
            self._duration_changed()
            self.output_profile.set(next((label for label, value in PROFILES.items() if value == settings.output_profile), next(iter(PROFILES))))
            self.encoder.set(settings.encoder); self.normalize.set(settings.normalization_enabled)
            self.loudness.set(str(int(settings.loudness_target)))
            self.transition_mode.set(settings.transition_mode); self.transition_seconds.set(str(int(settings.transition_seconds)))
            self.crossfade.set(str(settings.flow_crossfade)); self.flow_trim_start.set(str(settings.flow_trim_start))
            self.flow_trim_end.set(str(settings.flow_trim_end)); self.visual_motion.set(settings.visual_motion)
            self.overlay_path.set(settings.overlay_path); self.overlay_mode.set(settings.overlay_mode)
            self.overlay_opacity.set(settings.overlay_opacity); self.seed.set(settings.random_seed)
            saved_channel = data.get("channel", settings.channel_profile)
            if saved_channel in self.channel_combo.cget("values"):
                self.channel.set(saved_channel)
            filters = data.get("filters", {})
            self.artist_filter.set(filters.get("artist", "Tất cả nghệ sĩ"))
            self.genre_filter.set(filters.get("genre", "Tất cả thể loại"))
            self.instrument_filter.set(filters.get("instrument", "Tất cả nhạc cụ"))
            self.vocal_filter.set(filters.get("vocal", "Tất cả"))
            self.mood_filter.set(filters.get("mood", "Tất cả không khí"))
            self.status_filter.set(filters.get("status", "Đã kiểm tra"))
            self.include_music.set(settings.flow_music_enabled if self.mode.get() != "image" else True)
            self._update_source_mode()
            self._refresh_music()
            if data.get("selected_tracks"):
                wanted = set(data["selected_tracks"])
                for row in self.filtered_rows:
                    if str(row["path"]) in wanted:
                        self.music_table.selection_add(str(row["id"]))
                self.only_selected.set(True)
                self._sync_music_selection()
            for variable, value in zip(self.first_five_vars, data.get("first_five", [])):
                if value in self.track_labels:
                    variable.set(value)
            self.show_page(0)
            self.status.set(f"Đã mở dự án: {Path(path).name}")
        except Exception as exc:
            messagebox.showerror("Không mở được dự án", str(exc), parent=self)

    def save_preset_ui(self):
        try:
            settings = self.current_settings()
        except Exception as exc:
            messagebox.showerror("Preset chưa hợp lệ", str(exc), parent=self); return
        folder = OUTPUT_ROOT / "Presets"; folder.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(title="Lưu preset", initialdir=str(folder), initialfile="video_nhac.json",
                                            defaultextension=".json", filetypes=[("Preset JSON", "*.json")])
        if path:
            save_preset(Path(path), settings); self.status.set(f"Đã lưu preset: {Path(path).name}")

    def load_preset_ui(self):
        preset_dir = OUTPUT_ROOT / "Presets"
        if not preset_dir.is_dir() and (APP_ROOT / "presets").is_dir():
            preset_dir = APP_ROOT / "presets"
        path = filedialog.askopenfilename(title="Mở preset", initialdir=str(preset_dir),
                                          filetypes=[("Preset JSON", "*.json"), ("JSON", "*.json")])
        if not path:
            return
        try:
            settings = load_preset(Path(path))
            mode_by_source = {"Thumbnail": "image", "Flow Loop": "loop", "Footage Montage": "footage"}
            self.mode.set(mode_by_source.get(settings.visual_source, "image"))
            self.flow_clips = list(settings.flow_clips); self._refresh_clip_list(); self._update_source_mode()
            self.duration_choice.set(next((key for key, value in DURATIONS.items() if value == settings.duration_seconds), "Tùy chỉnh"))
            if self.duration_choice.get() == "Tùy chỉnh": self.custom_minutes.set(str(settings.duration_seconds // 60))
            self._duration_changed()
            self.output_profile.set(next((label for label, value in PROFILES.items() if value == settings.output_profile), next(iter(PROFILES))))
            self.encoder.set(settings.encoder); self.normalize.set(settings.normalization_enabled)
            self.loudness.set(str(int(settings.loudness_target))); self.transition_mode.set(settings.transition_mode)
            self.transition_seconds.set(str(int(settings.transition_seconds))); self.crossfade.set(str(settings.flow_crossfade))
            self.flow_trim_start.set(str(settings.flow_trim_start)); self.flow_trim_end.set(str(settings.flow_trim_end))
            self.visual_motion.set(settings.visual_motion); self.overlay_path.set(settings.overlay_path)
            self.overlay_mode.set(settings.overlay_mode); self.overlay_opacity.set(settings.overlay_opacity)
            self.include_music.set(settings.flow_music_enabled if self.mode.get() != "image" else True); self.seed.set(settings.random_seed)
            channels = self.channel_combo.cget("values")
            if settings.channel_profile in channels: self.channel.set(settings.channel_profile)
            self._refresh_music(); self.show_page(0)
            self.status.set(f"Đã mở preset: {Path(path).name}")
        except Exception as exc:
            messagebox.showerror("Không mở được preset", str(exc), parent=self)

    def test_qsv(self):
        self._test_encoder("intel", check_qsv, "Intel Quick Sync")

    def test_nvenc(self):
        self._test_encoder("nvidia", check_nvenc, "NVIDIA")

    def _test_encoder(self, name: str, checker, title: str):
        ffmpeg = find_binary("ffmpeg")
        if not ffmpeg:
            messagebox.showerror("Thiếu FFmpeg", "Không tìm thấy ffmpeg.exe.", parent=self); return
        self.status.set(f"Đang kiểm tra {title}…")
        def worker():
            ok, detail = checker(ffmpeg)
            self.ui_queue.put(("encoder", ok, title, detail))
        threading.Thread(target=worker, daemon=True).start()

    def open_content_hub(self):
        path = WORKSPACE_ROOT / "OPEN_CONTENT_HUB.bat"
        if path.is_file(): os.startfile(str(path))
        else: messagebox.showinfo("Content Hub", "Không tìm thấy OPEN_CONTENT_HUB.bat trong thư mục dự án.", parent=self)

    def open_music_manager(self):
        path = WORKSPACE_ROOT / "editer" / "Nhạc jazz" / "Mo_Quan_Ly_Nhac.cmd"
        if path.is_file(): os.startfile(str(path))
        else: messagebox.showinfo("Music Manager", "Không tìm thấy Mo_Quan_Ly_Nhac.cmd.", parent=self)

    def choose_output(self):
        default_name = Path(self.output_path.get()).name if self.output_path.get() else "video_moi.mp4"
        path = filedialog.asksaveasfilename(title="Chọn nơi lưu video", initialdir=str(OUTPUT_ROOT), initialfile=default_name,
                                            defaultextension=".mp4", filetypes=[("Video MP4", "*.mp4")])
        if path: self.output_path.set(path)

    def choose_overlay(self):
        path = filedialog.askopenfilename(title="Chọn overlay tuyết / mưa", filetypes=[("Video", "*.mp4 *.mov *.mkv *.webm")])
        if path:
            self.overlay_path.set(path)

    def cancel_render(self):
        if self.engine:
            self.engine.cancel(); self.status.set("Đang dừng…")


def main():
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--self-check":
        app = App(); app.withdraw(); app.update_idletasks()
        payload = {"ui": "OK", "ffmpeg": find_binary("ffmpeg"), "ffprobe": find_binary("ffprobe"),
                   "pages": len(app.pages), "channels": app.catalog.channel_names()}
        Path(sys.argv[2]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        app.destroy()
        return
    App().mainloop()


if __name__ == "__main__":
    main()
