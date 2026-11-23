"""YouTube Content Hub — local desktop workflow management."""
from __future__ import annotations
import argparse
import csv
import json
import os
import queue
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from store import Store, STAGES, KINDS, CHECKS, DomainError
from services import Adapters, InstanceLock, find_workspace
from youtube_analytics import YouTubeAnalyticsClient, video_id_from_url

TITLE = "YouTube Content Hub | Điều hành sản xuất nội dung"
ASSET_LABELS = {"research":"File nghiên cứu", "reference":"Ảnh tham khảo",
                "thumbnail":"Ảnh bìa / thumbnail", "clip":"Video clip thành phần",
                "music":"Nhạc nền", "final":"Video hoàn chỉnh"}
CHANNEL_ASSET_KINDS = {"research", "reference", "music"}
ASSET_KIND_BY_LABEL = {label: kind for kind, label in ASSET_LABELS.items()}
ASSET_KIND_BY_LABEL.update({label: kind for kind, label in KINDS.items()})
EVENT_LABELS = {
    "channel_saved":"Lưu kênh", "album_created":"Tạo đợt phát hành", "album_updated":"Sửa đợt phát hành",
    "video_project_created":"Tạo video", "project_updated":"Cập nhật thông tin", "video_album_changed":"Đổi đợt phát hành",
    "asset_imported":"Thêm file", "asset_deleted":"Gỡ file", "channel_asset_imported":"Thêm tài nguyên kênh",
    "channel_asset_deleted":"Gỡ tài nguyên kênh", "stage_changed":"Cập nhật Bước",
    "qc_approved":"Duyệt video", "qc_rejected":"Chưa duyệt", "rework_requested":"Yêu cầu chỉnh sửa",
    "handoff_prepared":"Chuẩn bị thư mục dự án", "tool_open_requested":"Mở công cụ hỗ trợ",
    "analytics_data_deleted":"Xóa dữ liệu Analytics",
    "video_music_playlist_linked":"Gắn playlist nhạc", "render_queued":"Đưa video vào hàng đợi",
    "render_started":"Bắt đầu dựng video", "render_succeeded":"Dựng video xong", "render_failed":"Dựng video lỗi",
    "render_interrupted":"Dựng video bị gián đoạn", "render_cancel_requested":"Yêu cầu dừng render",
}

class Hub(tk.Tk):
    def __init__(self, store, workspace):
        super().__init__()
        self.title(TITLE)
        width = min(1400, self.winfo_screenwidth()-60)
        height = min(900, self.winfo_screenheight()-90)
        self.geometry(f"{max(1000,width)}x{max(640,height)}")
        self.minsize(min(1000, width), min(640, height))
        self.configure(bg="#f2f5f9")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", rowheight=29, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(9, 5))
        self.store = store
        self.adapters = Adapters(store, workspace)
        self.analytics_client = YouTubeAnalyticsClient()
        self.analytics_project_rows = {}
        self.analytics_selected_id = None
        self.current = None
        self.actor = tk.StringVar(value="Người vận hành")
        self.channel_filter = tk.StringVar(value="Tất cả kênh")
        self.album_filter = tk.StringVar(value="Tất cả đợt phát hành")
        self.stage_filter = tk.StringVar(value="Tất cả trạng thái")
        self.search = tk.StringVar()
        self.status = tk.StringVar(value="Sẵn sàng · Dữ liệu cục bộ · Múi giờ Việt Nam UTC+7")
        self.messages = queue.Queue()
        self.busy = False
        self.channel_map = {}
        self.album_map = {}
        self.project_rows = {}
        self.asset_rows = {}
        self.channel_asset_rows = {}
        self._build()
        self.refresh()
        self.after(250, self.poll)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self):
        top = tk.Frame(self, bg="#14243c", padx=20, pady=14)
        top.pack(fill="x")
        tk.Label(top, text="CONTENT HUB", bg="#14243c", fg="white", font=("Segoe UI", 22, "bold")).pack(side="left")
        tk.Label(top, text="Theo dõi tiến độ video trên nhiều kênh", bg="#14243c", fg="#a9c1dc", font=("Segoe UI", 11)).pack(side="left", padx=22)
        self.main_tabs = ttk.Notebook(self)
        self.main_tabs.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self.home_page = ttk.Frame(self.main_tabs, padding=18)
        self.workspace_page = ttk.Frame(self.main_tabs)
        self.analytics_page = ttk.Frame(self.main_tabs, padding=12)
        self.main_tabs.add(self.home_page, text="Tổng quan")
        self.main_tabs.add(self.workspace_page, text="Danh sách video")
        self.main_tabs.add(self.analytics_page, text="Theo dõi video sau đăng")
        self._home()
        self._analytics()
        bar = ttk.Frame(self.workspace_page, padding=(12, 8))
        bar.pack(fill="x")
        self.summary = ttk.Label(bar, font=("Segoe UI", 11, "bold"))
        self.summary.pack(side="left")
        for label, action in [("Làm mới", self.refresh), ("Sao lưu dữ liệu", self.backup), ("Hướng dẫn", self.open_guide)]:
            ttk.Button(bar, text=label, command=lambda a=action: self.safe(a)).pack(side="right", padx=3)
        body = ttk.Panedwindow(self.workspace_page, orient="horizontal")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        left = ttk.Frame(body, padding=8)
        right = ttk.Frame(body, padding=8)
        body.add(left, weight=2)
        body.add(right, weight=4)
        ttk.Label(left, text="VIDEO ĐANG QUẢN LÝ", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        row = ttk.Frame(left)
        row.pack(fill="x", pady=6)
        self.channel_combo = ttk.Combobox(row, textvariable=self.channel_filter, state="readonly")
        self.channel_combo.pack(side="left", fill="x", expand=True)
        self.channel_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_albums())
        ttk.Button(row, text="Quản lý kênh", command=lambda: self.safe(self.channel_dialog)).pack(side="right", padx=(5, 0))
        row = ttk.Frame(left)
        row.pack(fill="x", pady=(0, 4))
        self.album_combo = ttk.Combobox(row, textvariable=self.album_filter, state="readonly")
        self.album_combo.pack(side="left", fill="x", expand=True)
        self.album_combo.bind("<<ComboboxSelected>>", self.select_album)
        ttk.Button(row, text="+ Đợt phát hành", command=lambda: self.safe(self.album_dialog)).pack(side="right", padx=(5, 0))
        ttk.Button(row, text="Sửa", command=lambda: self.safe(lambda: self.album_dialog(edit=True))).pack(side="right", padx=(5, 0))
        ttk.Label(left, text="Trạng thái").pack(anchor="w", pady=(4, 0))
        stage = ttk.Combobox(left, textvariable=self.stage_filter, state="readonly", values=["Tất cả trạng thái"]+list(STAGES.values()))
        stage.pack(fill="x", pady=3)
        stage.bind("<<ComboboxSelected>>", lambda e: self.refresh_projects())
        row = ttk.Frame(left)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text="Tìm video:").pack(side="left", padx=(0, 5))
        entry = ttk.Entry(row, textvariable=self.search)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda e: self.refresh_projects())
        ttk.Button(row, text="Tìm", command=self.refresh_projects).pack(side="right", padx=(5, 0))
        self.projects_tree = self.tree(left, [("title", "Video / mix", 190), ("stage", "Bước", 110), ("channel", "Kênh", 110)])
        self.projects_tree.bind("<<TreeviewSelect>>", self.select_project)
        self.projects_tree.bind("<Button-3>", self.project_context_menu)
        ttk.Button(left, text="+ Tạo video / mix", command=lambda: self.safe(self.project_dialog)).pack(fill="x", pady=8)
        ttk.Label(left, text="Mỗi video có brief, file và tiến độ riêng. Đợt phát hành chỉ dùng để nhóm video.", wraplength=340, foreground="#62738a").pack(anchor="w")
        self.project_heading = ttk.Label(right, text="Chọn một video để xem hoặc cập nhật", font=("Segoe UI", 15, "bold"), wraplength=760)
        self.project_heading.pack(anchor="w", pady=(0, 4))
        self.project_meta = ttk.Label(right, foreground="#456181")
        self.project_meta.pack(anchor="w", pady=(0, 8))
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self.overview = ttk.Frame(self.tabs, padding=10)
        self.asset_tab = ttk.Frame(self.tabs, padding=10)
        self.production_tab = ttk.Frame(self.tabs, padding=10)
        self.qc_tab = ttk.Frame(self.tabs, padding=10)
        self.audit_tab = ttk.Frame(self.tabs, padding=10)
        for tab, title in [(self.overview,"Thông tin"),(self.asset_tab,"Tài nguyên"),(self.production_tab,"Sản xuất"),
                           (self.qc_tab,"Kiểm duyệt và Đăng"),(self.audit_tab,"Lịch sử")]:
            self.tabs.add(tab, text=title)
        self.tabs.tab(self.qc_tab, state="normal")
        self._overview()
        self._assets()
        self._production()
        self._qc()
        self.audit_rows = {}
        self.audit_tree = self.tree(self.audit_tab, [("time","Thời điểm",145),("action","Thao tác",190),("summary","Chi tiết",360)], height=12)
        self.audit_tree.bind("<<TreeviewSelect>>", self.show_audit_detail)
        self.audit_detail = tk.Text(self.audit_tab, wrap="word", height=4, state="disabled", font=("Segoe UI", 9))
        self.audit_detail.pack(fill="x", pady=(6, 0))
        ttk.Button(self.audit_tab, text="Xuất hồ sơ dự án…", command=lambda: self.safe(self.export_project)).pack(anchor="e", pady=(6, 0))
        ttk.Label(self, textvariable=self.status, padding=(14, 6), foreground="#245b80").pack(fill="x")

    def _home(self):
        page = self.home_page
        tk.Label(page, text="Bảng điều hành sản xuất", bg="#f2f5f9", fg="#14243c",
                 font=("Segoe UI", 23, "bold")).pack(anchor="w")
        tk.Label(page, text="Xem việc cần làm tiếp theo và tiến độ video của từng kênh.",
                 bg="#f2f5f9", fg="#62738a", font=("Segoe UI", 11)).pack(anchor="w", pady=(2, 16))
        self.home_summary = tk.Frame(page, bg="#f2f5f9")
        self.home_summary.pack(fill="x", pady=(0, 16))
        actions = ttk.LabelFrame(page, text="Bắt đầu tại đây", padding=12)
        actions.pack(fill="x", pady=(0, 14))
        self.home_next_text = ttk.Label(actions, text="", wraplength=760)
        self.home_next_text.pack(anchor="w", pady=(0, 8))
        self.home_next_button = ttk.Button(actions, text="", command=lambda: None)
        self.home_next_button.pack(anchor="w")
        row = ttk.Frame(page)
        row.pack(fill="both", expand=True)
        left = ttk.LabelFrame(row, text="Đang sản xuất · chọn một video để tiếp tục", padding=10)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.home_tree = self.tree(left, [("title", "Video / mix", 310), ("stage", "Bước hiện tại", 130), ("channel", "Kênh", 160)], height=9)
        self.home_tree.bind("<Double-1>", self.open_home_project)
        ttk.Button(left, text="Mở video đang chọn", command=self.open_home_project).pack(anchor="e", pady=(8, 0))
        right = ttk.LabelFrame(row, text="Quy trình", padding=12)
        right.pack(side="left", fill="y")
        for text in ["1  Chọn kênh và tạo đợt phát hành",
                     "2  Tạo video, nhập mô tả và file",
                     "3  Kiểm tra video trước khi đăng",
                     "4  Ghi lịch hoặc xác nhận đã đăng"]:
            ttk.Label(right, text=text, wraplength=310).pack(anchor="w", pady=8)
        ttk.Separator(right).pack(fill="x", pady=8)
        ttk.Label(right, text="Các công cụ phụ không bắt buộc để theo dõi tiến độ.",
                  wraplength=310, foreground="#62738a").pack(anchor="w", pady=(5, 2))

    def _analytics(self):
        ttk.Label(self.analytics_page, text="Theo dõi hiệu suất sau đăng",
                  font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(self.analytics_page,
                  text="Chọn video đã đăng để xem snapshot. “Làm mới” lấy số mới nhất YouTube đã xử lý và lưu một snapshot mới.",
                  foreground="#62738a", wraplength=1100).pack(anchor="w", pady=(2, 8))
        toolbar = ttk.Frame(self.analytics_page)
        toolbar.pack(fill="x", pady=(0, 6))
        self.analytics_status = tk.StringVar(value="Chưa chọn video.")
        ttk.Label(toolbar, textvariable=self.analytics_status, foreground="#456181").pack(side="left", fill="x", expand=True)
        self.analytics_refresh_button = ttk.Button(toolbar, text="Làm mới chỉ số", command=lambda: self.safe(self.refresh_selected_analytics))
        self.analytics_refresh_button.pack(side="right", padx=(6, 0))
        ttk.Button(toolbar, text="Kết nối Google…", command=lambda: self.safe(self.connect_google)).pack(side="right")
        ttk.Button(toolbar, text="Ngắt kết nối & xóa snapshot", command=lambda: self.safe(self.disconnect_google)).pack(side="right", padx=(0, 6))
        ttk.Label(self.analytics_page, text="VIDEO ĐÃ ĐĂNG", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.analytics_tree = self.tree(self.analytics_page,
            [("title", "Video", 300), ("channel", "Kênh", 150), ("published", "Cập nhật Hub", 125),
             ("url", "URL YouTube", 360), ("snapshots", "Snapshots", 85)], height=7)
        self.analytics_tree.bind("<<TreeviewSelect>>", self.select_analytics_project)
        ttk.Label(self.analytics_page, text="LỊCH SỬ SNAPSHOT · CTR DÙNG BÁO CÁO 28 NGÀY GẦN NHẤT ĐÃ CÓ",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 4))
        self.analytics_history_tree = self.tree(self.analytics_page,
            [("recorded", "Đã làm mới", 145), ("views", "Lượt xem", 80), ("ctr", "CTR · 28 ngày", 95),
             ("avd", "AVD", 80), ("watch", "Thời gian xem (phút)", 140),
             ("impressions", "Impressions · 28 ngày", 150), ("comments", "Comment", 80),
             ("likes", "Like", 70), ("shares", "Share", 70), ("retention", "Xem trung bình", 110)],
            height=7, horizontal=True)
        ttk.Label(self.analytics_page,
                  text="CTR và impressions đến từ báo cáo hằng ngày của YouTube Reporting API; thời điểm dữ liệu có sẵn có thể trễ 1–2 ngày. AVD = thời lượng xem trung bình.",
                  foreground="#62738a", wraplength=1100).pack(anchor="w", pady=(5, 0))

    def refresh_analytics_projects(self):
        rows = self.store.published_projects()
        self.analytics_project_rows = {row["id"]: row for row in rows}
        self.analytics_tree.delete(*self.analytics_tree.get_children())
        for row in rows:
            snapshots = self.store.metric_snapshots(row["id"])
            label = f"{row['title']} · {row['album_name']}" if row.get("album_name") else row["title"]
            self.analytics_tree.insert("", "end", iid=row["id"], values=(
                label, row["channel_name"], row["updated_at"][:10], row["youtube_url"], len(snapshots)))
        if self.analytics_selected_id in self.analytics_project_rows:
            self.analytics_tree.selection_set(self.analytics_selected_id)
            self.show_analytics_history(self.analytics_selected_id)
        else:
            self.analytics_selected_id = None
            self.analytics_history_tree.delete(*self.analytics_history_tree.get_children())
            self.analytics_status.set(f"{len(rows)} video đã đăng. Chọn một video để xem lịch sử.")

    def select_analytics_project(self, _event=None):
        selected = self.analytics_tree.selection()
        if selected:
            self.analytics_selected_id = selected[0]
            self.show_analytics_history(selected[0])

    @staticmethod
    def _metric_number(value, decimals=0):
        if value is None:
            return "—"
        return f"{value:,.{decimals}f}"

    def show_analytics_history(self, project_id):
        self.analytics_history_tree.delete(*self.analytics_history_tree.get_children())
        project = self.analytics_project_rows.get(project_id, {})
        snapshots = self.store.metric_snapshots(project_id)
        for row in snapshots:
            try:
                values = json.loads(row.get("analytics_json") or "{}")
            except (TypeError, ValueError):
                values = {}
            if row.get("source") != "youtube_analytics":
                values = {"ctr": row["ctr"] / 100, "views": row["views"],
                          "watch_minutes": row["watch_minutes"], "impressions": row["impressions"]}
            avd = values.get("average_view_duration")
            avd_label = "—" if avd is None else f"{int(avd)//60}:{int(avd)%60:02d}"
            ctr = values.get("ctr")
            self.analytics_history_tree.insert("", "end", values=(
                row["recorded_at"][:16].replace("T", " "),
                self._metric_number(values.get("views")),
                "—" if ctr is None else f"{ctr * 100:.2f}%",
                avd_label,
                self._metric_number(values.get("watch_minutes"), 1),
                self._metric_number(values.get("impressions")),
                self._metric_number(values.get("comments")),
                self._metric_number(values.get("likes")),
                self._metric_number(values.get("shares")),
                "—" if values.get("average_view_percentage") is None else f"{values['average_view_percentage']:.1f}%"))
        self.analytics_status.set(
            f"{project.get('title', 'Video')} · {project.get('channel_name', '')} · {len(snapshots)} snapshot(s) · Chỉ số tích lũy từ lúc bắt đầu đăng ký video trong Hub; CTR theo 28 ngày gần nhất có báo cáo.")

    def connect_google(self):
        path = filedialog.askopenfilename(title="Chọn OAuth client Desktop app JSON",
            filetypes=[("OAuth client JSON", "*.json"), ("Tất cả file", "*.*")], parent=self)
        if not path:
            return
        self.analytics_client.configure(path)
        self.async_action(self.analytics_client.connect, "Đã kết nối Google Analytics. Bây giờ có thể làm mới chỉ số.")

    def disconnect_google(self):
        if not messagebox.askyesno("Ngắt kết nối Google",
                "Thu hồi quyền OAuth, xóa thông tin kết nối và xóa các snapshot Analytics đã lưu trong Hub?\n\n"
                "Việc này không thay đổi video hoặc số liệu trên YouTube.", parent=self):
            return
        actor = self.actor_name()

        def clear():
            self.analytics_client.disconnect()
            count = self.store.delete_analytics_data(actor)
            return {"snapshots_removed": count}
        self.async_action(clear, "Đã ngắt kết nối Google và xóa snapshot Analytics trong Hub.")

    def refresh_selected_analytics(self):
        project_id = self.analytics_selected_id
        if not project_id or project_id not in self.analytics_project_rows:
            raise DomainError("Chọn một video đã đăng trước khi làm mới.")
        project = dict(self.analytics_project_rows[project_id])
        video_id = video_id_from_url(project.get("youtube_url"))
        if not self.analytics_client.client_path.is_file():
            path = filedialog.askopenfilename(title="Chọn OAuth client Desktop app JSON",
                filetypes=[("OAuth client JSON", "*.json"), ("Tất cả file", "*.*")], parent=self)
            if not path:
                return
            self.analytics_client.configure(path)
        actor = self.actor_name()

        def update():
            values = self.analytics_client.video_metrics(video_id, project.get("created_at"))
            self.store.save_analytics_snapshot(project_id, values, actor)
            return values
        self.async_action(update, "Đã lưu snapshot YouTube Analytics.")

    def show_workspace(self):
        self.main_tabs.select(self.workspace_page)

    def open_home_project(self, event=None):
        selection = self.home_tree.selection()
        if not selection:
            return
        project_id = selection[0]
        self.show_workspace()
        self.channel_filter.set("Tất cả kênh")
        self.album_filter.set("Tất cả đợt phát hành")
        self.stage_filter.set("Tất cả trạng thái")
        self.search.set("")
        self.refresh_albums()
        self.refresh_projects()
        if project_id in self.project_rows:
            self.projects_tree.selection_set(project_id)
            self.load_project(project_id)
            self.tabs.select(self.overview)

    def tree(self, parent, columns, height=10, horizontal=False):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height, selectmode="browse")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        if horizontal:
            xscroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
            tree.configure(xscrollcommand=xscroll.set)
            xscroll.pack(side="bottom", fill="x")
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for key, title, width in columns:
            tree.heading(key, text=title)
            tree.column(key, width=width, minwidth=45)
        return tree

    def _overview(self):
        self.edit_title = tk.StringVar()
        self.edit_owner = tk.StringVar()
        self.edit_due = tk.StringVar()
        ttk.Label(self.overview, text="Đợt phát hành (tùy chọn)").pack(anchor="w", pady=(5, 2))
        album_row = ttk.Frame(self.overview)
        album_row.pack(fill="x")
        self.video_album = tk.StringVar(value="Không thuộc đợt phát hành")
        self.video_album_combo = ttk.Combobox(album_row, textvariable=self.video_album, state="readonly")
        self.video_album_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(album_row, text="Lưu đợt", command=lambda: self.safe(self.set_video_album)).pack(side="left", padx=(6, 0))
        for label, var in [("Tiêu đề dự kiến", self.edit_title), ("Người phụ trách", self.edit_owner), ("Hạn hoàn thành (YYYY-MM-DD)", self.edit_due)]:
            ttk.Label(self.overview, text=label).pack(anchor="w", pady=(5, 0))
            ttk.Entry(self.overview, textvariable=var).pack(fill="x")
        ttk.Label(self.overview, text="Mô tả riêng của video/mix (mô tả chung của đợt phát hành sẽ được dùng kèm)").pack(anchor="w", pady=(10, 3))
        self.brief = tk.Text(self.overview, height=8, wrap="word", font=("Segoe UI", 11))
        self.brief.pack(fill="both", expand=True)
        row = ttk.Frame(self.overview)
        row.pack(fill="x", pady=10)
        ttk.Button(row, text="Lưu thay đổi", command=lambda: self.safe(self.save_brief)).pack(side="left", padx=3)
        self.advance_button = ttk.Button(row, text="Chuyển bước", command=lambda: self.safe(self.advance))
        self.advance_button.pack(side="left", padx=3)
        self.rework_button = ttk.Button(row, text="Yêu cầu chỉnh sửa", command=lambda: self.safe(self.rework))
        self.rework_button.pack(side="left", padx=3)
        ttk.Label(self.overview, text="Thông tin và mô tả này thuộc riêng video đang chọn. Đợt phát hành chỉ dùng để nhóm các video.\n"
                  "Hub theo dõi file và tiến độ; việc đăng video vẫn thực hiện trên YouTube Studio.", wraplength=760, foreground="#62738a").pack(anchor="w")

    def _assets(self):
        row = ttk.Frame(self.asset_tab)
        row.pack(fill="x", pady=(0, 7))
        self.asset_kind = tk.StringVar(value=ASSET_LABELS["clip"])
        self.asset_kind_combo = ttk.Combobox(row, textvariable=self.asset_kind,
                                             values=[label for kind, label in ASSET_LABELS.items() if kind != "final"],
                                             state="readonly", width=25)
        self.asset_kind_combo.pack(side="left")
        ttk.Button(row, text="+ Nhập file", command=lambda: self.safe(self.import_assets)).pack(side="left", padx=5)
        ttk.Button(row, text="Mở file", command=lambda: self.safe(self.open_asset)).pack(side="left")
        ttk.Button(row, text="Kiểm tra file có đổi không", command=lambda: self.safe(self.verify_asset)).pack(side="left", padx=5)
        delete_row = ttk.Frame(self.asset_tab)
        delete_row.pack(fill="x", pady=(0, 7))
        ttk.Button(delete_row, text="Gỡ file khỏi dự án", command=lambda: self.safe(self.delete_asset)).pack(side="left")
        self.assets_tree = self.tree(self.asset_tab, [("kind","Loại",130),("scope","Gắn với",105),("slot","Nhóm",90),("version","Bản",45),
                                                      ("file","Tên file",210),("size","MB",65)])
        self.assets_tree.bind("<<TreeviewSelect>>", lambda e: self.asset_path.set(self.selected_asset().get("path", "") if self.assets_tree.selection() else ""))
        self.assets_tree.bind("<Double-1>", lambda e: self.safe(self.open_asset))
        self.asset_path = tk.StringVar()
        ttk.Entry(self.asset_tab, textvariable=self.asset_path, state="readonly").pack(fill="x", pady=7)
        ttk.Label(self.asset_tab, text="File nghiên cứu, ảnh tham khảo và nhạc nền dùng chung theo kênh; ảnh bìa / thumbnail và video clip thành phần thuộc video đang chọn.\n"
                  "Hub ghi nhận file gốc tại vị trí hiện tại. Nhập lại file cùng nhóm để lưu phiên bản mới.", wraplength=760).pack(anchor="w")

    def _production(self):
        primary = ttk.LabelFrame(self.production_tab, text="Bước 1 · Chuẩn bị nội dung", padding=10)
        primary.pack(fill="x", pady=(0, 8))
        row = ttk.Frame(primary)
        row.pack(fill="x")
        ttk.Button(row, text="Mở Google Flow", command=lambda: self.safe(self.open_flow)).pack(side="left")
        ttk.Button(row, text="Mở thư mục dự án", command=lambda: self.safe(self.handoff)).pack(side="left", padx=6)
        ttk.Label(primary, text="Dùng Flow trên website để tạo nội dung. Khi xong, quay lại tab Tài nguyên và nhập file vào đúng video/mix.",
                  wraplength=740, foreground="#62738a").pack(anchor="w", pady=(7, 0))

        optional = ttk.LabelFrame(self.production_tab, text="Công cụ hỗ trợ · chỉ mở khi cần", padding=8)
        optional.pack(fill="x", pady=(0, 8))
        row = ttk.Frame(optional)
        row.pack(fill="x")
        for label, action in [("Nghiên cứu thị trường", lambda: self.launch_tool("studio")),
                              ("Quản lý nhạc", lambda: self.launch_tool("music"))]:
            ttk.Button(row, text=label, command=lambda a=action: self.safe(a)).pack(side="left", padx=(0, 5))
        ttk.Label(self.production_tab,
                  text="Dùng CapCut để biên tập video và ghép nhạc. Khi hoàn tất, nhập video hoàn chỉnh tại tab Kiểm duyệt và Đăng.",
                  wraplength=740, foreground="#62738a").pack(anchor="w", pady=(4, 0))

    def _qc(self):
        ttk.Label(self.qc_tab, text="Kiểm tra bản video chính", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        final_row = ttk.Frame(self.qc_tab)
        final_row.pack(fill="x", pady=(6, 8))
        ttk.Button(final_row, text="+ Nhập video hoàn chỉnh", command=lambda: self.safe(self.import_final)).pack(side="left")
        ttk.Button(final_row, text="Mở video hoàn chỉnh", command=lambda: self.safe(self.open_final)).pack(side="left", padx=6)
        self.final_tree = self.tree(self.qc_tab, [("version", "Bản", 50), ("file", "Video hoàn chỉnh", 420), ("size", "MB", 70)], height=3)
        self.final_tree.bind("<Double-1>", lambda e: self.safe(self.open_final))
        check_labels = {
            "Hình ảnh và bố cục": "Hình ảnh và bố cục đạt yêu cầu",
            "Điểm nối loop": "Đoạn lặp không bị giật hoặc khựng",
            "Âm thanh / chủ đích không tiếng": "Âm thanh nghe ổn (hoặc tắt có chủ đích)",
            "Nguồn và quyền sử dụng tài nguyên": "Đã kiểm tra nguồn và quyền dùng file",
        }
        self.checks = {name: tk.BooleanVar() for name in CHECKS}
        for name, variable in self.checks.items():
            ttk.Checkbutton(self.qc_tab, text=check_labels[name], variable=variable).pack(anchor="w", pady=6)
        ttk.Label(self.qc_tab, text="Nhận xét / lý do cần sửa").pack(anchor="w", pady=(6, 2))
        self.qc_note = tk.Text(self.qc_tab, height=4, wrap="word", font=("Segoe UI", 10))
        self.qc_note.pack(fill="x")
        row = ttk.Frame(self.qc_tab)
        row.pack(fill="x", pady=8)
        ttk.Button(row, text="Duyệt → Sẵn sàng", command=lambda: self.safe(lambda: self.review(True))).pack(side="left")
        ttk.Button(row, text="Trả về chỉnh sửa", command=lambda: self.safe(lambda: self.review(False))).pack(side="left", padx=8)
        ttk.Separator(self.qc_tab).pack(fill="x", pady=10)
        self.scheduled_at = tk.StringVar()
        self.youtube_url = tk.StringVar()
        for label, var in [("Lịch đăng dự kiến, ví dụ 2026-12-01 18:00 (giờ Việt Nam)", self.scheduled_at),
                           ("Đường dẫn YouTube (điền sau khi đăng)", self.youtube_url)]:
            ttk.Label(self.qc_tab, text=label).pack(anchor="w", pady=(6, 2))
            ttk.Entry(self.qc_tab, textvariable=var).pack(fill="x")
        self.publish_button = ttk.Button(self.qc_tab, text="", command=lambda: self.safe(self.advance))
        self.publish_button.pack(anchor="w", pady=10)
        ttk.Label(self.qc_tab, text="Chỉ điền lịch sau khi video được duyệt. Hub không tự đăng hoặc đặt lịch trên YouTube.",
                  wraplength=740, foreground="#62738a").pack(anchor="w")

    def actor_name(self):
        name = self.actor.get().strip()
        if not name:
            raise DomainError("Thiếu tên người ghi nhận thao tác.")
        return name

    def safe(self, action):
        try:
            return action()
        except Exception as error:
            messagebox.showerror("Chưa thực hiện được", str(error), parent=self)

    def need_project(self):
        if not self.current:
            raise DomainError("Chọn một video trước.")
        return dict(self.current)

    def async_action(self, action, success="Đã hoàn tất."):
        if self.busy:
            raise DomainError("Đang xử lý thao tác trước; đợi hoàn tất.")
        self.busy = True
        self.status.set("Đang xử lý / kiểm tra file…")
        def run():
            try:
                result = action()
                self.messages.put(("done", success, result))
            except Exception as error:
                self.messages.put(("error", str(error), None))
        threading.Thread(target=run, daemon=True).start()

    def refresh(self):
        channels = self.store.channels()
        self.channel_map = {f"{c['name']} · {c['id'][:6]}" + (" [lưu trữ]" if c["archived"] else ""): c for c in channels}
        self.channel_combo["values"] = ["Tất cả kênh"]+list(self.channel_map)
        if self.channel_filter.get() not in self.channel_map:
            self.channel_filter.set("Tất cả kênh")
        projects = self.store.projects()
        albums = self.store.albums()
        ready = sum(p["stage"] == "ready" for p in projects)
        active = sum(p["stage"] != "published" for p in projects)
        self.summary.configure(text=f"{len(channels)} kênh   ·   {len(albums)} đợt phát hành   ·   {len(projects)} video/mix   ·   {active} đang sản xuất   ·   {ready} sẵn sàng")
        self.refresh_albums()
        self.refresh_projects()
        self.refresh_home(projects)
        self.refresh_analytics_projects()
        if self.current:
            self.load_project(self.current["id"])

    def refresh_home(self, projects=None):
        projects = projects if projects is not None else self.store.projects()
        channels = [row for row in self.store.channels() if not row["archived"]]
        albums = self.store.albums()
        counts = [("KÊNH", len(channels)), ("ĐỢT PHÁT HÀNH", len(albums)),
                  ("VIDEO ĐANG SẢN XUẤT", sum(p["stage"] not in ("published", "ready", "scheduled") for p in projects)),
                  ("SẴN SÀNG / ĐÃ LÊN LỊCH", sum(p["stage"] in ("ready", "scheduled") for p in projects))]
        if not channels:
            next_text = "Bước 1/3 · Tạo kênh đầu tiên. Đây là nơi nhóm các đợt phát hành và video."
            next_label, next_action = "Tạo kênh đầu tiên", self.channel_dialog
        elif not albums and not projects:
            next_text = "Bước 2/3 · Tạo đợt phát hành để nhóm các video cùng một lần ra mắt."
            next_label, next_action = "Tạo đợt phát hành", self.album_dialog
        elif not projects:
            next_text = "Bước 3/3 · Tạo video/mix đầu tiên trong một đợt phát hành."
            next_label, next_action = "Tạo video / mix", self.project_dialog
        else:
            next_text = "Chọn video bên dưới để tiếp tục, hoặc mở danh sách để lọc theo kênh và trạng thái."
            next_label, next_action = "Mở danh sách sản xuất", self.show_workspace
        self.home_next_text.configure(text=next_text)
        self.home_next_button.configure(text=next_label, command=lambda a=next_action: self.safe(a))
        for child in self.home_summary.winfo_children():
            child.destroy()
        for title, value in counts:
            card = tk.Frame(self.home_summary, bg="white", padx=16, pady=12, highlightbackground="#dce4ee", highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8))
            tk.Label(card, text=str(value), bg="white", fg="#14243c", font=("Segoe UI", 22, "bold")).pack(anchor="w")
            tk.Label(card, text=title, bg="white", fg="#62738a", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.home_tree.delete(*self.home_tree.get_children())
        active = [p for p in projects if p["stage"] not in ("published", "ready", "scheduled")]
        for project in active[:30]:
            label = f"{project['title']} · {project['album_name']}" if project.get("album_name") else project["title"]
            self.home_tree.insert("", "end", iid=project["id"], values=(label, STAGES[project["stage"]], project["channel_name"]))

    def refresh_albums(self):
        channel = self.channel_map.get(self.channel_filter.get(), {})
        rows = self.store.albums(channel.get("id", ""), self.search.get().strip())
        self.album_map = {f"{a['name']} · {a['channel_name']} · {a['published_count']}/{a['video_count']} đánh dấu đã đăng" + (f" · mục tiêu {a['target_date']}" if a.get("target_date") else ""): a for a in rows}
        values = ["Tất cả đợt phát hành", *self.album_map]
        current = self.album_filter.get()
        self.album_combo.configure(values=values)
        self.album_filter.set(current if current in self.album_map else values[0])
        self.refresh_projects()

    def select_album(self, event=None):
        album = self.album_map.get(self.album_filter.get())
        if album:
            label = next((key for key, value in self.channel_map.items() if value["id"] == album["channel_id"]), None)
            if label:
                self.channel_filter.set(label)
        self.refresh_albums()

    def refresh_projects(self):
        channel = self.channel_map.get(self.channel_filter.get(), {})
        stage = next((key for key, value in STAGES.items() if value == self.stage_filter.get()), "")
        album = self.album_map.get(self.album_filter.get(), {})
        projects = self.store.projects(channel.get("id", ""), self.search.get().strip(), stage, album.get("id", ""))
        selected = self.current["id"] if self.current else None
        self.projects_tree.delete(*self.projects_tree.get_children())
        self.project_rows = {p["id"]: p for p in projects}
        for p in projects:
            label = f"{p['title']} · {p['album_name']}" if p.get("album_name") else p["title"]
            self.projects_tree.insert("", "end", iid=p["id"], values=(label, STAGES[p["stage"]], p["channel_name"]))
        if selected in self.project_rows:
            self.projects_tree.selection_set(selected)
        elif selected:
            self.current = None
            self.tabs.tab(self.qc_tab, state="disabled")
            self.project_heading.configure(text="Chọn một video/mix trong danh sách đang lọc")
            self.project_meta.configure(text="")
            for var in (self.edit_title, self.edit_owner, self.edit_due, self.scheduled_at, self.youtube_url):
                var.set("")
            self.brief.delete("1.0", "end")
            self.assets_tree.delete(*self.assets_tree.get_children())
            self.asset_rows = {}
            self.channel_asset_rows = {}
            self.final_rows = {}
            self.final_tree.delete(*self.final_tree.get_children())
            self.asset_path.set("")
            self.audit_rows = {}
            self.audit_tree.delete(*self.audit_tree.get_children())
            self.audit_detail.configure(state="normal")
            self.audit_detail.delete("1.0", "end")
            self.audit_detail.configure(state="disabled")

    def select_project(self, event=None):
        selected = self.projects_tree.selection()
        if selected and (not self.current or selected[0] != self.current["id"]):
            self.safe(lambda: self.load_project(selected[0]))
            self.tabs.select(self.overview)

    def project_context_menu(self, event):
        project_id = self.projects_tree.identify_row(event.y)
        if not project_id:
            return
        self.projects_tree.selection_set(project_id)
        self.projects_tree.focus(project_id)
        menu = tk.Menu(self, tearoff=False)
        stage_menu = tk.Menu(menu, tearoff=False)
        current_stage = (self.project_rows.get(project_id) or {}).get("stage")
        for stage, label in STAGES.items():
            prefix = "✓ " if stage == current_stage else "   "
            stage_menu.add_command(label=prefix + label,
                                   command=lambda value=stage: self.safe(lambda: self.set_project_stage(project_id, value)))
        menu.add_cascade(label="Cập nhật Bước…", menu=stage_menu)
        menu.add_separator()
        menu.add_command(label="Xóa video…", command=lambda: self.safe(lambda: self.delete_project(project_id)))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def delete_project(self, project_id):
        project = self.project_rows.get(project_id) or self.store.project(project_id)
        if not messagebox.askyesno(
                "Xóa video",
                f"Xóa ‘{project['title']}’ khỏi Content Hub?\n\n"
                "Thông tin, tài nguyên đã nhập và lịch sử liên quan sẽ bị xóa khỏi Hub. "
                "File gốc trên máy sẽ được giữ nguyên.", parent=self):
            return
        self.store.delete_project(project_id, self.actor_name())
        if self.current and self.current["id"] == project_id:
            self.current = None
        self.refresh_projects()
        self.refresh_home()

    def load_project(self, project_id):
        self.current = self.store.project(project_id)
        p = self.current
        self.project_heading.configure(text=p["title"])
        album_label = f"Đợt phát hành: {p['album_name']}" if p.get("album_name") else "Chưa xếp đợt phát hành"
        self.project_meta.configure(text=f"{p['channel_name']}   /   {album_label}   /   {STAGES[p['stage']]}")
        self.tabs.tab(self.qc_tab, state="normal")
        self.rework_button.configure(state="normal" if p["stage"] in ("review", "ready", "scheduled") else "disabled")
        if p["stage"] == "ready":
            publish_label, publish_state = "Lưu lịch đăng", "normal"
        elif p["stage"] == "scheduled":
            publish_label, publish_state = "Xác nhận đã đăng", "normal"
        elif p["stage"] == "published":
            publish_label, publish_state = "Video đã đăng", "disabled"
        else:
            publish_label, publish_state = "Duyệt QC trước khi lên lịch", "disabled"
        self.publish_button.configure(text=publish_label, state=publish_state)
        stage_order = list(STAGES)
        if p["stage"] == "review":
            action_label, action_state = "Duyệt video ở tab Kiểm duyệt và Đăng", "disabled"
        elif p["stage"] == "ready":
            action_label, action_state = "Nhập lịch trong tab Kiểm duyệt và Đăng", "disabled"
        elif p["stage"] == "scheduled":
            action_label, action_state = "Xác nhận trong tab Kiểm duyệt và Đăng", "disabled"
        elif p["stage"] == "published":
            action_label, action_state = "Đã đăng", "disabled"
        else:
            next_stage = stage_order[stage_order.index(p["stage"]) + 1]
            action_label, action_state = f"Chuyển sang {STAGES[next_stage]}", "normal"
        self.advance_button.configure(text=action_label, state=action_state)
        self.edit_title.set(p["title"])
        self.edit_owner.set(p["owner"])
        self.edit_due.set(p["due_date"])
        album_options = {f"{row['name']} · {row['channel_name']}": row["id"]
                         for row in self.store.albums(p["channel_id"])}
        self.video_album_ids = album_options
        current_album = next((label for label, album_id in album_options.items() if album_id == p["album_id"]), None)
        self.video_album_combo.configure(values=["Không thuộc đợt phát hành", *album_options])
        self.video_album.set(current_album or "Không thuộc đợt phát hành")
        self.brief.delete("1.0", "end")
        self.brief.insert("1.0", p["brief"])
        self.scheduled_at.set(p["scheduled_at"][:16].replace("T", " "))
        self.youtube_url.set(p["youtube_url"])
        for var in self.checks.values():
            var.set(False)
        self.qc_note.delete("1.0", "end")
        assets = self.store.assets(project_id)
        channel_assets = self.store.channel_assets(p["channel_id"])
        self.asset_rows = {a["id"]: a for a in assets}
        self.channel_asset_rows = {a["id"]: a for a in channel_assets}
        self.assets_tree.delete(*self.assets_tree.get_children())
        for a in [*channel_assets, *(asset for asset in assets if asset["kind"] != "final")]:
            scope = "Kênh hiện tại" if a["id"] in self.channel_asset_rows else "Video hiện tại"
            self.assets_tree.insert("", "end", iid=a["id"], values=(ASSET_LABELS[a["kind"]], scope, a["slot"], a["version"], Path(a["path"]).name, f"{a['bytes']/1048576:.2f}"))
        self.asset_path.set("")
        final_assets = [a for a in assets if a["kind"] == "final"]
        self.final_rows = {a["id"]: a for a in final_assets}
        self.final_tree.delete(*self.final_tree.get_children())
        for asset in final_assets:
            self.final_tree.insert("", "end", iid=asset["id"],
                                   values=(asset["version"], Path(asset["path"]).name, f"{asset['bytes']/1048576:.2f}"))
        self.audit_rows = {}
        self.audit_tree.delete(*self.audit_tree.get_children())
        for index, event in enumerate(self.store.events(project_id)):
            event_id = str(index)
            self.audit_rows[event_id] = event
            timestamp = event["created_at"][:16].replace("T", " ")
            action = EVENT_LABELS.get(event["action"], event["action"].replace("_", " ").capitalize())
            self.audit_tree.insert("", "end", iid=event_id,
                                   values=(timestamp, action, self.audit_summary(event)))
        self.audit_detail.configure(state="normal")
        self.audit_detail.delete("1.0", "end")
        self.audit_detail.configure(state="disabled")

    def audit_summary(self, event):
        try:
            detail = json.loads(event["detail_json"])
        except (TypeError, json.JSONDecodeError):
            return ""
        if "from" in detail and "to" in detail:
            return f"{STAGES.get(detail['from'], detail['from'])} → {STAGES.get(detail['to'], detail['to'])}"
        if "title" in detail:
            return str(detail["title"])
        if "name" in detail:
            return str(detail["name"])
        if "kind" in detail:
            return ASSET_LABELS.get(detail["kind"], str(detail["kind"]))
        if "reason" in detail:
            return str(detail["reason"])
        if "error" in detail and detail["error"]:
            return str(detail["error"]).splitlines()[0][:120]
        if "note" in detail and detail["note"]:
            return str(detail["note"])
        return ""

    def show_audit_detail(self, event=None):
        selected = self.audit_tree.selection()
        if not selected:
            return
        row = self.audit_rows.get(selected[0], {})
        self.audit_detail.configure(state="normal")
        self.audit_detail.delete("1.0", "end")
        detail = json.loads(row.get("detail_json") or "{}")
        self.audit_detail.insert("1.0", json.dumps(detail, ensure_ascii=False, indent=2))
        self.audit_detail.configure(state="disabled")

    def channel_dialog(self):
        existing = self.channel_map.get(self.channel_filter.get())
        dialog = tk.Toplevel(self)
        dialog.title("Kênh YouTube")
        dialog.geometry("620x380")
        fields = {}
        for key, label in [("name","Tên kênh"),("niche","Ngách / thể loại"),("url","URL kênh"),("style","Phong cách hình ảnh và âm thanh")]:
            ttk.Label(dialog, text=label).pack(anchor="w", padx=15, pady=(8, 1))
            fields[key] = tk.StringVar(value=existing[key] if existing else "")
            ttk.Entry(dialog, textvariable=fields[key]).pack(fill="x", padx=15)
        archived = tk.BooleanVar(value=bool(existing and existing["archived"]))
        ttk.Checkbutton(dialog, text="Lưu trữ kênh (giữ dữ liệu dự án)", variable=archived).pack(anchor="w", padx=15, pady=8)
        def save():
            cid = self.store.save_channel(**{k:v.get().strip() for k,v in fields.items()},
                                         channel_id=existing["id"] if existing else None, actor=self.actor_name(), archived=archived.get())
            dialog.destroy()
            self.refresh()
            self.channel_filter.set(next(k for k,v in self.channel_map.items() if v["id"] == cid))
            self.refresh_projects()
        row = ttk.Frame(dialog)
        row.pack(fill="x", padx=15, pady=8)
        ttk.Button(row, text="Lưu kênh", command=lambda: self.safe(save)).pack(side="left")
        if existing:
            ttk.Button(row, text="Tạo kênh khác", command=lambda: (dialog.destroy(), self.channel_filter.set("Tất cả kênh"), self.channel_dialog())).pack(side="left", padx=8)
        dialog.transient(self)
        dialog.grab_set()

    def album_dialog(self, edit=False):
        channels = {k:v for k,v in self.channel_map.items() if not v["archived"]}
        existing = self.album_map.get(self.album_filter.get()) if edit else None
        if edit and not existing:
            raise DomainError("Chọn đợt phát hành cần sửa trước.")
        if not channels and not edit:
            raise DomainError("Tạo một kênh đang hoạt động trước.")
        dialog = tk.Toplevel(self)
        dialog.title("Sửa đợt phát hành" if edit else "Đợt phát hành mới")
        dialog.geometry("620x420")
        channel = tk.StringVar(value=self.channel_filter.get() if self.channel_filter.get() in channels else (next(iter(channels)) if channels else ""))
        if edit:
            channel.set(next((label for label, value in self.channel_map.items() if value["id"] == existing["channel_id"]), existing["channel_name"]))
        ttk.Label(dialog, text="Kênh đích").pack(anchor="w", padx=15, pady=(12, 2))
        ttk.Label(dialog, text=channel.get()).pack(anchor="w", padx=15)
        name = tk.StringVar(value=existing["name"] if edit else "")
        target = tk.StringVar(value=existing["target_date"] if edit else "")
        ttk.Label(dialog, text="Tên đợt phát hành").pack(anchor="w", padx=15, pady=(10, 2))
        ttk.Entry(dialog, textvariable=name).pack(fill="x", padx=15)
        ttk.Label(dialog, text="Ngày mục tiêu (không bắt buộc, ví dụ 2026-12-01)").pack(anchor="w", padx=15, pady=(10, 2))
        ttk.Entry(dialog, textvariable=target).pack(fill="x", padx=15)
        ttk.Label(dialog, text="Mô tả chung cho nhóm video (không bắt buộc)").pack(anchor="w", padx=15, pady=(10, 2))
        brief = tk.Text(dialog, height=6, wrap="word")
        brief.pack(fill="both", expand=True, padx=15)
        if edit:
            brief.insert("1.0", existing["brief"])
        def save():
            if edit:
                album_id = existing["id"]
                self.store.update_album(album_id, name.get(), brief.get("1.0", "end").strip(), target.get().strip(), self.actor_name())
            else:
                album_id = self.store.create_album(channels[channel.get()]["id"], name.get(),
                                                   brief.get("1.0", "end").strip(), target.get().strip(), self.actor_name())
            dialog.destroy()
            if not edit:
                self.channel_filter.set(channel.get())
            self.search.set("")
            self.refresh_albums()
            key = next((key for key, value in self.album_map.items() if value["id"] == album_id), None)
            if key:
                self.album_filter.set(key)
                self.refresh_projects()
            self.refresh_home()
            self.status.set("Đã lưu đợt phát hành. Mỗi video vẫn có file và tiến độ riêng.")
        ttk.Button(dialog, text="Lưu thay đổi" if edit else "Tạo đợt phát hành", command=lambda: self.safe(save)).pack(anchor="e", padx=15, pady=10)
        dialog.transient(self)
        dialog.grab_set()

    def project_dialog(self):
        channels = {k:v for k,v in self.channel_map.items() if not v["archived"]}
        if not channels:
            raise DomainError("Tạo một kênh đang hoạt động trước.")
        dialog = tk.Toplevel(self)
        dialog.title("Video / mix mới")
        dialog.geometry("650x490")
        channel = tk.StringVar(value=self.channel_filter.get() if self.channel_filter.get() in channels else next(iter(channels)))
        ttk.Label(dialog, text="Kênh đích").pack(anchor="w", padx=15, pady=8)
        ttk.Combobox(dialog, textvariable=channel, values=list(channels), state="readonly").pack(fill="x", padx=15)
        active_ids = {row["id"] for row in channels.values()}
        album_rows = [row for row in self.store.albums() if row["channel_id"] in active_ids]
        album_options = {f"{row['name']} · {row['channel_name']}": row for row in album_rows}
        initial_album = self.album_map.get(self.album_filter.get())
        album_var = tk.StringVar(value=next((key for key, row in album_options.items()
                                            if initial_album and row["id"] == initial_album["id"]), "Không thuộc đợt phát hành"))
        ttk.Label(dialog, text="Đợt phát hành (không bắt buộc)").pack(anchor="w", padx=15, pady=(8, 2))
        album_box = ttk.Combobox(dialog, textvariable=album_var, values=["Không thuộc đợt phát hành", *album_options], state="readonly")
        album_box.pack(fill="x", padx=15)
        def choose_album(event=None):
            selected = album_options.get(album_var.get())
            if selected:
                channel.set(next((key for key, value in channels.items() if value["id"] == selected["channel_id"]), channel.get()))
        album_box.bind("<<ComboboxSelected>>", choose_album)
        fields = {}
        for key, label in [("title","Tên video / mix"),("owner","Người phụ trách (không bắt buộc)"),("due_date","Hạn hoàn thành (ví dụ 2026-12-01, không bắt buộc)")]:
            ttk.Label(dialog, text=label).pack(anchor="w", padx=15, pady=(8, 1))
            fields[key] = tk.StringVar()
            ttk.Entry(dialog, textvariable=fields[key]).pack(fill="x", padx=15)
        ttk.Label(dialog, text="Mô tả nội dung (có thể bổ sung sau)").pack(anchor="w", padx=15, pady=8)
        brief = tk.Text(dialog, height=5, wrap="word")
        brief.pack(fill="both", expand=True, padx=15)
        def save():
            selected_album = album_options.get(album_var.get())
            pid = self.store.create_project(channels[channel.get()]["id"], **{k:v.get().strip() for k,v in fields.items()},
                                            brief=brief.get("1.0", "end").strip(), actor=self.actor_name(),
                                            album_id=selected_album["id"] if selected_album else None)
            self.channel_filter.set(channel.get())
            self.album_filter.set(next((key for key, value in self.album_map.items()
                                       if selected_album and value["id"] == selected_album["id"]), "Tất cả đợt phát hành"))
            self.stage_filter.set("Tất cả trạng thái")
            self.search.set("")
            dialog.destroy()
            self.refresh()
            self.load_project(pid)
            self.tabs.select(self.overview)
            self.show_workspace()
        ttk.Button(dialog, text="Tạo video / mix", command=lambda: self.safe(save)).pack(anchor="e", padx=15, pady=10)
        dialog.transient(self)
        dialog.grab_set()

    def save_brief(self):
        p = self.need_project()
        self.store.update_project(p["id"], p["revision"], self.edit_title.get(), self.brief.get("1.0", "end").strip(), self.edit_owner.get(), self.edit_due.get().strip(), self.actor_name())
        self.refresh()

    def set_video_album(self):
        p = self.need_project()
        album_id = self.video_album_ids.get(self.video_album.get())
        self.store.set_project_album(p["id"], album_id, self.actor_name())
        self.refresh()
        self.status.set("Đã cập nhật nhóm phát hành. File và tiến độ vẫn thuộc riêng video/mix này.")

    def advance(self):
        p, actor = self.need_project(), self.actor_name()
        scheduled, url = self.scheduled_at.get(), self.youtube_url.get()
        self.async_action(lambda: self.store.advance(p["id"], p["revision"], actor, scheduled, url), "Đã chuyển bước.")

    def set_project_stage(self, project_id, stage):
        self.store.set_stage(project_id, stage, self.actor_name())
        self.refresh()
        if project_id in self.project_rows:
            self.projects_tree.selection_set(project_id)
            self.projects_tree.focus(project_id)
            self.load_project(project_id)
        self.refresh_home()
        self.status.set(f"Đã cập nhật Bước: {STAGES[stage]}.")

    def rework(self):
        p = self.need_project()
        reason = simpledialog.askstring("Yêu cầu sửa", "Lý do chỉnh sửa:", parent=self)
        if reason:
            self.store.rework(p["id"], p["revision"], self.actor_name(), reason)
            self.refresh()

    def review(self, approved):
        p, actor = self.need_project(), self.actor_name()
        checks = [name for name,var in self.checks.items() if var.get()]
        note = self.qc_note.get("1.0", "end").strip()
        self.async_action(lambda: self.store.review(p["id"], p["revision"], actor, approved, checks, note), "Đã ghi nhận kết quả QC.")

    def import_assets(self):
        p, actor = self.need_project(), self.actor_name()
        kind = ASSET_KIND_BY_LABEL[self.asset_kind.get()]
        if kind == "final":
            raise DomainError("Video hoàn chỉnh được nhập tại tab Kiểm duyệt và Đăng.")
        paths = filedialog.askopenfilenames(title=f"Chọn {ASSET_LABELS[kind]}", parent=self)
        if not paths:
            return
        if kind in ("final", "thumbnail", "reference", "research") and len(paths)>1:
            raise DomainError("Loại này nhập một file mỗi lần để chọn rõ phiên bản main.")
        def action():
            if kind in CHANNEL_ASSET_KINDS:
                return [self.store.add_channel_asset(p["channel_id"], kind, Path(path), actor) for path in paths]
            return [self.store.add_asset(p["id"], kind, Path(path), actor) for path in paths]
        self.async_action(action, f"Đã nhập {len(paths)} tài nguyên; giữ nguyên file gốc.")

    def import_final(self):
        p, actor = self.need_project(), self.actor_name()
        paths = filedialog.askopenfilenames(title="Chọn video hoàn chỉnh", parent=self,
                                            filetypes=[("Video", "*.mp4 *.mov *.webm *.mkv")])
        if not paths:
            return
        if len(paths) != 1:
            raise DomainError("Chọn một video hoàn chỉnh mỗi lần.")
        self.async_action(lambda: self.store.add_asset(p["id"], "final", Path(paths[0]), actor),
                          "Đã nhập video hoàn chỉnh.")

    def open_final(self):
        p = self.need_project()
        selection = self.final_tree.selection()
        final = self.final_rows.get(selection[0]) if selection else next(
            (a for a in self.store.assets(p["id"], latest=True) if a["kind"] == "final"), None)
        if not final:
            raise DomainError("Chưa nhập video hoàn chỉnh.")
        self.open_path(Path(final["path"]))

    def selected_asset(self):
        selected = self.assets_tree.selection()
        if not selected:
            raise DomainError("Chọn một tài nguyên.")
        return self.asset_rows.get(selected[0]) or self.channel_asset_rows[selected[0]]

    def open_asset(self):
        self.open_path(Path(self.selected_asset()["path"]))

    def verify_asset(self):
        asset = self.selected_asset()
        self.async_action(lambda: self.store.verify_asset(asset), "File chưa thay đổi kể từ lần nhập.")

    def delete_asset(self):
        asset = self.selected_asset()
        filename = Path(asset["path"]).name
        if not messagebox.askyesno(
                "Xóa tài nguyên",
                f"Gỡ '{filename}' khỏi {'kênh' if asset['id'] in self.channel_asset_rows else 'video'}?\n\nFile gốc trên máy sẽ được giữ nguyên.",
                parent=self):
            return
        self.need_project()
        asset_id, actor = asset["id"], self.actor_name()
        if asset_id in self.channel_asset_rows:
            self.store.delete_channel_asset(asset_id, actor)
            self.load_project(self.current["id"])
        else:
            self.async_action(lambda: self.store.delete_asset(asset_id, actor), "Đã xóa tài nguyên khỏi danh sách.")

    def open_path(self, path):
        if not path.exists():
            raise DomainError(f"Không tìm thấy: {path}")
        os.startfile(str(path))

    def handoff(self):
        p = self.need_project()
        folder = self.adapters.prepare_handoff(p["id"], self.actor_name())
        self.open_path(folder)
        self.refresh()

    def launch_tool(self, tool):
        p = self.need_project()
        folder = self.adapters.launch(tool, p["id"], self.actor_name())
        self.status.set(f"Đã yêu cầu mở tool. Bàn giao: {folder}")
        self.refresh()

    def open_flow(self):
        p = self.need_project()
        folder = self.adapters.prepare_handoff(p["id"], self.actor_name())
        webbrowser.open("https://labs.google/fx/tools/flow")
        self.open_path(folder)
        self.status.set("Đã mở Flow và thư mục bàn giao. Bật Agent trên website nếu cần trợ lý sáng tạo; nhập kết quả vào video/mix này.")

    def export_project(self):
        p = self.need_project()
        output_folder = self.adapters.output_root / "Exports"
        output_folder.mkdir(parents=True, exist_ok=True)
        filename = filedialog.asksaveasfilename(title="Xuất hồ sơ dự án", initialdir=str(output_folder), initialfile=f"project_{p['id'][:8]}.json", defaultextension=".json", parent=self)
        if filename:
            try:
                Path(filename).resolve().relative_to(self.adapters.output_root.resolve())
            except ValueError:
                raise DomainError(f"File xuất phải nằm trong {self.adapters.output_root}.")
            Path(filename).write_text(json.dumps(self.store.export_bundle(p["id"]), ensure_ascii=False, indent=2), encoding="utf-8")
            self.status.set("Đã xuất hồ sơ gồm nguồn, phiên bản, QC, tác vụ và lịch sử.")

    def backup(self):
        output_folder = self.adapters.output_root / "Backups"
        output_folder.mkdir(parents=True, exist_ok=True)
        filename = filedialog.asksaveasfilename(title="Backup database", initialdir=str(output_folder), initialfile="content_hub_backup.sqlite3", defaultextension=".sqlite3", parent=self)
        if filename:
            try:
                Path(filename).resolve().relative_to(self.adapters.output_root.resolve())
            except ValueError:
                raise DomainError(f"File backup phải nằm trong {self.adapters.output_root}.")
            self.store.backup(filename)
            self.status.set("Đã backup database nhất quán. File media vẫn nằm ở đường dẫn gốc.")

    def open_guide(self):
        self.open_path(self.adapters.workspace / "CONTENT HUB" / "README.md")

    def poll(self):
        try:
            while True:
                kind, message, result = self.messages.get_nowait()
                self.busy = False
                if kind == "done" and isinstance(result, dict) and result.get("ctr_warning"):
                    message += " CTR: " + result["ctr_warning"]
                self.status.set(message)
                if kind == "error":
                    messagebox.showerror("Thao tác chưa hoàn tất", message, parent=self)
                self.refresh()
        except queue.Empty:
            pass
        self.after(250, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo("Đang xử lý", "Đợi thao tác nhập/kiểm tra file hoàn tất trước khi đóng.", parent=self)
            return
        self.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--self-check", type=Path)
    parser.add_argument("--smoke-render", type=Path)
    args = parser.parse_args()
    workspace = find_workspace()
    if args.smoke_render:
        from smoke import run
        run(workspace, args.smoke_render)
        return
    folder = workspace / "CONTENT HUB" / "data"
    folder.mkdir(parents=True, exist_ok=True)
    database = folder / ("demo.sqlite3" if args.demo else "content_hub.sqlite3")
    lock = None
    if not args.self_check:
        lock = InstanceLock(database.with_suffix(".lock"))
    try:
        store = Store(database)
        if args.demo:
            from demo import seed
            seed(store, workspace)
        app = Hub(store, workspace)
        if args.self_check:
            app.withdraw()
            app.update()
            if store.projects():
                app.load_project(store.projects()[0]["id"])
            args.self_check.write_text(json.dumps({"ui": "OK", "database": str(database),
                                                  "adapters": app.adapters.status(), "tabs": len(app.tabs.tabs()),
                                                  "channels": len(store.channels()), "projects": len(store.projects()),
                                                  "window_size": [app.winfo_width(), app.winfo_height()],
                                                  "screen_size": [app.winfo_screenwidth(), app.winfo_screenheight()]}, ensure_ascii=False, indent=2), encoding="utf-8")
            app.destroy()
        else:
            app.mainloop()
    finally:
        if lock:
            lock.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        import traceback
        log = Path(__file__).resolve().parent / "startup_error.log"
        try:
            log.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Content Hub", f"{error}\n\n{log}")
        root.destroy()
        raise SystemExit(1)
