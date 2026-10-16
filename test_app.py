"""
Automated Test Suite for Faery Transcriber
==========================================
Verifies:
1. Configuration loading, saving, and corrupted file handling.
2. FFmpeg probing of media files (valid, no audio, corrupt, empty).
3. 16kHz mono audio extraction.
4. File hygiene: strict context manager purge of all scratch files.
5. Faster-Whisper CPU int8 inference.
6. GUI widget initialization and lifecycle.
"""

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

# Add current workspace to path
sys.path.insert(0, str(Path(__file__).parent))

import imageio_ffmpeg
from app import (
    ConfigManager,
    MediaProcessor,
    TranscriptionEngine,
    TranscriptSegment,
    MediaMetadata,
    FaeryTranscriberApp,
    get_verified_ffmpeg_exe,
    check_free_disk_space,
    open_system_folder,
)


class TestConfigManager(unittest.TestCase):
    def test_config_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_file = Path(td) / "test_config.json"
            cfg = ConfigManager(config_path=cfg_file)
            
            # Default check
            self.assertTrue(Path(cfg.output_directory).exists())
            self.assertEqual(cfg.model_selection, "High Accuracy (small.en - Recommended)")
            
            # Modify and save
            new_out = Path(td) / "CustomTranscripts"
            new_out.mkdir()
            cfg.output_directory = new_out
            cfg.model_selection = "Standard (base.en - Fast)"
            cfg.appearance_mode = "Dark"

            # Reload in new instance
            cfg2 = ConfigManager(config_path=cfg_file)
            self.assertEqual(cfg2.output_directory, new_out)
            self.assertEqual(cfg2.model_selection, "Standard (base.en - Fast)")
            self.assertEqual(cfg2.appearance_mode, "Dark")

    def test_corrupted_config_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_file = Path(td) / "corrupt.json"
            cfg_file.write_text("NOT_VALID_JSON{", encoding="utf-8")
            cfg = ConfigManager(config_path=cfg_file)
            self.assertIsNotNone(cfg.output_directory)


class TestMediaProcessorAndHygiene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ffmpeg = get_verified_ffmpeg_exe()
        cls.td = tempfile.TemporaryDirectory()
        cls.test_dir = Path(cls.td.name)

        # 1. Create a 3-second audio file
        cls.audio_file = cls.test_dir / "sample_audio.mp4"
        import subprocess
        subprocess.run(
            [
                cls.ffmpeg, "-y", "-f", "lavfi",
                "-i", "sine=frequency=880:duration=3",
                "-c:a", "aac", str(cls.audio_file)
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # 2. Create a video file with NO audio
        cls.no_audio_file = cls.test_dir / "silent_video.mp4"
        subprocess.run(
            [
                cls.ffmpeg, "-y", "-f", "lavfi",
                "-i", "testsrc=duration=2:size=160x120:rate=10",
                "-c:v", "libx264", str(cls.no_audio_file)
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # 3. Create an empty 0-byte file
        cls.empty_file = cls.test_dir / "empty.mp4"
        cls.empty_file.touch()

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def test_probe_valid_media(self):
        meta = MediaProcessor.probe_file(self.audio_file)
        self.assertTrue(meta.has_audio)
        self.assertGreater(meta.duration_seconds, 2.5)
        self.assertGreater(meta.file_size_bytes, 0)
        self.assertIn(":", meta.formatted_duration)

    def test_probe_no_audio(self):
        with self.assertRaises(ValueError) as ctx:
            MediaProcessor.probe_file(self.no_audio_file)
        self.assertIn("No audio track was detected", str(ctx.exception))

    def test_probe_empty_file(self):
        with self.assertRaises(ValueError) as ctx:
            MediaProcessor.probe_file(self.empty_file)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_probe_nonexistent_file(self):
        with self.assertRaises(FileNotFoundError):
            MediaProcessor.probe_file(self.test_dir / "does_not_exist.mp4")

    def test_extract_16k_mono_wav(self):
        cancel_event = threading.Event()
        out_wav = self.test_dir / "extracted.wav"
        MediaProcessor.extract_16k_mono_wav(self.audio_file, out_wav, cancel_event)
        self.assertTrue(out_wav.exists())
        self.assertGreater(out_wav.stat().st_size, 1000)

        # Inspect extracted WAV format via FFmpeg
        import subprocess, re
        res = subprocess.run([self.ffmpeg, "-hide_banner", "-i", str(out_wav)], stderr=subprocess.PIPE, text=True)
        self.assertIn("16000 Hz", res.stderr)
        self.assertIn("mono", res.stderr)
        out_wav.unlink()

    def test_transcription_engine_hygiene(self):
        """Tests end-to-end transcription pipeline and verifies ZERO scratch files remain."""
        engine = TranscriptionEngine()
        meta = MediaProcessor.probe_file(self.audio_file)
        cancel_event = threading.Event()

        with tempfile.TemporaryDirectory() as out_td:
            output_dir = Path(out_td)
            status_updates = []
            progress_updates = []
            segments = []

            clean_path, timecoded_path, md_path, segs = engine.run_transcription(
                media_file=self.audio_file,
                media_meta=meta,
                model_name="base.en",
                output_dir=output_dir,
                cancel_event=cancel_event,
                status_cb=lambda s: status_updates.append(s),
                progress_cb=lambda p: progress_updates.append(p),
                segment_cb=lambda seg: segments.append(seg),
            )

            # Assert outputs created
            self.assertTrue(Path(clean_path).exists())
            self.assertTrue(Path(timecoded_path).exists())
            self.assertTrue(Path(md_path).exists())

            # Read Markdown to verify structure
            md_text = Path(md_path).read_text(encoding="utf-8")
            self.assertIn("# Transcription:", md_text)
            self.assertIn("YouTube Chapters & Timestamps", md_text)

            # Verify no temporary folders with prefix faery_transcribe_ are left in system temp
            temp_sys = Path(tempfile.gettempdir())
            scratch_dirs = list(temp_sys.glob("faery_transcribe_*"))
            self.assertEqual(len(scratch_dirs), 0, f"Found lingering scratch dirs: {scratch_dirs}")

    def test_transcript_formatter(self):
        from app import TranscriptFormatter
        segs = [
            TranscriptSegment(start=0.0, end=2.0, text="First introductory thought."),
            TranscriptSegment(start=3.5, end=5.0, text="Second thought after long pause."),
            TranscriptSegment(start=5.2, end=7.0, text="Continuous thought immediately following."),
        ]
        # Paragraphs test: 3.5 - 2.0 = 1.5s pause => newlines
        paragraphs = TranscriptFormatter.to_paragraphs(segs)
        self.assertIn("\n\n", paragraphs)
        self.assertTrue(paragraphs.startswith("First introductory thought.\n\nSecond thought"))

        # Timecoded test
        timecoded = TranscriptFormatter.to_timecoded(segs)
        self.assertIn("[00:00] First introductory thought.", timecoded)
        self.assertIn("[00:03] Second thought after long pause.", timecoded)

        # Raw test
        raw = TranscriptFormatter.to_raw(segs)
        self.assertNotIn("\n", raw)
        self.assertIn("First introductory thought. Second thought", raw)


class TestHistoryManager(unittest.TestCase):
    def test_history_crud(self):
        from app import HistoryManager, HistoryRecord
        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td)
            hist_file = temp_path / "history.json"
            hm = HistoryManager(history_path=hist_file)

            # Create dummy files
            p_file = temp_path / "clip_paragraphs.txt"
            t_file = temp_path / "clip_timecoded.txt"
            m_file = temp_path / "clip_transcript.md"
            p_file.write_text("Test paragraph content.", encoding="utf-8")
            t_file.write_text("[00:00] Test paragraph content.", encoding="utf-8")
            m_file.write_text("# Markdown content", encoding="utf-8")

            # CREATE: Add record
            rec = HistoryRecord(
                id="rec_1",
                title="clip",
                source_filename="clip.mp4",
                duration_str="01:00",
                created_at="2026-10-16 17:00",
                model="small.en",
                paragraphs_file=str(p_file),
                timecoded_file=str(t_file),
                markdown_file=str(m_file),
                word_count=3,
            )
            hm.add_or_update(rec)
            self.assertEqual(len(hm.records), 1)

            # READ / RELOAD
            hm2 = HistoryManager(history_path=hist_file)
            self.assertEqual(len(hm2.records), 1)
            self.assertEqual(hm2.records[0].title, "clip")

            # UPDATE: Rename
            updated = hm2.rename_record("rec_1", "renamed_clip")
            self.assertIsNotNone(updated)
            self.assertEqual(updated.title, "renamed_clip")
            self.assertTrue(Path(updated.paragraphs_file).exists())
            self.assertEqual(Path(updated.paragraphs_file).name, "renamed_clip_paragraphs.txt")

            # DELETE: Delete record and files
            success = hm2.delete_record("rec_1")
            self.assertTrue(success)
            self.assertEqual(len(hm2.records), 0)
            self.assertFalse(Path(updated.paragraphs_file).exists())


class TestGUIComponents(unittest.TestCase):
    def test_app_lifecycle(self):
        from app import APP_NAME, FAERY_GOOD_TAGLINE, FAERY_PURPLE, get_assets_dir
        app = FaeryTranscriberApp()
        app.update_idletasks()

        # Verify Faery Good brand identity & assets
        self.assertEqual(APP_NAME, "Faery Good Transcriber")
        self.assertEqual(FAERY_GOOD_TAGLINE, "Whimsy is Power")
        self.assertEqual(FAERY_PURPLE, ("#7A2DB4", "#9146CC"))

        assets_dir = get_assets_dir()
        self.assertTrue((assets_dir / "faery_icon.png").exists())
        self.assertTrue((assets_dir / "faery_icon.icns").exists())
        self.assertTrue((assets_dir / "faery_icon.ico").exists())
        self.assertTrue((assets_dir / "faery_good_theme.json").exists())
        self.assertIsNotNone(app.brand.mascot_header)
        self.assertIsNotNone(app.brand.logo_header)
        self.assertIsNotNone(app.brand.icon_butterfly)
        self.assertIsNotNone(app.brand.icon_mortar)
        self.assertIsNotNone(app.brand.icon_sprig)

        # Check Tabview
        self.assertIsNotNone(app.tabview)
        self.assertIsNotNone(app.tab_transcribe)
        self.assertIsNotNone(app.tab_history)

        # Check Transcribe Studio widgets
        self.assertIsNotNone(app.select_file_btn)
        self.assertIsNotNone(app.url_entry)
        self.assertIsNotNone(app.paste_url_btn)
        self.assertIsNotNone(app.cookie_dropdown)
        self.assertIsNotNone(app.generate_btn)
        self.assertIsNotNone(app.model_dropdown)
        self.assertIsNotNone(app.textbox)
        self.assertIsNotNone(app.view_selector)
        self.assertIsNotNone(app.copy_btn)
        self.assertIsNotNone(app.save_txt_btn)
        self.assertIsNotNone(app.save_md_btn)
        self.assertIsNotNone(app.open_folder_btn)

        # Test URL entry activation
        app._activate_online_url("https://www.instagram.com/reel/C123456789/")
        self.assertEqual(app.selected_url, "https://www.instagram.com/reel/C123456789/")
        self.assertIsNone(app.selected_file)
        self.assertIn("Instagram", app.file_name_label.cget("text"))

        # Check History Tab widgets
        self.assertIsNotNone(app.history_search_entry)
        self.assertIsNotNone(app.history_refresh_btn)
        self.assertIsNotNone(app.history_textbox)
        self.assertIsNotNone(app.h_rename_btn)
        self.assertIsNotNone(app.h_save_btn)
        self.assertIsNotNone(app.h_delete_btn)

        # Check textbox stats update
        app.textbox.insert("1.0", "Hello world this is a test transcript.")
        app._update_stats()
        self.assertIn("7 words", app.stats_badge.cget("text"))

        # Test theme cycle
        app._cycle_theme()
        self.assertIn(app.config.appearance_mode, ["System", "Dark", "Light"])

        # Test Dialogs (instantiation without errors)
        try:
            app._show_quick_guide()
        except Exception as e:
            self.fail(f"_show_quick_guide failed: {e}")

        try:
            app._show_about_dialog()
        except Exception as e:
            self.fail(f"_show_about_dialog failed: {e}")

        # Destroy cleanly
        app.destroy()

    def test_mac_polish_utilities(self):
        from app import play_completion_sound
        # Ensure completion sound call completes without raising exceptions
        try:
            play_completion_sound()
        except Exception as e:
            self.fail(f"play_completion_sound raised an exception: {e}")

        # Test initial media directory fallback
        with tempfile.TemporaryDirectory() as td:
            cfg = ConfigManager(config_path=Path(td) / "cfg.json")
            initial_dir = cfg.get_initial_media_dir()
            self.assertTrue(initial_dir.exists())

        # Test model cache detector
        self.assertIsInstance(TranscriptionEngine.is_model_cached("base.en"), bool)


class TestOnlineMediaFetcherAndHygiene(unittest.TestCase):
    def test_url_validation_and_platform_detection(self):
        from app import OnlineMediaFetcher
        self.assertTrue(OnlineMediaFetcher.is_valid_url("https://www.instagram.com/reel/C9xYz123/"))
        self.assertTrue(OnlineMediaFetcher.is_valid_url("https://youtu.be/dQw4w9WgXcQ"))
        self.assertTrue(OnlineMediaFetcher.is_valid_url("https://www.tiktok.com/@user/video/123456"))
        self.assertTrue(OnlineMediaFetcher.is_valid_url("https://fb.watch/abc123xyz/"))
        self.assertFalse(OnlineMediaFetcher.is_valid_url("not_a_url"))
        self.assertFalse(OnlineMediaFetcher.is_valid_url("ftp://files.server.com/clip.mp4"))

        self.assertEqual(OnlineMediaFetcher.detect_platform("https://www.instagram.com/reel/abc/"), "Instagram")
        self.assertEqual(OnlineMediaFetcher.detect_platform("https://www.youtube.com/shorts/abc"), "YouTube")
        self.assertEqual(OnlineMediaFetcher.detect_platform("https://vm.tiktok.com/ZM123/"), "TikTok")
        self.assertEqual(OnlineMediaFetcher.detect_platform("https://www.facebook.com/reel/12345"), "Facebook")

    def test_sanitize_title(self):
        from app import OnlineMediaFetcher
        clean = OnlineMediaFetcher.sanitize_title("My Magical Apothecary Reel! ✨ #faerygood / 2026: Part 1?", "Instagram_Clip")
        self.assertNotIn("/", clean)
        self.assertNotIn(":", clean)
        self.assertNotIn("?", clean)
        self.assertTrue(len(clean) > 0)

        fallback = OnlineMediaFetcher.sanitize_title("???", "TikTok_Clip")
        self.assertEqual(fallback, "TikTok_Clip")

    def test_online_transcription_temp_audio_hygiene(self):
        """Verifies that online audio downloads are strictly temporary and 100% purged after transcription."""
        from unittest.mock import patch
        from app import OnlineMediaFetcher, OnlineClipInfo

        ffmpeg = get_verified_ffmpeg_exe()
        engine = TranscriptionEngine()
        cancel_event = threading.Event()
        captured_temp_files = []

        def fake_download_audio_to_temp(url, temp_dir, cancel_event, status_cb=None, progress_cb=None, cookie_browser_label=""):
            # Generate a temporary downloaded audio file inside temp_dir (simulating yt-dlp)
            dl_path = Path(temp_dir) / "online_source_test.m4a"
            import subprocess
            subprocess.run(
                [
                    ffmpeg, "-y", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=2",
                    "-c:a", "aac", str(dl_path)
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            captured_temp_files.append(dl_path)
            return OnlineClipInfo(
                url=url,
                platform="Instagram",
                title="Instagram Test Reel",
                sanitized_title="Instagram_Test_Reel",
                video_id="test12345",
                duration_seconds=2.0,
                temp_media_path=dl_path,
            )

        with tempfile.TemporaryDirectory() as out_td:
            output_dir = Path(out_td)
            with patch.object(OnlineMediaFetcher, "download_audio_to_temp", side_effect=fake_download_audio_to_temp):
                clean_p, time_p, md_p, segs, base_name, dur_str = engine.run_online_transcription(
                    url="https://www.instagram.com/reel/test12345/",
                    model_name="base.en",
                    output_dir=output_dir,
                    cancel_event=cancel_event,
                    cookie_browser_label="Auto / Public (Recommended)",
                    status_cb=lambda s: None,
                    progress_cb=lambda p: None,
                    segment_cb=lambda seg: None,
                )

                # Verify transcript files were saved
                self.assertTrue(Path(clean_p).exists())
                self.assertTrue(Path(time_p).exists())
                self.assertTrue(Path(md_p).exists())
                md_content = Path(md_p).read_text(encoding="utf-8")
                self.assertIn("https://www.instagram.com/reel/test12345/", md_content)
                self.assertIn("Instagram", md_content)

                # Verify the temporary downloaded audio file AND its scratch directory are completely deleted
                self.assertEqual(len(captured_temp_files), 1)
                self.assertFalse(captured_temp_files[0].exists(), "Temporary downloaded audio must be deleted!")
                self.assertFalse(captured_temp_files[0].parent.exists(), "Temporary directory must be deleted!")


if __name__ == "__main__":
    unittest.main()


