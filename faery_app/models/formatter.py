"""
Transcript Formatting Utilities for Faery Good Transcriber
"""

from __future__ import annotations

from typing import List, Optional, Union
from faery_app.models.metadata import TranscriptSegment, format_seconds_mm_ss


def format_eta(seconds: Union[int, float]) -> str:
    """
    Formats estimated remaining seconds into human-friendly countdown copy:
    - < 15: "a few seconds"
    - < 60: "{s}s"
    - < 3600: "{m} min" (if s == 0) or "{m}m {s}s"
    - >= 3600: "{h}h {m}m"
    """
    sec = float(seconds)
    if sec < 15:
        return "a few seconds"
    elif sec < 60:
        return f"{int(sec)}s"
    elif sec < 3600:
        m = int(sec) // 60
        s = int(sec) % 60
        if s == 0:
            return f"{m} min"
        else:
            return f"{m}m {s}s"
    else:
        h = int(sec) // 3600
        m = (int(sec) % 3600) // 60
        return f"{h}h {m}m"


def format_timestamp(seconds: float) -> str:
    """Formats timestamp in seconds as MM:SS (or HH:MM:SS if >= 1 hour)."""
    return format_seconds_mm_ss(seconds)


class TranscriptFormatter:
    """Utilities to format raw Whisper segments into clean paragraphs, timecodes, or raw text."""

    @staticmethod
    def _heal_paragraph(para_text: str) -> str:
        """
        Applies sentence and paragraph boundary healing to a closed paragraph:
        1. Cleans leading and trailing whitespace.
        2. Capitalizes the first character if it starts with a lowercase letter.
        3. Cleans trailing whitespace.
        4. If the paragraph ends with a comma (,), colon (:), or semicolon (;), replaces it with a period (.).
        5. If the paragraph ends with an alphanumeric character without terminal punctuation
           (not ending with ., !, ?, .", !", ?", ”, …), appends a period (.).
        """
        text = para_text.strip()
        if not text:
            return ""

        # Capitalize the first character of each new paragraph if lowercase
        if text[0].islower():
            text = text[0].upper() + text[1:]

        # Clean trailing whitespace
        text = text.rstrip()

        # Boundary terminal punctuation healing
        terminal_punctuations = (".", "!", "?", '."', '!"', '?"', "”", "…")
        if text.endswith((",", ":", ";")):
            text = text[:-1].rstrip() + "."
        elif not text.endswith(terminal_punctuations):
            if text[-1].isalnum():
                text = text + "."

        return text

    @staticmethod
    def to_paragraphs(
        segments: List[TranscriptSegment],
        pause_threshold_sec: float = 1.0,
        sentence_pause_threshold_sec: float = 0.6,
        max_sentences_per_para: int = 4,
        max_words_per_para: int = 70,
    ) -> str:
        """
        Organizes segments into clean, publication-ready paragraphs using:
        1. Acoustic silence between segments (pauses >= pause_threshold_sec).
        2. Sentence-ending punctuation followed by pause (>= sentence_pause_threshold_sec).
        3. Pacing limits (max sentences or words per paragraph) to prevent unbroken walls of text.
        4. Sentence and paragraph boundary healing (punctuation and capitalization repair).
        """
        if not segments:
            return ""

        paragraphs: List[str] = []
        current_para_parts: List[str] = []
        sentence_count = 0
        word_count = 0
        prev_end: Optional[float] = None

        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue

            gap = (seg.start - prev_end) if prev_end is not None else 0.0

            prev_ended_sentence = (
                current_para_parts
                and current_para_parts[-1].rstrip().endswith((".", "!", "?", '."', '!"', '?"', "”", "…"))
            )
            is_long_pause = prev_end is not None and gap >= pause_threshold_sec
            is_sentence_pause = prev_ended_sentence and gap >= sentence_pause_threshold_sec
            is_para_limit = (
                prev_ended_sentence
                and (sentence_count >= max_sentences_per_para or word_count >= max_words_per_para)
            )

            if (is_long_pause or is_sentence_pause or is_para_limit) and current_para_parts:
                healed = TranscriptFormatter._heal_paragraph(" ".join(current_para_parts))
                if healed:
                    paragraphs.append(healed)
                current_para_parts = []
                sentence_count = 0
                word_count = 0

            current_para_parts.append(text)
            prev_end = seg.end
            word_count += len(text.split())
            if text.endswith((".", "!", "?", '."', '!"', '?"', "”", "…")):
                sentence_count += 1

        if current_para_parts:
            healed = TranscriptFormatter._heal_paragraph(" ".join(current_para_parts))
            if healed:
                paragraphs.append(healed)

        return "\n\n".join(paragraphs)

    @staticmethod
    def to_timecoded(segments: List[TranscriptSegment]) -> str:
        """Formats each segment with its timestamp [MM:SS] on separate lines."""
        if not segments:
            return ""
        return "\n".join(f"[{seg.formatted_timestamp}] {seg.text}" for seg in segments)

    @staticmethod
    def to_raw(segments: List[TranscriptSegment]) -> str:
        """Formats segments into a single continuous stream of text."""
        if not segments:
            return ""
        return " ".join(seg.text.strip() for seg in segments if seg.text.strip())
