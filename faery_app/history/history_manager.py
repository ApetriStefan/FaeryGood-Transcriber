"""
Historical Transcripts Management (CRUD) for Faery Good Transcriber
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from faery_app.constants import HISTORY_PATH


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
        )

    def matches_query(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Performs multi-token search across title, filename, date, model,
        and full spoken transcript content.
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

        # Read transcript text for content search (paragraphs preferred, markdown fallback)
        content_text = ""
        for f_path in [self.paragraphs_file, self.markdown_file]:
            if f_path and os.path.exists(f_path):
                try:
                    with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                        content_text = f.read()
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


class HistoryManager:
    """Manages persistent transcription library and synchronization with disk."""

    def __init__(self, history_path: Path = HISTORY_PATH):
        self.history_path = history_path
        self.records: List[HistoryRecord] = []
        self.load()

    def load(self) -> None:
        self.records.clear()
        if self.history_path.exists():
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    raw_list = json.load(f)
                    if isinstance(raw_list, list):
                        self.records = [HistoryRecord.from_dict(item) for item in raw_list]
            except Exception as err:
                print(f"[Warning] Failed to load history: {err}", file=sys.stderr)

    def save(self) -> None:
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self.records], f, indent=2)
        except Exception as err:
            print(f"[Warning] Failed to save history: {err}", file=sys.stderr)

    def add_or_update(self, record: HistoryRecord) -> None:
        """Inserts a new record or replaces an existing one with identical paths/title."""
        for idx, r in enumerate(self.records):
            if (
                r.id == record.id
                or r.markdown_file == record.markdown_file
                or (r.title == record.title and r.paragraphs_file == record.paragraphs_file)
            ):
                self.records[idx] = record
                self.save()
                return
        self.records.insert(0, record)
        self.save()

    def sync_with_directory(self, output_dir: Path) -> List[HistoryRecord]:
        """Scans output_dir, auto-discovers external or older transcripts and purges missing files."""
        if not output_dir.exists():
            return self.records

        discovered_stems = set()
        for f in output_dir.glob("*_transcript.md"):
            stem = f.name[:-14]  # strip "_transcript.md"
            discovered_stems.add(stem)
        for f in output_dir.glob("*_paragraphs.txt"):
            stem = f.name[:-15]  # strip "_paragraphs.txt"
            discovered_stems.add(stem)

        known_titles = {r.title for r in self.records}
        known_files = {r.markdown_file for r in self.records}

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
                self.records.append(new_rec)

        # Remove records where all associated files no longer exist on disk
        valid_records = []
        for r in self.records:
            has_p = r.paragraphs_file and os.path.exists(r.paragraphs_file)
            has_t = r.timecoded_file and os.path.exists(r.timecoded_file)
            has_m = r.markdown_file and os.path.exists(r.markdown_file)
            if has_p or has_t or has_m:
                valid_records.append(r)
        self.records = valid_records
        self.save()
        return self.records

    def rename_record(self, record_id: str, new_title: str) -> Optional[HistoryRecord]:
        """Renames a transcript and updates associated files on disk."""
        new_title = re.sub(r'[\\/*?:"<>|]', "", new_title).strip()
        if not new_title:
            return None

        for r in self.records:
            if r.id == record_id:
                old_p = Path(r.paragraphs_file) if r.paragraphs_file else None
                old_t = Path(r.timecoded_file) if r.timecoded_file else None
                old_m = Path(r.markdown_file) if r.markdown_file else None

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
                        r.paragraphs_file = str(new_p)
                    if old_t and old_t.exists():
                        old_t.rename(new_t)
                        r.timecoded_file = str(new_t)
                    if old_m and old_m.exists():
                        old_m.rename(new_m)
                        r.markdown_file = str(new_m)

                    r.title = new_title
                    self.save()
                    return r
                except Exception as err:
                    raise IOError(f"Could not rename files: {err}")
        return None

    def delete_record(self, record_id: str) -> bool:
        """Deletes files from disk and removes the record from library."""
        for idx, r in enumerate(self.records):
            if r.id == record_id:
                for path_str in [r.paragraphs_file, r.timecoded_file, r.markdown_file]:
                    if path_str and os.path.exists(path_str):
                        try:
                            os.remove(path_str)
                        except Exception:
                            pass
                self.records.pop(idx)
                self.save()
                return True
        return False
