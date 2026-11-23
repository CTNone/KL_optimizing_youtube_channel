import ctypes
import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from core import Catalog, STATUSES

ROOT = Path(__file__).resolve().parent.parent


class AudioPlayer:
    """Small Windows MCI player so the app can track playback state."""

    ALIAS = 'musicmanager_audio'

    def __init__(self):
        self.winmm = ctypes.WinDLL('winmm')
        self.send = self.winmm.mciSendStringW
        self.send.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
        self.send.restype = ctypes.c_uint
        self.error_text = self.winmm.mciGetErrorStringW
        self.error_text.argtypes = (ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint)
        self.error_text.restype = ctypes.c_int
        self.opened = False

    def command(self, command, result=False):
        buffer = ctypes.create_unicode_buffer(256) if result else None
        code = self.send(command, buffer, len(buffer) if buffer else 0, None)
        if code:
            error = ctypes.create_unicode_buffer(256)
            self.error_text(code, error, len(error))
            raise RuntimeError(error.value or f'MCI error {code}')
        return buffer.value if buffer else ''

    def open_and_play(self, path):
        self.stop()
        device_type = 'waveaudio' if path.suffix.lower() == '.wav' else 'mpegvideo'
        self.command(f'open "{path}" type {device_type} alias {self.ALIAS}')
        self.opened = True
        self.command(f'set {self.ALIAS} time format milliseconds')
        self.command(f'play {self.ALIAS}')

    def mode(self):
        if not self.opened:
            return 'stopped'
        return self.command(f'status {self.ALIAS} mode', result=True).strip().casefold()

    def pause(self):
        self.command(f'pause {self.ALIAS}')

    def resume(self):
        self.command(f'resume {self.ALIAS}')

    def position(self):
        return self._time('position')

    def duration(self):
        return self._time('length')

    def _time(self, field):
        if not self.opened:
            return 0
        value = self.command(f'status {self.ALIAS} {field}', result=True).strip()
        try:
            return int(value)
        except ValueError:
            return 0

    def seek(self, milliseconds):
        mode = self.mode()
        target = max(0, int(milliseconds))
        duration = self.duration()
        if duration:
            target = min(target, duration)
        self.command(f'seek {self.ALIAS} to {target}')
        if mode in ('playing', 'paused'):
            self.command(f'play {self.ALIAS}')
            if mode == 'paused':
                self.command(f'pause {self.ALIAS}')

    def stop(self):
        if self.opened:
            self.command(f'stop {self.ALIAS}')
            self.close()

    def close(self):
        if self.opened:
            try:
                self.command(f'close {self.ALIAS}')
            finally:
                self.opened = False


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Music Manager')
        self.state('zoomed')
        self.minsize(980, 640)
        self.catalog = Catalog(ROOT)
        self.catalog.backup()
        self.loading = False
        self.tid = None
        self.pid = None
        self.audio_player = None
        self.audio_track_id = None
        self.highlighted_track_id = None
        self.audio_state = 'stopped'
        if os.name == 'nt':
            try:
                self.audio_player = AudioPlayer()
            except (AttributeError, OSError):
                pass
        self.channel_map = {}
        self.project_map = {}
        self.pref_channel_id = os.environ.get('CONTENT_HUB_CHANNEL_ID', '').strip()
        self.pref_music_project_id = os.environ.get('CONTENT_HUB_MUSIC_PROJECT_ID', '').strip()
        self.scan_path_file = self.catalog.output_root / 'library_path.txt'
        initial_path = self.scan_path_file.read_text(encoding='utf-8').strip() if self.scan_path_file.exists() else str(ROOT)
        if not Path(initial_path).expanduser().is_dir():
            initial_path = str(ROOT)
        if Path(initial_path).expanduser().is_dir():
            self.catalog.scan(initial_path)

        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Treeview', rowheight=32, font=('Segoe UI', 10), background='#FFFFFF',
                        fieldbackground='#FFFFFF', borderwidth=1, relief='solid')
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), background='#DCE7F2',
                        foreground='#20364A', bordercolor='#A9B8C7', relief='raised', padding=(9, 8))
        style.map('Treeview.Heading', background=[('active', '#C9D9E8')])
        style.configure('TButton', padding=(8, 5), font=('Segoe UI', 9))

        header = ttk.Frame(self, padding=(12, 10, 12, 6))
        header.pack(fill='x')
        ttk.Label(header, text='THƯ VIỆN NHẠC', font=('Segoe UI', 17, 'bold')).pack(side='left')
        ttk.Button(header, text='Lịch sử', command=self.show_history).pack(side='right', padx=3)
        ttk.Button(header, text='Xuất CapCut · chuẩn hóa', command=self.export_normalized_project).pack(side='right', padx=3)
        ttk.Button(header, text='Xuất CapCut', command=self.export_project).pack(side='right', padx=3)
        ttk.Button(header, text='Xóa dự án', command=self.delete_project).pack(side='right', padx=3)
        ttk.Button(header, text='Dự án mới', command=self.new_project).pack(side='right', padx=3)

        folder_bar = ttk.Frame(self, padding=(12, 3))
        folder_bar.pack(fill='x')
        ttk.Label(folder_bar, text='Thư mục nhạc').pack(side='left')
        self.folder = tk.StringVar(value=initial_path)
        ttk.Entry(folder_bar, textvariable=self.folder).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(folder_bar, text='Chọn thư mục…', command=self.choose_folder).pack(side='left')
        ttk.Button(folder_bar, text='Quét lại', command=self.scan).pack(side='left', padx=(6, 0))

        filters = ttk.Frame(self, padding=(12, 8, 12, 6))
        filters.pack(fill='x')
        ttk.Label(filters, text='Tìm').pack(side='left')
        self.search = tk.StringVar()
        ttk.Entry(filters, textvariable=self.search, width=28).pack(side='left', padx=(6, 12))
        ttk.Label(filters, text='Kênh').pack(side='left')
        self.channel = tk.StringVar(value='Tất cả kênh')
        self.channel_box = ttk.Combobox(filters, textvariable=self.channel, state='readonly', width=21)
        self.channel_box.pack(side='left', padx=6)
        self.only_channel = tk.BooleanVar(value=False)
        ttk.Label(filters, text='Dự án').pack(side='left')
        self.project = tk.StringVar(value='Tất cả dự án')
        self.project_box = ttk.Combobox(filters, textvariable=self.project, state='readonly', width=26)
        self.project_box.pack(side='left', padx=6)
        self.only_project = tk.BooleanVar(value=False)
        filter_line = ttk.Frame(self, padding=(12, 0, 12, 6))
        filter_line.pack(fill='x')
        ttk.Checkbutton(filter_line, text='Chỉ kênh hiện tại', variable=self.only_channel, command=self.refresh).pack(side='left')
        ttk.Checkbutton(filter_line, text='Chỉ dự án hiện tại', variable=self.only_project, command=self.refresh).pack(side='left', padx=(10, 18))
        ttk.Label(filter_line, text='Trạng thái ghi công').pack(side='left')
        self.status = tk.StringVar(value='Tất cả')
        self.status_box = ttk.Combobox(filter_line, textvariable=self.status, state='readonly', width=24,
                                       values=('Tất cả', *STATUSES, 'Thiếu tệp'))
        self.status_box.pack(side='left', padx=8)

        self.current_counts = ttk.Label(self, padding=(12, 0, 12, 4), foreground='#444')
        self.current_counts.pack(fill='x')
        playback_bar = ttk.Frame(self, padding=(12, 0, 12, 6))
        playback_bar.pack(fill='x')
        self.now_playing = ttk.Label(playback_bar, text='Chưa phát bài nào', foreground='#28613A', width=42)
        self.now_playing.pack(side='left')
        ttk.Button(playback_bar, text='−10 giây', command=lambda: self.seek_relative(-10)).pack(side='left', padx=(8, 3))
        self.seek_value = tk.DoubleVar(value=0)
        self.seek_scale = ttk.Scale(playback_bar, from_=0, to=1000, variable=self.seek_value)
        self.seek_scale.pack(side='left', fill='x', expand=True, padx=6)
        self.seek_scale.bind('<Button-1>', self.click_or_drag_seek)
        self.seek_scale.bind('<ButtonRelease-1>', self.finish_seek)
        ttk.Button(playback_bar, text='+10 giây', command=lambda: self.seek_relative(10)).pack(side='left', padx=3)
        self.playback_time = ttk.Label(playback_bar, text='00:00 / 00:00', width=13, anchor='e')
        self.playback_time.pack(side='left', padx=(8, 0))
        self.seeking = False
        self.summary = ttk.Label(self, padding=(12, 0, 12, 6), foreground='#555')
        self.summary.pack(fill='x')
        frame = ttk.Frame(self, padding=(12, 0, 12, 10))
        frame.pack(fill='both', expand=True)
        columns = ('play', 'title', 'artist', 'status', 'channel', 'project', 'files', 'groups')
        self.table = ttk.Treeview(frame, columns=columns, show='headings', selectmode='extended')
        labels = ('Nghe', 'Tên bài', 'Nghệ sĩ', 'Ghi công', 'Kênh', 'Dự án', 'Tệp', 'Thư mục')
        widths = (55, 285, 170, 145, 180, 200, 50, 180)
        for column, label, width in zip(columns, labels, widths):
            self.table.heading(column, text=label)
            self.table.column(column, width=width, minwidth=55)
        self.table.column('play', anchor='center', stretch=False)
        self.table.column('files', anchor='center', stretch=False)
        yscroll = ttk.Scrollbar(frame, orient='vertical', command=self.table.yview)
        xscroll = ttk.Scrollbar(frame, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.table.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.table.tag_configure('stripe_even', background='#FFFFFF')
        self.table.tag_configure('stripe_odd', background='#F1F5F9')
        for tag, color in (('unknown', '#8a5200'), ('required', '#8c2648'), ('missing', '#a00000')):
            self.table.tag_configure(tag, foreground=color)
        self.table.tag_configure('playing', background='#CDEBD5', foreground='#103E20',
                                 font=('Segoe UI', 11, 'bold'))
        self.table.tag_configure('paused', background='#FFF0CC', foreground='#6B531A')

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label='Nghe bài', command=self.preview)
        self.menu.add_command(label='Ghi công / xem chi tiết…', command=self.edit_credit)
        self.menu.add_separator()
        status_menu = tk.Menu(self.menu, tearoff=False)
        for value in STATUSES:
            status_menu.add_command(label=value, command=lambda v=value: self.set_status(v))
        self.menu.add_cascade(label='Đặt trạng thái ghi công', menu=status_menu)
        self.menu.add_separator()
        self.menu.add_command(label='Thêm vào dự án đang chọn', command=self.add_to_project)
        self.menu.add_command(label='Bỏ khỏi dự án đang chọn', command=self.remove_from_project)
        self.menu.add_command(label='Gán vào kênh đang chọn', command=self.assign_channel)
        self.menu.add_command(label='Bỏ khỏi kênh đang chọn', command=self.unassign_channel)
        self.menu.add_separator()
        self.menu.add_command(label='Xóa bài và tệp nhạc gốc…', command=self.delete_context_track)
        self.table.bind('<Button-3>', self.popup_menu)
        self.table.bind('<Button-1>', self.on_cell_click)
        self.table.bind('<Double-1>', self.on_double_click)

        for variable in (self.search, self.channel, self.project, self.status):
            variable.trace_add('write', lambda *_: self.refresh())
        self.refresh_channels()
        self.refresh_projects()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh()
        self.after(400, self.check_playback)

    def popup_menu(self, event):
        row = self.table.identify_row(event.y)
        column = self.table.identify_column(event.x)
        if row:
            self.context_track_id = row
        if row and column in ('#5', '#6'):
            self.table.selection_set(row)
            self.table.focus(row)
            if column == '#6':
                self.show_project_menu(row, event.x_root, event.y_root)
            else:
                self.show_channel_menu(row, event.x_root, event.y_root)
            return
        if row and column == '#4':
            self.table.selection_set(row)
            self.table.focus(row)
            self.show_credit_menu(row, event.x_root, event.y_root)
            return
        if row and row not in self.table.selection():
            self.table.selection_set(row)
        if row:
            self.menu.tk_popup(event.x_root, event.y_root)

    def show_credit_menu(self, track_id, x, y):
        track = self.catalog.get(track_id)
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label=f"Ghi công của: {track['title']}", state='disabled')
        menu.add_separator()
        for status in STATUSES:
            marker = '✓ ' if track['status'] == status else ''
            menu.add_command(label=marker + status,
                             command=lambda value=status: self.set_track_status(track_id, value))
        menu.add_separator()
        menu.add_command(label='Xóa bài và tệp nhạc gốc…', command=lambda: self.delete_track(track_id))
        self.cell_menu = menu
        menu.tk_popup(x, y)

    def set_track_status(self, track_id, status):
        track = self.catalog.get(track_id)
        if status == STATUSES[2] and not track['credit'].strip():
            self.table.selection_set(track_id)
            self.edit_credit(status)
            return
        self.catalog.save_review(track_id, status, track['credit'], track['source'], track['license'], track['notes'])
        self.refresh()

    def delete_context_track(self):
        track_id = getattr(self, 'context_track_id', None)
        if not track_id:
            return
        track = self.catalog.get(track_id)
        file_rows = self.catalog.db.execute(
            'SELECT path FROM music_files WHERE track_id=? AND present=1 ORDER BY path', (track_id,)
        ).fetchall()
        file_count = len(file_rows)
        examples = '\n'.join(row['path'] for row in file_rows[:3])
        if file_count > 3:
            examples += f'\n… ועוד {file_count - 3} tệp'
        details = f"\n\nSố tệp nhạc sẽ xóa: {file_count}"
        if examples:
            details += '\n' + examples
        if not messagebox.askyesno(
            'Xóa bài hát và tệp gốc',
            f"Xóa “{track['title']} — {track['artist']}” khỏi Music Manager và xóa vĩnh viễn tệp nhạc gốc?"
            f"{details}\n\nBài cũng sẽ được gỡ khỏi các dự án và kênh.",
            parent=self,
        ):
            return
        if self.audio_track_id == track_id and self.audio_player:
            try:
                self.audio_player.stop()
            except RuntimeError:
                pass
            self.audio_track_id = None
            self.highlighted_track_id = None
            self.audio_state = 'stopped'
            self.update_playing_label()
        try:
            self.catalog.delete_track(track_id)
            self.context_track_id = None
            self.refresh()
            messagebox.showinfo('Đã xóa', 'Đã xóa bài khỏi danh mục và xóa các tệp nhạc đã quét.', parent=self)
        except Exception as error:
            self.refresh()
            messagebox.showerror('Không xóa hết được tệp', str(error), parent=self)

    def delete_track(self, track_id):
        self.context_track_id = track_id
        self.delete_context_track()

    def show_project_menu(self, track_id, x, y):
        row = self.catalog.get(track_id)
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label=f"Dự án của: {row['title']}", state='disabled')
        menu.add_separator()
        projects = self.catalog.projects()
        if not projects:
            menu.add_command(label='Chưa có dự án', state='disabled')
        for project in projects:
            present = self.catalog.db.execute(
                'SELECT 1 FROM music_project_tracks WHERE project_id=? AND track_id=?',
                (project['id'], track_id),
            ).fetchone()
            verb = '✓ Bỏ khỏi' if present else '+ Thêm vào'
            label = f"{verb} {project['name']} [#{project['id']}]"
            menu.add_command(label=label, command=lambda pid=project['id']: self.toggle_project(track_id, pid))
        menu.add_separator()
        menu.add_command(label='Xóa bài và tệp nhạc gốc…', command=lambda: self.delete_track(track_id))
        self.cell_menu = menu
        menu.tk_popup(x, y)

    def show_channel_menu(self, track_id, x, y):
        row = self.catalog.get(track_id)
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label=f"Kênh của: {row['title']}", state='disabled')
        menu.add_separator()
        channels = [channel for channel in self.catalog.channels() if not channel['archived']]
        if not channels:
            menu.add_command(label='Chưa có kênh', state='disabled')
        for channel in channels:
            present = self.catalog.db.execute(
                'SELECT 1 FROM music_channel_tracks WHERE channel_id=? AND track_id=?',
                (channel['id'], track_id),
            ).fetchone()
            verb = '✓ Bỏ khỏi' if present else '+ Gán vào'
            menu.add_command(label=f"{verb} {channel['name']}",
                             command=lambda cid=channel['id']: self.toggle_channel(track_id, cid))
        menu.add_separator()
        menu.add_command(label='Xóa bài và tệp nhạc gốc…', command=lambda: self.delete_track(track_id))
        self.cell_menu = menu
        menu.tk_popup(x, y)

    def toggle_project(self, track_id, project_id):
        present = self.catalog.db.execute(
            'SELECT 1 FROM music_project_tracks WHERE project_id=? AND track_id=?',
            (project_id, track_id),
        ).fetchone()
        if present:
            self.catalog.remove(project_id, [track_id])
        elif not self.catalog.source_file(track_id):
            messagebox.showwarning('Thiếu tệp', 'Chỉ thêm bài đang có tệp âm thanh vào dự án.', parent=self)
            return
        else:
            self.catalog.add(project_id, [track_id])
        self.refresh()

    def toggle_channel(self, track_id, channel_id):
        present = self.catalog.db.execute(
            'SELECT 1 FROM music_channel_tracks WHERE channel_id=? AND track_id=?',
            (channel_id, track_id),
        ).fetchone()
        if present:
            self.catalog.unassign_channel(channel_id, [track_id])
        else:
            self.catalog.assign_channel(channel_id, [track_id])
        self.refresh()

    def on_cell_click(self, event):
        row = self.table.identify_row(event.y)
        if row and self.table.identify_column(event.x) == '#1':
            self.table.selection_set(row)
            self.table.focus(row)
            self.play_track(row)
            return 'break'

    def on_double_click(self, event):
        row = self.table.identify_row(event.y)
        if not row or self.table.identify_column(event.x) != '#2':
            return
        title = self.table.item(row, 'values')[1]
        self.clipboard_clear()
        self.clipboard_append(title)
        self.update()
        self.summary.configure(text=f'Đã sao chép tên bài: {title}')

    def choose_folder(self):
        path = filedialog.askdirectory(parent=self, initialdir=self.folder.get() or str(ROOT))
        if path:
            self.folder.set(path)

    def refresh_channels(self):
        channels = [channel for channel in self.catalog.channels() if not channel['archived']]
        self.channel_map = {channel['name']: channel['id'] for channel in channels}
        values = ['Tất cả kênh', *self.channel_map]
        self.channel_box.configure(values=values)
        preferred = next((name for name, channel_id in self.channel_map.items()
                          if channel_id == self.pref_channel_id), None)
        if preferred:
            self.channel.set(preferred)
            self.pref_channel_id = ''
        if self.channel.get() not in values:
            self.channel.set(values[0])

    def refresh_projects(self):
        projects = self.catalog.projects()
        self.project_map = {f"{item['name']} [#{item['id']}]": item['id'] for item in projects}
        values = ['Tất cả dự án', *self.project_map]
        self.project_box.configure(values=values)
        preferred = next((name for name, project_id in self.project_map.items()
                          if str(project_id) == self.pref_music_project_id), None)
        if preferred:
            self.project.set(preferred)
            self.only_project.set(True)
            self.pref_music_project_id = ''
        if self.project.get() not in values:
            self.project.set(values[0])
        self.pid = self.project_map.get(self.project.get())

    def refresh(self):
        if not hasattr(self, 'table'):
            return
        self.pid = self.project_map.get(self.project.get())
        query = self.search.get().casefold().strip()
        status = self.status.get()
        channel_id = self.channel_map.get(self.channel.get()) if self.only_channel.get() else None
        project_id = self.pid if self.only_project.get() else None
        rows = self.catalog.tracks()
        projects = self.catalog.projects()
        project_tracks = {project['id']: {item['id'] for item in self.catalog.project_items(project['id'])} for project in projects}
        channel_tracks = {item['id'] for item in self.catalog.channel_tracks(channel_id)} if channel_id else set()
        if project_id:
            positions = {item['id']: item['position'] for item in self.catalog.project_items(project_id)}
            rows.sort(key=lambda row: positions.get(row['id'], float('inf')))
        self.table.delete(*self.table.get_children())
        visible = 0
        for row in rows:
            if query and query not in (row['title'] + ' ' + row['artist']).casefold():
                continue
            if status in STATUSES and row['status'] != status:
                continue
            if status == 'Thiếu tệp' and row['file_count']:
                continue
            if status != 'Thiếu tệp' and not row['file_count']:
                continue
            if channel_id and row['id'] not in channel_tracks:
                continue
            project_names = [project['name'] for project in projects if row['id'] in project_tracks[project['id']]]
            if project_id and row['id'] not in project_tracks.get(project_id, set()):
                continue
            tag = 'missing' if not row['file_count'] else 'unknown' if row['status'] == STATUSES[0] else 'required' if row['status'] == STATUSES[2] else ''
            row_tags = ['stripe_even' if visible % 2 == 0 else 'stripe_odd']
            if tag:
                row_tags.append(tag)
            if self.highlighted_track_id == row['id']:
                row_tags.append('paused' if self.audio_state == 'paused' else 'playing')
            play_icon = 'Ⅱ' if self.audio_track_id == row['id'] and self.audio_state == 'playing' else '▶'
            self.table.insert('', 'end', iid=row['id'], values=(play_icon, row['title'], row['artist'], row['status'],
                               row['channels'] or '', ', '.join(project_names), row['file_count'], row['groups'] or ''), tags=tuple(row_tags))
            visible += 1
        exists = sum(bool(row['file_count']) for row in rows)
        missing = len(rows) - exists
        unchecked = sum(row['status'] == STATUSES[0] and row['file_count'] > 0 for row in rows)
        channel_name = self.channel.get()
        project_name = self.project.get()
        channel_count = self.catalog.channel_track_count(self.channel_map[channel_name]) if channel_name in self.channel_map else 0
        project_count = next((project['count'] for project in projects if project['id'] == self.pid), 0)
        self.current_counts.configure(
            text=f'Kênh hiện tại: {channel_name if channel_name != "Tất cả kênh" else "Chưa chọn"} · {channel_count} bài'
                 f'     |     Dự án hiện tại: {project_name if project_name != "Tất cả dự án" else "Chưa chọn"} · {project_count} bài')
        self.summary.configure(text=f'{exists} bài có tệp · {missing} bài thiếu tệp · {unchecked} bài chưa kiểm tra · hiển thị {visible}')

    def scan(self):
        folder = Path(self.folder.get()).expanduser()
        if not folder.is_dir():
            messagebox.showerror('Không tìm thấy thư mục', 'Hãy chọn một thư mục nhạc tồn tại.', parent=self)
            return
        try:
            self.scan_path_file.parent.mkdir(parents=True, exist_ok=True)
            self.scan_path_file.write_text(str(folder.resolve()), encoding='utf-8')
            count = self.catalog.scan(folder)
            self.refresh_channels()
            self.refresh()
            self.catalog.log_event('Quét thư viện', details={'folder': str(folder.resolve()), 'file_count': count})
            messagebox.showinfo('Đã quét thư viện', f'Đã tìm thấy {count} tệp âm thanh.', parent=self)
        except Exception as error:
            messagebox.showerror('Lỗi quét', str(error), parent=self)

    def selected_ids(self):
        return list(self.table.selection())

    def preview(self):
        ids = self.selected_ids()
        if not ids:
            return
        self.play_track(ids[0])

    def play_track(self, track_id):
        path = self.catalog.source_file(track_id)
        if not path:
            messagebox.showwarning('Thiếu tệp', 'Bài này chưa có tệp âm thanh.', parent=self)
            return
        if self.audio_player is None:
            try:
                os.startfile(str(path))
                self.highlighted_track_id = track_id
                title = self.catalog.get(track_id)['title']
                self.now_playing.configure(text=f'Đã mở ngoài: {title} · không theo dõi trạng thái phát')
                self.seek_value.set(0)
                self.playback_time.configure(text='--:-- / --:--')
                self.refresh()
            except OSError as error:
                messagebox.showerror('Không mở được trình phát', str(error), parent=self)
            return
        try:
            if self.audio_track_id == track_id:
                mode = self.audio_player.mode()
                if mode == 'playing':
                    self.audio_player.pause()
                    self.audio_state = 'paused'
                elif mode == 'paused':
                    self.audio_player.resume()
                    self.audio_state = 'playing'
                else:
                    self.audio_player.open_and_play(path)
                    self.audio_state = 'playing'
            else:
                self.audio_player.open_and_play(path)
                self.audio_track_id = track_id
                self.audio_state = 'playing'
            self.highlighted_track_id = track_id
            self.update_playing_label()
            self.refresh()
        except (OSError, RuntimeError) as error:
            try:
                self.audio_player.close()
            except RuntimeError:
                pass
            self.audio_track_id = None
            self.audio_state = 'external'
            try:
                os.startfile(str(path))
                title = self.catalog.get(track_id)['title']
                self.highlighted_track_id = track_id
                self.now_playing.configure(text=f'Đã mở ngoài: {title} · định dạng này không được theo dõi trong ứng dụng')
                self.seek_value.set(0)
                self.playback_time.configure(text='--:-- / --:--')
            except OSError:
                messagebox.showerror('Không phát được bài này', str(error), parent=self)
            self.refresh()

    def update_playing_label(self):
        if not self.audio_track_id:
            self.now_playing.configure(text='Chưa phát bài nào')
            self.seek_value.set(0)
            self.playback_time.configure(text='00:00 / 00:00')
            return
        title = self.catalog.get(self.audio_track_id)['title']
        if self.audio_state == 'playing':
            self.now_playing.configure(text=f'♫ Đang phát: {title} · bấm Ⅱ để tạm dừng')
        elif self.audio_state == 'paused':
            self.now_playing.configure(text=f'Ⅱ Đang tạm dừng: {title} · bấm ▶ để tiếp tục')

    @staticmethod
    def format_time(milliseconds):
        seconds = max(0, int(milliseconds // 1000))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f'{hours}:{minutes:02d}:{seconds:02d}' if hours else f'{minutes:02d}:{seconds:02d}'

    def click_or_drag_seek(self, event):
        if self.seek_scale.identify(event.x, event.y) == 'slider':
            self.seeking = True
            return
        width = max(1, self.seek_scale.winfo_width())
        fraction = min(1.0, max(0.0, event.x / width))
        self.seek_value.set(fraction * 1000)
        self.seeking = False
        self.finish_seek()
        return 'break'

    def finish_seek(self, _event=None):
        self.seeking = False
        if not self.audio_track_id or not self.audio_player:
            return
        try:
            duration = self.audio_player.duration()
            self.audio_player.seek(duration * self.seek_value.get() / 1000)
            self.update_playback_progress()
        except RuntimeError as error:
            messagebox.showerror('Không tua được bài', str(error), parent=self)

    def seek_relative(self, seconds):
        if not self.audio_track_id or not self.audio_player:
            return
        try:
            position = self.audio_player.position() + seconds * 1000
            self.audio_player.seek(position)
            self.update_playback_progress()
        except RuntimeError as error:
            messagebox.showerror('Không tua được bài', str(error), parent=self)

    def update_playback_progress(self):
        if not self.audio_track_id or not self.audio_player:
            self.playback_time.configure(text='00:00 / 00:00')
            return
        duration = self.audio_player.duration()
        position = min(self.audio_player.position(), duration) if duration else 0
        if not self.seeking:
            self.seek_value.set(position * 1000 / duration if duration else 0)
        self.playback_time.configure(text=f'{self.format_time(position)} / {self.format_time(duration)}')

    def check_playback(self):
        if self.audio_track_id and self.audio_player:
            try:
                state = self.audio_player.mode()
                if state == 'stopped':
                    finished_track_id = self.audio_track_id
                    self.audio_player.close()
                    self.audio_track_id = None
                    self.audio_state = 'stopped'
                    if self.highlighted_track_id == finished_track_id:
                        self.highlighted_track_id = None
                    self.update_playing_label()
                    self.refresh()
                elif state in ('playing', 'paused') and state != self.audio_state:
                    self.audio_state = state
                    self.update_playing_label()
                    self.refresh()
                if state in ('playing', 'paused'):
                    self.update_playback_progress()
            except RuntimeError:
                self.audio_track_id = None
                self.audio_state = 'stopped'
                self.highlighted_track_id = None
                self.update_playing_label()
                self.refresh()
        self.after(400, self.check_playback)

    def set_status(self, status):
        ids = self.selected_ids()
        if status == STATUSES[2] and any(not self.catalog.get(track_id)['credit'].strip() for track_id in ids):
            if len(ids) == 1:
                self.edit_credit(status)
            else:
                messagebox.showinfo('Cần nội dung ghi công', 'Hãy mở từng bài để nhập nội dung ghi công chính xác.', parent=self)
            return
        for track_id in ids:
            row = self.catalog.get(track_id)
            self.catalog.save_review(track_id, status, row['credit'], row['source'], row['license'], row['notes'])
        self.refresh()

    def edit_credit(self, status_override=None):
        ids = self.selected_ids()
        if len(ids) != 1:
            messagebox.showinfo('Chọn một bài', 'Chọn đúng một bài để sửa hồ sơ ghi công.', parent=self)
            return
        track_id = ids[0]
        row = self.catalog.get(track_id)
        win = tk.Toplevel(self)
        win.title(f"Ghi công · {row['title']}")
        win.geometry('760x620')
        win.transient(self)
        win.grab_set()
        ttk.Label(win, text=f"{row['title']} — {row['artist']}", font=('Segoe UI', 12, 'bold'), padding=12).pack(anchor='w')
        body = ttk.Frame(win, padding=(12, 0))
        body.pack(fill='both', expand=True)
        state = tk.StringVar(value=status_override or row['status'])
        ttk.Label(body, text='Trạng thái').pack(anchor='w')
        ttk.Combobox(body, textvariable=state, state='readonly', values=STATUSES).pack(fill='x', pady=(3, 10))
        ttk.Label(body, text='Nội dung ghi công chính xác').pack(anchor='w')
        credit = tk.Text(body, height=9, wrap='word', font=('Segoe UI', 10), undo=True)
        credit.pack(fill='both', expand=True, pady=(3, 8))
        credit.insert('1.0', row['credit'])
        source = tk.StringVar(value=row['source'])
        license_name = tk.StringVar(value=row['license'])
        ttk.Label(body, text='Link nguồn').pack(anchor='w')
        ttk.Entry(body, textvariable=source).pack(fill='x', pady=(3, 8))
        ttk.Label(body, text='Giấy phép').pack(anchor='w')
        ttk.Entry(body, textvariable=license_name).pack(fill='x', pady=(3, 8))
        ttk.Label(body, text='Ghi chú').pack(anchor='w')
        notes = tk.Text(body, height=3, wrap='word', font=('Segoe UI', 10), undo=True)
        notes.pack(fill='x', pady=(3, 8))
        notes.insert('1.0', row['notes'])
        controls = ttk.Frame(win, padding=12)
        controls.pack(fill='x')
        ttk.Button(controls, text='Lịch sử bài này', command=lambda: self.show_history(track_id)).pack(side='left')

        def save():
            try:
                self.catalog.save_review(track_id, state.get(), credit.get('1.0', 'end-1c'), source.get(), license_name.get(), notes.get('1.0', 'end-1c'))
                win.destroy()
                self.refresh()
            except Exception as error:
                messagebox.showerror('Không lưu được', str(error), parent=win)

        ttk.Button(controls, text='Lưu', command=save).pack(side='right')
        ttk.Button(controls, text='Đóng', command=win.destroy).pack(side='right', padx=6)

    def new_project(self):
        name = simpledialog.askstring('Dự án mới', 'Tên dự án CapCut:', parent=self)
        if name and name.strip():
            self.pid = self.catalog.new_project(name)
            self.catalog.log_event('Tạo dự án', details={'project_id': self.pid, 'name': name.strip()})
            self.refresh_projects()
            project_name = next((key for key, value in self.project_map.items() if value == self.pid), '')
            self.project.set(project_name)

    def delete_project(self):
        if not self.pid:
            messagebox.showinfo('Chọn dự án', 'Chọn dự án cần xóa trên thanh phía trên.', parent=self)
            return
        label = self.project.get()
        if not messagebox.askyesno('Xóa dự án', f'Xóa “{label}” cùng danh sách bài trong dự án?', parent=self):
            return
        self.catalog.delete_project(self.pid)
        self.project.set('Tất cả dự án')
        self.refresh_projects()
        self.refresh()

    def add_to_project(self):
        ids = self.selected_ids()
        if not ids:
            return
        if not self.pid:
            messagebox.showinfo('Chọn dự án', 'Chọn dự án trên thanh phía trên hoặc tạo dự án mới.', parent=self)
            return
        missing = [track_id for track_id in ids if not self.catalog.source_file(track_id)]
        if missing:
            messagebox.showwarning('Thiếu tệp', 'Chỉ thêm các bài đang có tệp âm thanh.', parent=self)
            return
        self.catalog.add(self.pid, ids)
        self.refresh()

    def remove_from_project(self):
        if self.pid and self.selected_ids():
            self.catalog.remove(self.pid, self.selected_ids())
            self.refresh()

    def assign_channel(self):
        channel_id = self.channel_map.get(self.channel.get())
        ids = self.selected_ids()
        if not channel_id or not ids:
            messagebox.showinfo('Chọn kênh', 'Chọn kênh và bài hát trên thanh phía trên.', parent=self)
            return
        self.catalog.assign_channel(channel_id, ids)
        self.refresh()

    def unassign_channel(self):
        channel_id = self.channel_map.get(self.channel.get())
        if channel_id and self.selected_ids():
            self.catalog.unassign_channel(channel_id, self.selected_ids())
            self.refresh()

    def export_project(self):
        self._export_project(normalize_audio=False)

    def export_normalized_project(self):
        self._export_project(normalize_audio=True)

    def _export_project(self, normalize_audio=False):
        if not self.pid:
            messagebox.showinfo('Chọn dự án', 'Chọn dự án trên thanh phía trên trước khi xuất.', parent=self)
            return
        if normalize_audio and not messagebox.askyesno(
            'Xuất âm thanh đã chuẩn hóa',
            'Tạo bản MP3 riêng cho CapCut, cân mức âm lượng khoảng -14 LUFS, giới hạn đỉnh ở -2 dBTP để chừa khoảng an toàn cho MP3, '
            'cắt im lặng đầu/cuối và giữ 0,3 giây yên lặng ở mỗi đầu?\n\nTệp nhạc gốc sẽ không bị thay đổi.',
            parent=self,
        ):
            return
        issues = self.catalog.issues(self.pid)
        draft = False
        if issues:
            detail = '\n'.join(f'• {title}: {reason}' for title, reason in issues[:10])
            draft = messagebox.askyesno('Còn bài cần kiểm tra', detail + '\n\nXuất bản nháp?', parent=self)
            if not draft:
                return
        try:
            path = self.catalog.export(self.pid, draft, normalize_audio=normalize_audio)
            self.catalog.log_event('Xuất dự án', details={
                'project_id': self.pid, 'path': str(path), 'draft': draft,
                'normalized_audio': normalize_audio,
            })
            messagebox.showinfo('Đã xuất', str(path), parent=self)
            os.startfile(str(path))
        except Exception as error:
            messagebox.showerror('Không xuất được', str(error), parent=self)

    def show_history(self, track_id=None):
        win = tk.Toplevel(self)
        win.title('Lịch sử hoạt động' if not track_id else 'Lịch sử bài hát')
        win.geometry('820x540')
        text = tk.Text(win, wrap='word', font=('Segoe UI', 10), padx=12, pady=10)
        scroll = ttk.Scrollbar(win, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        for item in self.catalog.history(track_id):
            try:
                before = json.loads(item['before_json'] or '{}')
                after = json.loads(item['after_json'] or '{}')
            except (TypeError, json.JSONDecodeError):
                before, after = {}, {}
            if item['track_id']:
                try:
                    title = self.catalog.get(item['track_id'])['title']
                except ValueError:
                    title = after.get('title', 'Bài đã xóa')
            else:
                title = after.get('title', 'Thư viện')
            action = after.get('action', 'Cập nhật ghi công')
            summary = after.get('status', '')
            if before and after.get('status'):
                summary += f" · trước: {before.get('status', '')}"
            extra = {key: value for key, value in after.items() if key not in ('action', 'status', 'credit')}
            text.insert('end', f"{item['changed']} · {title} · {action}{(' · ' + summary) if summary else ''}\n")
            if after.get('credit'):
                text.insert('end', after['credit'] + '\n')
            for field, label in (('source', 'Nguồn'), ('license', 'Giấy phép'), ('notes', 'Ghi chú')):
                if after.get(field):
                    text.insert('end', f"{label}: {after[field]}\n")
            if extra:
                text.insert('end', json.dumps(extra, ensure_ascii=False) + '\n')
            text.insert('end', '\n')
        if not text.get('1.0', 'end-1c').strip():
            text.insert('1.0', 'Chưa có hoạt động nào được ghi lại.')
        text.configure(state='disabled')

    def close(self):
        if self.audio_player and self.audio_track_id:
            try:
                self.audio_player.stop()
            except RuntimeError:
                pass
        self.catalog.db.close()
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
