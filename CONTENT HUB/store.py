"""SQLite domain layer. All state changes and audit records commit together."""
from __future__ import annotations
import contextlib
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=7))
STAGES = {
    "idea": "Ý tưởng", "research": "Nghiên cứu", "thumbnail": "Thumbnail",
    "clip": "Clip Flow", "editing": "Dựng video", "review": "Kiểm duyệt",
    "ready": "Sẵn sàng", "scheduled": "Đã lên lịch", "published": "Đã đăng",
}
KINDS = {"research": "Dữ liệu nghiên cứu", "reference": "Ảnh tham chiếu",
         "thumbnail": "Thumbnail", "clip": "Clip Flow", "music": "Nhạc",
         "final": "Video thành phẩm"}
CHECKS = ("Hình ảnh và bố cục", "Điểm nối loop", "Âm thanh / chủ đích không tiếng", "Nguồn và quyền sử dụng tài nguyên")

def now():
    return datetime.now(TZ).isoformat(timespec="seconds")

def uid():
    return uuid.uuid4().hex

class DomainError(ValueError):
    pass

def required(value, label, limit=2000):
    value = str(value or "").strip()
    if not value or len(value) > limit:
        raise DomainError(f"{label}: bắt buộc nhập, tối đa {limit} ký tự.")
    return value

def fingerprint(path: Path):
    path = path.resolve()
    if not path.is_file():
        raise DomainError(f"File không tồn tại: {path}")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise DomainError("File đang thay đổi; đợi ghi xong rồi nhập lại.")
    return {"path": str(path), "bytes": after.st_size, "mtime_ns": after.st_mtime_ns,
            "sha256": digest.hexdigest()}

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, niche TEXT NOT NULL DEFAULT '',
 url TEXT NOT NULL DEFAULT '', style TEXT NOT NULL DEFAULT '', archived INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, channel_id TEXT NOT NULL REFERENCES channels(id), title TEXT NOT NULL,
 brief TEXT NOT NULL DEFAULT '', owner TEXT NOT NULL DEFAULT '', stage TEXT NOT NULL DEFAULT 'idea',
 due_date TEXT NOT NULL DEFAULT '', scheduled_at TEXT NOT NULL DEFAULT '', youtube_url TEXT NOT NULL DEFAULT '',
 revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS project_channel ON projects(channel_id,stage);
CREATE TABLE IF NOT EXISTS assets (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), kind TEXT NOT NULL,
 slot TEXT NOT NULL, version INTEGER NOT NULL, path TEXT NOT NULL, bytes INTEGER NOT NULL,
 mtime_ns INTEGER NOT NULL, sha256 TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
 UNIQUE(project_id,kind,slot,version));
CREATE TABLE IF NOT EXISTS reviews (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), asset_id TEXT NOT NULL REFERENCES assets(id),
 decision TEXT NOT NULL, reviewer TEXT NOT NULL, checks_json TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), kind TEXT NOT NULL,
 state TEXT NOT NULL, payload_json TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0,
 message TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '', result_json TEXT NOT NULL DEFAULT '{}',
 retry_of TEXT REFERENCES jobs(id), created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_job ON jobs(project_id)
 WHERE state IN ('queued','running','cancelling');
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT REFERENCES projects(id),
 actor TEXT NOT NULL, action TEXT NOT NULL, detail_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS metrics (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), recorded_at TEXT NOT NULL,
 views INTEGER NOT NULL, watch_minutes REAL NOT NULL, impressions INTEGER NOT NULL, ctr REAL NOT NULL,
 source TEXT NOT NULL DEFAULT 'manual');
CREATE TABLE IF NOT EXISTS music_tracks (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, artist TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'Chưa kiểm tra', credit TEXT NOT NULL DEFAULT '',
 source TEXT NOT NULL DEFAULT '', license TEXT NOT NULL DEFAULT '',
 notes TEXT NOT NULL DEFAULT '', reviewed TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS music_memberships (
 track_id TEXT NOT NULL REFERENCES music_tracks(id) ON DELETE CASCADE,
 name TEXT NOT NULL, PRIMARY KEY(track_id,name));
CREATE TABLE IF NOT EXISTS music_files (
 path TEXT PRIMARY KEY, track_id TEXT NOT NULL REFERENCES music_tracks(id), size INTEGER,
 modified INTEGER, present INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS music_projects (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS music_project_tracks (
 project_id INTEGER NOT NULL REFERENCES music_projects(id) ON DELETE CASCADE,
 track_id TEXT NOT NULL REFERENCES music_tracks(id), position INTEGER NOT NULL,
 PRIMARY KEY(project_id,track_id));
CREATE TABLE IF NOT EXISTS music_history (
 id INTEGER PRIMARY KEY, track_id TEXT, changed TEXT, before_json TEXT, after_json TEXT);
CREATE TABLE IF NOT EXISTS music_exports (
 id INTEGER PRIMARY KEY, project_id INTEGER, created TEXT, path TEXT, draft INTEGER);
CREATE TABLE IF NOT EXISTS music_channel_tracks (
 channel_id TEXT NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
 track_id TEXT NOT NULL REFERENCES music_tracks(id) ON DELETE CASCADE,
 PRIMARY KEY(channel_id,track_id));
CREATE TABLE IF NOT EXISTS music_migrations (
 source TEXT PRIMARY KEY, imported_at TEXT NOT NULL);
PRAGMA user_version=2;
"""

class Store:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.closing(self.connect()) as db:
            db.executescript(SCHEMA)
        if self.path.name == "content_hub.sqlite3" and self.path.parent.name == "data":
            self.import_legacy_music()

    def import_legacy_music(self):
        """Copy the standalone Music Manager catalog once, preserving its source file."""
        workspace = self.path.parents[2]
        source = workspace / "editer" / "Nhạc jazz" / "Music_Manager" / "data" / "music.sqlite3"
        if not source.is_file():
            return
        source_key = str(source.resolve())
        if self.one("SELECT 1 FROM music_migrations WHERE source=?", (source_key,)):
            return
        old = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        old.row_factory = sqlite3.Row
        table_map = {
            "tracks": "music_tracks", "memberships": "music_memberships", "files": "music_files",
            "projects": "music_projects", "project_tracks": "music_project_tracks",
            "history": "music_history", "exports": "music_exports",
        }
        try:
            with self.transaction() as db:
                for old_name, new_name in table_map.items():
                    exists = old.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (old_name,)).fetchone()
                    if not exists:
                        continue
                    rows = old.execute(f"SELECT * FROM {old_name}").fetchall()
                    if not rows:
                        continue
                    columns = rows[0].keys()
                    column_sql = ",".join('"' + name + '"' for name in columns)
                    marks = ",".join("?" for _ in columns)
                    db.executemany(f"INSERT OR IGNORE INTO {new_name} ({column_sql}) VALUES ({marks})",
                                   (tuple(row) for row in rows))
                db.execute("INSERT INTO music_migrations(source,imported_at) VALUES(?,?)", (source_key, now()))
        finally:
            old.close()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    @contextlib.contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def rows(self, sql, params=()):
        with contextlib.closing(self.connect()) as db:
            return [dict(r) for r in db.execute(sql, params)]

    def one(self, sql, params=()):
        rows = self.rows(sql, params)
        return rows[0] if rows else None

    def event(self, db, project_id, actor, action, detail):
        db.execute("INSERT INTO events(project_id,actor,action,detail_json,created_at) VALUES(?,?,?,?,?)",
                   (project_id, required(actor, "Người thao tác", 100), action,
                    json.dumps(detail, ensure_ascii=False), now()))

    def channels(self):
        return self.rows("SELECT * FROM channels ORDER BY archived,name")

    def channel_music(self, channel_id):
        return self.rows("""SELECT t.*,
            (SELECT f.path FROM music_files f WHERE f.track_id=t.id AND f.present=1 ORDER BY f.path LIMIT 1) AS path
            FROM music_channel_tracks ct JOIN music_tracks t ON t.id=ct.track_id
            WHERE ct.channel_id=? AND EXISTS(SELECT 1 FROM music_files f WHERE f.track_id=t.id AND f.present=1)
            ORDER BY t.title COLLATE NOCASE,t.artist""", (channel_id,))

    def save_channel(self, name, niche="", url="", style="", channel_id=None, actor="Local operator", archived=False):
        name = required(name, "Tên kênh", 150)
        channel_id = channel_id or uid()
        with self.transaction() as db:
            exists = db.execute("SELECT id FROM channels WHERE id=?", (channel_id,)).fetchone()
            if exists:
                db.execute("UPDATE channels SET name=?,niche=?,url=?,style=?,archived=? WHERE id=?",
                           (name, niche, url, style, int(archived), channel_id))
            else:
                db.execute("INSERT INTO channels VALUES(?,?,?,?,?,?,?)",
                           (channel_id, name, niche, url, style, int(archived), now()))
            self.event(db, None, actor, "channel_saved", {"channel_id": channel_id, "name": name})
        return channel_id

    def projects(self, channel_id="", query="", stage=""):
        sql = "SELECT p.*, c.name AS channel_name FROM projects p JOIN channels c ON c.id=p.channel_id WHERE 1=1"
        args = []
        for value, clause in [(channel_id, "p.channel_id=?"), (stage, "p.stage=?")]:
            if value:
                sql += " AND " + clause
                args.append(value)
        if query:
            sql += " AND (p.title LIKE ? OR p.owner LIKE ?)"
            args += ["%" + query + "%"]*2
        return self.rows(sql + " ORDER BY p.updated_at DESC", args)

    def project(self, project_id):
        row = self.one("SELECT p.*, c.name AS channel_name,c.style AS channel_style FROM projects p JOIN channels c ON c.id=p.channel_id WHERE p.id=?", (project_id,))
        if not row:
            raise DomainError("Không tìm thấy dự án.")
        return row

    def create_project(self, channel_id, title, brief="", owner="", due_date="", actor="Local operator"):
        title = required(title, "Tiêu đề", 250)
        if due_date:
            datetime.strptime(due_date, "%Y-%m-%d")
        project_id = uid()
        with self.transaction() as db:
            channel = db.execute("SELECT * FROM channels WHERE id=? AND archived=0", (channel_id,)).fetchone()
            if not channel:
                raise DomainError("Chọn kênh đang hoạt động.")
            db.execute("INSERT INTO projects(id,channel_id,title,brief,owner,due_date,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                       (project_id, channel_id, title, brief, owner, due_date, now(), now()))
            self.event(db, project_id, actor, "project_created", {"title": title, "channel_id": channel_id})
        return project_id

    def update_project(self, project_id, revision, title, brief, owner, due_date, actor):
        title = required(title, "Tiêu đề", 250)
        if due_date:
            datetime.strptime(due_date, "%Y-%m-%d")
        with self.transaction() as db:
            changed = db.execute("UPDATE projects SET title=?,brief=?,owner=?,due_date=?,revision=revision+1,updated_at=? WHERE id=? AND revision=?",
                                 (title, brief, owner, due_date, now(), project_id, revision))
            if changed.rowcount != 1:
                raise DomainError("Dự án vừa được thay đổi. Làm mới trước khi lưu.")
            self.event(db, project_id, actor, "project_updated", {"title": title})

    def assets(self, project_id, latest=False):
        sql = "SELECT a.* FROM assets a WHERE project_id=?"
        if latest:
            sql += " AND NOT EXISTS(SELECT 1 FROM assets b WHERE b.project_id=a.project_id AND b.kind=a.kind AND b.slot=a.slot AND b.version>a.version)"
        return self.rows(sql + " ORDER BY kind,slot,version DESC", (project_id,))

    def add_asset(self, project_id, kind, path, actor, slot="", note="", expected_fingerprint=None):
        if kind not in KINDS:
            raise DomainError("Loại tài nguyên không hợp lệ.")
        path = Path(path)
        extensions = {"thumbnail": {".png", ".jpg", ".jpeg", ".webp"},
                      "reference": {".png", ".jpg", ".jpeg", ".webp"},
                      "clip": {".mp4", ".mov", ".webm", ".mkv"},
                      "final": {".mp4", ".mov", ".webm", ".mkv"},
                      "music": {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}}
        if kind in extensions and path.suffix.lower() not in extensions[kind]:
            raise DomainError("Định dạng file không phù hợp loại tài nguyên.")
        info = fingerprint(path)
        if expected_fingerprint and info["sha256"] != expected_fingerprint:
            raise DomainError("File không khớp mã kiểm tra được chờ đợi.")
        slot = required(slot or (path.stem if kind in ("clip", "music") else "main"), "Nhóm phiên bản", 200)
        with self.transaction() as db:
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not project or project["stage"] in ("scheduled", "published"):
                raise DomainError("Không thay tài nguyên khi đã lên lịch/đăng; đưa về chỉnh sửa trước.")
            existing = db.execute("SELECT * FROM assets WHERE project_id=? AND kind=? AND slot=? ORDER BY version DESC LIMIT 1", (project_id, kind, slot)).fetchone()
            if existing and existing["sha256"] == info["sha256"] and existing["path"] == info["path"]:
                return existing["id"]
            version = (existing["version"] if existing else 0) + 1
            asset_id = uid()
            db.execute("INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (asset_id, project_id, kind, slot, version, info["path"], info["bytes"],
                        info["mtime_ns"], info["sha256"], note, now()))
            # Any changed production input invalidates the accepted package.
            stage = "editing" if project["stage"] in ("review", "ready") else project["stage"]
            db.execute("UPDATE projects SET stage=?,revision=revision+1,updated_at=? WHERE id=?", (stage, now(), project_id))
            self.event(db, project_id, actor, "asset_imported", {"asset_id": asset_id, "kind": kind, "slot": slot, "version": version})
        return asset_id

    def delete_asset(self, asset_id, actor):
        """Remove an asset reference while preserving its original file and audit trail."""
        with self.transaction() as db:
            asset = db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
            if not asset:
                raise DomainError("Tài nguyên không còn tồn tại; hãy làm mới.")
            project = db.execute("SELECT * FROM projects WHERE id=?", (asset["project_id"],)).fetchone()
            if not project or project["stage"] in ("scheduled", "published"):
                raise DomainError("Không xóa tài nguyên khi đã lên lịch/đăng; đưa dự án về chỉnh sửa trước.")
            reviewed = db.execute("SELECT 1 FROM reviews WHERE asset_id=? LIMIT 1", (asset_id,)).fetchone()
            if reviewed:
                raise DomainError("Tài nguyên này đã được dùng trong lịch sử QC nên không thể xóa.")
            db.execute("DELETE FROM assets WHERE id=?", (asset_id,))
            stage = "editing" if project["stage"] in ("review", "ready") else project["stage"]
            db.execute("UPDATE projects SET stage=?,revision=revision+1,updated_at=? WHERE id=?",
                       (stage, now(), project["id"]))
            self.event(db, project["id"], actor, "asset_deleted", {
                "asset_id": asset_id, "kind": asset["kind"], "slot": asset["slot"],
                "version": asset["version"], "path": asset["path"],
            })

    def verify_asset(self, asset):
        current = fingerprint(Path(asset["path"]))
        if current["sha256"] != asset["sha256"]:
            raise DomainError(f"File đã thay đổi ngoài hệ thống: {Path(asset['path']).name}. Nhập phiên bản mới trước.")
        return current

    def _latest_final(self, db, project_id):
        return db.execute("SELECT * FROM assets WHERE project_id=? AND kind='final' AND slot='main' ORDER BY version DESC LIMIT 1", (project_id,)).fetchone()

    def advance(self, project_id, revision, actor, scheduled_at="", youtube_url=""):
        with self.transaction() as db:
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not project or project["revision"] != revision:
                raise DomainError("Dữ liệu đã thay đổi; hãy làm mới.")
            keys = list(STAGES)
            old = project["stage"]
            if old == "published":
                raise DomainError("Dự án đã đăng.")
            target = keys[keys.index(old)+1]
            kinds = {r[0] for r in db.execute("SELECT DISTINCT kind FROM assets WHERE project_id=?", (project_id,))}
            if target == "research" and not project["brief"].strip():
                raise DomainError("Nhập brief/mục tiêu trước khi nghiên cứu.")
            if target == "thumbnail" and "research" not in kinds:
                raise DomainError("Cần đính kèm dữ liệu nghiên cứu.")
            if target == "clip" and "thumbnail" not in kinds:
                raise DomainError("Cần đính kèm thumbnail đã chọn.")
            if target == "editing" and "clip" not in kinds:
                raise DomainError("Cần clip Flow trước khi dựng.")
            if target == "review":
                if db.execute("SELECT 1 FROM jobs WHERE project_id=? AND state IN ('queued','running','cancelling')", (project_id,)).fetchone():
                    raise DomainError("Đợi tác vụ render kết thúc trước khi kiểm duyệt.")
                if not self._latest_final(db, project_id):
                    raise DomainError("Cần video thành phẩm nhóm main.")
            if target == "ready":
                raise DomainError("Dùng nút Duyệt QC với checklist để chuyển sang Sẵn sàng.")
            if target in ("scheduled", "published"):
                final = self._latest_final(db, project_id)
                review = db.execute("SELECT * FROM reviews WHERE project_id=? ORDER BY rowid DESC LIMIT 1", (project_id,)).fetchone()
                if not final or not review or review["decision"] != "approved" or review["asset_id"] != final["id"]:
                    raise DomainError("Chưa có QC được duyệt cho bản thành phẩm hiện tại.")
                self.verify_asset(final)
            if target == "scheduled":
                try:
                    parsed = datetime.strptime(scheduled_at.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
                except ValueError:
                    raise DomainError("Lịch đăng nhập dạng YYYY-MM-DD HH:MM, giờ Việt Nam.")
                if parsed <= datetime.now(TZ):
                    raise DomainError("Lịch đăng phải ở tương lai.")
                scheduled_at = parsed.isoformat(timespec="seconds")
            else:
                scheduled_at = project["scheduled_at"]
            if target == "published":
                from urllib.parse import urlparse
                parsed = urlparse(youtube_url.strip())
                if parsed.scheme != "https" or parsed.hostname not in ("youtube.com", "www.youtube.com", "youtu.be"):
                    raise DomainError("Nhập URL HTTPS YouTube xác nhận video đã đăng.")
            else:
                youtube_url = project["youtube_url"]
            db.execute("UPDATE projects SET stage=?,scheduled_at=?,youtube_url=?,revision=revision+1,updated_at=? WHERE id=?",
                       (target, scheduled_at, youtube_url, now(), project_id))
            self.event(db, project_id, actor, "stage_changed", {"from": old, "to": target})
        return target

    def review(self, project_id, revision, reviewer, approved, checks, note):
        reviewer = required(reviewer, "Người duyệt", 100)
        if not approved and not str(note).strip():
            raise DomainError("Nhập lý do yêu cầu chỉnh sửa.")
        if approved and set(checks) != set(CHECKS):
            raise DomainError("Cần xác nhận đủ bốn mục QC.")
        with self.transaction() as db:
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not project or project["revision"] != revision or project["stage"] != "review":
                raise DomainError("Chỉ duyệt dự án đang Kiểm duyệt, với dữ liệu mới nhất.")
            final = self._latest_final(db, project_id)
            if not final:
                raise DomainError("Không có video thành phẩm.")
            if approved:
                self.verify_asset(final)
            decision = "approved" if approved else "rejected"
            db.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?)",
                       (uid(), project_id, final["id"], decision, reviewer, json.dumps(list(checks), ensure_ascii=False), note, now()))
            target = "ready" if approved else "editing"
            db.execute("UPDATE projects SET stage=?,revision=revision+1,updated_at=? WHERE id=?", (target, now(), project_id))
            self.event(db, project_id, reviewer, "qc_"+decision, {"asset_id": final["id"], "note": note})

    def rework(self, project_id, revision, actor, reason):
        reason = required(reason, "Lý do chỉnh sửa")
        with self.transaction() as db:
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not project or project["revision"] != revision or project["stage"] not in ("review", "ready", "scheduled"):
                raise DomainError("Chỉ đưa về chỉnh sửa từ Kiểm duyệt / Sẵn sàng / Đã lên lịch.")
            db.execute("UPDATE projects SET stage='editing',scheduled_at='',revision=revision+1,updated_at=? WHERE id=?", (now(), project_id))
            self.event(db, project_id, actor, "rework_requested", {"reason": reason})

    def add_metrics(self, project_id, views, watch_minutes, impressions, ctr, actor):
        import math
        if min(views, watch_minutes, impressions, ctr) < 0 or ctr > 100 or not all(math.isfinite(x) for x in (views, watch_minutes, impressions, ctr)):
            raise DomainError("Chỉ số phải hữu hạn, không âm; CTR từ 0–100%.")
        if self.project(project_id)["stage"] != "published":
            raise DomainError("Chỉ ghi hiệu suất cho video đã đăng.")
        with self.transaction() as db:
            db.execute("INSERT INTO metrics VALUES(?,?,?,?,?,?,?,?)", (uid(), project_id, now(), int(views), watch_minutes, int(impressions), ctr, "manual"))
            self.event(db, project_id, actor, "metrics_recorded", {"source": "manual", "views": views})

    def backup(self, destination):
        if Path(destination).resolve() == self.path:
            raise DomainError("Backup phải khác database đang dùng.")
        with contextlib.closing(self.connect()) as source, contextlib.closing(sqlite3.connect(destination)) as target:
            source.backup(target)

    def events(self, project_id=None):
        return self.rows("SELECT * FROM events" + (" WHERE project_id=?" if project_id else "") + " ORDER BY id DESC LIMIT 300",
                         (project_id,) if project_id else ())

    def create_job(self, project_id, payload, actor, retry_of=None):
        with self.transaction() as db:
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not project or project["stage"] != "editing":
                raise DomainError("Dự án phải ở bước Dựng video để thêm render.")
            job_id = uid()
            try:
                db.execute("INSERT INTO jobs(id,project_id,kind,state,payload_json,retry_of,created_at) VALUES(?,?,'render_loop','queued',?,?,?)",
                           (job_id, project_id, json.dumps(payload, ensure_ascii=False), retry_of, now()))
            except sqlite3.IntegrityError:
                raise DomainError("Dự án đã có render đang chờ/chạy.")
            self.event(db, project_id, actor, "render_queued", {"job_id": job_id, "retry_of": retry_of})
        return job_id

    def jobs(self):
        return self.rows("SELECT j.*,p.title,c.name AS channel_name FROM jobs j JOIN projects p ON p.id=j.project_id JOIN channels c ON c.id=p.channel_id ORDER BY j.created_at DESC")

    def claim_job(self):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created_at,rowid LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET state='running',started_at=?,message='Đang chuẩn bị' WHERE id=?", (now(), row["id"]))
            self.event(db, row["project_id"], "render-worker", "render_started", {"job_id": row["id"]})
            return dict(row)

    def recover_jobs(self):
        with self.transaction() as db:
            rows = db.execute("SELECT * FROM jobs WHERE state IN ('running','cancelling')").fetchall()
            for row in rows:
                db.execute("UPDATE jobs SET state='interrupted',finished_at=?,message='Ứng dụng dừng khi tác vụ chưa kết thúc' WHERE id=?", (now(), row["id"]))
                self.event(db, row["project_id"], "system", "render_interrupted", {"job_id": row["id"]})

    def job_progress(self, job_id, progress, message):
        with self.transaction() as db:
            db.execute("UPDATE jobs SET progress=MAX(progress,?),message=? WHERE id=? AND state='running'", (min(99, max(0, progress)), message, job_id))

    def finish_job(self, job_id, state, result=None, error=""):
        if state not in ("succeeded", "failed", "cancelled"):
            raise DomainError("Trạng thái kết thúc không hợp lệ.")
        with self.transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row["state"] not in ("running", "cancelling"):
                raise DomainError("Tác vụ không còn chạy.")
            db.execute("UPDATE jobs SET state=?,progress=?,message=?,error=?,result_json=?,finished_at=? WHERE id=?",
                       (state, 100 if state == "succeeded" else row["progress"], state, error,
                        json.dumps(result or {}, ensure_ascii=False), now(), job_id))
            self.event(db, row["project_id"], "render-worker", "render_"+state, {"job_id": job_id, "error": error})

    def cancel_job(self, job_id, actor):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row["state"] not in ("queued", "running", "cancelling"):
                raise DomainError("Tác vụ không ở trạng thái có thể hủy.")
            target = "cancelled" if row["state"] == "queued" else "cancelling"
            db.execute("UPDATE jobs SET state=?,finished_at=? WHERE id=?", (target, now() if target == "cancelled" else None, job_id))
            self.event(db, row["project_id"], actor, "render_cancel_requested", {"job_id": job_id})

    def export_bundle(self, project_id):
        return {"schema_version": 1, "exported_at": now(), "project": self.project(project_id),
                "assets": self.assets(project_id), "events": self.events(project_id),
                "reviews": self.rows("SELECT * FROM reviews WHERE project_id=?", (project_id,)),
                "metrics": self.rows("SELECT * FROM metrics WHERE project_id=? ORDER BY recorded_at", (project_id,)),
                "jobs": [j for j in self.jobs() if j["project_id"] == project_id]}
