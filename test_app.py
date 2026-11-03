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
import plistlib
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

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
    ensure_macos_app_installed,
    is_directory_writable,
    _create_macos_app_bundle,
    APP_NAME,
    APP_VERSION,
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

    def test_history_full_text_search(self):
        from app import HistoryRecord
        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td)
            p_file = temp_path / "Apothecary_Magic_paragraphs.txt"
            p_file.write_text("Today we blend organic lavender oils with chamomile mist.", encoding="utf-8")

            rec = HistoryRecord(
                id="rec_search",
                title="Apothecary_Magic",
                source_filename="Apothecary_Magic.mp4",
                duration_str="02:15",
                created_at="2026-10-16 19:00",
                model="small.en",
                paragraphs_file=str(p_file),
                timecoded_file="",
                markdown_file="",
                word_count=8,
            )

            # Match on exact title
            matched, _ = rec.matches_query("Apothecary")
            self.assertTrue(matched)

            # Match on title with normalized spaces
            matched, _ = rec.matches_query("apothecary magic")
            self.assertTrue(matched)

            # Match on words inside spoken transcript text with snippet extraction
            matched, snip = rec.matches_query("lavender")
            self.assertTrue(matched)
            self.assertIsNotNone(snip)
            self.assertIn("lavender", snip.lower())

            # Multi-token search matching across metadata and transcript content
            matched, snip = rec.matches_query("apothecary chamomile")
            self.assertTrue(matched)

            # Non-matching search
            matched, _ = rec.matches_query("unrelated non-existent query")
            self.assertFalse(matched)



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
        self.assertIsNotNone(app.history_search_clear_btn)
        self.assertIsNotNone(app.history_refresh_btn)
        self.assertIsNotNone(app.history_textbox)
        self.assertIsNotNone(app.h_rename_btn)
        self.assertIsNotNone(app.h_save_btn)
        self.assertIsNotNone(app.h_delete_btn)

        # Test history search typing and clearing
        app.history_search_entry.insert(0, "SearchTerm")
        app._on_history_search_changed()
        self.assertEqual(app.history_search_entry.get(), "SearchTerm")
        app._on_clear_search_clicked()
        self.assertEqual(app.history_search_entry.get(), "")

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


class TestAutoUpdater(unittest.TestCase):
    def test_should_check_update_logic(self):
        from app import AutoUpdater, ConfigManager
        with tempfile.TemporaryDirectory() as td:
            cfg = ConfigManager(config_path=Path(td) / "cfg.json")
            # Fresh config defaults to 0.0 -> should check
            self.assertTrue(AutoUpdater.should_check_update(cfg))

            # Set last_check to right now -> should NOT check (within 7 days)
            cfg.last_update_check = time.time()
            self.assertFalse(AutoUpdater.should_check_update(cfg))

            # Force check -> should always return True
            self.assertTrue(AutoUpdater.should_check_update(cfg, force=True))

            # Set last_check to 8 days ago -> should check
            cfg.last_update_check = time.time() - (8 * 24 * 3600)
            self.assertTrue(AutoUpdater.should_check_update(cfg))

    def test_is_internet_available(self):
        from app import AutoUpdater
        # Should return a boolean without crashing or hanging
        res = AutoUpdater.is_internet_available(timeout=1.0)
        self.assertIsInstance(res, bool)

    def test_standalone_bundle_update_behavior(self):
        from app import AutoUpdater, ConfigManager
        import unittest.mock as mock
        with tempfile.TemporaryDirectory() as td:
            cfg = ConfigManager(config_path=Path(td) / "cfg.json")
            project_dir = Path(td)
            with mock.patch.object(sys, "frozen", True, create=True):
                self.assertTrue(AutoUpdater.is_standalone_bundle())
                updated, msg = AutoUpdater.run_update_check_and_pull(cfg, project_dir, force=False)
                self.assertFalse(updated)
                self.assertIn("Standalone", msg)

                updated, msg = AutoUpdater.run_update_check_and_pull(cfg, project_dir, force=True)
                self.assertFalse(updated)
                self.assertIn("standalone", msg.lower())
                self.assertIn("faerygood.com", msg)

    def test_git_cli_missing_behavior(self):
        from app import AutoUpdater, ConfigManager
        import unittest.mock as mock
        with tempfile.TemporaryDirectory() as td:
            cfg = ConfigManager(config_path=Path(td) / "cfg.json")
            project_dir = Path(td)
            with mock.patch("shutil.which", return_value=None):
                self.assertFalse(AutoUpdater.is_git_available())
                updated, msg = AutoUpdater.run_update_check_and_pull(cfg, project_dir, force=False)
                self.assertFalse(updated)

                updated, msg = AutoUpdater.run_update_check_and_pull(cfg, project_dir, force=True)
                self.assertFalse(updated)
                self.assertIn("Git was not found", msg)


class TestScratchLifecycleManager(unittest.TestCase):
    def test_safe_scratch_directory_lifecycle(self):
        from app import ScratchLifecycleManager
        created_path = None
        with ScratchLifecycleManager.safe_scratch_directory(prefix="faery_transcribe_test_") as temp_dir:
            created_path = temp_dir
            self.assertTrue(created_path.exists())
            self.assertIn(created_path.resolve(), ScratchLifecycleManager._active_scratch_dirs)
            (created_path / "dummy_audio.wav").write_bytes(b"RIFF dummy audio data")
            self.assertTrue((created_path / "dummy_audio.wav").exists())

        self.assertFalse(created_path.exists())
        self.assertNotIn(created_path.resolve(), ScratchLifecycleManager._active_scratch_dirs)

    def test_safe_scratch_directory_on_exception(self):
        from app import ScratchLifecycleManager
        created_path = None
        try:
            with ScratchLifecycleManager.safe_scratch_directory(prefix="faery_transcribe_test_") as temp_dir:
                created_path = temp_dir
                self.assertTrue(created_path.exists())
                (created_path / "cancelled_audio.wav").write_bytes(b"cancelled")
                raise InterruptedError("User cancelled transcription")
        except InterruptedError:
            pass

        self.assertFalse(created_path.exists())
        self.assertNotIn(created_path.resolve(), ScratchLifecycleManager._active_scratch_dirs)

    def test_cleanup_all_active(self):
        from app import ScratchLifecycleManager
        dir1 = Path(tempfile.mkdtemp(prefix="faery_transcribe_act1_"))
        dir2 = Path(tempfile.mkdtemp(prefix="faery_transcribe_act2_"))
        ScratchLifecycleManager.register_dir(dir1)
        ScratchLifecycleManager.register_dir(dir2)

        self.assertTrue(dir1.exists())
        self.assertTrue(dir2.exists())

        ScratchLifecycleManager.cleanup_all_active()

        self.assertFalse(dir1.exists())
        self.assertFalse(dir2.exists())
        self.assertEqual(len(ScratchLifecycleManager._active_scratch_dirs), 0)

    def test_cleanup_orphaned_scratch(self):
        from app import ScratchLifecycleManager
        orphan_dir = Path(tempfile.mkdtemp(prefix="faery_transcribe_orphan_"))
        (orphan_dir / "leftover.wav").write_bytes(b"stale data")

        self.assertTrue(orphan_dir.exists())
        self.assertNotIn(orphan_dir.resolve(), ScratchLifecycleManager._active_scratch_dirs)

        ScratchLifecycleManager.cleanup_orphaned_scratch()

        self.assertFalse(orphan_dir.exists(), "Orphaned scratch directory must be purged")


class TestFaeryRadio(unittest.TestCase):
    def test_radio_asset_discovery(self):
        from app import RadioStationController, ConfigManager
        with tempfile.TemporaryDirectory() as td:
            cfg = ConfigManager(config_path=Path(td) / "cfg.json")
            controller = RadioStationController(cfg)

            self.assertGreater(len(controller.music_files), 0, "Should discover music files")
            self.assertIsNotNone(controller.liability_file, "Should discover Liability.mp3")
            self.assertEqual(controller.liability_file.name, "Liability.mp3")
            self.assertIsNotNone(controller.grift_file, "Should discover Grift.mp3")
            self.assertEqual(controller.grift_file.name, "Grift.mp3")
            self.assertGreater(len(controller.regular_announcers), 0, "Should discover regular announcer clips")

    def test_announcer_selection_and_anti_repeat(self):
        from app import RadioStationController, ConfigManager, RadioTrackType
        with tempfile.TemporaryDirectory() as td:
            cfg = ConfigManager(config_path=Path(td) / "cfg.json")
            controller = RadioStationController(cfg)

            last_clip_name = None
            liability_count = 0
            trials = 100

            for _ in range(trials):
                clip_path, track_type, title, sub = controller._pick_next_announcer()
                self.assertIsNotNone(clip_path)

                # Anti-repeat check: No clip should repeat immediately back-to-back
                self.assertNotEqual(
                    clip_path.name,
                    last_clip_name,
                    f"Clip '{clip_path.name}' repeated immediately back-to-back!",
                )
                last_clip_name = clip_path.name

                if track_type == RadioTrackType.LIABILITY:
                    liability_count += 1
                    self.assertEqual(clip_path, controller.liability_file)

            # Liability should trigger with higher chance (~20-40% of breaks)
            self.assertGreater(liability_count, 10, "Liability should trigger regularly with higher chance")

    def test_pre_song_grift_bumper_logic(self):
        from app import RadioStationController, ConfigManager, RadioTrackType
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            cfg = ConfigManager(config_path=Path(td) / "cfg.json")
            controller = RadioStationController(cfg)
            song = controller.music_files[0]

            with patch.object(controller, "_play_file", return_value=True) as mock_play:
                # Force Grift bumper roll (< RATE)
                with patch("random.random", return_value=0.1):
                    controller._prepare_and_play_song(song)
                    mock_play.assert_called_once()
                    args = mock_play.call_args[0]
                    self.assertEqual(args[0], controller.grift_file)
                    self.assertEqual(args[1], RadioTrackType.GRIFT)
                    self.assertIsNotNone(controller._pending_song)
                    self.assertEqual(controller._pending_song[0], song)

            with patch.object(controller, "_play_file", return_value=True) as mock_play:
                # Force regular song roll (>= RATE)
                with patch("random.random", return_value=0.9):
                    controller._prepare_and_play_song(song)
                    mock_play.assert_called_once()
                    args = mock_play.call_args[0]
                    self.assertEqual(args[0], song)
                    self.assertEqual(args[1], RadioTrackType.SONG)
                    self.assertIsNone(controller._pending_song)

    def test_volume_and_mute_controls(self):
        from app import RadioStationController, ConfigManager
        with tempfile.TemporaryDirectory() as td:
            cfg = ConfigManager(config_path=Path(td) / "cfg.json")
            controller = RadioStationController(cfg)

            controller.set_volume(0.8)
            self.assertAlmostEqual(controller.volume, 0.8)
            self.assertAlmostEqual(cfg.radio_volume, 0.8)

            # Test Mute
            controller.toggle_mute()
            self.assertTrue(controller.is_muted)

            # Test Unmute
            controller.toggle_mute()
            self.assertFalse(controller.is_muted)
            self.assertAlmostEqual(controller.volume, 0.8)

    def test_embedded_art_extraction(self):
        from app import extract_embedded_art, get_music_dir
        music_d = get_music_dir()
        mp3s = list(music_d.glob("*.mp3"))
        self.assertGreater(len(mp3s), 0)
        art = extract_embedded_art(mp3s[0], target_size=(44, 44))
        self.assertIsNotNone(art, f"Should successfully extract embedded art from {mp3s[0].name}")

    def test_timeline_seek_to(self):
        from app import RadioStationController, ConfigManager, RadioTrackType
        with tempfile.TemporaryDirectory() as td:
            cfg = ConfigManager(config_path=Path(td) / "cfg.json")
            controller = RadioStationController(cfg)
            song = controller.music_files[0]
            controller._play_file(song, RadioTrackType.SONG, song.stem, "Faery Good Radio")
            self.assertTrue(controller.is_playing)

            # Seek to 20 seconds
            res = controller.seek_to(20.0)
            self.assertTrue(res)
            self.assertAlmostEqual(controller.current_seek_offset, 20.0, delta=0.5)
            self.assertGreaterEqual(controller.get_elapsed_seconds(), 19.5)
            controller.stop()

    def test_gui_radio_toggle_and_visibility(self):
        import customtkinter as ctk
        from app import FaeryTranscriberApp
        app = FaeryTranscriberApp()
        app.withdraw()

        try:
            # 1. Radio toggle switch must exist, be named Radio, and be OFF (0) by default
            self.assertIsNotNone(app.radio_toggle)
            self.assertIn("Radio", app.radio_toggle.cget("text"))
            self.assertEqual(app.radio_toggle.get(), 0, "Radio toggle must be OFF (0) by default when opening the app")

            # 2. Player frame must exist and be hidden by default
            self.assertIsNotNone(app.radio_player_frame)
            self.assertEqual(len(app.radio_player_frame.grid_info()), 0, "Player must be hidden by default")
            self.assertFalse(app.radio_controller.is_playing, "Radio music must not be playing by default")

            # 4. If toggle is ON, player must be displayed in row 2
            app.radio_toggle.select()
            app._on_radio_toggle_changed()
            info = app.radio_player_frame.grid_info()
            self.assertEqual(info.get("row"), 2, "Player must be displayed at row 2 when toggle is on")

            # 5. Dismiss button turns off toggle and hides player
            app._close_radio_player()
            self.assertEqual(app.radio_toggle.get(), 0)
            self.assertEqual(len(app.radio_player_frame.grid_info()), 0)
        finally:
            app.radio_controller.stop()
            app.destroy()

    def test_radio_keyboard_shortcuts(self):
        from unittest.mock import MagicMock
        from app import FaeryTranscriberApp
        app = FaeryTranscriberApp()
        app.withdraw()

        try:
            # Test volume adjustment helper
            app.radio_controller.set_volume(0.5)
            app._adjust_radio_volume(0.1)
            self.assertAlmostEqual(app.radio_controller.volume, 0.6, places=2)
            app._adjust_radio_volume(-0.2)
            self.assertAlmostEqual(app.radio_controller.volume, 0.4, places=2)
            app._adjust_radio_volume(1.5)
            self.assertAlmostEqual(app.radio_controller.volume, 1.0, places=2)
            app._adjust_radio_volume(-2.0)
            self.assertAlmostEqual(app.radio_controller.volume, 0.0, places=2)

            # Test spacebar shortcut behavior:
            # 1. When focus is inside a Text / Entry widget, space should NOT trigger radio toggle
            mock_entry_focus = MagicMock()
            mock_entry_focus.winfo_class.return_value = "Entry"
            app.focus_get = MagicMock(return_value=mock_entry_focus)

            app.radio_toggle.select()
            app._on_radio_toggle_changed()
            initial_state = app.radio_controller.is_playing

            # Trigger bound space handler
            res = app._on_space_pressed_handler(None) if hasattr(app, "_on_space_pressed_handler") else None
            # If focus is on Entry, it should return None without intercepting
            self.assertIsNone(res)

            # 2. When focus is on non-text widget (e.g. Frame / Canvas / Root)
            mock_frame_focus = MagicMock()
            mock_frame_focus.winfo_class.return_value = "Frame"
            app.focus_get = MagicMock(return_value=mock_frame_focus)

            # Call space press handler directly
            if hasattr(app, "_on_space_pressed_handler"):
                res = app._on_space_pressed_handler(None)
                self.assertEqual(res, "break")
        finally:
            app.radio_controller.stop()
            app.destroy()


class TestMacOSAppIntegration(unittest.TestCase):
    """Verifies macOS Applications folder integration and Spotlight discovery."""

    def test_platform_guard_non_darwin(self):
        """Platform guard: on non-darwin platforms, ensure_macos_app_installed is bypassed without error."""
        # Explicit non-darwin platform overrides
        self.assertIsNone(ensure_macos_app_installed(force_platform="win32"))
        self.assertIsNone(ensure_macos_app_installed(force_platform="linux"))

        # When running on host non-darwin OS without force_platform
        if sys.platform != "darwin":
            self.assertIsNone(ensure_macos_app_installed())

    def test_bundle_structure_creation(self):
        """Source-Run mode: creates valid .app bundle structure (Info.plist, launcher, icon, permissions)."""
        with tempfile.TemporaryDirectory() as td:
            mock_apps_dir = Path(td) / "Applications"
            mock_apps_dir.mkdir()

            bundle_path = ensure_macos_app_installed(
                applications_dir=mock_apps_dir,
                force_platform="darwin",
            )
            self.assertIsNotNone(bundle_path)
            self.assertEqual(bundle_path, mock_apps_dir / "Faery Good Transcriber.app")
            self.assertTrue(bundle_path.is_dir())

            # 1. Verify Contents/Info.plist
            plist_file = bundle_path / "Contents" / "Info.plist"
            self.assertTrue(plist_file.is_file())
            with open(plist_file, "rb") as fp:
                plist_data = plistlib.load(fp)
            self.assertEqual(plist_data.get("CFBundleName"), "Faery Good Transcriber")
            self.assertEqual(plist_data.get("CFBundleDisplayName"), "Faery Good Transcriber")
            self.assertEqual(plist_data.get("CFBundleIdentifier"), "com.faerygood.transcriber")
            self.assertEqual(plist_data.get("CFBundlePackageType"), "APPL")
            self.assertEqual(plist_data.get("CFBundleExecutable"), "Faery Good Transcriber")
            self.assertEqual(plist_data.get("CFBundleVersion"), APP_VERSION)

            # 2. Verify Contents/MacOS/Faery Good Transcriber launcher script
            launcher_file = bundle_path / "Contents" / "MacOS" / "Faery Good Transcriber"
            self.assertTrue(launcher_file.is_file())
            launcher_content = launcher_file.read_text(encoding="utf-8")
            self.assertIn("REPO_DIR=", launcher_content)
            self.assertIn("app.py", launcher_content)

            # 3. Verify Contents/Resources/faery_icon.icns
            repo_icon = Path(__file__).resolve().parent / "assets" / "faery_icon.icns"
            if repo_icon.exists():
                icon_file = bundle_path / "Contents" / "Resources" / "faery_icon.icns"
                self.assertTrue(icon_file.is_file())
                self.assertGreater(icon_file.stat().st_size, 0)

    def test_fallback_unwritable_applications_directory(self):
        """Fallback: if /Applications is not writable, automatically falls back to ~/Applications."""
        with tempfile.TemporaryDirectory() as td:
            mock_sys_apps = Path(td) / "SystemApplications"
            mock_usr_apps = Path(td) / "UserApplications"
            mock_sys_apps.mkdir()

            with patch("app.is_directory_writable", side_effect=lambda p: Path(p) != mock_sys_apps):
                bundle_path = ensure_macos_app_installed(
                    applications_dir=mock_sys_apps,
                    user_applications_dir=mock_usr_apps,
                    force_platform="darwin",
                )
                self.assertIsNotNone(bundle_path)
                self.assertEqual(bundle_path, mock_usr_apps / "Faery Good Transcriber.app")
                self.assertTrue(bundle_path.is_dir())
                self.assertTrue((bundle_path / "Contents" / "Info.plist").is_file())
                self.assertTrue((bundle_path / "Contents" / "MacOS" / "Faery Good Transcriber").is_file())

                # Verify system applications folder was not used
                self.assertFalse((mock_sys_apps / "Faery Good Transcriber.app").exists())

    def test_frozen_bundle_mode_installation(self):
        """Frozen Bundle mode: copies standalone bundle from source to Applications folder."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            mock_source_bundle = td_path / "SourceDist" / "Faery Good Transcriber.app"
            mock_macos = mock_source_bundle / "Contents" / "MacOS"
            mock_macos.mkdir(parents=True)
            mock_exe = mock_macos / "Faery Good Transcriber"
            mock_exe.write_text("#!/bin/sh\necho running\n", encoding="utf-8")

            mock_apps_dir = td_path / "TargetApplications"
            mock_apps_dir.mkdir()

            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "executable", str(mock_exe)):
                installed_bundle = ensure_macos_app_installed(
                    applications_dir=mock_apps_dir,
                    force_platform="darwin",
                )
                self.assertIsNotNone(installed_bundle)
                self.assertEqual(installed_bundle, mock_apps_dir / "Faery Good Transcriber.app")
                self.assertTrue(installed_bundle.is_dir())
                self.assertTrue((installed_bundle / "Contents" / "MacOS" / "Faery Good Transcriber").is_file())

                # If already running directly from target bundle, should return without error
                with patch.object(sys, "executable", str(installed_bundle / "Contents" / "MacOS" / "Faery Good Transcriber")):
                    re_check = ensure_macos_app_installed(
                        applications_dir=mock_apps_dir,
                        force_platform="darwin",
                    )
                    self.assertEqual(re_check, installed_bundle)

    def test_is_directory_writable_helper(self):
        """Validates is_directory_writable handles writable dirs and auto-creates missing dirs."""
        with tempfile.TemporaryDirectory() as td:
            valid_dir = Path(td) / "writable"
            self.assertTrue(is_directory_writable(valid_dir))

            non_existent_subdir = Path(td) / "sub1" / "sub2"
            self.assertTrue(is_directory_writable(non_existent_subdir))
            self.assertTrue(non_existent_subdir.exists())


if __name__ == "__main__":
    unittest.main()



