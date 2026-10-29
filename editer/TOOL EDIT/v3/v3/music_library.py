"""Small local catalog for manually reviewing music against channel identities."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


CHANNEL_PROFILES = {
    "HEARTHLUNE": {
        "target_lufs": -16,
        "summary": "Jazz ấm, piano nhẹ, nhạc mùa lễ; ưu tiên track ít trống.",
        "tags": "cozy, cafe jazz, piano, holiday, fireplace",
    },
    "SYLVANREST": {
        "target_lufs": -18,
        "summary": "Harp/flute/Celtic mộc; nhạc Jazz chỉ dùng khi hòa âm và nhịp phù hợp.",
        "tags": "forest, celtic, harp, flute, stream",
    },
    "ASTRALOOM": {
        "target_lufs": -18,
        "summary": "Ambient drone, synth chậm, không có nhịp rõ; Jazz thường không phù hợp.",
        "tags": "space, drone, synth, noise, no beat",
    },
}


def _catalog_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "FlowLoopEditor" / "music_catalog.sqlite3"


class MusicCatalog:
    def __init__(self, path: Path | None = None):
        self.path = path or _catalog_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS track_review (
                    path TEXT PRIMARY KEY,
                    hearthlune INTEGER NOT NULL DEFAULT 0,
                    sylvanrest INTEGER NOT NULL DEFAULT 0,
                    astraloom INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT ''
                )"""
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        try:
            yield db
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _key(path: Path) -> str:
        return os.path.normcase(str(path.resolve()))

    def get_review(self, path: Path) -> dict:
        with self._connect() as db:
            row = db.execute(
                "SELECT hearthlune, sylvanrest, astraloom, notes FROM track_review WHERE path=?",
                (self._key(path),),
            ).fetchone()
        if row is None:
            return {"HEARTHLUNE": 0, "SYLVANREST": 0, "ASTRALOOM": 0, "notes": ""}
        return dict(zip((*CHANNEL_PROFILES, "notes"), row))

    def get_reviews(self, paths: list[Path]) -> dict[str, dict]:
        if not paths:
            return {}
        keys = [self._key(path) for path in paths]
        placeholders = ",".join("?" for _ in keys)
        with self._connect() as db:
            rows = db.execute(
                "SELECT path, hearthlune, sylvanrest, astraloom, notes "
                f"FROM track_review WHERE path IN ({placeholders})",
                keys,
            ).fetchall()
        result = {
            row[0]: dict(zip((*CHANNEL_PROFILES, "notes"), row[1:]))
            for row in rows
        }
        return {
            key: result.get(key, {"HEARTHLUNE": 0, "SYLVANREST": 0, "ASTRALOOM": 0, "notes": ""})
            for key in keys
        }

    def save_review(self, path: Path, scores: dict[str, int], notes: str = "") -> None:
        values = [int(scores.get(channel, 0)) for channel in CHANNEL_PROFILES]
        if any(score < 0 or score > 5 for score in values):
            raise ValueError("Điểm phù hợp phải từ 0 đến 5.")
        with self._connect() as db:
            db.execute(
                """INSERT INTO track_review(path, hearthlune, sylvanrest, astraloom, notes)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(path) DO UPDATE SET
                     hearthlune=excluded.hearthlune,
                     sylvanrest=excluded.sylvanrest,
                     astraloom=excluded.astraloom,
                     notes=excluded.notes""",
                (self._key(path), *values, notes.strip()),
            )

    def score(self, path: Path, channel: str) -> int:
        if channel not in CHANNEL_PROFILES:
            return 0
        return int(self.get_review(path)[channel])

    def approved_tracks(self, paths: list[Path], channel: str, minimum: int = 3) -> list[Path]:
        if channel not in CHANNEL_PROFILES or not paths:
            return []
        column = channel.lower()
        keys = [self._key(path) for path in paths]
        placeholders = ",".join("?" for _ in keys)
        with self._connect() as db:
            rows = db.execute(
                f"SELECT path FROM track_review WHERE {column} >= ? AND path IN ({placeholders})",
                [minimum, *keys],
            ).fetchall()
        approved = {row[0] for row in rows}
        return [path for path, key in zip(paths, keys) if key in approved]


class SharedMusicCatalog:
    """Read the channel playlists maintained by Music Manager's SQLite catalog."""

    def __init__(self):
        workspace = next(
            (parent for parent in Path(__file__).resolve().parents
             if (parent / "CONTENT HUB").is_dir() and (parent / "editer" / "Nhạc jazz").is_dir()),
            Path(__file__).resolve().parents[4],
        )
        self.music_root = workspace / "editer" / "Nhạc jazz"
        configured = os.environ.get("CONTENT_HUB_DATABASE")
        self.path = Path(configured).resolve() if configured else workspace / "CONTENT HUB" / "data" / "content_hub.sqlite3"

    def channel_names(self) -> list[str]:
        if not self.path.is_file():
            return []
        with sqlite3.connect(self.path) as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='channels'").fetchone()
            return [row[0] for row in db.execute("SELECT name FROM channels WHERE archived=0 ORDER BY name COLLATE NOCASE")] if exists else []

    def library_rows(self, channel: str = "") -> list[dict]:
        """Return music metadata from Music Manager for Editor filters and previews."""
        if not self.path.is_file():
            return []
        with sqlite3.connect(self.path, timeout=15) as db:
            db.row_factory = sqlite3.Row
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"music_tracks", "music_files"}.issubset(tables):
                return []
            if channel and not {"music_channel_tracks", "channels"}.issubset(tables):
                return []
            has_tags = "music_track_tags" in tables
            has_memberships = "music_memberships" in tables
            tag_query = lambda category: (
                f"(SELECT group_concat(value, ', ') FROM music_track_tags WHERE track_id=t.id AND category='{category}')"
                if has_tags else "''"
            )
            groups_query = (
                "(SELECT group_concat(name, ', ') FROM music_memberships m WHERE m.track_id=t.id)"
                if has_memberships else "''"
            )
            channel_filter = ""
            parameters: tuple = ()
            if channel:
                channel_filter = " AND EXISTS (SELECT 1 FROM music_channel_tracks ct JOIN channels c ON c.id=ct.channel_id WHERE ct.track_id=t.id AND c.name=? AND c.archived=0)"
                parameters = (channel,)
            query = f"""SELECT t.id,t.title,t.artist,t.status,t.credit,
                (SELECT path FROM music_files f WHERE f.track_id=t.id AND f.present=1 ORDER BY path LIMIT 1) AS path,
                {groups_query} AS groups,
                {tag_query('genre')} AS genre,
                {tag_query('instrument')} AS instrument,
                {tag_query('vocal')} AS vocal,
                {tag_query('mood')} AS mood
                FROM music_tracks t
                WHERE EXISTS(SELECT 1 FROM music_files f WHERE f.track_id=t.id AND f.present=1){channel_filter}
                ORDER BY t.title COLLATE NOCASE,t.artist COLLATE NOCASE"""
            rows = [dict(row) for row in db.execute(query, parameters)]
            result = []
            for row in rows:
                path = Path(row.get("path") or "")
                if path.is_file():
                    row["path"] = path
                    result.append(row)
            return result

    def channel_tracks(self, channel: str) -> list[Path]:
        if not channel or not self.path.is_file():
            return []
        with sqlite3.connect(self.path) as db:
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='music_channel_tracks'"
            ).fetchone()
            if not exists:
                return []
            rows = db.execute("""SELECT (SELECT f.path FROM music_files f
                WHERE f.track_id=ct.track_id AND f.present=1 ORDER BY f.path LIMIT 1)
                FROM music_channel_tracks ct
                JOIN channels c ON c.id=ct.channel_id AND c.archived=0
                WHERE c.name=? AND EXISTS(SELECT 1 FROM music_files f WHERE f.track_id=ct.track_id AND f.present=1)
                ORDER BY ct.track_id""", (channel,)).fetchall()
        return [Path(row[0]) for row in rows if Path(row[0]).is_file()]

    def library_tracks(self) -> list[Path]:
        if not self.path.is_file():
            return []
        with sqlite3.connect(self.path) as db:
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='music_files'"
            ).fetchone()
            if not exists:
                return []
            rows = db.execute("SELECT path FROM music_files WHERE present=1 ORDER BY path").fetchall()
        return [Path(row[0]) for row in rows if Path(row[0]).is_file()]
