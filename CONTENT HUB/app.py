"""YouTube Content Hub — local desktop workflow management."""
from __future__ import annotations
import argparse
import csv
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from store import Store, STAGES, KINDS, CHECKS, DomainError
from services import Adapters, RenderWorker, InstanceLock, find_workspace

TITLE = "YouTube Content Hub | Quản trị sản xuất đa kênh"
JOB_LABELS = {"queued":"Chờ", "running":"Đang chạy", "cancelling":"Đang dừng", "succeeded":"Hoàn tất",
              "failed":"Lỗi", "cancelled":"Đã hủy", "interrupted":"Gián đoạn"}

class Hub(tk.Tk):
    def __init__(self, store, workspace, start_worker=True):
        super().__init__()
        self.title(TITLE)
        width = min(1400, self.winfo_screenwidth()-60)
        height = min(900, self.winfo_screenheight()-90)
        self.geometry(f"{max(1000,width)}x{max(640,height)}")
        self.minsize(min(1150, width), min(680, height))
        self.configure(bg="#f2f5f9")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", rowheight=29, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(9, 5))
        self.store = store
        self.adapters = Adapters(store, workspace)
        self.worker = RenderWorker(store, self.adapters)
        self.current = None
        self.actor = tk.StringVar(value="Chủ dự án")
        self.channel_filter = tk.StringVar(value="Tất cả kênh")
        self.stage_filter = tk.StringVar(value="Tất cả trạng thái")
        self.search = tk.StringVar()
        self.status = tk.StringVar(value="Sẵn sàng · Dữ liệu cục bộ · Múi giờ Việt Nam UTC+7")
        self.messages = queue.Queue()
        self.busy = False
        self.channel_map = {}
        self.project_rows = {}
        self.asset_rows = {}
        self.job_rows = {}
        self._build()
        self.refresh()
        self.after(250, self.poll)
        self.protocol("WM_DELETE_WINDOW", self.close)
        if start_worker:
            self.worker.start()

    def _build(self):
        top = tk.Frame(self, bg="#14243c", padx=20, pady=14)
        top.pack(fill="x")
        tk.Label(top, text="CONTENT HUB", bg="#14243c", fg="white", font=("Segoe UI", 22, "bold")).pack(side="left")
        tk.Label(top, text="Nghiên cứu → Sản xuất → Kiểm duyệt → Xuất bản", bg="#14243c", fg="#a9c1dc", font=("Segoe UI", 11)).pack(side="left", padx=22)
        ttk.Entry(top, textvariable=self.actor, width=18).pack(side="right")
        tk.Label(top, text="Người thao tác", bg="#14243c", fg="white").pack(side="right", padx=8)
        bar = ttk.Frame(self, padding=(12, 8))
        bar.pack(fill="x")
        self.summary = ttk.Label(bar, font=("Segoe UI", 11, "bold"))
        self.summary.pack(side="left")
        for label, action in [("Làm mới", self.refresh), ("Backup DB", self.backup), ("Hướng dẫn", self.open_guide)]:
            ttk.Button(bar, text=label, command=lambda a=action: self.safe(a)).pack(side="right", padx=3)
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        left = ttk.Frame(body, padding=8)
        right = ttk.Frame(body, padding=8)
        body.add(left, weight=2)
        body.add(right, weight=4)
        ttk.Label(left, text="DANH MỤC SẢN XUẤT", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        row = ttk.Frame(left)
        row.pack(fill="x", pady=6)
        self.channel_combo = ttk.Combobox(row, textvariable=self.channel_filter, state="readonly")
        self.channel_combo.pack(side="left", fill="x", expand=True)
        self.channel_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_projects())
        ttk.Button(row, text="Kênh", command=lambda: self.safe(self.channel_dialog)).pack(side="right", padx=(5, 0))
        stage = ttk.Combobox(left, textvariable=self.stage_filter, state="readonly", values=["Tất cả trạng thái"]+list(STAGES.values()))
        stage.pack(fill="x", pady=3)
        stage.bind("<<ComboboxSelected>>", lambda e: self.refresh_projects())
        row = ttk.Frame(left)
        row.pack(fill="x", pady=5)
        entry = ttk.Entry(row, textvariable=self.search)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda e: self.refresh_projects())
        ttk.Button(row, text="Tìm", command=self.refresh_projects).pack(side="right", padx=(5, 0))
        self.projects_tree = self.tree(left, [("title", "Nội dung", 190), ("stage", "Trạng thái", 110), ("channel", "Kênh", 110)])
        self.projects_tree.bind("<<TreeviewSelect>>", self.select_project)
        ttk.Button(left, text="+ Dự án nội dung", command=lambda: self.safe(self.project_dialog)).pack(fill="x", pady=8)
        ttk.Label(left, text="Chọn kênh cụ thể rồi bấm Kênh để chỉnh sửa.\nKhông có dữ liệu mẫu trong database sản xuất.", wraplength=340, foreground="#62738a").pack(anchor="w")
        self.project_heading = ttk.Label(right, text="Chọn hoặc tạo một dự án nội dung", font=("Segoe UI", 15, "bold"), wraplength=760)
        self.project_heading.pack(anchor="w", pady=(0, 4))
        self.project_meta = ttk.Label(right, foreground="#456181")
        self.project_meta.pack(anchor="w", pady=(0, 8))
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self.overview = ttk.Frame(self.tabs, padding=10)
        self.asset_tab = ttk.Frame(self.tabs, padding=10)
        self.production_tab = ttk.Frame(self.tabs, padding=10)
        self.qc_tab = ttk.Frame(self.tabs, padding=10)
        self.metrics_tab = ttk.Frame(self.tabs, padding=10)
        self.audit_tab = ttk.Frame(self.tabs, padding=10)
        for tab, title in [(self.overview,"Dự án"),(self.asset_tab,"Tài nguyên"),(self.production_tab,"Tool & Render"),
                           (self.qc_tab,"QC & Lịch đăng"),(self.metrics_tab,"Hiệu suất"),(self.audit_tab,"Lịch sử")]:
            self.tabs.add(tab, text=title)
        self._overview()
        self._assets()
        self._production()
        self._qc()
        self._metrics()
        self.audit_text = tk.Text(self.audit_tab, wrap="word", state="disabled", font=("Consolas", 10))
        self.audit_text.pack(fill="both", expand=True)
        ttk.Label(self, textvariable=self.status, padding=(14, 6), foreground="#245b80").pack(fill="x")

    def tree(self, parent, columns, height=10):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height, selectmode="browse")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
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
        for label, var in [("Tiêu đề dự kiến", self.edit_title), ("Người phụ trách", self.edit_owner), ("Hạn hoàn thành (YYYY-MM-DD)", self.edit_due)]:
            ttk.Label(self.overview, text=label).pack(anchor="w", pady=(5, 0))
            ttk.Entry(self.overview, textvariable=var).pack(fill="x")
        ttk.Label(self.overview, text="Brief: mục tiêu, đối tượng, ý tưởng riêng, yêu cầu hình ảnh/âm thanh").pack(anchor="w", pady=(10, 3))
        self.brief = tk.Text(self.overview, height=8, wrap="word", font=("Segoe UI", 11))
        self.brief.pack(fill="both", expand=True)
        row = ttk.Frame(self.overview)
        row.pack(fill="x", pady=10)
        for label, action in [("Lưu brief", self.save_brief), ("Chuyển bước tiếp", self.advance),
                               ("Yêu cầu sửa", self.rework), ("Xuất hồ sơ JSON", self.export_project)]:
            ttk.Button(row, text=label, command=lambda a=action: self.safe(a)).pack(side="left", padx=3)
        ttk.Label(self.overview, text="Quy trình: Ý tưởng → Nghiên cứu → Thumbnail → Clip → Dựng → QC → Sẵn sàng → Lịch đăng → Đã đăng.\n"
                  "Mỗi bước kiểm tra đầu vào. Đăng YouTube và xác nhận số liệu thực hiện thủ công trong bản này.", wraplength=760, foreground="#62738a").pack(anchor="w")

    def _assets(self):
        row = ttk.Frame(self.asset_tab)
        row.pack(fill="x", pady=(0, 7))
        self.asset_kind = tk.StringVar(value="Clip Flow")
        ttk.Combobox(row, textvariable=self.asset_kind, values=list(KINDS.values()), state="readonly", width=22).pack(side="left")
        ttk.Button(row, text="+ Nhập file", command=lambda: self.safe(self.import_assets)).pack(side="left", padx=5)
        ttk.Button(row, text="Mở file", command=lambda: self.safe(self.open_asset)).pack(side="left")
        ttk.Button(row, text="Kiểm tra SHA-256", command=lambda: self.safe(self.verify_asset)).pack(side="left", padx=5)
        delete_row = ttk.Frame(self.asset_tab)
        delete_row.pack(fill="x", pady=(0, 7))
        ttk.Button(delete_row, text="Xóa tài nguyên", command=lambda: self.safe(self.delete_asset)).pack(side="left")
        self.assets_tree = self.tree(self.asset_tab, [("kind","Loại",100),("slot","Nhóm",100),("version","Bản",45),
                                                      ("file","Tên file",230),("size","MB",70)])
        self.assets_tree.bind("<<TreeviewSelect>>", lambda e: self.asset_path.set(self.selected_asset().get("path", "") if self.assets_tree.selection() else ""))
        self.assets_tree.bind("<Double-1>", lambda e: self.safe(self.open_asset))
        self.asset_path = tk.StringVar()
        ttk.Entry(self.asset_tab, textvariable=self.asset_path, state="readonly").pack(fill="x", pady=7)
        ttk.Label(self.asset_tab, text="Lưu tham chiếu file gốc + SHA-256, không nhân bản video dung lượng lớn.\n"
                  "Ảnh và thành phẩm dùng nhóm main. Clip/nhạc dùng tên file làm nhóm; nhập lại cùng nhóm để tăng phiên bản.\n"
                  "Thay tài nguyên sau QC sẽ đưa dự án về Dựng video để duyệt lại.", wraplength=760).pack(anchor="w")

    def _production(self):
        row = ttk.Frame(self.production_tab)
        row.pack(fill="x")
        for label, action in [("Mở Studio", lambda: self.launch_tool("studio")), ("Mở Editor", lambda: self.launch_tool("editor")),
                              ("Thư mục bàn giao", self.handoff)]:
            ttk.Button(row, text=label, command=lambda a=action: self.safe(a)).pack(side="left", padx=3)
        available = self.adapters.status()
        ttk.Label(self.production_tab, text=" · ".join(f"{name}: {'✓' if ok else 'thiếu'}" for name, ok in available.items()), wraplength=760).pack(anchor="w", pady=8)
        ttk.Label(self.production_tab, text="Studio mở để bạn nghiên cứu/tạo ảnh/clip. Mở tool chưa có nghĩa là đã sản xuất xong.\n"
                  "Thư mục bàn giao có brief, danh sách nguồn và editor_project.json; nhập kết quả về đúng dự án.", wraplength=760).pack(anchor="w")
        frame = ttk.LabelFrame(self.production_tab, text="Render nền bằng engine editor hiện có", padding=8)
        frame.pack(fill="x", pady=10)
        row = ttk.Frame(frame)
        row.pack(fill="x")
        self.render_minutes = tk.StringVar(value="60")
        self.resolution = tk.StringVar(value="720p")
        self.overlap = tk.StringVar(value="0.8")
        self.with_music = tk.BooleanVar(value=False)
        for label, variable in [("Phút", self.render_minutes), ("Overlap giây", self.overlap)]:
            ttk.Label(row, text=label).pack(side="left", padx=(5, 3))
            ttk.Entry(row, textvariable=variable, width=7).pack(side="left")
        ttk.Combobox(row, textvariable=self.resolution, state="readonly", values=["720p", "1080p", "1440p"], width=9).pack(side="left", padx=8)
        ttk.Checkbutton(row, text="Ghép nhạc (≥5 bài)", variable=self.with_music).pack(side="left")
        ttk.Button(frame, text="+ Đưa vào hàng đợi render", command=lambda: self.safe(self.enqueue)).pack(anchor="w", pady=(8, 0))
        self.jobs_tree = self.tree(self.production_tab, [("title","Dự án",180),("state","Trạng thái",90),("progress","%",45),("message","Thông tin",230)], height=5)
        self.jobs_tree.bind("<<TreeviewSelect>>", lambda e: self.show_job())
        row = ttk.Frame(self.production_tab)
        row.pack(fill="x", pady=5)
        for label, action in [("Hủy tác vụ", self.cancel_job), ("Thử lại", self.retry_job), ("Mở kết quả / log", self.open_job_folder)]:
            ttk.Button(row, text=label, command=lambda a=action: self.safe(a)).pack(side="left", padx=3)
        self.job_detail = tk.StringVar()
        ttk.Label(self.production_tab, textvariable=self.job_detail, wraplength=740, foreground="#6b4350").pack(anchor="w")

    def _qc(self):
        ttk.Label(self.qc_tab, text="Duyệt phiên bản video main mới nhất", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.checks = {name: tk.BooleanVar() for name in CHECKS}
        for name, variable in self.checks.items():
            ttk.Checkbutton(self.qc_tab, text=name, variable=variable).pack(anchor="w", pady=6)
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
        for label, var in [("Lịch đăng: YYYY-MM-DD HH:MM (giờ Việt Nam)", self.scheduled_at),
                           ("URL YouTube sau khi tự đăng", self.youtube_url)]:
            ttk.Label(self.qc_tab, text=label).pack(anchor="w", pady=(6, 2))
            ttk.Entry(self.qc_tab, textvariable=var).pack(fill="x")
        ttk.Button(self.qc_tab, text="Xác nhận bước lịch đăng / đã đăng", command=lambda: self.safe(self.advance)).pack(anchor="w", pady=10)
        ttk.Label(self.qc_tab, text="Lịch ở đây là kế hoạch nội bộ. Bản này không tự đăng hoặc đặt lịch trên YouTube.\n"
                  "Tên người thao tác là nhãn nhật ký cục bộ, chưa phải tài khoản có xác thực/phân quyền.", wraplength=740, foreground="#62738a").pack(anchor="w")

    def _metrics(self):
        ttk.Label(self.metrics_tab, text="Ảnh chụp chỉ số tích lũy — nhập thủ công từ YouTube Studio", wraplength=750).pack(anchor="w", pady=6)
        self.metric_vars = {}
        for name, label in [("views","Lượt xem"),("watch_minutes","Thời gian xem (phút)"),("impressions","Lượt hiển thị"),("ctr","CTR (%)")]:
            row = ttk.Frame(self.metrics_tab)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, width=28).pack(side="left")
            self.metric_vars[name] = tk.StringVar(value="0")
            ttk.Entry(row, textvariable=self.metric_vars[name]).pack(side="left", fill="x", expand=True)
        ttk.Button(self.metrics_tab, text="Lưu snapshot chỉ số", command=lambda: self.safe(self.save_metrics)).pack(anchor="w", pady=8)
        self.metrics_tree = self.tree(self.metrics_tab, [("time","Thời điểm UTC+7",190),("views","Views",90),("watch","Phút xem",100),("ctr","CTR %",80)])
        ttk.Label(self.metrics_tab, text="Snapshot là số tích lũy tại thời điểm ghi; không cộng các snapshot thành tổng lượt xem.\n"
                  "Bản này chưa kết nối YouTube Analytics tự động.", wraplength=740).pack(anchor="w", pady=6)

    def actor_name(self):
        name = self.actor.get().strip()
        if not name:
            raise DomainError("Nhập tên người thao tác ở góc phải.")
        return name

    def safe(self, action):
        try:
            return action()
        except Exception as error:
            messagebox.showerror("Chưa thực hiện được", str(error), parent=self)

    def need_project(self):
        if not self.current:
            raise DomainError("Chọn dự án nội dung trước.")
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
        ready = sum(p["stage"] == "ready" for p in projects)
        active = sum(p["stage"] != "published" for p in projects)
        self.summary.configure(text=f"{len(channels)} kênh   ·   {len(projects)} dự án   ·   {active} đang sản xuất   ·   {ready} sẵn sàng")
        self.refresh_projects()
        self.refresh_jobs()
        if self.current:
            self.load_project(self.current["id"])

    def refresh_projects(self):
        channel = self.channel_map.get(self.channel_filter.get(), {})
        stage = next((key for key, value in STAGES.items() if value == self.stage_filter.get()), "")
        projects = self.store.projects(channel.get("id", ""), self.search.get().strip(), stage)
        selected = self.current["id"] if self.current else None
        self.projects_tree.delete(*self.projects_tree.get_children())
        self.project_rows = {p["id"]: p for p in projects}
        for p in projects:
            self.projects_tree.insert("", "end", iid=p["id"], values=(p["title"], STAGES[p["stage"]], p["channel_name"]))
        if selected in self.project_rows:
            self.projects_tree.selection_set(selected)
        elif selected:
            self.current = None
            self.project_heading.configure(text="Chọn một dự án trong danh sách đang lọc")
            self.project_meta.configure(text="")
            for var in (self.edit_title, self.edit_owner, self.edit_due, self.scheduled_at, self.youtube_url):
                var.set("")
            self.brief.delete("1.0", "end")
            self.assets_tree.delete(*self.assets_tree.get_children())
            self.metrics_tree.delete(*self.metrics_tree.get_children())
            self.asset_rows = {}
            self.asset_path.set("")

    def select_project(self, event=None):
        selected = self.projects_tree.selection()
        if selected and (not self.current or selected[0] != self.current["id"]):
            self.safe(lambda: self.load_project(selected[0]))

    def load_project(self, project_id):
        self.current = self.store.project(project_id)
        p = self.current
        self.project_heading.configure(text=p["title"])
        self.project_meta.configure(text=f"{p['channel_name']}   /   {STAGES[p['stage']]}   /   {p['id'][:8]}   /   revision {p['revision']}")
        self.edit_title.set(p["title"])
        self.edit_owner.set(p["owner"])
        self.edit_due.set(p["due_date"])
        self.brief.delete("1.0", "end")
        self.brief.insert("1.0", p["brief"])
        self.scheduled_at.set(p["scheduled_at"][:16].replace("T", " "))
        self.youtube_url.set(p["youtube_url"])
        for var in self.checks.values():
            var.set(False)
        self.qc_note.delete("1.0", "end")
        assets = self.store.assets(project_id)
        self.asset_rows = {a["id"]: a for a in assets}
        self.assets_tree.delete(*self.assets_tree.get_children())
        for a in assets:
            self.assets_tree.insert("", "end", iid=a["id"], values=(KINDS[a["kind"]], a["slot"], a["version"], Path(a["path"]).name, f"{a['bytes']/1048576:.2f}"))
        self.asset_path.set("")
        self.metrics_tree.delete(*self.metrics_tree.get_children())
        for m in self.store.rows("SELECT * FROM metrics WHERE project_id=? ORDER BY recorded_at DESC", (project_id,)):
            self.metrics_tree.insert("", "end", values=(m["recorded_at"], m["views"], m["watch_minutes"], m["ctr"]))
        events = self.store.events(project_id)
        self.audit_text.configure(state="normal")
        self.audit_text.delete("1.0", "end")
        for e in events:
            self.audit_text.insert("end", f"{e['created_at']} | {e['actor']} | {e['action']}\n{e['detail_json']}\n\n")
        self.audit_text.configure(state="disabled")

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

    def project_dialog(self):
        channels = {k:v for k,v in self.channel_map.items() if not v["archived"]}
        if not channels:
            raise DomainError("Tạo một kênh đang hoạt động trước.")
        dialog = tk.Toplevel(self)
        dialog.title("Dự án nội dung mới")
        dialog.geometry("650x490")
        channel = tk.StringVar(value=self.channel_filter.get() if self.channel_filter.get() in channels else next(iter(channels)))
        ttk.Label(dialog, text="Kênh đích").pack(anchor="w", padx=15, pady=8)
        ttk.Combobox(dialog, textvariable=channel, values=list(channels), state="readonly").pack(fill="x", padx=15)
        fields = {}
        for key, label in [("title","Tiêu đề"),("owner","Người phụ trách"),("due_date","Hạn YYYY-MM-DD (tùy chọn)")]:
            ttk.Label(dialog, text=label).pack(anchor="w", padx=15, pady=(8, 1))
            fields[key] = tk.StringVar()
            ttk.Entry(dialog, textvariable=fields[key]).pack(fill="x", padx=15)
        ttk.Label(dialog, text="Brief").pack(anchor="w", padx=15, pady=8)
        brief = tk.Text(dialog, height=5, wrap="word")
        brief.pack(fill="both", expand=True, padx=15)
        def save():
            pid = self.store.create_project(channels[channel.get()]["id"], **{k:v.get().strip() for k,v in fields.items()},
                                            brief=brief.get("1.0", "end").strip(), actor=self.actor_name())
            self.channel_filter.set(channel.get())
            self.stage_filter.set("Tất cả trạng thái")
            self.search.set("")
            dialog.destroy()
            self.refresh()
            self.load_project(pid)
        ttk.Button(dialog, text="Tạo dự án", command=lambda: self.safe(save)).pack(anchor="e", padx=15, pady=10)
        dialog.transient(self)
        dialog.grab_set()

    def save_brief(self):
        p = self.need_project()
        self.store.update_project(p["id"], p["revision"], self.edit_title.get(), self.brief.get("1.0", "end").strip(), self.edit_owner.get(), self.edit_due.get().strip(), self.actor_name())
        self.refresh()

    def advance(self):
        p, actor = self.need_project(), self.actor_name()
        scheduled, url = self.scheduled_at.get(), self.youtube_url.get()
        self.async_action(lambda: self.store.advance(p["id"], p["revision"], actor, scheduled, url), "Đã chuyển bước.")

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
        kind = next(k for k,v in KINDS.items() if v == self.asset_kind.get())
        paths = filedialog.askopenfilenames(title=f"Nhập {KINDS[kind]}", parent=self)
        if not paths:
            return
        if kind in ("final", "thumbnail", "reference", "research") and len(paths)>1:
            raise DomainError("Loại này nhập một file mỗi lần để chọn rõ phiên bản main.")
        def action():
            return [self.store.add_asset(p["id"], kind, Path(path), actor) for path in paths]
        self.async_action(action, f"Đã nhập {len(paths)} tài nguyên; giữ nguyên file gốc.")

    def selected_asset(self):
        selected = self.assets_tree.selection()
        if not selected:
            raise DomainError("Chọn một tài nguyên.")
        return self.asset_rows[selected[0]]

    def open_asset(self):
        self.open_path(Path(self.selected_asset()["path"]))

    def verify_asset(self):
        asset = self.selected_asset()
        self.async_action(lambda: self.store.verify_asset(asset), "SHA-256 khớp; file không thay đổi.")

    def delete_asset(self):
        asset = self.selected_asset()
        filename = Path(asset["path"]).name
        if not messagebox.askyesno(
                "Xóa tài nguyên",
                f"Xóa mục tham chiếu '{filename}' khỏi dự án?\n\nFile gốc trên máy sẽ được giữ nguyên.",
                parent=self):
            return
        self.need_project()
        asset_id, actor = asset["id"], self.actor_name()
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

    def enqueue(self):
        p = self.need_project()
        minutes = float(self.render_minutes.get())
        seconds = round(minutes*60)
        if abs(minutes*60-seconds) > 1e-6:
            raise DomainError("Thời lượng phải quy đổi thành số giây nguyên.")
        self.adapters.enqueue_render(p["id"], seconds, self.resolution.get(), float(self.overlap.get()), self.actor_name(), music_enabled=self.with_music.get())
        self.refresh_jobs()
        self.status.set("Đã xếp hàng. Worker chạy từng render để hạn chế RAM; bấm Làm mới khi hoàn tất.")

    def refresh_jobs(self):
        selected = self.jobs_tree.selection()
        self.job_rows = {j["id"]:j for j in self.store.jobs()}
        self.jobs_tree.delete(*self.jobs_tree.get_children())
        for job in self.job_rows.values():
            self.jobs_tree.insert("", "end", iid=job["id"], values=(f"{job['channel_name']} • {job['title']}", JOB_LABELS.get(job["state"], job["state"]), f"{job['progress']:.0f}", job["message"]))
        if selected and selected[0] in self.job_rows:
            self.jobs_tree.selection_set(selected[0])

    def selected_job(self):
        selected = self.jobs_tree.selection()
        if not selected:
            raise DomainError("Chọn một tác vụ trong bảng.")
        return self.job_rows[selected[0]]

    def show_job(self):
        if self.jobs_tree.selection():
            j = self.selected_job()
            self.job_detail.set(f"{j['id'][:8]} · {j['error'] or j['message']}")

    def cancel_job(self):
        self.worker.cancel(self.selected_job()["id"], self.actor_name())
        self.refresh_jobs()

    def retry_job(self):
        self.adapters.retry(self.selected_job()["id"], self.actor_name())
        self.refresh_jobs()

    def open_job_folder(self):
        j = self.selected_job()
        folder = self.adapters.output_root / "Renders" / j["project_id"] / j["id"]
        self.open_path(folder)

    def save_metrics(self):
        p = self.need_project()
        values = {k: float(v.get()) for k,v in self.metric_vars.items()}
        if values["views"] != int(values["views"]) or values["impressions"] != int(values["impressions"]):
            raise DomainError("Views và impressions phải là số nguyên.")
        self.store.add_metrics(p["id"], **values, actor=self.actor_name())
        self.refresh()

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
                self.status.set(message)
                if kind == "error":
                    messagebox.showerror("Thao tác chưa hoàn tất", message, parent=self)
                self.refresh()
        except queue.Empty:
            pass
        if not getattr(self, "_last_job_poll", 0) or __import__("time").monotonic()-self._last_job_poll > 1.5:
            self.refresh_jobs()
            self._last_job_poll = __import__("time").monotonic()
        self.after(250, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo("Đang xử lý", "Đợi thao tác nhập/kiểm tra file hoàn tất trước khi đóng.", parent=self)
            return
        if self.worker.current_id and not messagebox.askyesno("Đang render", "Dừng render và đóng? Tác vụ chờ được giữ để chạy lần sau.", parent=self):
            return
        self.worker.shutdown()
        self.status.set("Đang dừng worker…")
        def finish():
            if self.worker.thread and self.worker.thread.is_alive():
                self.after(150, finish)
            else:
                self.destroy()
        finish()


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
        app = Hub(store, workspace, start_worker=not bool(args.self_check))
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
