"""
Historical Transcripts Management (CRUD) and Full-Text Search for Faery Good Transcriber
Powered by embedded SQLite and SQLite FTS5.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from typing import Iterator, List, Optional, Tuple, Union

from faery_app.constants import DB_FILE_NAME, DB_PATH, HISTORY_FILE_NAME, HISTORY_PATH


@dataclass
class HistoryRecord:
    """Represents an archived transcription session."""
    id: str
    title: str
    source_filename: str
    duration_str: str
    created_at: str
    model: str
    paragraphs_file: str
    timecoded_file: str
    markdown_file: str
    word_count: int = 0
    is_favorite: bool = False
    tags: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "source_filename": self.source_filename,
            "duration_str": self.duration_str,
            "created_at": self.created_at,
            "model": self.model,
            "paragraphs_file": self.paragraphs_file,
            "timecoded_file": self.timecoded_file,
            "markdown_file": self.markdown_file,
            "word_count": self.word_count,
            "is_favorite": bool(self.is_favorite),
            "tags": self.tags,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> HistoryRecord:
        return cls(
            id=data.get("id", ""),
            title=data.get("title", "Untitled"),
            source_filename=data.get("source_filename", ""),
            duration_str=data.get("duration_str", "--:--"),
            created_at=data.get("created_at", ""),
            model=data.get("model", ""),
            paragraphs_file=data.get("paragraphs_file", ""),
            timecoded_file=data.get("timecoded_file", ""),
            markdown_file=data.get("markdown_file", ""),
            word_count=data.get("word_count", 0),
            is_favorite=bool(data.get("is_favorite", False)),
            tags=data.get("tags", ""),
            updated_at=data.get("updated_at", ""),
        )

    def matches_query(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Performs multi-token search across title, filename, date, model,
        tags, and full spoken transcript content.
        Returns (is_match, optional_content_snippet).
        """
        clean_q = (query or "").strip()
        if not clean_q:
            return True, None

        terms = [t.lower() for t in clean_q.split() if t]
        if not terms:
            return True, None

        title_raw = self.title.lower()
        title_norm = self.title.lower().replace("_", " ").replace("-", " ")
        source_raw = self.source_filename.lower()
        source_norm = self.source_filename.lower().replace("_", " ").replace("-", " ")
        date_str = self.created_at.lower()
        model_str = self.model.lower()
        tags_str = (self.tags or "").lower()

        # Read transcript text for content search (paragraphs preferred, markdown fallback)
        content_text = ""
        for f_path in [self.paragraphs_file, self.markdown_file]:
            if f_path and os.path.exists(f_path):
                try:
                    with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                        content_text = f.read()
                    if content_text.strip():
                        break
                except Exception:
                    pass

        content_lower = content_text.lower()
        snippet = None

        for term in terms:
            in_meta = (
                term in title_raw
                or term in title_norm
                or term in source_raw
                or term in source_norm
                or term in date_str
                or term in model_str
                or term in tags_str
            )
            in_content = term in content_lower
            if not (in_meta or in_content):
                return False, None

            # Extract a contextual snippet if matched in transcript body
            if in_content and not in_meta and snippet is None:
                pos = content_lower.find(term)
                if pos != -1:
                    start = max(0, pos - 25)
                    end = min(len(content_text), pos + len(term) + 35)
                    snip = content_text[start:end].replace("\n", " ").strip()
                    snippet = f"...{snip}..."

        return True, snippet


class SearchResult(HistoryRecord):
    """
    Encapsulates a search hit, providing access to HistoryRecord attributes,
    the search snippet, and supporting 2-tuple unpacking: `record, snippet = result`.
    """

    def __init__(self, record: HistoryRecord, snippet: Optional[str] = None):
        underlying = record.record if isinstance(record, SearchResult) else record

        super().__init__(
            id=underlying.id,
            title=underlying.title,
            source_filename=underlying.source_filename,
            duration_str=underlying.duration_str,
            created_at=underlying.created_at,
            model=underlying.model,
            paragraphs_file=underlying.paragraphs_file,
            timecoded_file=underlying.timecoded_file,
            markdown_file=underlying.markdown_file,
            word_count=underlying.word_count,
            is_favorite=underlying.is_favorite,
            tags=underlying.tags,
            updated_at=underlying.updated_at,
        )
        self.record: HistoryRecord = underlying
        self.snippet: Optional[str] = snippet

    def __iter__(self):
        yield self.record
        yield self.snippet

    def __getitem__(self, index: int):
        if index == 0:
            return self.record
        elif index == 1:
            return self.snippet
        raise IndexError(f"SearchResult index out of range (0=record, 1=snippet): {index}")

    def __len__(self) -> int:
        return 2

    def __repr__(self) -> str:
        return f"SearchResult(id={self.id!r}, title={self.title!r}, snippet={self.snippet!r})"


class HistoryManager:
    """Manages persistent transcription library using embedded SQLite and FTS5 full-text search."""

    def __init__(
        self,
        history_path: Optional[Path] = None,
        db_path: Optional[Path] = None,
    ):
        # Resolve history_path and db_path
        if history_path is None and db_path is None:
            self.history_path = HISTORY_PATH
            self.db_path = DB_PATH
        elif db_path is not None and history_path is None:
            self.db_path = Path(db_path)
            self.history_path = self.db_path.with_suffix(".json")
        elif history_path is not None and db_path is None:
            h_p = Path(history_path)
            if h_p.suffix.lower() in (".db", ".sqlite", ".sqlite3"):
                self.db_path = h_p
                self.history_path = h_p.with_suffix(".json")
            else:
                self.history_path = h_p
                if h_p == HISTORY_PATH or h_p.name == HISTORY_FILE_NAME:
                    self.db_path = h_p.parent / DB_FILE_NAME
                else:
                    self.db_path = h_p.parent / f"{h_p.stem}.db"
        else:
            self.history_path = Path(history_path)
            self.db_path = Path(db_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.records: List[HistoryRecord] = []
        self._init_db()
        self._migrate_legacy_json()
        self.load()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    @contextmanager
    def _connection(self, write_wal: bool = False) -> Iterator[sqlite3.Connection]:
        """Context manager that commits/rolls back and guarantees closing the SQLite file handle."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            if write_wal:
                conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=10000;")
            conn.execute("PRAGMA foreign_keys=ON;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initializes tables, FTS5 virtual table, and triggers in SQLite."""
        with self._connection(write_wal=True) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_filename TEXT DEFAULT '',
                    duration_str TEXT DEFAULT '--:--',
                    created_at TEXT DEFAULT '',
                    model TEXT DEFAULT '',
                    paragraphs_file TEXT DEFAULT '',
                    timecoded_file TEXT DEFAULT '',
                    markdown_file TEXT DEFAULT '',
                    word_count INTEGER DEFAULT 0,
                    is_favorite INTEGER DEFAULT 0,
                    tags TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                );
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS transcriptions_fts USING fts5(
                    id UNINDEXED,
                    title,
                    content,
                    tokenize = 'unicode61'
                );
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_transcriptions_delete 
                AFTER DELETE ON transcriptions
                BEGIN
                    DELETE FROM transcriptions_fts WHERE id = old.id;
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_transcriptions_update_title 
                AFTER UPDATE OF title ON transcriptions
                BEGIN
                    UPDATE transcriptions_fts SET title = new.title WHERE id = old.id;
                END;
                """
            )

    def _migrate_legacy_json(self) -> None:
        """Seamlessly migrates legacy JSON history into SQLite and renames file to .bak."""
        target_json = self.history_path
        if not target_json or not target_json.exists():
            if target_json != HISTORY_PATH and HISTORY_PATH.exists() and self.db_path == DB_PATH:
                target_json = HISTORY_PATH
            else:
                return

        if not target_json.is_file() or target_json.suffix.lower() != ".json":
            return

        try:
            with open(target_json, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
                if isinstance(raw_list, list):
                    with self._connection() as conn:
                        for item in raw_list:
                            if isinstance(item, dict):
                                rec = HistoryRecord.from_dict(item)
                                self._upsert_record_in_conn(conn, rec)
            bak_path = target_json.with_name(target_json.name + ".bak")
            if bak_path.exists():
                bak_path.unlink()
            target_json.rename(bak_path)
        except Exception as err:
            print(f"[Warning] Failed to migrate legacy history JSON: {err}", file=sys.stderr)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> HistoryRecord:
        return HistoryRecord(
            id=row["id"],
            title=row["title"],
            source_filename=row["source_filename"] or "",
            duration_str=row["duration_str"] or "--:--",
            created_at=row["created_at"] or "",
            model=row["model"] or "",
            paragraphs_file=row["paragraphs_file"] or "",
            timecoded_file=row["timecoded_file"] or "",
            markdown_file=row["markdown_file"] or "",
            word_count=int(row["word_count"] or 0),
            is_favorite=bool(row["is_favorite"]),
            tags=row["tags"] or "",
            updated_at=row["updated_at"] or "",
        )

    def _read_content_for_record(self, record: HistoryRecord) -> str:
        content = ""
        for f_path in [record.paragraphs_file, record.markdown_file]:
            if f_path and os.path.exists(f_path):
                try:
                    with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if content.strip():
                        break
                except Exception:
                    pass
        return content

    def _upsert_record_in_conn(
        self,
        conn: sqlite3.Connection,
        record: HistoryRecord,
        content: Optional[str] = None,
    ) -> None:
        """Upserts a record and its FTS5 entry inside an existing SQLite connection/transaction."""
        now_str = record.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            INSERT OR REPLACE INTO transcriptions (
                id, title, source_filename, duration_str, created_at, model,
                paragraphs_file, timecoded_file, markdown_file, word_count,
                is_favorite, tags, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                record.id,
                record.title,
                record.source_filename,
                record.duration_str,
                record.created_at,
                record.model,
                record.paragraphs_file,
                record.timecoded_file,
                record.markdown_file,
                record.word_count,
                1 if record.is_favorite else 0,
                record.tags or "",
                now_str,
            ),
        )
        body_text = content if content is not None else self._read_content_for_record(record)
        conn.execute("DELETE FROM transcriptions_fts WHERE id = ?;", (record.id,))
        conn.execute(
            "INSERT INTO transcriptions_fts (id, title, content) VALUES (?, ?, ?);",
            (record.id, record.title, body_text),
        )

    def _insert_record(self, record: HistoryRecord) -> None:
        with self._connection() as conn:
            self._upsert_record_in_conn(conn, record)

    def load(self) -> None:
        """Loads all records from SQLite into memory ordered by favorite and date."""
        self.records.clear()
        try:
            with self._connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM transcriptions 
                    ORDER BY is_favorite DESC, created_at DESC, id DESC;
                    """
                ).fetchall()
                self.records = [self._row_to_record(r) for r in rows]
        except Exception as err:
            print(f"[Warning] Failed to load history from SQLite: {err}", file=sys.stderr)

    def save(self) -> None:
        """Synchronizes all in-memory records into SQLite in a single transaction."""
        try:
            with self._connection() as conn:
                for r in self.records:
                    self._upsert_record_in_conn(conn, r)
        except Exception as err:
            print(f"[Warning] Failed to save history to SQLite: {err}", file=sys.stderr)

    def update_record_content(
        self,
        record_id: str,
        new_content: str,
        update_fts: bool = True,
    ) -> Optional[HistoryRecord]:
        """Updates word_count and FTS5 content for a single edited record in O(1) time."""
        wcount = len(new_content.split())
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connection() as conn:
            conn.execute(
                "UPDATE transcriptions SET word_count = ?, updated_at = ? WHERE id = ?;",
                (wcount, now_str, record_id),
            )
            if update_fts:
                conn.execute(
                    "UPDATE transcriptions_fts SET content = ? WHERE id = ?;",
                    (new_content, record_id),
                )
        for r in self.records:
            if r.id == record_id:
                r.word_count = wcount
                r.updated_at = now_str
                return r
        return None

    def add_or_update(self, record: HistoryRecord) -> None:
        """Inserts a new record or updates an existing record with matching ID, title, or paths."""
        existing_id = None
        for r in self.records:
            if (
                r.id == record.id
                or (record.markdown_file and r.markdown_file == record.markdown_file)
                or (record.paragraphs_file and r.title == record.title and r.paragraphs_file == record.paragraphs_file)
            ):
                existing_id = r.id
                break

        with self._connection() as conn:
            if existing_id and existing_id != record.id:
                conn.execute("DELETE FROM transcriptions WHERE id = ?;", (existing_id,))
                conn.execute("DELETE FROM transcriptions_fts WHERE id = ?;", (existing_id,))
            self._upsert_record_in_conn(conn, record)

        self.load()

    def get_all(self) -> List[HistoryRecord]:
        """Returns all history records ordered by favorites first, then newest creation date."""
        self.load()
        return list(self.records)

    def get_by_id(self, record_id: str) -> Optional[HistoryRecord]:
        """Finds a single history record by ID."""
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM transcriptions WHERE id = ?;", (record_id,)).fetchone()
            if row:
                return self._row_to_record(row)
        return None

    def toggle_favorite(self, record_id: str) -> bool:
        """Toggles the favorite flag for a record and returns the new state."""
        with self._connection() as conn:
            row = conn.execute("SELECT is_favorite FROM transcriptions WHERE id = ?;", (record_id,)).fetchone()
            if not row:
                return False
            current_fav = bool(row["is_favorite"])
            new_fav = not current_fav
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE transcriptions SET is_favorite = ?, updated_at = ? WHERE id = ?;",
                (1 if new_fav else 0, now_str, record_id),
            )

        for r in self.records:
            if r.id == record_id:
                r.is_favorite = new_fav
                r.updated_at = now_str
                break

        # Re-sort records with updated favorite status
        self.records.sort(key=lambda r: (1 if r.is_favorite else 0, r.created_at, r.id), reverse=True)
        return new_fav

    def delete(self, record_id: str, delete_files: bool = True) -> bool:
        """Deletes a transcript record from the database and optionally purges files on disk."""
        rec = self.get_by_id(record_id)
        if not rec:
            return False

        if delete_files:
            for path_str in [rec.paragraphs_file, rec.timecoded_file, rec.markdown_file]:
                if path_str and os.path.exists(path_str):
                    try:
                        os.remove(path_str)
                    except Exception:
                        pass

        with self._connection() as conn:
            conn.execute("DELETE FROM transcriptions WHERE id = ?;", (record_id,))
            conn.execute("DELETE FROM transcriptions_fts WHERE id = ?;", (record_id,))

        self.records = [r for r in self.records if r.id != record_id]
        return True

    def delete_record(self, record_id: str) -> bool:
        """Backwards-compatible alias for delete(record_id, delete_files=True)."""
        return self.delete(record_id, delete_files=True)

    def rename_record(self, record_id: str, new_title: str) -> Optional[HistoryRecord]:
        """Renames a transcript, renames associated files on disk, and updates SQLite and FTS5."""
        new_title = re.sub(r'[\\/*?:"<>|]', "", new_title).strip()
        if not new_title:
            return None

        rec = self.get_by_id(record_id)
        if not rec:
            return None

        old_p = Path(rec.paragraphs_file) if rec.paragraphs_file else None
        old_t = Path(rec.timecoded_file) if rec.timecoded_file else None
        old_m = Path(rec.markdown_file) if rec.markdown_file else None

        parent_dir = None
        for p in [old_p, old_t, old_m]:
            if p and p.parent.exists():
                parent_dir = p.parent
                break
        if not parent_dir:
            return None

        new_p = parent_dir / f"{new_title}_paragraphs.txt"
        new_t = parent_dir / f"{new_title}_timecoded.txt"
        new_m = parent_dir / f"{new_title}_transcript.md"

        try:
            if old_p and old_p.exists():
                old_p.rename(new_p)
                rec.paragraphs_file = str(new_p)
            if old_t and old_t.exists():
                old_t.rename(new_t)
                rec.timecoded_file = str(new_t)
            if old_m and old_m.exists():
                old_m.rename(new_m)
                rec.markdown_file = str(new_m)

            rec.title = new_title
            rec.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with self._connection() as conn:
                conn.execute(
                    """
                    UPDATE transcriptions
                    SET title = ?, paragraphs_file = ?, timecoded_file = ?, markdown_file = ?, updated_at = ?
                    WHERE id = ?;
                    """,
                    (
                        rec.title,
                        rec.paragraphs_file,
                        rec.timecoded_file,
                        rec.markdown_file,
                        rec.updated_at,
                        rec.id,
                    ),
                )
                content = self._read_content_for_record(rec)
                conn.execute("DELETE FROM transcriptions_fts WHERE id = ?;", (rec.id,))
                conn.execute(
                    "INSERT INTO transcriptions_fts (id, title, content) VALUES (?, ?, ?);",
                    (rec.id, rec.title, content),
                )

            for idx, r in enumerate(self.records):
                if r.id == record_id:
                    self.records[idx] = rec
                    break
            return rec
        except Exception as err:
            raise IOError(f"Could not rename files: {err}")

    def sync_with_directory(self, output_dir: Path) -> List[HistoryRecord]:
        """Scans output_dir, auto-discovers external or older transcripts, and purges missing files."""
        if not output_dir or not output_dir.exists():
            return self.records

        discovered_stems = set()
        for f in output_dir.glob("*_transcript.md"):
            discovered_stems.add(f.name[:-14])
        for f in output_dir.glob("*_paragraphs.txt"):
            discovered_stems.add(f.name[:-15])

        known_titles = {r.title for r in self.records}
        known_files = {r.markdown_file for r in self.records}

        new_records: List[HistoryRecord] = []
        for stem in discovered_stems:
            para_f = output_dir / f"{stem}_paragraphs.txt"
            time_f = output_dir / f"{stem}_timecoded.txt"
            md_f = output_dir / f"{stem}_transcript.md"

            if str(md_f) not in known_files and stem not in known_titles:
                wcount = 0
                if para_f.exists():
                    try:
                        wcount = len(para_f.read_text(encoding="utf-8", errors="ignore").split())
                    except Exception:
                        pass
                mtime_str = datetime.fromtimestamp(
                    (md_f if md_f.exists() else para_f).stat().st_mtime
                ).strftime("%Y-%m-%d %H:%M")

                new_rec = HistoryRecord(
                    id=f"{stem}_{int(time.time())}",
                    title=stem,
                    source_filename=f"{stem}.mp4",
                    duration_str="--:--",
                    created_at=mtime_str,
                    model="Whisper",
                    paragraphs_file=str(para_f) if para_f.exists() else "",
                    timecoded_file=str(time_f) if time_f.exists() else "",
                    markdown_file=str(md_f) if md_f.exists() else "",
                    word_count=wcount,
                )
                new_records.append(new_rec)

        # Remove records where all associated files no longer exist on disk
        to_delete: List[str] = []
        for r in self.records:
            has_p = bool(r.paragraphs_file and os.path.exists(r.paragraphs_file))
            has_t = bool(r.timecoded_file and os.path.exists(r.timecoded_file))
            has_m = bool(r.markdown_file and os.path.exists(r.markdown_file))
            if not (has_p or has_t or has_m):
                to_delete.append(r.id)

        if not new_records and not to_delete:
            return self.records

        with self._connection() as conn:
            for rec in new_records:
                self._upsert_record_in_conn(conn, rec)
            for r_id in to_delete:
                conn.execute("DELETE FROM transcriptions WHERE id = ?;", (r_id,))
                conn.execute("DELETE FROM transcriptions_fts WHERE id = ?;", (r_id,))

        self.load()
        return self.records

    def resync_with_disk(self, output_dir: Path) -> List[HistoryRecord]:
        """Backwards-compatible alias for sync_with_directory."""
        return self.sync_with_directory(output_dir)

    def search_with_snippets(self, query: str) -> List[SearchResult]:
        """
        Performs full-text search with FTS5, returning SearchResult objects supporting
        both HistoryRecord attribute access and 2-tuple unpacking (record, snippet).
        """
        clean_q = (query or "").strip()
        if not clean_q:
            return [SearchResult(record=r, snippet=None) for r in self.records]

        tokens = re.findall(r"[\w]+", clean_q)
        if not tokens:
            return [SearchResult(record=r, snippet=None) for r in self.records]

        fts_q = " ".join(f'"{t}"*' for t in tokens)

        try:
            with self._connection() as conn:
                query_sql = """
                    SELECT 
                        t.*, 
                        fts.snip AS fts_snippet,
                        fts.rank AS fts_rank
                    FROM transcriptions t
                    LEFT JOIN (
                        SELECT 
                            id, 
                            snippet(transcriptions_fts, 2, '', '', '...', 15) AS snip, 
                            rank
                        FROM transcriptions_fts
                        WHERE transcriptions_fts MATCH ?
                    ) fts ON t.id = fts.id
                    WHERE fts.id IS NOT NULL
                       OR t.title LIKE ?
                       OR t.source_filename LIKE ?
                       OR t.model LIKE ?
                       OR t.created_at LIKE ?
                       OR t.tags LIKE ?
                    ORDER BY t.is_favorite DESC, (fts.rank IS NOT NULL) DESC, fts.rank ASC, t.created_at DESC;
                """
                like_param = f"%{tokens[0]}%"
                rows = conn.execute(
                    query_sql,
                    (fts_q, like_param, like_param, like_param, like_param, like_param),
                ).fetchall()

                results: List[SearchResult] = []
                for row in rows:
                    rec = self._row_to_record(row)
                    raw_snip = row["fts_snippet"] if "fts_snippet" in row.keys() else None
                    snippet = None
                    if raw_snip:
                        cleaned = raw_snip.replace("\n", " ").strip()
                        if cleaned:
                            if not cleaned.startswith("..."):
                                cleaned = "..." + cleaned
                            if not cleaned.endswith("..."):
                                cleaned = cleaned + "..."
                            snippet = cleaned

                    results.append(SearchResult(record=rec, snippet=snippet))
                return results
        except Exception:
            # Fallback to in-memory matches_query if FTS query syntax error occurs
            fallback_results: List[SearchResult] = []
            for r in self.records:
                matched, snip = r.matches_query(clean_q)
                if matched:
                    fallback_results.append(SearchResult(record=r, snippet=snip))
            return fallback_results

    def search(self, query: str) -> List[SearchResult]:
        """Searches transcription history, returning matching SearchResult objects."""
        return self.search_with_snippets(query)
