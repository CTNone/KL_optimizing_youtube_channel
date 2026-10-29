"""Read existing records without changing source histories or moving old outputs."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import os
import re
import uuid
import tkinter as tk
from tkinter import ttk, messagebox

LOCAL = timezone(timedelta(hours=7))

def external_output_root(project_root):
    return Path(project_root).parent / 'TOOL Video Flow OUTPUT'

def dated_output(base, category):
    now = datetime.now(LOCAL)
    folder = Path(base).resolve() / category / now.strftime('%Y-%m-%d') / (now.strftime('%H-%M-%S') + '_' + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    return folder

def register_video_folder(root, folder):
    path = Path(root) / 'video-runs.json'
    try:
        folders = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        folders = []
    folders = list(dict.fromkeys(folders + [str(Path(folder).resolve())]))
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(folders, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)

def local_time(value, fallback):
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000 if value > 10**11 else value, LOCAL)
        date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return date.astimezone(LOCAL) if date.tzinfo else date.replace(tzinfo=LOCAL)
    except (ValueError, TypeError, OSError):
        return datetime.fromtimestamp(fallback, LOCAL)

class HistoryView(ttk.Frame):
    def __init__(self, parent, root, nctt, source):
        super().__init__(parent)
        self.root, self.nctt, self.source = root, nctt, source
        self.records = {}
        bar = ttk.Frame(self)
        bar.pack(fill='x')
        self.category = tk.StringVar(value='Tất cả')
        combo = ttk.Combobox(bar, textvariable=self.category, values=['Tất cả', 'NCTT', 'Thumbnail', 'Video'], state='readonly')
        combo.pack(side='left')
        combo.bind('<<ComboboxSelected>>', lambda _: self.refresh())
        ttk.Button(bar, text='Làm mới lịch sử', command=self.refresh).pack(side='left', padx=8)
        ttk.Button(bar, text='Mở thư mục kết quả', command=self.open_selected).pack(side='left')
        self.tree = ttk.Treeview(self, columns=('type', 'status'), selectmode='browse')
        self.tree.heading('#0', text='Ngày / giờ chạy / nội dung')
        self.tree.heading('type', text='Loại')
        self.tree.heading('status', text='Trạng thái')
        self.tree.column('#0', width=550)
        self.tree.column('type', width=100)
        self.tree.column('status', width=180)
        scroll = ttk.Scrollbar(self, command=self.tree.yview)
        scroll.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(fill='both', expand=True, pady=8)
        self.detail = tk.Text(self, height=5, wrap='word', state='disabled')
        self.detail.pack(fill='x')
        self.tree.bind('<<TreeviewSelect>>', self.show_detail)
        self.refresh()
        self.after(5000, self.poll)

    def poll(self):
        self.refresh()
        self.after(5000, self.poll)

    def refresh(self):
        rows = []
        for state in (self.source / 'desktop-data').glob('*/state.json'):
            try:
                data = json.loads(state.read_text(encoding='utf-8'))
                for row in data.get('history', []):
                    files = [f for a in row.get('attempts', []) for f in a.get('files', []) + a.get('croppedFiles', [])]
                    rows.append((local_time(row.get('time'), state.stat().st_mtime), 'Thumbnail', row.get('status', ''), row.get('prompt', ''), files, str(state), str(row.get('id', ''))))
            except (OSError, ValueError, TypeError):
                continue
        old_exports = self.nctt / 'exports'
        folders = list(old_exports.iterdir()) if old_exports.exists() else []
        folders += list((external_output_root(self.root) / 'NCTT').glob('*/*'))
        for folder in folders:
            if not folder.is_dir():
                continue
            files = list(folder.glob('*.xlsx')) + list(folder.glob('*.csv'))
            match = re.search(r'(\d{8}_\d{6})', folder.name)
            stamp = datetime.strptime(match[1], '%Y%m%d_%H%M%S').replace(tzinfo=LOCAL) if match else local_time(None, folder.stat().st_mtime)
            rows.append((stamp, 'NCTT', 'Có báo cáo' if files else 'Chưa có báo cáo', folder.name, [str(f) for f in files], str(folder), str(folder)))
        output_video = external_output_root(self.root) / 'Video'
        drafts = set(output_video.glob('*/*/draft.json')) | set(output_video.glob('*/*/video.json'))
        try:
            registered = json.loads((self.root / 'video-runs.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            registered = []
        for folder in registered:
            for name in ('draft.json', 'video.json'):
                candidate = Path(folder) / name
                if candidate.is_file():
                    drafts.add(candidate)
        for draft in drafts:
            try:
                row = json.loads(draft.read_text(encoding='utf-8'))
                rows.append((local_time(None, draft.stat().st_mtime), 'Video', row['status'], row['prompt'] + ('\nMô hình: ' + row['model'] if row.get('model') else '') + ('\nCài đặt: ' + str(row.get('mode', '')) + ' · ' + str(row.get('ratio', '')) + ' · x' + str(row.get('count', '')) if row.get('model') else '') + ('\nMức tải: ' + ', '.join(row['resolutions']) if row.get('resolutions') else '') + ('\nLỗi: ' + row['error'] if row.get('error') else '') + ('\nLưu ý: ' + '; '.join(row['warnings']) if row.get('warnings') else ''), row.get('files', []) + [str(draft)], str(draft.parent), str(draft)))
            except (OSError, ValueError, KeyError):
                continue
        rows.sort(key=lambda r: r[0], reverse=True)
        signature = repr(rows) + self.category.get()
        if signature == getattr(self, 'signature', None):
            return
        self.signature = signature
        selected=self.tree.selection()
        selected_source=self.records.get(selected[0], ('',[],None))[2] if selected else None
        self.tree.delete(*self.tree.get_children())
        self.records.clear()
        groups = {}
        for stamp, category, status, prompt, files, source, key in rows:
            if self.category.get() not in ('Tất cả', category):
                continue
            date = stamp.strftime('%Y-%m-%d')
            if date not in groups:
                groups[date] = self.tree.insert('', 'end', text=stamp.strftime('%d/%m/%Y'), open=True)
            item = self.tree.insert(groups[date], 'end', text=stamp.strftime('%H:%M:%S') + ' · ' + prompt.replace('\n', ' ')[:110], values=(category, status))
            self.records[item] = (prompt, files, source)
            if source==selected_source:self.tree.selection_set(item)

    def video_record_to_download(self):
        selection=self.tree.selection()
        row=self.records.get(selection[0]) if selection else None
        if row:
            path=Path(row[2])/'video.json'
            if path.is_file():return path
        paths=set((external_output_root(self.root)/'Video').glob('*/*/video.json'))
        try:
            for folder in json.loads((self.root/'video-runs.json').read_text(encoding='utf-8')):
                path=Path(folder)/'video.json'
                if path.is_file():paths.add(path)
        except (OSError,ValueError):pass
        candidates=[]
        for path in paths:
            try:
                record=json.loads(path.read_text(encoding='utf-8'))
                if record.get('submitted') and record.get('status')!='Hoàn tất':
                    candidates.append((record.get('time',''),path))
            except (OSError,ValueError):pass
        return max(candidates,key=lambda pair:pair[0])[1] if candidates else None

    def show_detail(self, event=None):
        selected = self.tree.selection()
        row = self.records.get(selected[0]) if selected else None
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        if row:
            self.detail.insert('1.0', row[0] + '\n' + '\n'.join(row[1]) + '\nNguồn: ' + row[2])
        self.detail.configure(state='disabled')

    def open_selected(self):
        selected = self.tree.selection()
        row = self.records.get(selected[0]) if selected else None
        if row:
            path = Path(row[1][0] if row[1] else row[2])
            path = path if path.is_dir() else path.parent
            if path.exists():
                os.startfile(str(path))
            else:
                messagebox.showerror('Lịch sử', 'Thư mục kết quả không còn tồn tại.')
