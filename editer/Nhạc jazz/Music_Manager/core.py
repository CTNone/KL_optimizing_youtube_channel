"""Local music catalog, manual credit records and reproducible project exports."""
import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import unicodedata
from contextlib import closing
from datetime import datetime
from pathlib import Path

STATUSES = ('Chưa kiểm tra', 'Không cần ghi công', 'Cần ghi công')
EXTENSIONS = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.wma'}
GROUPS = ('Chrismas', 'Winter_Cozy', 'Cafe_Jazz', 'Study_Reading', 'Deep_Relax', 'Romantic_Dinner')

def stamp():
    return datetime.now().isoformat(timespec='seconds')

def normalize(value):
    return ' '.join(unicodedata.normalize('NFC', value).replace('’', "'").casefold().split())

def filename_key(value):
    return re.sub(r'[^\w]', '', normalize(value))

def identity(title, artist):
    return hashlib.sha256((normalize(title) + '\0' + normalize(artist)).encode()).hexdigest()[:24]

def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip().rstrip('.')[:120]
    if not value or value.upper().split('.')[0] in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        value = '_' + value
    return value or 'project'

def csv_value(value):
    value = str(value or '')
    return "'" + value if value.startswith(('=', '+', '-', '@')) else value

class Catalog:
    def __init__(self, root, data_dir=None):
        self.root = Path(root).resolve()
        self.output_root = self.root.parents[1] / 'TOOL Video Flow OUTPUT' / 'Music Manager'
        self.output_root.mkdir(parents=True, exist_ok=True)
        workspace = self.root.parents[1]
        hub_dir = workspace / 'CONTENT HUB'
        self.shared = data_dir is None and (hub_dir / 'store.py').is_file()
        if self.shared:
            if str(hub_dir) not in __import__('sys').path:
                __import__('sys').path.insert(0, str(hub_dir))
            from store import Store
            production_db = (hub_dir / 'data' / 'content_hub.sqlite3').resolve()
            self.db_path = Path(os.environ.get('CONTENT_HUB_DATABASE', production_db)).resolve()
            Store(self.db_path)  # Apply the Hub schema before opening its shared database.
        else:
            self.data_dir = Path(data_dir or self.root / 'Music_Manager' / 'data')
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = self.data_dir / 'music.sqlite3'
        self.db = sqlite3.connect(self.db_path, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS music_tracks (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, artist TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'Chưa kiểm tra', credit TEXT NOT NULL DEFAULT '',
          source TEXT NOT NULL DEFAULT '', license TEXT NOT NULL DEFAULT '',
          notes TEXT NOT NULL DEFAULT '', reviewed TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS music_memberships (
          track_id TEXT REFERENCES music_tracks(id), name TEXT, PRIMARY KEY(track_id,name));
        CREATE TABLE IF NOT EXISTS music_track_tags (
          track_id TEXT NOT NULL REFERENCES music_tracks(id) ON DELETE CASCADE,
          category TEXT NOT NULL, value TEXT NOT NULL,
          PRIMARY KEY(track_id, category, value));
        CREATE TABLE IF NOT EXISTS music_channel_tracks (
          channel_id TEXT NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
          track_id TEXT NOT NULL REFERENCES music_tracks(id) ON DELETE CASCADE,
          PRIMARY KEY(channel_id, track_id));
        CREATE TABLE IF NOT EXISTS music_files (
          path TEXT PRIMARY KEY, track_id TEXT REFERENCES music_tracks(id), size INTEGER,
          modified INTEGER, present INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS music_projects (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS music_project_tracks (
          project_id INTEGER REFERENCES music_projects(id), track_id TEXT REFERENCES music_tracks(id),
          position INTEGER NOT NULL, PRIMARY KEY(project_id,track_id));
        CREATE TABLE IF NOT EXISTS music_history (
          id INTEGER PRIMARY KEY, track_id TEXT, changed TEXT, before_json TEXT, after_json TEXT);
        CREATE TABLE IF NOT EXISTS music_exports (
          id INTEGER PRIMARY KEY, project_id INTEGER, created TEXT, path TEXT, draft INTEGER);
        CREATE TABLE IF NOT EXISTS music_migrations (
          source TEXT PRIMARY KEY, imported_at TEXT NOT NULL);
        CREATE VIEW IF NOT EXISTS tracks AS SELECT * FROM music_tracks;
        ''')
        self.db.commit()

    def backup(self):
        folder = self.output_root / 'Backups'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / ('music_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.sqlite3')
        with closing(sqlite3.connect(path)) as dest:
            self.db.backup(dest)
        return path

    def scan(self):
        metadata_path = self.output_root.parent / 'Music Library' / 'library_audit.json'
        if not metadata_path.exists():
            metadata_path = self.root / 'library_audit.json'
        metadata = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else []
        lookup = {}
        with self.db:
            self.db.execute('UPDATE music_files SET present=0')
            self.db.execute('DELETE FROM music_memberships')
            for item in metadata:
                tid = identity(item['title'], item['artist'])
                self.db.execute('INSERT OR IGNORE INTO music_tracks(id,title,artist) VALUES(?,?,?)', (tid,item['title'],item['artist']))
                self.db.execute('INSERT OR IGNORE INTO music_memberships VALUES(?,?)', (tid,item['folder']))
                for name in (item.get('filename',''), f"{item['title']} - {item['artist']}"):
                    lookup[filename_key(re.sub(r'^\d+\s*-\s*','',Path(name).stem if name.endswith('.mp3') else name))] = tid
            count = 0
            scan_roots = (self.root, self.output_root.parent / 'Music Library' / 'Tracks')
            for scan_root in scan_roots:
                if not scan_root.is_dir():
                    continue
                for path in scan_root.rglob('*'):
                    rel = path.relative_to(scan_root)
                    if scan_root == self.root and any(p.startswith('.') or p in ('Music_Manager','CapCut_Exports','__pycache__') for p in rel.parts):
                        continue
                    if path.suffix.lower() not in EXTENSIONS or not path.is_file():
                        continue
                    base = re.sub(r'^\d+\s*-\s*','',path.stem)
                    marked_credit = bool(re.search(r'\s*-\s*GHI\s+CÔNG\s*$',base,re.I))
                    base = re.sub(r'\s*-\s*GHI\s+CÔNG\s*$','',base,flags=re.I)
                    tid = lookup.get(filename_key(base))
                    if not tid:
                        parts = base.rsplit(' - ', 1)
                        title, artist = (parts if len(parts)==2 else (base, 'Chưa xác định'))
                        tid = identity(title, artist)
                        self.db.execute('INSERT OR IGNORE INTO music_tracks(id,title,artist) VALUES(?,?,?)',(tid,title,artist))
                    group = rel.parts[0] if len(rel.parts)>1 else 'Thư mục gốc'
                    if marked_credit:
                        self.db.execute("UPDATE music_tracks SET notes=? WHERE id=? AND notes=''",('Tên tệp nguồn có đánh dấu GHI CÔNG. Hãy kiểm tra và nhập nội dung ghi công.',tid))
                    self.db.execute('INSERT OR IGNORE INTO music_memberships VALUES(?,?)',(tid,group))
                    stat = path.stat()
                    self.db.execute('INSERT OR REPLACE INTO music_files VALUES(?,?,?,?,1)',(str(path.resolve()),tid,stat.st_size,stat.st_mtime_ns))
                    count += 1
        return count

    def tracks(self):
        return [dict(row) for row in self.db.execute('''SELECT t.*,
        (SELECT group_concat(m.name, ', ') FROM music_memberships m WHERE m.track_id=t.id) AS groups,
        (SELECT group_concat(c.name, ', ') FROM music_channel_tracks mc JOIN channels c ON c.id=mc.channel_id WHERE mc.track_id=t.id) AS channels,
        (SELECT count(*) FROM music_files f WHERE f.track_id=t.id AND f.present=1) AS file_count,
        (SELECT count(*) FROM music_project_tracks pt WHERE pt.track_id=t.id) AS uses,
        (SELECT group_concat(value, ' · ') FROM music_track_tags mt WHERE mt.track_id=t.id) AS tags
        FROM music_tracks t ORDER BY t.title COLLATE NOCASE, t.artist''')]

    def track_tags(self, track_id):
        rows = self.db.execute(
            'SELECT category,value FROM music_track_tags WHERE track_id=? ORDER BY category,value',
            (track_id,),
        ).fetchall()
        result = {}
        for row in rows:
            result.setdefault(row['category'], []).append(row['value'])
        return result

    def save_track_tags(self, track_ids, tags):
        allowed = {'genre', 'instrument', 'vocal', 'mood'}
        updates = {key: values for key, values in tags.items() if key in allowed}
        with self.db:
            for track_id in track_ids:
                for category, values in updates.items():
                    self.db.execute(
                        'DELETE FROM music_track_tags WHERE track_id=? AND category=?',
                        (track_id, category),
                    )
                    self.db.executemany(
                        'INSERT OR IGNORE INTO music_track_tags(track_id,category,value) VALUES(?,?,?)',
                        ((track_id, category, value) for value in sorted(set(values))),
                    )

    def channels(self):
        return [dict(r) for r in self.db.execute('SELECT id,name,niche,style,archived FROM channels ORDER BY archived,name COLLATE NOCASE')]

    def assign_channel(self, name, track_ids):
        if not self.db.execute('SELECT 1 FROM channels WHERE id=? AND archived=0', (name,)).fetchone():
            raise ValueError('Không tìm thấy kênh')
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO music_channel_tracks(channel_id,track_id) VALUES(?,?)',
                                ((name, tid) for tid in track_ids))

    def unassign_channel(self, name, track_ids):
        with self.db:
            self.db.executemany('DELETE FROM music_channel_tracks WHERE channel_id=? AND track_id=?',
                                ((name, tid) for tid in track_ids))

    def channel_tracks(self, name):
        return [dict(r) for r in self.db.execute('''SELECT t.*,
            (SELECT f.path FROM music_files f WHERE f.track_id=t.id AND f.present=1 ORDER BY f.path LIMIT 1) AS path
            FROM music_channel_tracks ct JOIN music_tracks t ON t.id=ct.track_id
            WHERE ct.channel_id=? AND EXISTS(SELECT 1 FROM music_files f WHERE f.track_id=t.id AND f.present=1)
            ORDER BY t.title COLLATE NOCASE, t.artist''', (name,))]

    def get(self, tid):
        row = self.db.execute('SELECT * FROM music_tracks WHERE id=?',(tid,)).fetchone()
        if not row: raise ValueError('Không tìm thấy bài hát')
        return dict(row)

    def save_review(self, tid, status, credit, source='', license='', notes=''):
        if status not in STATUSES: raise ValueError('Trạng thái không hợp lệ')
        if status == STATUSES[2] and not credit.strip():
            raise ValueError('Bài cần ghi công: hãy dán nội dung ghi công trước khi lưu.')
        old = self.get(tid)
        new = dict(status=status,credit=credit.strip(),source=source.strip(),license=license.strip(),notes=notes.strip(),reviewed=stamp())
        with self.db:
            self.db.execute('UPDATE music_tracks SET status=:status,credit=:credit,source=:source,license=:license,notes=:notes,reviewed=:reviewed WHERE id=:id',{**new,'id':tid})
            self.db.execute('INSERT INTO music_history(track_id,changed,before_json,after_json) VALUES(?,?,?,?)',(tid,stamp(),json.dumps(old,ensure_ascii=False),json.dumps(new,ensure_ascii=False)))

    def projects(self):
        return [dict(r) for r in self.db.execute('SELECT p.*,count(pt.track_id) AS count FROM music_projects p LEFT JOIN music_project_tracks pt ON pt.project_id=p.id GROUP BY p.id ORDER BY p.id DESC')]

    def new_project(self, name):
        if not name.strip(): raise ValueError('Hãy nhập tên dự án')
        with self.db:
            cur = self.db.execute('INSERT INTO music_projects(name,created) VALUES(?,?)',(name.strip(),stamp()))
        return cur.lastrowid

    def delete_project(self, pid):
        with self.db:
            self.db.execute('DELETE FROM music_project_tracks WHERE project_id=?',(pid,))
            self.db.execute('DELETE FROM music_projects WHERE id=?',(pid,))

    def project_items(self, pid):
        return [dict(r) for r in self.db.execute('SELECT t.*,pt.position FROM music_project_tracks pt JOIN music_tracks t ON t.id=pt.track_id WHERE pt.project_id=? ORDER BY pt.position',(pid,))]

    def add(self, pid, ids):
        with self.db:
            pos = self.db.execute('SELECT coalesce(max(position),0) FROM music_project_tracks WHERE project_id=?',(pid,)).fetchone()[0]
            for tid in ids:
                pos += 1
                self.db.execute('INSERT OR IGNORE INTO music_project_tracks VALUES(?,?,?)',(pid,tid,pos))

    def remove(self, pid, ids):
        with self.db:
            for tid in ids: self.db.execute('DELETE FROM music_project_tracks WHERE project_id=? AND track_id=?',(pid,tid))

    def reorder(self, pid, ordered_ids):
        current = {r['id'] for r in self.project_items(pid)}
        if len(ordered_ids)!=len(current) or set(ordered_ids)!=current: raise ValueError('Danh sách thứ tự không hợp lệ')
        with self.db:
            for i,tid in enumerate(ordered_ids,1): self.db.execute('UPDATE music_project_tracks SET position=? WHERE project_id=? AND track_id=?',(i,pid,tid))

    def source_file(self, tid):
        for row in self.db.execute('SELECT path FROM music_files WHERE track_id=? AND present=1 ORDER BY path',(tid,)):
            stored = Path(row['path'])
            p = (stored if stored.is_absolute() else self.root / stored).resolve()
            if p.is_file() and p.stat().st_size > 0: return p
        return None

    def issues(self, pid):
        issues = []
        for r in self.project_items(pid):
            reasons=[]
            if not self.source_file(r['id']): reasons.append('Không có tệp âm thanh')
            if r['status']==STATUSES[0]: reasons.append('Chưa kiểm tra ghi công')
            if r['status']==STATUSES[2] and not r['credit'].strip(): reasons.append('Thiếu nội dung ghi công')
            if reasons: issues.append((r['title'], '; '.join(reasons)))
        return issues

    def credit_text(self, pid):
        return '\n\n'.join(r['credit'].strip() for r in self.project_items(pid) if r['status']==STATUSES[2] and r['credit'].strip())

    def export(self, pid, draft=False):
        project = self.db.execute('SELECT * FROM music_projects WHERE id=?',(pid,)).fetchone()
        if not project: raise ValueError('Chưa chọn dự án')
        rows = self.project_items(pid)
        if not rows: raise ValueError('Dự án chưa có bài hát')
        issues = self.issues(pid)
        if any(not self.source_file(r['id']) for r in rows): raise ValueError('Có bài thiếu tệp âm thanh. Hãy bỏ bài thiếu hoặc quét lại thư viện.')
        if issues and not draft: raise ValueError('Còn bài chưa kiểm tra hoặc thiếu ghi công. Kiểm tra trước hoặc xuất bản nháp.')
        parent = self.output_root / 'CapCut_Exports'; parent.mkdir(parents=True, exist_ok=True)
        tag = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        dest = parent / (safe_name(project['name']) + '_' + tag)
        staging = parent / ('.building_' + tag)
        staging.mkdir(); audio = staging / 'Audio'; audio.mkdir()
        manifest=[]
        try:
            for index,r in enumerate(rows,1):
                src = self.source_file(r['id'])
                name = f'{index:03d} - {safe_name(r["title"] + " - " + r["artist"])}{src.suffix.lower()}'
                shutil.copy2(src,audio/name)
                manifest.append({**r,'export_file':'Audio/'+name,'original_file':str(src)})
            (staging/'GHI_CONG.txt').write_text(self.credit_text(pid),encoding='utf-8-sig')
            (staging/'CAN_KIEM_TRA.txt').write_text('\n'.join(f'{title}: {reason}' for title,reason in issues) or 'Đã kiểm tra tất cả bài hát theo trạng thái bạn nhập.',encoding='utf-8-sig')
            snapshot={'project':dict(project),'exported':stamp(),'draft':draft,'tracks':manifest}
            (staging/'project_snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
            with (staging/'DANH_SACH.csv').open('w',encoding='utf-8-sig',newline='') as f:
                fields=['position','title','artist','status','credit','source','license','reviewed','export_file','original_file']
                writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader()
                for r in manifest: writer.writerow({k:csv_value(r[k]) for k in fields})
            (staging/'HUONG_DAN.txt').write_text(('BẢN NHÁP — CÒN BÀI CHƯA KIỂM TRA.\n' if issues else '') + 'Mở dự án CapCut > Media > Import và chọn các tệp trong Audio.\nTên tệp có số thứ tự theo danh sách dự án.\nGHI_CONG.txt chứa nguyên văn nội dung bạn nhập cho các bài cần ghi công.\nDán nội dung này vào mô tả khi đăng video. Xem CAN_KIEM_TRA.txt trước khi đăng.\nĐây là gói tài nguyên, không phải tệp dự án CapCut.\nNếu đổi trạng thái ghi công hoặc danh sách bài, hãy xuất một gói mới.\n',encoding='utf-8-sig')
            staging.rename(dest)
        except Exception:
            # Keep failed staging output for diagnosis; never advertise it as a finished export.
            raise
        with self.db: self.db.execute('INSERT INTO music_exports(project_id,created,path,draft) VALUES(?,?,?,?)',(pid,stamp(),str(dest),int(draft)))
        return dest

    def export_catalog(self, path):
        path = Path(path).resolve()
        try:
            path.relative_to(self.output_root.resolve())
        except ValueError:
            raise ValueError(f'Danh mục xuất phải nằm trong {self.output_root}.')
        fields=['id','title','artist','status','credit','source','license','notes','reviewed','groups','file_count','uses']
        with path.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader()
            for r in self.tracks(): writer.writerow({k:csv_value(r[k]) for k in fields})
