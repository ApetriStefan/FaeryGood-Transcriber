"""
Speech Recognition Engine for Faery Good Transcriber (faster-whisper)
"""

from __future__ import annotations

from datetime import datetime
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

WhisperModel = None

from faery_app.constants import MIN_DISK_SPACE_MB, DEFAULT_COOKIE_BROWSER
from faery_app.lifecycle.scratch import ScratchLifecycleManager
from faery_app.media.processor import MediaProcessor
from faery_app.media.online_fetcher import OnlineMediaFetcher
from faery_app.models.formatter import TranscriptFormatter
from faery_app.models.metadata import MediaMetadata, TranscriptSegment, OnlineClipInfo
from faery_app.utils.system import check_free_disk_space
from faery_app.utils.macos import prevent_app_nap


class TranscriptionEngine:
    """
    Manages Whisper model loading (cached in memory) and executes transcription
    strictly inside a tempfile.TemporaryDirectory context manager to guarantee zero
    scratch files remain on disk.
    """

    def __init__(self):
        self._cached_model: Optional[WhisperModel] = None
        self._cached_model_name: Optional[str] = None
        self._lock = threading.Lock()

    @staticmethod
    def get_optimal_cpu_threads() -> int:
        """
        Computes optimal CTranslate2 CPU thread count by targeting physical cores.
        Prevents hyperthread cache thrashing and excessive thermal throttling on
        constrained CPUs (e.g., Intel MacBook Pro 10th-gen 28W quad-core).
        Capped to range [2, 8].
        """
        try:
            physical_cores: Optional[int] = None

            # 1. macOS physical core detection via sysctl
            if sys.platform == "darwin":
                try:
                    output = subprocess.check_output(
                        ["sysctl", "-n", "hw.physicalcpu"],
                        text=True,
                        timeout=2,
                    ).strip()
                    if output.isdigit():
                        physical_cores = int(output)
                except Exception:
                    physical_cores = None

            # 2. Windows / Linux physical core detection via psutil (if available)
            if physical_cores is None:
                try:
                    import psutil
                    count = psutil.cpu_count(logical=False)
                    if count is not None and count > 0:
                        physical_cores = count
                except Exception:
                    physical_cores = None

            # 3. Fallback heuristic using logical core count
            if physical_cores is None:
                logical = os.cpu_count() or 4
                if logical > 4:
                    physical_cores = logical // 2
                else:
                    physical_cores = logical

            return min(8, max(2, physical_cores))
        except Exception:
            logical = os.cpu_count() or 4
            return min(4, max(2, logical))

    @staticmethod
    def is_model_cached(model_size_or_path: str) -> bool:
        """Checks if the model weights are already downloaded locally."""
        try:
            from faster_whisper.utils import download_model
            download_model(model_size_or_path, local_files_only=True)
            return True
        except Exception:
            return False

    def get_model(self, model_size_or_path: str, status_cb: Callable[[str], None]) -> WhisperModel:
        """Retrieves or loads the requested faster-whisper model strictly configured for CPU."""
        global WhisperModel
        with self._lock:
            if self._cached_model is not None and self._cached_model_name == model_size_or_path:
                return self._cached_model

            if self.is_model_cached(model_size_or_path):
                status_cb("⚡ Loading speech model into memory...")
            else:
                status_cb(
                    "📥 First-time setup: Downloading speech recognition model (~460 MB)... "
                    "(One-time download. Future runs will be 100% offline!)"
                )

            if WhisperModel is None:
                from faster_whisper import WhisperModel as _WM
                WhisperModel = _WM

            model = WhisperModel(
                model_size_or_path,
                device="cpu",
                compute_type="int8",
                cpu_threads=self.get_optimal_cpu_threads(),
            )
            self._cached_model = model
            self._cached_model_name = model_size_or_path
            return model

    def run_transcription(
        self,
        media_file: Path,
        media_meta: MediaMetadata,
        model_name: str,
        output_dir: Path,
        cancel_event: threading.Event,
        status_cb: Callable[[str], None],
        progress_cb: Callable[[float], None],
        segment_cb: Callable[[TranscriptSegment], None],
        overwrite: bool = False,
    ) -> tuple[str, str, str, List[TranscriptSegment]]:
        """
        Executes the full pipeline:
        1. Validates disk space.
        2. Enters TemporaryDirectory context manager.
        3. Extracts 16kHz mono WAV scratch file.
        4. Transcribes audio with faster-whisper.
        5. Writes output transcripts to output_dir (overwriting or creating numbered copy based on user choice).
        6. Purges TemporaryDirectory upon exit under ALL conditions.
        """
        if not check_free_disk_space(output_dir, min_mb=MIN_DISK_SPACE_MB):
            raise IOError(
                f"Low disk space: The output drive has less than {MIN_DISK_SPACE_MB} MB free. "
                "Please free up disk space before proceeding."
            )

        segments_collected: List[TranscriptSegment] = []

        with ScratchLifecycleManager.safe_scratch_directory(prefix="faery_transcribe_") as temp_dir_path:
            scratch_wav = temp_dir_path / "audio_16k_mono.wav"

            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")

            status_cb("Preparing audio track for transcription...")
            MediaProcessor.extract_16k_mono_wav(media_file, scratch_wav, cancel_event)

            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")

            whisper_model = self.get_model(model_name, status_cb)

            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")

            status_cb("Transcribing audio (this usually takes 1–2 minutes)...")

            with prevent_app_nap():
                segments_gen, info = whisper_model.transcribe(
                    str(scratch_wav),
                    language="en",
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                )

                total_duration = media_meta.duration_seconds if media_meta.duration_seconds > 0 else (info.duration or 1.0)

                for segment in segments_gen:
                    if cancel_event.is_set():
                        raise InterruptedError("Transcription cancelled.")

                    seg_obj = TranscriptSegment(
                        start=segment.start,
                        end=segment.end,
                        text=segment.text.strip(),
                    )
                    segments_collected.append(seg_obj)
                    segment_cb(seg_obj)

                    if total_duration > 0:
                        pct = min(0.99, max(0.01, segment.end / total_duration))
                        progress_cb(pct)
                        status_cb(
                            f"Transcribing: [{seg_obj.formatted_timestamp} / {media_meta.formatted_duration}] "
                            f"({int(pct * 100)}%)..."
                        )

        if cancel_event.is_set():
            raise InterruptedError("Transcription cancelled.")

        # Build clean plain text, timecoded text, raw text, and Markdown representations
        paragraphs_text = TranscriptFormatter.to_paragraphs(segments_collected)
        timecoded_text = TranscriptFormatter.to_timecoded(segments_collected)
        markdown_text = self._build_markdown(media_meta, model_name, paragraphs_text, segments_collected)

        base_name = media_file.stem
        if overwrite:
            clean_txt_path = output_dir / f"{base_name}_paragraphs.txt"
            timecoded_txt_path = output_dir / f"{base_name}_timecoded.txt"
            md_path = output_dir / f"{base_name}_transcript.md"
        else:
            clean_txt_path = self._get_unique_path(output_dir / f"{base_name}_paragraphs.txt")
            timecoded_txt_path = self._get_unique_path(output_dir / f"{base_name}_timecoded.txt")
            md_path = self._get_unique_path(output_dir / f"{base_name}_transcript.md")

        with open(clean_txt_path, "w", encoding="utf-8") as f:
            f.write(paragraphs_text + "\n")

        with open(timecoded_txt_path, "w", encoding="utf-8") as f:
            f.write(timecoded_text + "\n")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_text + "\n")

        return str(clean_txt_path), str(timecoded_txt_path), str(md_path), segments_collected

    def run_online_transcription(
        self,
        url: str,
        model_name: str,
        output_dir: Path,
        cancel_event: threading.Event,
        status_cb: Callable[[str], None],
        progress_cb: Callable[[float], None],
        segment_cb: Callable[[TranscriptSegment], None],
        cookie_browser_label: str = DEFAULT_COOKIE_BROWSER,
        overwrite: Optional[bool] = None,
        overwrite_prompt_cb: Optional[Callable[[str, Path], Optional[bool]]] = None,
        cookie_permission_cb: Optional[Callable[[str], bool]] = None,
    ) -> tuple[str, str, str, List[TranscriptSegment], str, str]:
        """
        Executes the full online link pipeline with 100% scratch file hygiene:
        1. Validates disk space.
        2. Enters TemporaryDirectory context manager.
        3. Downloads temporary audio stream via yt-dlp directly into TemporaryDirectory.
        4. Converts audio to 16kHz mono WAV and immediately purges the downloaded stream.
        5. Transcribes audio with faster-whisper on CPU.
        6. Purges TemporaryDirectory upon exit under ALL conditions (success, error, cancel).
        7. Saves output transcripts named after the video's title.
        """
        if not check_free_disk_space(output_dir, min_mb=MIN_DISK_SPACE_MB):
            raise IOError(
                f"Low disk space: The output drive has less than {MIN_DISK_SPACE_MB} MB free. "
                "Please free up disk space before proceeding."
            )

        segments_collected: List[TranscriptSegment] = []
        clip_info: Optional[OnlineClipInfo] = None
        probed_meta: Optional[MediaMetadata] = None

        with ScratchLifecycleManager.safe_scratch_directory(prefix="faery_transcribe_") as temp_dir_path:
            scratch_wav = temp_dir_path / "audio_16k_mono.wav"

            # 1. Download temporary audio into temp_dir_path
            clip_info = OnlineMediaFetcher.download_audio_to_temp(
                url=url,
                temp_dir=temp_dir_path,
                cancel_event=cancel_event,
                status_cb=status_cb,
                progress_cb=progress_cb,
                cookie_browser_label=cookie_browser_label,
                cookie_permission_cb=cookie_permission_cb,
            )

            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")

            # 2. Convert to 16kHz mono WAV inside temp_dir_path
            status_cb(f"🎵 Preparing audio track for '{clip_info.sanitized_title}'...")
            MediaProcessor.extract_16k_mono_wav(clip_info.temp_media_path, scratch_wav, cancel_event)

            # Immediately purge the raw downloaded audio stream
            try:
                if clip_info.temp_media_path.exists():
                    clip_info.temp_media_path.unlink()
            except Exception:
                pass

            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")

            # Probe the converted WAV for exact duration
            wav_meta = MediaProcessor.probe_file(scratch_wav)
            eff_duration = wav_meta.duration_seconds if wav_meta.duration_seconds > 0 else clip_info.duration_seconds
            probed_meta = MediaMetadata(
                path=Path(f"{clip_info.sanitized_title}.mp4"),
                file_size_bytes=wav_meta.file_size_bytes,
                duration_seconds=eff_duration,
                has_audio=True,
                format_name=clip_info.platform,
            )

            # 3. Load Whisper model & transcribe
            whisper_model = self.get_model(model_name, status_cb)

            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")

            status_cb(f"🎙️ Transcribing '{clip_info.sanitized_title}'...")

            with prevent_app_nap():
                segments_gen, info = whisper_model.transcribe(
                    str(scratch_wav),
                    language="en",
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                )

                total_duration = probed_meta.duration_seconds if probed_meta.duration_seconds > 0 else (info.duration or 1.0)

                for segment in segments_gen:
                    if cancel_event.is_set():
                        raise InterruptedError("Transcription cancelled.")

                    seg_obj = TranscriptSegment(
                        start=segment.start,
                        end=segment.end,
                        text=segment.text.strip(),
                    )
                    segments_collected.append(seg_obj)
                    segment_cb(seg_obj)

                    if total_duration > 0:
                        pct = min(0.99, max(0.01, segment.end / total_duration))
                        progress_cb(pct)
                        status_cb(
                            f"Transcribing: [{seg_obj.formatted_timestamp} / {probed_meta.formatted_duration}] "
                            f"({int(pct * 100)}%)..."
                        )

        if cancel_event.is_set() or clip_info is None or probed_meta is None:
            raise InterruptedError("Transcription cancelled.")

        base_name = clip_info.sanitized_title
        existing_p = output_dir / f"{base_name}_paragraphs.txt"
        existing_m = output_dir / f"{base_name}_transcript.md"

        if overwrite is None:
            if (existing_p.exists() or existing_m.exists()) and overwrite_prompt_cb is not None:
                ans = overwrite_prompt_cb(base_name, existing_p if existing_p.exists() else existing_m)
                if ans is None:
                    raise InterruptedError("Transcription cancelled.")
                overwrite = ans
            else:
                overwrite = False

        paragraphs_text = TranscriptFormatter.to_paragraphs(segments_collected)
        timecoded_text = TranscriptFormatter.to_timecoded(segments_collected)
        markdown_text = self._build_markdown(
            probed_meta,
            model_name,
            paragraphs_text,
            segments_collected,
            source_url=clip_info.url,
            platform=clip_info.platform,
        )

        if overwrite:
            clean_txt_path = output_dir / f"{base_name}_paragraphs.txt"
            timecoded_txt_path = output_dir / f"{base_name}_timecoded.txt"
            md_path = output_dir / f"{base_name}_transcript.md"
        else:
            clean_txt_path = self._get_unique_path(output_dir / f"{base_name}_paragraphs.txt")
            timecoded_txt_path = self._get_unique_path(output_dir / f"{base_name}_timecoded.txt")
            md_path = self._get_unique_path(output_dir / f"{base_name}_transcript.md")

        with open(clean_txt_path, "w", encoding="utf-8") as f:
            f.write(paragraphs_text + "\n")

        with open(timecoded_txt_path, "w", encoding="utf-8") as f:
            f.write(timecoded_text + "\n")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_text + "\n")

        return (
            str(clean_txt_path),
            str(timecoded_txt_path),
            str(md_path),
            segments_collected,
            base_name,
            probed_meta.formatted_duration,
        )

    @staticmethod
    def _get_unique_path(target_path: Path) -> Path:
        """Appends a numeric index if target_path already exists."""
        if not target_path.exists():
            return target_path
        parent = target_path.parent
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1
        while True:
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _build_markdown(
        meta: MediaMetadata,
        model_name: str,
        paragraphs_text: str,
        segments: List[TranscriptSegment],
        source_url: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> str:
        """Constructs a clean, production-grade Markdown document with segment timestamps."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title_str = meta.path.stem if source_url else meta.path.name
        lines = [
            f"# Transcription: {title_str}",
            "",
            "### Metadata",
        ]
        if source_url:
            lines.append(f"- **Source Link:** {source_url} ({platform or 'Online Clip'})")
        else:
            lines.append(f"- **Source File:** `{meta.path.name}`")
            lines.append(f"- **File Size:** {meta.formatted_size}")
        lines.extend([
            f"- **Audio Duration:** {meta.formatted_duration}",
            f"- **Engine Model:** `{model_name}` (CPU int8)",
            f"- **Generated On:** {now_str}",
            "",
            "---",
            "",
            "## Formatted Transcript (Clean Paragraphs)",
            paragraphs_text if paragraphs_text else "*(No speech detected)*",
            "",
            "---",
            "",
            "## Timestamped Transcript",
        ])
        if segments:
            for seg in segments:
                lines.append(f"- **[{seg.formatted_timestamp}]** {seg.text}")
        else:
            lines.append("*(No timestamped segments)*")

        lines.append("")
        return "\n".join(lines)
