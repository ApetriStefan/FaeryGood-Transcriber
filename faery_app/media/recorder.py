"""
Microphone Voice Recording Subsystem for Faery Good Transcriber
"""

from __future__ import annotations

from datetime import datetime
import logging
import queue
import sys
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

_logger = logging.getLogger("faery_crash_logger")


class MicrophoneRecorder:
    """
    Captures live 16-bit mono PCM audio from the system's default input microphone
    at the device's native sample rate (falling back to 16kHz) into a
    ScratchLifecycleManager-tracked temporary WAV file.

    Uses a lock-free queue and dedicated writer thread so disk I/O never blocks
    PortAudio's real-time audio callback, while tracking peak amplitude / RMS levels
    to detect silent or macOS TCC-gated microphone streams.
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1
    DTYPE = "int16"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._is_recording: bool = False
        self._start_time: float = 0.0
        self._last_nonzero_time: float = 0.0
        self._stream = None
        self._wav_file: Optional[wave.Wave_write] = None
        self._temp_dir: Optional[Path] = None
        self._output_path: Optional[Path] = None
        self._frames_written: int = 0
        self._active_sample_rate: int = self.SAMPLE_RATE
        self._device_name: str = "Default Microphone"
        self._peak_sample: int = 0
        self._current_level: float = 0.0
        self._non_zero_chunks: int = 0
        self._callback_errors: int = 0
        self._audio_queue: Optional[queue.SimpleQueue] = None
        self._writer_thread: Optional[threading.Thread] = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def output_path(self) -> Optional[Path]:
        return self._output_path

    @property
    def device_name(self) -> str:
        return self._device_name

    @property
    def current_level(self) -> float:
        """Normalized live audio level in [0.0, 1.0]."""
        return self._current_level

    @property
    def peak_sample(self) -> int:
        return self._peak_sample

    def is_all_silent(self) -> bool:
        """Returns True if no non-zero PCM sample has been observed so far."""
        return self._peak_sample == 0

    def get_silence_duration_seconds(self) -> float:
        """Returns seconds elapsed since start or last non-zero audio sample."""
        if not self._is_recording or self._start_time <= 0:
            return 0.0
        ref = self._last_nonzero_time if self._last_nonzero_time > 0 else self._start_time
        return max(0.0, time.monotonic() - ref)

    @staticmethod
    def is_available() -> bool:
        """Checks if sounddevice is installed and an audio input device is available."""
        try:
            import sounddevice as sd
            dev = sd.query_devices(kind="input")
            return dev is not None
        except Exception:
            return False

    @staticmethod
    def _probe_input_device(sd) -> Tuple[str, int]:
        """Resolves default input device display name and native sample rate safely."""
        dev_name = "Default Microphone"
        sample_rate = MicrophoneRecorder.SAMPLE_RATE
        try:
            dev = sd.query_devices(kind="input")
            if isinstance(dev, dict):
                raw_name = str(dev.get("name") or "").strip()
                if raw_name:
                    dev_name = raw_name
                raw_sr = dev.get("default_samplerate")
                if raw_sr:
                    sr_int = int(round(float(raw_sr)))
                    if 8000 <= sr_int <= 192000:
                        sample_rate = sr_int
        except Exception:
            pass
        return dev_name, sample_rate

    def _writer_loop(self, audio_q: queue.SimpleQueue, wf: wave.Wave_write) -> None:
        """Background writer draining PCM buffers from SimpleQueue to the WAV file."""
        while True:
            item = audio_q.get()
            if item is None:
                break
            raw_bytes, frames = item
            try:
                wf.writeframes(raw_bytes)
                self._frames_written += int(frames)
            except Exception as err:
                self._callback_errors += 1
                _logger.warning(f"Microphone WAV write error: {err}")

    def _audio_callback(self, indata, frames: int, time_info, status) -> None:
        """PortAudio stream callback invoked from the audio hardware thread."""
        if not self._is_recording:
            return

        if status:
            self._callback_errors += 1

        try:
            raw_bytes = indata.tobytes() if hasattr(indata, "tobytes") else bytes(indata)
        except Exception:
            return

        # Compute amplitude & RMS without acquiring file/thread locks
        try:
            import numpy as np

            samples = np.frombuffer(raw_bytes, dtype="<i2")
            if samples.size > 0:
                samples_i32 = samples.astype(np.int32)
                chunk_peak = int(np.abs(samples_i32).max())
                rms_norm = float(np.sqrt(np.mean(np.square(samples_i32.astype(np.float32)))) / 32768.0)
                self._current_level = min(1.0, max(0.0, rms_norm * 5.0))
                if chunk_peak > 0:
                    if chunk_peak > self._peak_sample:
                        self._peak_sample = chunk_peak
                    self._non_zero_chunks += 1
                    self._last_nonzero_time = time.monotonic()
                else:
                    self._current_level = max(0.0, self._current_level * 0.5)
        except Exception:
            pass

        q = self._audio_queue
        if q is not None:
            try:
                q.put((raw_bytes, int(frames)))
            except Exception:
                pass
        elif self._wav_file is not None:
            # Direct fallback if callback invoked without active queue
            with self._lock:
                if self._is_recording and self._wav_file is not None:
                    try:
                        self._wav_file.writeframes(raw_bytes)
                        self._frames_written += int(frames)
                    except Exception:
                        pass

    def start_recording(self) -> Path:
        """Starts capturing microphone audio to a temporary mono WAV file."""
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
        self._peak_sample = 0
        self._current_level = 0.0
        self._non_zero_chunks = 0
        self._callback_errors = 0

        dev_name, detected_sr = self._probe_input_device(sd)
        self._device_name = dev_name

        # Prefer 16kHz mono directly (fast zero-copy path for Whisper) and fall back to
        # the hardware's native sample rate if the driver/interface rejects 16kHz.
        rates_to_try = [self.SAMPLE_RATE] if detected_sr == self.SAMPLE_RATE else [self.SAMPLE_RATE, detected_sr]
        last_err: Optional[Exception] = None

        try:
            stream = None
            chosen_sr = self.SAMPLE_RATE
            for sr in rates_to_try:
                try:
                    stream = sd.InputStream(
                        samplerate=sr,
                        channels=self.CHANNELS,
                        dtype=self.DTYPE,
                        callback=self._audio_callback,
                    )
                    chosen_sr = sr
                    break
                except Exception as open_err:
                    last_err = open_err
                    stream = None

            if stream is None:
                raise last_err or RuntimeError("Could not open audio input stream.")

            self._active_sample_rate = chosen_sr
            wf = wave.open(str(wav_path), "wb")
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)  # 16-bit PCM = 2 bytes
            wf.setframerate(chosen_sr)
            self._wav_file = wf

            audio_q: queue.SimpleQueue = queue.SimpleQueue()
            self._audio_queue = audio_q
            writer = threading.Thread(
                target=self._writer_loop,
                args=(audio_q, wf),
                name="FaeryMicWriter",
                daemon=True,
            )
            self._writer_thread = writer
            writer.start()

            self._stream = stream
            now_mono = time.monotonic()
            self._start_time = now_mono
            self._last_nonzero_time = now_mono
            self._is_recording = True
            stream.start()
            return wav_path
        except Exception as err:
            self.cleanup()
            raise RuntimeError(
                f"Could not start microphone recording: {err}\n\n"
                "Please check that a microphone is connected and microphone permissions are enabled."
            ) from err

    def stop_recording(self) -> Tuple[Path, MediaMetadata]:
        """Stops active recording, flushes writer, validates non-silent audio, and returns (path, metadata)."""
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

        audio_q = self._audio_queue
        writer = self._writer_thread
        self._audio_queue = None
        self._writer_thread = None

        if audio_q is not None:
            try:
                audio_q.put(None)
            except Exception:
                pass
        if writer is not None and writer.is_alive():
            writer.join(timeout=3.0)

        with self._lock:
            wf = self._wav_file
            self._wav_file = None
            frames_written = self._frames_written
            peak_sample = self._peak_sample
            sample_rate = self._active_sample_rate or self.SAMPLE_RATE

        if wf is not None:
            try:
                wf.close()
            except Exception:
                pass

        self._current_level = 0.0
        out_path = self._output_path
        computed_duration = frames_written / float(sample_rate)
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

        if peak_sample == 0:
            self.cleanup()
            if sys.platform == "darwin":
                raise PermissionError(
                    "No microphone audio signal was detected (macOS recorded pure silence).\n\n"
                    "On macOS, this almost always means Microphone permission isn't enabled for "
                    "this app (or Terminal) in System Settings -> Privacy & Security -> Microphone, "
                    "or the wrong input device is muted.\n\n"
                    "Please enable Microphone access for Faery Good Transcriber and try recording again."
                )
            raise ValueError(
                "No microphone audio signal was detected (recorded pure silence).\n\n"
                "Please check that your microphone is not muted and that the right input device is selected."
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
        return max(0.0, time.monotonic() - self._start_time)

    def cleanup(self) -> None:
        """Stops any open stream/writer/file and deletes the temporary microphone directory."""
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

        audio_q = self._audio_queue
        writer = self._writer_thread
        self._audio_queue = None
        self._writer_thread = None

        if audio_q is not None:
            try:
                audio_q.put(None)
            except Exception:
                pass
        if writer is not None and writer.is_alive():
            writer.join(timeout=2.0)

        with self._lock:
            wf = self._wav_file
            self._wav_file = None
            self._frames_written = 0

        if wf is not None:
            try:
                wf.close()
            except Exception:
                pass

        self._peak_sample = 0
        self._current_level = 0.0
        self._non_zero_chunks = 0
        self._last_nonzero_time = 0.0
        self._active_sample_rate = self.SAMPLE_RATE

        temp_dir = self._temp_dir
        self._temp_dir = None
        self._output_path = None
        self._start_time = 0.0

        if temp_dir is not None:
            try:
                ScratchLifecycleManager.safe_remove_tree(temp_dir)
            finally:
                ScratchLifecycleManager.unregister_dir(temp_dir)
