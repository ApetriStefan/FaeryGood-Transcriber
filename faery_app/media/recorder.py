"""
Microphone Voice Recording Subsystem for Faery Good Transcriber
"""

from __future__ import annotations

from datetime import datetime
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Optional, Tuple

from faery_app.constants import MIN_DISK_SPACE_MB
from faery_app.lifecycle.scratch import ScratchLifecycleManager
from faery_app.models.metadata import MediaMetadata
from faery_app.utils.system import check_free_disk_space


class MicrophoneRecorder:
    """
    Captures live 16kHz 16-bit mono PCM audio from the system's default input microphone
    directly into a ScratchLifecycleManager-tracked temporary WAV file.
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1
    DTYPE = "int16"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._is_recording: bool = False
        self._start_time: float = 0.0
        self._stream = None
        self._wav_file: Optional[wave.Wave_write] = None
        self._temp_dir: Optional[Path] = None
        self._output_path: Optional[Path] = None
        self._frames_written: int = 0

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def output_path(self) -> Optional[Path]:
        return self._output_path

    @staticmethod
    def is_available() -> bool:
        """Checks if sounddevice is installed and an audio input device is available."""
        try:
            import sounddevice as sd
            dev = sd.query_devices(kind="input")
            return dev is not None
        except Exception:
            return False

    def _audio_callback(self, indata, frames: int, time_info, status) -> None:
        """PortAudio stream callback invoked from the audio hardware thread."""
        with self._lock:
            if self._is_recording and self._wav_file is not None:
                try:
                    self._wav_file.writeframes(bytes(indata))
                    self._frames_written += int(frames)
                except Exception:
                    pass

    def start_recording(self) -> Path:
        """Starts capturing microphone audio to a temporary 16kHz mono WAV file."""
        self.cleanup()

        if not check_free_disk_space(Path(tempfile.gettempdir()), min_mb=MIN_DISK_SPACE_MB):
            raise IOError(
                f"Low disk space: Less than {MIN_DISK_SPACE_MB} MB free in temporary storage. "
                "Please free up disk space before recording."
            )

        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "Microphone recording library (sounddevice) is not installed."
            ) from exc

        temp_dir = Path(tempfile.mkdtemp(prefix="faery_mic_"))
        ScratchLifecycleManager.register_dir(temp_dir)
        self._temp_dir = temp_dir

        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        wav_path = temp_dir / f"Voice_Recording_{timestamp_str}.wav"
        self._output_path = wav_path
        self._frames_written = 0

        try:
            wf = wave.open(str(wav_path), "wb")
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)  # 16-bit PCM = 2 bytes
            wf.setframerate(self.SAMPLE_RATE)
            self._wav_file = wf

            stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                callback=self._audio_callback,
            )
            self._stream = stream
            self._is_recording = True
            self._start_time = time.time()
            stream.start()
            return wav_path
        except Exception as err:
            self.cleanup()
            raise RuntimeError(
                f"Could not start microphone recording: {err}\n\n"
                "Please check that a microphone is connected and microphone permissions are enabled."
            ) from err

    def stop_recording(self) -> Tuple[Path, MediaMetadata]:
        """Stops the active recording, finalizes the WAV header, and returns (path, metadata)."""
        with self._lock:
            self._is_recording = False
            stream = self._stream
            self._stream = None

        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass

        with self._lock:
            wf = self._wav_file
            self._wav_file = None
            frames_written = self._frames_written

        if wf is not None:
            try:
                wf.close()
            except Exception:
                pass

        out_path = self._output_path
        computed_duration = frames_written / float(self.SAMPLE_RATE)
        if out_path is None or not out_path.exists():
            self.cleanup()
            raise ValueError(
                "No audio was captured from the microphone. Please check your microphone and try again."
            )

        file_size = out_path.stat().st_size
        if file_size <= 44 or computed_duration <= 0.1:
            self.cleanup()
            raise ValueError(
                "No audio was captured from the microphone. Please check your microphone and try again."
            )

        duration_sec = max(0.1, computed_duration)
        meta = MediaMetadata(
            path=out_path,
            file_size_bytes=file_size,
            duration_seconds=duration_sec,
            has_audio=True,
            format_name="Microphone WAV",
        )
        return out_path, meta

    def get_elapsed_seconds(self) -> float:
        """Returns the elapsed recording time in seconds."""
        if not self._is_recording or self._start_time <= 0:
            return 0.0
        return max(0.0, time.time() - self._start_time)

    def cleanup(self) -> None:
        """Stops any open stream/file and deletes the temporary microphone directory."""
        with self._lock:
            self._is_recording = False
            stream = self._stream
            self._stream = None

        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass

        with self._lock:
            wf = self._wav_file
            self._wav_file = None
            self._frames_written = 0

        if wf is not None:
            try:
                wf.close()
            except Exception:
                pass

        temp_dir = self._temp_dir
        self._temp_dir = None
        self._output_path = None
        self._start_time = 0.0

        if temp_dir is not None:
            try:
                ScratchLifecycleManager.safe_remove_tree(temp_dir)
            finally:
                ScratchLifecycleManager.unregister_dir(temp_dir)
