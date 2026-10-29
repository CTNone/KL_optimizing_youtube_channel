"""NCTT + Flow TXT: reuse NCTT UI and hand off explicit jobs to Chrome."""
from pathlib import Path
import importlib.util
import json
import os
import uuid
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from PIL import Image, ImageTk
from desktop_flow import DesktopFlow
from chrome_profile import discover_profiles

ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT.parent / 'TOOL Video Flow OUTPUT' / 'Thumbnail'
NCTT = ROOT.parent / 'TOOL NCTT'
QUEUE = ROOT / 'chrome-extension' / 'native-host' / 'nctt-job.json'


class ScrollablePanel(ttk.Frame):
    """Keep the entire thumbnail form reachable on smaller displays."""
    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.vertical = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.vertical.grid(row=0, column=1, sticky='ns')
        self.horizontal = ttk.Scrollbar(self, orient='horizontal', command=self.canvas.xview)
        self.horizontal.grid(row=1, column=0, sticky='ew')
        self.canvas.configure(yscrollcommand=self.vertical.set, xscrollcommand=self.horizontal.set)
        self.content = ttk.Frame(self.canvas, padding=12)
        self.window = self.canvas.create_window(0, 0, window=self.content, anchor='nw')
        self.content.bind('<Configure>', self.resize)
        self.canvas.bind('<Configure>', self.resize)
        self.bind_all('<MouseWheel>', self.wheel, add='+')

    def resize(self, event=None):
        width = max(self.content.winfo_reqwidth(), self.canvas.winfo_width())
        height = max(self.content.winfo_reqheight(), self.canvas.winfo_height())
        self.canvas.itemconfigure(self.window, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))

    def wheel(self, event):
        widget = event.widget
        if not str(widget).startswith(str(self) + '.'):
            return
        # Prompt/library keep their own scrolling; the form scrolls elsewhere.
        if widget.winfo_class() in ('Text', 'Listbox', 'TCombobox'):
            return
        units = -int(event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1)
        if event.state & 1:
            self.canvas.xview_scroll(units, 'units')
        else:
            self.canvas.yview_scroll(units, 'units')
        return 'break'


def write_job(prompt, reference=None, model='Nano Banana 2 Lite', count=1):
    if not prompt.strip():
        raise ValueError('Chưa nhập prompt.')
    if len(prompt) > 100000:
        raise ValueError('Prompt vượt 100.000 ký tự.')
    if reference:
        reference = Path(reference).resolve(strict=True)
        reference.relative_to(NCTT.resolve())
        if reference.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
            raise ValueError('Ảnh mẫu không đúng định dạng.')
    if QUEUE.exists():
        raise ValueError('Còn yêu cầu chưa được nhận. Mở Flow TXT và nhận yêu cầu trước khi chuyển tiếp.')
    job = {'id': uuid.uuid4().hex, 'prompt': prompt.strip(), 'reference': str(reference) if reference else None,
           'model': model, 'count': int(count)}
    temporary = QUEUE.with_suffix('.tmp')
    temporary.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
    os.replace(temporary, QUEUE)
    return job


def load_nctt():
    spec = importlib.util.spec_from_file_location('market_research', NCTT / 'app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    market = load_nctt()

    class UnifiedApp(market.App):
        def build(self):
            super().build()
            style = ttk.Style(self)
            style.theme_use('clam')
            style.configure('.', font=('Segoe UI', 10))
            style.configure('TFrame', background='#f3f5fa')
            style.configure('TLabel', background='#f3f5fa', foreground='#23324a')
            style.configure('Card.TFrame', background='#ffffff')
            style.configure('Card.TLabel', background='#ffffff', foreground='#23324a')
            style.configure('Muted.TLabel', background='#ffffff', foreground='#68778d')
            style.configure('Title.TLabel', background='#ffffff', foreground='#15243c', font=('Segoe UI', 13, 'bold'))
            style.configure('TButton', padding=(12, 8), background='#e8edf5', borderwidth=0)
            style.configure('Primary.TButton', background='#2563eb', foreground='#ffffff', font=('Segoe UI', 10, 'bold'))
            style.map('Primary.TButton', background=[('active', '#1d4ed8'), ('disabled', '#9caac0')])
            style.configure('TNotebook', background='#f3f5fa', borderwidth=0)
            style.configure('TNotebook.Tab', padding=(22, 12))
            style.map('TNotebook.Tab', background=[('selected', '#ffffff')], foreground=[('selected', '#2563eb')])
            widgets = [(widget, widget.pack_info()) for widget in self.winfo_children() if widget.winfo_manager() == 'pack']
            for widget, _ in widgets:
                widget.pack_forget()
            header = tk.Frame(self, bg='#14243d', padx=24, pady=16)
            header.pack(fill='x')
            tk.Label(header, text='YOUTUBE MUSIC STUDIO', bg='#14243d', fg='white', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
            hub_channel = os.environ.get('CONTENT_HUB_CHANNEL_NAME', '').strip()
            subtitle = 'Nghiên cứu thị trường  /  Xây dựng ý tưởng  /  Tạo thumbnail'
            if hub_channel:
                subtitle += f'  ·  Kênh Content Hub: {hub_channel}'
            tk.Label(header, text=subtitle, bg='#14243d', fg='#b8c8e1', font=('Segoe UI', 10)).pack(anchor='w', pady=(4, 0))
            tabs = ttk.Notebook(self)
            tabs.pack(fill='both', expand=True)
            research = ttk.Frame(tabs)
            self.thumbnail_scroller = ScrollablePanel(tabs)
            thumbnail = self.thumbnail_scroller.content
            tabs.add(research, text='1. Nghiên cứu thị trường')
            tabs.add(self.thumbnail_scroller, text='2. Làm thumbnail')
            for widget, options in widgets:
                options.pop('in', None)
                widget.pack(in_=research, **options)
            self.title('NCTT + Thumbnail')
            self.geometry(f'{min(1320, self.winfo_screenwidth() - 80)}x{min(940, self.winfo_screenheight() - 100)}')
            self.minsize(800, 520)
            self.references = []
            self.reference = None
            self.selected = tk.StringVar(value="Không dùng ảnh mẫu")
            self.thumbnail_model = tk.StringVar(value="Nano Banana 2 Lite")
            self.thumbnail_count = tk.StringVar(value="1")
            self.thumbnail_ratio = tk.StringVar(value='4:3')
            self.redesign_thumbnail(thumbnail)
            self.desktop_running = False
            self.closing = False
            self.controller = DesktopFlow(self.handle_flow_state, self.handle_flow_error)
            settings_file = ROOT / 'desktop-settings.json'
            try:
                self.desktop_cfg = json.loads(settings_file.read_text(encoding='utf-8')) if settings_file.exists() else {}
            except Exception:
                self.desktop_cfg = {}
            history_tab = ttk.Frame(tabs, padding=16)
            tabs.add(history_tab, text='3. Trạng thái & lịch sử')
            self.flow_logs = tk.Text(history_tab, wrap='word', bg='#ffffff', fg='#23324a', font=('Segoe UI', 10), padx=16, pady=16, state='disabled')
            self.flow_logs.pack(fill='both', expand=True)
            self.protocol('WM_DELETE_WINDOW', self.close_studio)

        def redesign_thumbnail(self, parent):
            # Rebuild only this tab; research keeps its existing widgets.
            prompt = ""
            for widget in parent.winfo_children():
                widget.destroy()
            parent.columnconfigure(0, weight=0, minsize=270)
            parent.columnconfigure(1, weight=1)
            parent.columnconfigure(2, weight=0, minsize=250)
            parent.rowconfigure(0, weight=0)
            parent.rowconfigure(1, weight=1)
            parent.rowconfigure(2, weight=0)
            ttk.Label(parent, text='Tạo thumbnail trực tiếp trên Google Flow', font=('Segoe UI', 18, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(4, 16))
            library = ttk.Frame(parent, style='Card.TFrame', padding=16)
            library.grid(row=1, column=0, sticky='nsew', padx=(0, 12))
            library.columnconfigure(0, weight=1)
            library.rowconfigure(3, weight=1)
            ttk.Label(library, text='01  Thư viện ảnh', style='Title.TLabel').grid(row=0, column=0, columnspan=2, sticky='w')
            self.reference_folder = tk.StringVar(value='Chưa chọn thư mục ảnh')
            ttk.Button(library, text='Chọn thư mục ảnh input…', command=self.choose_reference_folder).grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 4))
            ttk.Label(library, textvariable=self.reference_folder, style='Muted.TLabel', wraplength=230).grid(row=2, column=0, columnspan=2, sticky='w', pady=(0, 8))
            self.library_count = tk.StringVar()
            ttk.Label(library, textvariable=self.library_count, style='Muted.TLabel').grid(row=3, column=0, columnspan=2, sticky='w', pady=(0, 8))
            self.search_reference = tk.StringVar()
            search = ttk.Entry(library, textvariable=self.search_reference, width=30)
            search.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(0, 10))
            self.search_reference.trace_add('write', lambda *_: self.filter_gallery())
            self.gallery = tk.Listbox(library, width=29, exportselection=False, bg='#ffffff', fg='#334155', selectbackground='#dbeafe', selectforeground='#1e40af', borderwidth=0, highlightthickness=0, font=('Segoe UI', 10), activestyle='none')
            self.gallery.grid(row=5, column=0, sticky='nsew')
            scrollbar = ttk.Scrollbar(library, command=self.gallery.yview)
            scrollbar.grid(row=5, column=1, sticky='ns')
            self.gallery.configure(yscrollcommand=scrollbar.set)
            self.gallery.bind('<<ListboxSelect>>', self.select_reference)
            ttk.Button(library, text='Chọn một ảnh riêng…', command=self.pick_reference).grid(row=6, column=0, columnspan=2, sticky='ew', pady=(12, 6))
            ttk.Button(library, text='Nạp lại thư mục đã chọn', command=self.refresh_gallery).grid(row=7, column=0, columnspan=2, sticky='ew')
            workspace = ttk.Frame(parent, style='Card.TFrame', padding=20)
            workspace.grid(row=1, column=1, sticky='nsew', padx=(0, 12))
            workspace.columnconfigure(0, weight=1)
            workspace.rowconfigure(5, weight=1)
            ttk.Label(workspace, text='02  Ý tưởng & bố cục', style='Title.TLabel').grid(row=0, column=0, sticky='w')
            self.preview = ttk.Label(workspace, text='Chọn ảnh bên trái để xem trước\nhoặc dùng prompt để tạo ý tưởng mới', anchor='center', style='Muted.TLabel', padding=22)
            self.preview.grid(row=1, column=0, sticky='ew', pady=(14, 8))
            self.selected.set('Không dùng ảnh mẫu')
            self.reference = None
            ttk.Label(workspace, textvariable=self.selected, style='Muted.TLabel', wraplength=470).grid(row=2, column=0, sticky='w')
            ttk.Button(workspace, text='Bỏ ảnh · chỉ dùng prompt', command=self.clear_reference).grid(row=3, column=0, sticky='w', pady=(8, 18))
            prompt_header = ttk.Frame(workspace, style='Card.TFrame')
            prompt_header.grid(row=4, column=0, sticky='ew', pady=(0, 8))
            ttk.Label(prompt_header, text='Ý tưởng thumbnail', style='Card.TLabel', font=('Segoe UI', 11, 'bold')).pack(side='left')
            ttk.Button(prompt_header, text='Mở prompt TXT…', command=self.import_prompt).pack(side='right')
            prompt_frame = ttk.Frame(workspace)
            prompt_frame.grid(row=5, column=0, sticky='nsew')
            prompt_frame.rowconfigure(0, weight=1)
            prompt_frame.columnconfigure(0, weight=1)
            self.thumbnail_prompt = tk.Text(prompt_frame, height=9, wrap='word', bg='#f8fafc', fg='#23324a', insertbackground='#2563eb', font=('Segoe UI', 11), relief='flat', highlightthickness=1, highlightbackground='#dce3ee', padx=12, pady=12, undo=True)
            self.thumbnail_prompt.grid(row=0, column=0, sticky='nsew')
            self.prompt_scrollbar = ttk.Scrollbar(prompt_frame, orient='vertical', command=self.thumbnail_prompt.yview)
            self.prompt_scrollbar.grid(row=0, column=1, sticky='ns')
            self.thumbnail_prompt.configure(yscrollcommand=self.prompt_scrollbar.set)
            self.thumbnail_prompt.insert('1.0', prompt)
            settings = ttk.Frame(parent, style='Card.TFrame', padding=18)
            settings.grid(row=1, column=2, sticky='nsew')
            ttk.Label(settings, text='03  Chuẩn bị tạo', style='Title.TLabel').pack(anchor='w', pady=(0, 20))
            ttk.Label(settings, text='Mô hình trên Google Flow', style='Card.TLabel').pack(anchor='w')
            ttk.Combobox(settings, textvariable=self.thumbnail_model, values=['Nano Banana Pro', 'Nano Banana 2.1', 'Nano Banana 2 Lite'], state='readonly', width=23).pack(fill='x', pady=(8, 18))
            ttk.Label(settings, text='Số ảnh cần tạo', style='Card.TLabel').pack(anchor='w')
            ttk.Combobox(settings, textvariable=self.thumbnail_count, values=['1', '2', '3', '4'], state='readonly', width=5).pack(fill='x', pady=(8, 22))
            ttk.Label(settings, text='Tỉ lệ ảnh trên Google Flow', style='Card.TLabel').pack(anchor='w')
            ttk.Combobox(settings, textvariable=self.thumbnail_ratio, values=['16:9','4:3','1:1','3:4','9:16'], state='readonly', width=10).pack(fill='x', pady=(6, 12))
            ttk.Label(settings, text='Bản gốc theo tỉ lệ đã chọn.\nBản cắt vẫn là 16:9.', style='Muted.TLabel').pack(anchor='w', pady=(0, 12))
            ttk.Separator(settings).pack(fill='x')
            self.chrome_profile = tk.StringVar(value='account-1')
            ttk.Label(settings, text='Hồ sơ Desktop riêng (tùy chọn)', style='Card.TLabel').pack(anchor='w', pady=(12, 4))
            ttk.Entry(settings, textvariable=self.chrome_profile, width=23).pack(fill='x')
            ttk.Button(settings, text='Mở Flow trong hồ sơ riêng', command=lambda: self.controller.submit(self.controller.open(self.chrome_profile.get().strip()))).pack(fill='x', pady=(6, 12))
            ttk.Button(settings, text='Nhập phiên (tùy chọn)…', command=self.import_chrome_profile).pack(fill='x', pady=(0, 8))
            self.source_profiles = []
            self.source_profile_choice = tk.StringVar()
            self.source_profile_label = ttk.Label(settings, text='Hồ sơ Chrome trên máy')
            self.source_profile_label.pack(anchor='w')
            self.source_profile_combo = ttk.Combobox(settings, textvariable=self.source_profile_choice, state='readonly', width=23)
            self.source_profile_combo.pack(fill='x', pady=(4, 4))
            ttk.Button(settings, text='Quét lại hồ sơ Chrome', command=self.refresh_chrome_profiles).pack(fill='x', pady=(0, 8))
            self.refresh_chrome_profiles()
            ttk.Button(settings, text='Kết nối Chrome đang mở', style='Primary.TButton', command=self.connect_current_chrome).pack(fill='x', pady=(0, 8))
            ttk.Label(settings, text='Dùng phiên có sẵn: chọn hồ sơ,\nmở Flow rồi bấm Kết nối.', style='Muted.TLabel').pack(anchor='w', pady=(0, 8))
            OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
            self.output_folder = tk.StringVar(value=str(OUTPUT_ROOT))
            ttk.Button(settings, text='Chọn nơi lưu ảnh…', command=self.choose_output).pack(fill='x')
            ttk.Label(settings, textvariable=self.output_folder, style='Muted.TLabel', wraplength=225).pack(anchor='w', pady=(6, 12))
            self.create_thumbnail = ttk.Button(settings, text='Tạo ảnh trực tiếp trên Flow', style='Primary.TButton', command=self.send_thumbnail)
            self.create_thumbnail.pack(fill='x', pady=(8, 6))
            self.stop_thumbnail = ttk.Button(settings, text='Dừng lượt hiện tại', command=lambda: self.controller.submit(self.controller.stop()), state='disabled')
            self.stop_thumbnail.pack(fill='x', pady=(0, 8))
            ttk.Button(settings, text='Đã đổi account · đặt lại hạn mức', command=lambda: self.controller.submit(self.controller.reset_limits())).pack(fill='x', pady=(4, 10))
            ttk.Button(settings, text='Cài đặt nâng cao…', command=self.advanced_flow).pack(fill='x', pady=(0, 8))
            ttk.Label(settings, text='Tải 2K • lưu gốc + 16:9\nĐăng nhập/đổi account trong\ncửa sổ Chrome của Desktop.', style='Muted.TLabel', justify='left').pack(anchor='w')
            self.studio_status = tk.StringVar(value='Sẵn sàng • Chọn ảnh mẫu hoặc nhập prompt để bắt đầu')
            ttk.Label(parent, textvariable=self.studio_status).grid(row=2, column=0, columnspan=3, sticky='w', pady=(14, 2))
            self.refresh_gallery()

        def filter_gallery(self):
            query = self.search_reference.get().strip().casefold() if hasattr(self, 'search_reference') else ''
            self.display_references = [path for path in self.references if query in str(path.relative_to(self.reference_folder_path)).casefold()]
            self.gallery.delete(0, 'end')
            for path in self.display_references:
                self.gallery.insert('end', path.stem)
            if hasattr(self, 'library_count'):
                self.library_count.set(f'{len(self.display_references)} ảnh • tìm theo tên ở ô dưới' if getattr(self, 'reference_folder_path', None) else 'Chọn thư mục input để nạp ảnh')

        def choose_reference_folder(self):
            current = getattr(self, 'reference_folder_path', NCTT / 'thumbnails')
            path = filedialog.askdirectory(parent=self, title='Chọn thư mục ảnh input', initialdir=str(current))
            if path:
                self.reference_folder_path = Path(path)
                self.reference_folder.set(str(self.reference_folder_path))
                self.clear_reference()
                self.refresh_gallery()

        def refresh_gallery(self):
            folder = getattr(self, 'reference_folder_path', None)
            self.references = sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp')) if folder and folder.is_dir() else []
            self.filter_gallery()

        def show_reference(self, path):
            path = Path(path).resolve(strict=True)
            with Image.open(path) as image:
                image.thumbnail((480, 240))
                self.preview_image = ImageTk.PhotoImage(image.copy())
            self.preview.configure(image=self.preview_image, text='')
            self.reference = path
            self.selected.set(str(path))

        def select_reference(self, _event):
            selection = self.gallery.curselection()
            if selection:
                try:
                    self.show_reference(self.display_references[selection[0]])
                except Exception as error:
                    messagebox.showerror('Ảnh mẫu', str(error))

        def pick_reference(self):
            path = filedialog.askopenfilename(initialdir=NCTT / 'thumbnails', filetypes=[('Ảnh', '*.jpg *.jpeg *.png *.webp')])
            if path:
                try:
                    self.show_reference(path)
                except Exception as error:
                    messagebox.showerror('Ảnh mẫu', str(error))

        def clear_reference(self):
            self.reference = None
            self.selected.set('Không dùng ảnh mẫu')
            self.preview.configure(image='', text='Chỉ dùng prompt')

        def send_thumbnail(self):
            try:
                if self.desktop_running:
                    return
                prompt = self.thumbnail_prompt.get('1.0', 'end').strip()
                if not prompt:
                    raise ValueError('Chưa nhập prompt.')
                if not self.controller.external_browser and self.controller.profile != self.chrome_profile.get().strip():
                    raise ValueError('Bấm Mở Google Flow cho hồ sơ đã chọn trước khi tạo ảnh.')
                if self.controller.external_browser:
                    index = self.source_profile_combo.current()
                    if index < 0 or self.source_profiles[index]['path'] != self.controller.connected_source:
                        raise ValueError('Bạn vừa đổi hồ sơ Chrome. Bấm Kết nối Chrome đang mở để chọn lại tab trước khi tạo ảnh.')
                self.desktop_running = True
                self.create_thumbnail.configure(state='disabled')
                self.stop_thumbnail.configure(state='normal')
                self.studio_status.set('Desktop đang điều khiển Flow trực tiếp…')
                self.controller.submit(self.controller.start(prompt, self.reference, self.thumbnail_model.get(), int(self.thumbnail_count.get()), self.output_folder.get(), {**self.desktop_cfg, 'aspectRatio':self.thumbnail_ratio.get()}))
            except Exception as error:
                messagebox.showerror('Chuyển sang Flow', str(error))

        def connect_current_chrome(self):
            if self.desktop_running or self.controller.opening:
                return
            index = self.source_profile_combo.current()
            if not 0 <= index < len(self.source_profiles):
                messagebox.showerror('Kết nối Chrome', 'Chọn hồ sơ Chrome trong danh sách trước.', parent=self)
                return
            self.studio_status.set('Đang kết nối Chrome hiện tại… Bấm Allow trong Chrome nếu được hỏi.')
            future = self.controller.submit(self.controller.connect_existing(self.source_profiles[index]['path']))
            def completed(job):
                if self.closing or job.exception():
                    return
                self.after(0, lambda: self.pick_existing_flow_tab(job.result()))
            future.add_done_callback(completed)

        def pick_existing_flow_tab(self, tabs):
            if len(tabs) == 1:
                self.studio_status.set('Đã kết nối tab Flow đang mở. Sẵn sàng tạo ảnh bằng phiên hiện tại.')
                return
            dialog = tk.Toplevel(self)
            dialog.title('Chọn tab Flow để điều khiển')
            dialog.geometry('740x320')
            ttk.Label(dialog, text='Chrome có nhiều tab Flow. Chọn đúng dự án bạn muốn chạy:', padding=12).pack(anchor='w')
            listing = tk.Listbox(dialog, exportselection=False)
            listing.pack(fill='both', expand=True, padx=12)
            for tab in tabs:
                listing.insert('end', f"{tab['title']} · {tab['url']}")
            listing.selection_set(0)
            def select():
                selected = listing.curselection()
                if selected:
                    self.controller.submit(self.controller.select_existing_tab(selected[0], tabs[selected[0]]['url']))
                    dialog.destroy()
                    self.studio_status.set('Đã chọn tab Flow. Sẵn sàng tạo ảnh bằng phiên hiện tại.')
            ttk.Button(dialog, text='Dùng tab đã chọn', command=select).pack(pady=12)
            dialog.transient(self)
            dialog.grab_set()

        def import_chrome_profile(self):
            if self.desktop_running or self.controller.opening:
                return
            messagebox.showinfo('Nhập phiên Chrome', 'Đóng Chrome nguồn trước khi nhập. Chọn thư mục Default hoặc Profile 1… trong Google\\Chrome\\User Data.\n\nTool sao chép dữ liệu phiên sang hồ sơ mới, giữ nguyên hồ sơ nguồn. Không sao chép mật khẩu đã lưu hoặc lịch sử duyệt web. Google có thể yêu cầu đăng nhập lại do cơ chế mã hóa cookie.', parent=self)
            index = self.source_profile_combo.current()
            source = self.source_profiles[index]['path'] if 0 <= index < len(self.source_profiles) else filedialog.askdirectory(parent=self, title='Chọn hồ sơ Chrome: Default hoặc Profile 1…', initialdir=str(Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Google' / 'Chrome' / 'User Data'))
            if not source:
                return
            profile = simpledialog.askstring('Tên hồ sơ mới', 'Đặt tên hồ sơ riêng cho tool (chữ không dấu, số, - hoặc _):', initialvalue='chrome-import', parent=self)
            if profile:
                self.chrome_profile.set(profile.strip())
                self.controller.submit(self.controller.import_chrome_session(source, profile.strip()))

        def refresh_chrome_profiles(self):
            previous = self.source_profile_choice.get()
            try:
                self.source_profiles = discover_profiles()
            except OSError:
                self.source_profiles = []
            labels = [f"{p['name']} · {p['directory']}" for p in self.source_profiles]
            self.source_profile_combo.configure(values=labels)
            self.source_profile_label.configure(text=f'Hồ sơ Chrome đang dùng: {len(labels)}')
            if previous in labels:
                self.source_profile_choice.set(previous)
            elif labels:
                self.source_profile_combo.current(0)
            else:
                self.source_profile_choice.set('')

        def choose_output(self):
            if self.desktop_running:
                return
            path = filedialog.askdirectory(initialdir=self.output_folder.get(), title='Nơi lưu bản gốc và bản 16:9')
            if path:
                try:
                    Path(path).resolve().relative_to(OUTPUT_ROOT.resolve())
                    self.output_folder.set(path)
                except ValueError:
                    messagebox.showerror('Vị trí lưu ảnh', f'Chọn thư mục nằm trong {OUTPUT_ROOT}.')

        def import_prompt(self):
            if self.desktop_running:
                return
            filename = filedialog.askopenfilename(filetypes=[('Prompt', '*.txt')])
            if filename:
                try:
                    path = Path(filename)
                    if path.stat().st_size > 1024*1024:
                        raise ValueError('File prompt vượt 1 MB.')
                    text = path.read_text(encoding='utf-8-sig').replace('\r\n', '\n').strip()
                    self.thumbnail_prompt.delete('1.0', 'end')
                    self.thumbnail_prompt.insert('1.0', text)
                except Exception as error:
                    messagebox.showerror('Prompt', str(error))

        def advanced_flow(self):
            if self.desktop_running:
                return
            dialog = tk.Toplevel(self)
            dialog.title('Cài đặt Flow · Desktop')
            dialog.geometry('680x650')
            dialog.transient(self)
            frame = ttk.Frame(dialog, padding=16)
            frame.pack(fill='both', expand=True)
            frame.columnconfigure(1, weight=1)
            fields = [('timeout', 'Chờ ảnh tối đa (giây)', '240'), ('prompt', 'CSS ô prompt', ''), ('generate', 'CSS nút gửi', ''), ('card', 'CSS thẻ ảnh', ''), ('image', 'CSS ảnh', 'img'), ('countControl', 'CSS điều khiển số ảnh', ''), ('countOption', 'CSS số ảnh ({count})', ''), ('downloadButton', 'CSS nút Download', ''), ('download2k', 'CSS lựa chọn 2K', ''), ('original', 'CSS link ảnh gốc', '')]
            variables = {}
            for row, (key, title, default) in enumerate(fields):
                ttk.Label(frame, text=title).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=7)
                variable = tk.StringVar(value=str(self.desktop_cfg.get(key, default)))
                variables[key] = variable
                ttk.Entry(frame, textvariable=variable).grid(row=row, column=1, sticky='ew')
            ttk.Label(frame, text='Để trống CSS để tự nhận diện. Desktop dùng cùng logic chọn model, số ảnh và tải 2K.').grid(row=10, column=0, columnspan=2, sticky='w', pady=12)
            def save():
                try:
                    config = {key: value.get().strip() for key, value in variables.items()}
                    if not 10 <= int(config['timeout']) <= 3600:
                        raise ValueError('Thời gian chờ phải từ 10 đến 3600 giây.')
                    self.desktop_cfg = config
                    (ROOT / 'desktop-settings.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
                    dialog.destroy()
                except Exception as error:
                    messagebox.showerror('Cài đặt', str(error), parent=dialog)
            ttk.Button(frame, text='Lưu cài đặt', style='Primary.TButton', command=save).grid(row=11, column=1, sticky='e')

        def handle_flow_state(self, state):
            if not self.closing:
                self.after(0, lambda: self.render_flow_state(state))

        def render_flow_state(self, state):
            if self.closing:
                return
            self.desktop_running = bool(state.get('running'))
            self.create_thumbnail.configure(state='disabled' if self.desktop_running else 'normal')
            self.stop_thumbnail.configure(state='normal' if self.desktop_running else 'disabled')
            logs = state.get('logs', [])
            if logs:
                self.studio_status.set(logs[-1][:170])
            if state.get('finished'):
                return
            text = '\n'.join(logs)
            for item in state.get('items', []):
                text += '\n\nKết quả: ' + item.get('status', '')
                text += '\n' + '\n'.join(item.get('files', []) + item.get('croppedFiles', []))
            limits = state.get('limits', {})
            text += '\n\nHẠN MỨC MÔ HÌNH\n' + ('\n'.join(f"{model}: {row.get('count', 0)}/3 · {'KHÓA' if row.get('disabled') else 'theo dõi'}" for model, row in limits.items()) or 'Chưa có mô hình hết lượt được xác nhận.')
            text += '\n\nLỊCH SỬ GẦN ĐÂY\n'
            for row in state.get('history', [])[:20]:
                text += f"\n{row.get('time', '')} · {row.get('status', '')}\n{row.get('prompt', '')}\n"
                for attempt in row.get('attempts', []):
                    text += f"Lần {attempt.get('attempt')} · {attempt.get('model')} · {attempt.get('status')}\n{attempt.get('reason') or ''}\n" + '\n'.join(attempt.get('files', [])) + '\n'
            self.flow_logs.configure(state='normal')
            self.flow_logs.delete('1.0', 'end')
            self.flow_logs.insert('1.0', text)
            self.flow_logs.configure(state='disabled')

        def handle_flow_error(self, error):
            if not self.closing:
                self.after(0, lambda: self.show_flow_error(error))

        def show_flow_error(self, error):
            self.desktop_running = False
            self.create_thumbnail.configure(state='normal')
            self.stop_thumbnail.configure(state='disabled')
            self.studio_status.set(error)
            messagebox.showerror('Desktop · Google Flow', error)

        def close_studio(self):
            self.closing = True
            self.studio_status.set('Đang dừng và đóng Chrome của Desktop…')
            future = self.controller.submit(self.controller.shutdown())
            def finish():
                if future.done():
                    self.destroy()
                else:
                    self.after(50, finish)
            self.after(50, finish)

    UnifiedApp().mainloop()


if __name__ == '__main__':
    main()
