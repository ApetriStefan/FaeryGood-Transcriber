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
import customtkinter as ctk
from faery_app.ui.dialogs.quick_guide import QuickGuideDialog
from faery_app.ui.dialogs.about import AboutDialog
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
    DEFAULT_MODEL_DISPLAY,
    DEFAULT_PUNCTUATION_PROMPT,
    MODEL_DISPLAY_NAMES,
    format_eta,
    init_crash_logging,
    log_exception,
    get_diagnostic_log_content,
    CRASH_LOG_PATH,
)


class TestConfigManager(unittest.TestCase):
    def test_config_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_file = Path(td) / "test_config.json"
            cfg = ConfigManager(config_path=cfg_file)
            
            # Default check
            self.assertTrue(Path(cfg.output_directory).exists())
            self.assertEqual(cfg.model_selection, DEFAULT_MODEL_DISPLAY)
            self.assertEqual(cfg.model_selection, "Maximum Accuracy (large-v3-turbo - Best Punctuation)")
            
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
            self.assertIn("Timestamped Transcript", md_text)

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

    def test_sqlite_wal_and_schema(self):
        from app import HistoryManager
        import sqlite3
        with tempfile.TemporaryDirectory() as td:
            db_file = Path(td) / "test_store.db"
            hm = HistoryManager(history_path=db_file)
            self.assertTrue(db_file.exists())

            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            self.assertEqual(mode.lower(), "wal")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall()}
            self.assertIn("transcriptions", tables)
            self.assertIn("transcriptions_fts", tables)
            conn.close()

    def test_auto_migration_from_legacy_json(self):
        from app import HistoryManager
        import json
        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td)
            legacy_json = temp_path / "legacy_history.json"
            dummy_data = [
                {
                    "id": "migrated_1",
                    "title": "Migrated Reel",
                    "source_filename": "reel.mp4",
                    "duration_str": "00:45",
                    "created_at": "2026-10-15 12:00",
                    "model": "small.en",
                    "paragraphs_file": "",
                    "timecoded_file": "",
                    "markdown_file": "",
                    "word_count": 42,
                }
            ]
            legacy_json.write_text(json.dumps(dummy_data), encoding="utf-8")

            hm = HistoryManager(history_path=legacy_json)
            self.assertEqual(len(hm.records), 1)
            self.assertEqual(hm.records[0].id, "migrated_1")
            self.assertEqual(hm.records[0].title, "Migrated Reel")

            self.assertFalse(legacy_json.exists())
            bak_file = temp_path / "legacy_history.json.bak"
            self.assertTrue(bak_file.exists())

    def test_fts5_search_and_snippets(self):
        from app import HistoryManager, HistoryRecord, SearchResult
        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td)
            db_file = temp_path / "fts_test.db"
            hm = HistoryManager(history_path=db_file)

            p1 = temp_path / "botanical_paragraphs.txt"
            p1.write_text("Infusing organic lavender blossoms with sweet almond elixir.", encoding="utf-8")

            p2 = temp_path / "herbal_paragraphs.txt"
            p2.write_text("Harvesting wild rosemary needles under the waxing moon.", encoding="utf-8")

            r1 = HistoryRecord(
                id="rec_lavender",
                title="Botanical Salve",
                source_filename="salve.mp4",
                duration_str="01:30",
                created_at="2026-10-10 10:00",
                model="small.en",
                paragraphs_file=str(p1),
                timecoded_file="",
                markdown_file="",
                word_count=8,
            )
            r2 = HistoryRecord(
                id="rec_rosemary",
                title="Herbal Moon Ritual",
                source_filename="ritual.mp4",
                duration_str="02:00",
                created_at="2026-10-11 11:00",
                model="small.en",
                paragraphs_file=str(p2),
                timecoded_file="",
                markdown_file="",
                word_count=8,
            )
            hm.add_or_update(r1)
            hm.add_or_update(r2)

            # 1. Search for "lavender" -> matches r1
            results = hm.search_with_snippets("lavender")
            self.assertEqual(len(results), 1)
            res = results[0]

            # Test SearchResult direct attributes
            self.assertEqual(res.id, "rec_lavender")
            self.assertEqual(res.title, "Botanical Salve")
            self.assertIsNotNone(res.snippet)
            self.assertIn("lavender", res.snippet.lower())

            # Test SearchResult 2-tuple unpacking
            rec_unpacked, snip_unpacked = res
            self.assertEqual(rec_unpacked.id, "rec_lavender")
            self.assertIn("lavender", snip_unpacked.lower())

            # 2. Multi-token search across title and content: "moon rosemary" -> matches r2
            results_m = hm.search_with_snippets("moon rosemary")
            self.assertEqual(len(results_m), 1)
            self.assertEqual(results_m[0].id, "rec_rosemary")

            # 3. Empty query returns all records
            all_res = hm.search_with_snippets("")
            self.assertEqual(len(all_res), 2)
            for item in all_res:
                self.assertIsNone(item.snippet)

            # 4. Non-matching query returns empty list
            no_res = hm.search_with_snippets("nonexistent_apothecary_keyword_xyz")
            self.assertEqual(len(no_res), 0)

    def test_favorite_and_delete_operations(self):
        from app import HistoryManager, HistoryRecord
        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td)
            db_file = temp_path / "ops_test.db"
            hm = HistoryManager(history_path=db_file)

            p_file = temp_path / "item_paragraphs.txt"
            p_file.write_text("Content to be deleted.", encoding="utf-8")

            r1 = HistoryRecord(
                id="rec_fav",
                title="Favorite Test",
                source_filename="fav.mp4",
                duration_str="01:00",
                created_at="2026-10-01 10:00",
                model="small.en",
                paragraphs_file=str(p_file),
                timecoded_file="",
                markdown_file="",
                word_count=4,
            )
            hm.add_or_update(r1)
            self.assertFalse(hm.get_by_id("rec_fav").is_favorite)

            # Toggle favorite ON
            new_state = hm.toggle_favorite("rec_fav")
            self.assertTrue(new_state)
            self.assertTrue(hm.get_by_id("rec_fav").is_favorite)

            # Toggle favorite OFF
            new_state = hm.toggle_favorite("rec_fav")
            self.assertFalse(new_state)
            self.assertFalse(hm.get_by_id("rec_fav").is_favorite)

            # Test delete with file purge
            self.assertTrue(p_file.exists())
            del_success = hm.delete("rec_fav", delete_files=True)
            self.assertTrue(del_success)
            self.assertIsNone(hm.get_by_id("rec_fav"))
            self.assertEqual(len(hm.records), 0)
            self.assertFalse(p_file.exists(), "Associated file should be purged on delete")

            # Delete non-existent record returns False
            self.assertFalse(hm.delete("non_existent_id"))



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
        self.assertIsNotNone(app.record_mic_btn)
        self.assertIsNotNone(app.select_file_btn)
        self.assertIsNotNone(app.url_entry)
        self.assertIsNotNone(app.paste_url_btn)
        self.assertIsNotNone(app.cookie_dropdown)
        self.assertIsNotNone(app.generate_btn)
        self.assertIsNotNone(app.model_dropdown)
        self.assertIsNotNone(app.textbox)
        self.assertIsNotNone(app.view_selector)
        self.assertIn("⏱️ Timestamped", app.view_selector.cget("values"))
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

        # Test Dialogs (instantiation without errors and keyboard dismiss bindings)
        try:
            qg = QuickGuideDialog(app)
            self.assertTrue(bool(qg.bind("<Escape>")))
            qg.destroy()
        except Exception as e:
            self.fail(f"QuickGuideDialog failed: {e}")

        try:
            ab = AboutDialog(app)
            self.assertTrue(bool(ab.bind("<Escape>")))
            ab.destroy()
        except Exception as e:
            self.fail(f"AboutDialog failed: {e}")

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

        def fake_download_audio_to_temp(
            url,
            temp_dir,
            cancel_event,
            status_cb=None,
            progress_cb=None,
            cookie_browser_label="",
            cookie_permission_cb=None,
        ):
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
            music_names = [p.name for p in controller.music_files]
            self.assertIn("The Green Leaf Thief.mp3", music_names, "Should discover 'The Green Leaf Thief.mp3'")
            self.assertIn("Where You Gonna Run.mp3", music_names, "Should discover 'Where You Gonna Run.mp3'")
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

            # Test focus inside Text widget
            mock_text_focus = MagicMock()
            mock_text_focus.winfo_class.return_value = "Text"
            app.focus_get = MagicMock(return_value=mock_text_focus)
            self.assertIsNone(app._on_space_pressed_handler(None))

            # Test focus inside CTkTextbox/CTkEntry instance
            mock_ctk_focus = MagicMock(spec=ctk.CTkTextbox)
            mock_ctk_focus.winfo_class.return_value = "CustomWidget"
            app.focus_get = MagicMock(return_value=mock_ctk_focus)
            self.assertIsNone(app._on_space_pressed_handler(None))

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


class TestAuditRemediationAndEnhancements(unittest.TestCase):
    """Verifies the 6 post-audit fixes and enhancements."""

    def test_microphone_recorder_capture_and_scratch_cleanup(self):
        from faery_app.media.recorder import MicrophoneRecorder
        from faery_app.lifecycle.scratch import ScratchLifecycleManager
        import sounddevice as sd

        mock_stream = MagicMock()
        with patch.object(sd, "InputStream", return_value=mock_stream):
            recorder = MicrophoneRecorder()
            wav_path = recorder.start_recording()
            self.assertTrue(recorder.is_recording)
            self.assertTrue(wav_path.exists())
            self.assertTrue(wav_path.parent.name.startswith("faery_mic_"))
            self.assertIn(wav_path.parent.resolve(), ScratchLifecycleManager._active_scratch_dirs)

            # Feed 1 second (16,000 samples) of 16-bit mono PCM audio frames
            synthetic_pcm = b"\x10\x00" * 16000
            recorder._audio_callback(synthetic_pcm, 16000, None, None)

            out_path, meta = recorder.stop_recording()
            self.assertFalse(recorder.is_recording)
            self.assertEqual(out_path, wav_path)
            self.assertTrue(out_path.exists())
            self.assertTrue(meta.has_audio)
            self.assertGreaterEqual(meta.duration_seconds, 0.9)
            self.assertEqual(meta.format_name, "Microphone WAV")

            temp_dir = wav_path.parent
            recorder.cleanup()
            self.assertFalse(wav_path.exists())
            self.assertFalse(temp_dir.exists())
            self.assertNotIn(temp_dir.resolve(), ScratchLifecycleManager._active_scratch_dirs)

    def test_brave_cookie_option_and_fallback(self):
        from faery_app.constants import COOKIE_BROWSER_OPTIONS
        from faery_app.media.online_fetcher import OnlineMediaFetcher
        import yt_dlp

        self.assertIn("Brave", COOKIE_BROWSER_OPTIONS)
        self.assertEqual(COOKIE_BROWSER_OPTIONS["Brave"], "brave")

        captured_opts = []

        class FakeYDL:
            def __init__(self, opts):
                captured_opts.append(opts)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

            def extract_info(self, url, download=True):
                outtmpl = captured_opts[-1]["outtmpl"]
                target_dir = Path(outtmpl).parent
                if captured_opts[-1].get("cookiesfrombrowser") == ("brave",):
                    (target_dir / "online_source_b123.m4a").write_bytes(b"audio_bytes")
                    return {"id": "b123", "title": "Brave Test Clip", "duration": 5.0}
                raise Exception("ERROR: Sign in to confirm your age")

        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            cancel_event = threading.Event()
            with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
                # 1. Explicit Brave selection
                info = OnlineMediaFetcher.download_audio_to_temp(
                    url="https://www.instagram.com/reel/b123/",
                    temp_dir=temp_dir,
                    cancel_event=cancel_event,
                    cookie_browser_label="Brave",
                )
                self.assertEqual(len(captured_opts), 1)
                self.assertEqual(captured_opts[0].get("cookiesfrombrowser"), ("brave",))
                self.assertEqual(info.video_id, "b123")

                # 2. Auto fallback when permitted includes Brave
                captured_opts.clear()
                info2 = OnlineMediaFetcher.download_audio_to_temp(
                    url="https://www.instagram.com/reel/b123/",
                    temp_dir=temp_dir,
                    cancel_event=cancel_event,
                    cookie_browser_label="Auto / Public (Recommended)",
                    cookie_permission_cb=lambda platform: True,
                )
                browser_attempts = [opt.get("cookiesfrombrowser") for opt in captured_opts]
                self.assertIsNone(browser_attempts[0])
                self.assertIn(("brave",), browser_attempts)
                self.assertEqual(info2.video_id, "b123")

    def test_auto_cookie_permission_dialog_gating(self):
        from faery_app.media.online_fetcher import OnlineMediaFetcher
        import yt_dlp

        captured_opts = []

        class FakeAuthWallYDL:
            def __init__(self, opts):
                captured_opts.append(opts)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

            def extract_info(self, url, download=True):
                outtmpl = captured_opts[-1]["outtmpl"]
                target_dir = Path(outtmpl).parent
                if captured_opts[-1].get("cookiesfrombrowser") is not None:
                    (target_dir / "online_source_auth1.m4a").write_bytes(b"audio_bytes")
                    return {"id": "auth1", "title": "Auth Clip", "duration": 4.0}
                raise Exception("ERROR: Sign in to confirm")

        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            cancel_event = threading.Event()
            with patch.object(yt_dlp, "YoutubeDL", FakeAuthWallYDL):
                # 1. Permission denied (False) -> called ONLY once (anonymous), zero browser cookies read
                captured_opts.clear()
                with self.assertRaises(RuntimeError):
                    OnlineMediaFetcher.download_audio_to_temp(
                        url="https://www.instagram.com/reel/auth1/",
                        temp_dir=temp_dir,
                        cancel_event=cancel_event,
                        cookie_browser_label="Auto / Public (Recommended)",
                        cookie_permission_cb=lambda platform: False,
                    )
                self.assertEqual(len(captured_opts), 1)
                self.assertNotIn("cookiesfrombrowser", captured_opts[0])

                # 2. Permission callback None -> called ONLY once (anonymous), zero browser cookies read
                captured_opts.clear()
                with self.assertRaises(RuntimeError):
                    OnlineMediaFetcher.download_audio_to_temp(
                        url="https://www.instagram.com/reel/auth1/",
                        temp_dir=temp_dir,
                        cancel_event=cancel_event,
                        cookie_browser_label="Auto / Public (Recommended)",
                        cookie_permission_cb=None,
                    )
                self.assertEqual(len(captured_opts), 1)
                self.assertNotIn("cookiesfrombrowser", captured_opts[0])

                # 3. Permission granted (True) -> retries with browser cookies and succeeds
                captured_opts.clear()
                info = OnlineMediaFetcher.download_audio_to_temp(
                    url="https://www.instagram.com/reel/auth1/",
                    temp_dir=temp_dir,
                    cancel_event=cancel_event,
                    cookie_browser_label="Auto / Public (Recommended)",
                    cookie_permission_cb=lambda platform: True,
                )
                self.assertGreaterEqual(len(captured_opts), 2)
                self.assertNotIn("cookiesfrombrowser", captured_opts[0])
                self.assertIn("cookiesfrombrowser", captured_opts[1])
                self.assertEqual(info.video_id, "auth1")

    def test_deno_runtime_discovery(self):
        from faery_app.media.online_fetcher import OnlineMediaFetcher
        import yt_dlp

        deno_bin = OnlineMediaFetcher._get_deno_executable()
        self.assertIsNotNone(deno_bin, "Should resolve deno executable from installed deno package")
        self.assertTrue(Path(deno_bin).is_file(), f"Resolved deno path must exist: {deno_bin}")

        captured_opts = []

        class FakeDenoCheckYDL:
            def __init__(self, opts):
                captured_opts.append(opts)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

            def extract_info(self, url, download=True):
                outtmpl = captured_opts[-1]["outtmpl"]
                target_dir = Path(outtmpl).parent
                (target_dir / "online_source_yt1.m4a").write_bytes(b"audio_bytes")
                return {"id": "yt1", "title": "YouTube JS Challenge Clip", "duration": 6.0}

        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            cancel_event = threading.Event()
            with patch.object(yt_dlp, "YoutubeDL", FakeDenoCheckYDL):
                OnlineMediaFetcher.download_audio_to_temp(
                    url="https://www.youtube.com/watch?v=yt1",
                    temp_dir=temp_dir,
                    cancel_event=cancel_event,
                )
                self.assertEqual(len(captured_opts), 1)
                self.assertIn("js_runtimes", captured_opts[0])
                self.assertIn("deno", captured_opts[0]["js_runtimes"])
                self.assertEqual(captured_opts[0]["js_runtimes"]["deno"]["path"], deno_bin)

    def test_updater_upgrade_runtime_dependencies(self):
        from faery_app.lifecycle.updater import AutoUpdater

        # 1. When frozen (standalone bundle), returns False without calling subprocess.run
        with patch.object(AutoUpdater, "is_standalone_bundle", return_value=True), \
             patch("subprocess.run") as mock_run:
            self.assertFalse(AutoUpdater.upgrade_runtime_dependencies())
            mock_run.assert_not_called()

        # 2. When not frozen, invokes pip install --upgrade yt-dlp[default] yt-dlp-ejs deno
        mock_proc = MagicMock(returncode=0)
        with patch.object(AutoUpdater, "is_standalone_bundle", return_value=False), \
             patch("subprocess.run", return_value=mock_proc) as mock_run:
            self.assertTrue(AutoUpdater.upgrade_runtime_dependencies())
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            self.assertEqual(cmd[:5], [sys.executable, "-m", "pip", "install", "--upgrade"])
            self.assertIn("yt-dlp[default]", cmd)
            self.assertIn("yt-dlp-ejs", cmd)
            self.assertIn("deno", cmd)

    def test_timestamped_framing_and_macos_mic_plist(self):
        from faery_app.transcription.engine import TranscriptionEngine
        from faery_app.ui.views.transcribe_view import TranscribeStudioView
        import inspect

        meta = MediaMetadata(
            path=Path("clip.mp4"),
            file_size_bytes=1024,
            duration_seconds=15.0,
            has_audio=True,
            format_name="mp4",
        )
        segs = [TranscriptSegment(start=0.0, end=3.0, text="Hello apothecary world.")]
        md = TranscriptionEngine._build_markdown(meta, "small.en", "Hello apothecary world.", segs)
        self.assertIn("## Timestamped Transcript", md)
        self.assertNotIn("YouTube Chapters", md)

        view_src = inspect.getsource(TranscribeStudioView.build)
        self.assertIn("record_mic_btn", view_src)
        self.assertIn("⏱️ Timestamped", view_src)
        self.assertNotIn("YouTube Chapters", view_src)

        with tempfile.TemporaryDirectory() as td:
            bundle_dir = Path(td) / "Faery Good Transcriber.app"
            _create_macos_app_bundle(bundle_dir, repo_dir=Path(__file__).resolve().parent)
            plist_file = bundle_dir / "Contents" / "Info.plist"
            self.assertTrue(plist_file.is_file())
            with open(plist_file, "rb") as fp:
                plist_data = plistlib.load(fp)
            self.assertIn("NSMicrophoneUsageDescription", plist_data)
            self.assertIn("microphone", plist_data["NSMicrophoneUsageDescription"].lower())


class TestPerformanceOptimizations(unittest.TestCase):
    """Verifies Phases 1–4 runtime, I/O, SQLite, and UI performance optimizations."""

    def test_wav_fast_path_probe_and_16k_extract_bypass(self):
        import wave

        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            wav_path = temp_dir / "fast_16k_mono.wav"
            out_wav = temp_dir / "extracted_out.wav"

            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x08\x00" * 16000)

            self.assertTrue(MediaProcessor.is_16k_mono_pcm_wav(wav_path))

            with patch("subprocess.run") as mock_run:
                meta = MediaProcessor.probe_file(wav_path)
                mock_run.assert_not_called()
                self.assertTrue(meta.has_audio)
                self.assertEqual(meta.format_name, "wav")
                self.assertAlmostEqual(meta.duration_seconds, 1.0, places=2)

            with patch("subprocess.Popen") as mock_popen:
                MediaProcessor.extract_16k_mono_wav(wav_path, out_wav, threading.Event())
                mock_popen.assert_not_called()
                self.assertTrue(out_wav.exists())
                self.assertTrue(MediaProcessor.is_16k_mono_pcm_wav(out_wav))

    def test_cached_ffmpeg_and_deno_lookup(self):
        from faery_app.media.online_fetcher import OnlineMediaFetcher

        exe1 = get_verified_ffmpeg_exe()
        self.assertTrue(Path(exe1).is_file())
        with patch("imageio_ffmpeg.get_ffmpeg_exe") as mock_get_ffmpeg:
            exe2 = get_verified_ffmpeg_exe()
            mock_get_ffmpeg.assert_not_called()
            self.assertEqual(exe1, exe2)

        deno1 = OnlineMediaFetcher._get_deno_executable()
        self.assertIsNotNone(deno1)
        self.assertTrue(Path(deno1).is_file())
        self.assertEqual(OnlineMediaFetcher._cached_deno_exe, deno1)
        with patch("shutil.which") as mock_which:
            deno2 = OnlineMediaFetcher._get_deno_executable()
            mock_which.assert_not_called()
            self.assertEqual(deno1, deno2)

    def test_adaptive_cpu_threads(self):
        # 1. Fallback heuristic based on logical core count:
        # 2 logical -> 2 physical -> 2 threads
        # 4 logical -> 4 physical -> 4 threads
        # 8 logical -> 4 physical (capped to physical cores) -> 4 threads
        # 16 logical -> 8 physical -> 8 threads
        with patch("sys.platform", "win32"), patch.dict("sys.modules", {"psutil": None}):
            for cores, expected in [(2, 2), (4, 4), (8, 4), (16, 8)]:
                with patch("os.cpu_count", return_value=cores):
                    self.assertEqual(TranscriptionEngine.get_optimal_cpu_threads(), expected)

        # 2. macOS physical core detection via sysctl (Ericka's MacBook Pro 1068NG7)
        with patch("sys.platform", "darwin"), patch("subprocess.check_output", return_value="4"):
            self.assertEqual(TranscriptionEngine.get_optimal_cpu_threads(), 4)

        # 3. macOS physical core detection with 2 cores
        with patch("sys.platform", "darwin"), patch("subprocess.check_output", return_value="2"):
            self.assertEqual(TranscriptionEngine.get_optimal_cpu_threads(), 2)

        # 4. macOS sysctl failure fallbacks gracefully
        with patch("sys.platform", "darwin"), patch("subprocess.check_output", side_effect=Exception("error")), patch.dict("sys.modules", {"psutil": None}):
            with patch("os.cpu_count", return_value=8):
                self.assertEqual(TranscriptionEngine.get_optimal_cpu_threads(), 4)

    def test_prevent_app_nap_lifecycle(self):
        from faery_app.utils.macos import prevent_app_nap
        from unittest.mock import MagicMock

        # On non-darwin: does nothing
        with patch("sys.platform", "win32"):
            with patch("subprocess.Popen") as mock_popen:
                with prevent_app_nap():
                    pass
                mock_popen.assert_not_called()

        # On darwin: launches caffeinate and terminates it
        with patch("sys.platform", "darwin"):
            mock_proc = MagicMock()
            with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
                with prevent_app_nap():
                    mock_popen.assert_called_once()
                mock_proc.terminate.assert_called_once()
                mock_proc.wait.assert_called_once()

    def test_intel_openmp_env_vars(self):
        self.assertEqual(os.environ.get("KMP_BLOCKTIME"), "0")
        self.assertEqual(os.environ.get("OMP_WAIT_POLICY"), "PASSIVE")

    def test_history_single_record_content_update_and_in_place_selection(self):
        from app import HistoryManager, HistoryRecord

        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td)
            db_file = temp_path / "perf_hist.db"
            hm = HistoryManager(history_path=db_file)

            p1 = temp_path / "clip1_paragraphs.txt"
            p2 = temp_path / "clip2_paragraphs.txt"
            p1.write_text("initial short text", encoding="utf-8")
            p2.write_text("second clip text", encoding="utf-8")

            r1 = HistoryRecord(
                id="rec_perf_1",
                title="First Clip",
                source_filename="clip1.mp4",
                duration_str="00:10",
                created_at="2026-11-05 10:00",
                model="small.en",
                paragraphs_file=str(p1),
                timecoded_file="",
                markdown_file="",
                word_count=3,
            )
            r2 = HistoryRecord(
                id="rec_perf_2",
                title="Second Clip",
                source_filename="clip2.mp4",
                duration_str="00:20",
                created_at="2026-11-05 10:05",
                model="small.en",
                paragraphs_file=str(p2),
                timecoded_file="",
                markdown_file="",
                word_count=3,
            )
            hm.add_or_update(r1)
            hm.add_or_update(r2)

            updated = hm.update_record_content("rec_perf_1", "new edited text with seven spoken words")
            self.assertIsNotNone(updated)
            self.assertEqual(updated.word_count, 7)
            self.assertEqual(hm.get_by_id("rec_perf_1").word_count, 7)

            hits = hm.search_with_snippets("seven")
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].id, "rec_perf_1")

            app = FaeryTranscriberApp()
            app.withdraw()
            try:
                app.history = hm
                app._refresh_history_list(filter_text="", resync=False)
                self.assertIn("rec_perf_1", app._history_card_widgets)
                self.assertIn("rec_perf_2", app._history_card_widgets)

                card_ref_1 = app._history_card_widgets["rec_perf_1"][0]
                card_ref_2 = app._history_card_widgets["rec_perf_2"][0]

                app._select_history_item("rec_perf_1")
                self.assertIs(app._history_card_widgets["rec_perf_1"][0], card_ref_1)
                self.assertIn("🦋", app._history_card_widgets["rec_perf_1"][1].cget("text"))

                app._select_history_item("rec_perf_2")
                self.assertIs(app._history_card_widgets["rec_perf_1"][0], card_ref_1)
                self.assertIs(app._history_card_widgets["rec_perf_2"][0], card_ref_2)
                self.assertNotIn("🦋", app._history_card_widgets["rec_perf_1"][1].cget("text"))
                self.assertIn("🦋", app._history_card_widgets["rec_perf_2"][1].cget("text"))
            finally:
                app.radio_controller.stop()
                app.destroy()

    def test_radio_tick_idle_when_off(self):
        app = FaeryTranscriberApp()
        app.withdraw()
        try:
            self.assertFalse(app.config.radio_enabled)
            self.assertIsNone(app._radio_after_id)

            app.radio_toggle.select()
            app._on_radio_toggle_changed()
            self.assertTrue(app.config.radio_enabled)
            self.assertIsNotNone(app._radio_after_id)

            app._close_radio_player()
            self.assertFalse(app.config.radio_enabled)
            self.assertIsNone(app._radio_after_id)
        finally:
            app.radio_controller.stop()
            app.destroy()


class TestCrashLoggerAndTaskETA(unittest.TestCase):
    """
    Test suite for:
    1. format_eta formatting across boundaries.
    2. ConfigManager model_rtf getter, EMA updater, and persistence.
    3. Silent Rotating Diagnostic & Crash Logger and get_diagnostic_log_content.
    4. TranscriptionEngine self-calibrating live RTF countdown and dynamic recalculation.
    """

    def test_format_eta_boundaries(self):
        # < 15s boundary
        self.assertEqual(format_eta(0), "a few seconds")
        self.assertEqual(format_eta(5), "a few seconds")
        self.assertEqual(format_eta(14.9), "a few seconds")

        # < 60s boundary
        self.assertEqual(format_eta(15), "15s")
        self.assertEqual(format_eta(45), "45s")
        self.assertEqual(format_eta(59), "59s")

        # < 3600s boundary
        self.assertEqual(format_eta(60), "1 min")
        self.assertEqual(format_eta(75), "1m 15s")
        self.assertEqual(format_eta(120), "2 min")
        self.assertEqual(format_eta(600), "10 min")
        self.assertEqual(format_eta(725), "12m 5s")

        # >= 3600s boundary
        self.assertEqual(format_eta(3600), "1h 0m")
        self.assertEqual(format_eta(3660), "1h 1m")
        self.assertEqual(format_eta(7325), "2h 2m")

    def test_config_manager_model_rtf(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "test_config.json"
            cfg = ConfigManager(cfg_path)

            # Test defaults
            self.assertAlmostEqual(cfg.get_model_rtf("large-v3-turbo"), 0.48)
            self.assertAlmostEqual(cfg.get_model_rtf("turbo"), 0.48)
            self.assertAlmostEqual(cfg.get_model_rtf("Maximum Accuracy (large-v3-turbo - Best Punctuation)"), 0.48)
            self.assertAlmostEqual(cfg.get_model_rtf("Maximum Accuracy"), 0.48)
            self.assertAlmostEqual(cfg.get_model_rtf("small.en"), 0.35)
            self.assertAlmostEqual(cfg.get_model_rtf("High Accuracy (small.en - Fast)"), 0.35)
            self.assertAlmostEqual(cfg.get_model_rtf("High Accuracy (small.en - Recommended)"), 0.35)
            self.assertAlmostEqual(cfg.get_model_rtf("base.en"), 0.15)
            self.assertAlmostEqual(cfg.get_model_rtf("Standard Draft (base.en - Ultra Fast)"), 0.15)
            self.assertAlmostEqual(cfg.get_model_rtf("Standard (base.en - Fast)"), 0.15)

            # Test EMA update: 0.7 * 0.35 + 0.3 * 0.15 = 0.245 + 0.045 = 0.29
            cfg.update_model_rtf("small.en", 0.15)
            self.assertAlmostEqual(cfg.get_model_rtf("small.en"), 0.29, places=3)
            self.assertAlmostEqual(cfg.get_model_rtf("High Accuracy (small.en - Recommended)"), 0.29, places=3)

            # Test EMA update for large-v3-turbo: 0.7 * 0.48 + 0.3 * 0.40 = 0.336 + 0.120 = 0.456
            cfg.update_model_rtf("large-v3-turbo", 0.40)
            self.assertAlmostEqual(cfg.get_model_rtf("large-v3-turbo"), 0.456, places=3)
            self.assertAlmostEqual(cfg.get_model_rtf("Maximum Accuracy (large-v3-turbo - Best Punctuation)"), 0.456, places=3)

            # Test persistence in new instance
            cfg2 = ConfigManager(cfg_path)
            self.assertAlmostEqual(cfg2.get_model_rtf("small.en"), 0.29, places=3)
            self.assertAlmostEqual(cfg2.get_model_rtf("large-v3-turbo"), 0.456, places=3)

            # Test clamping to [0.05, 3.0]
            cfg.update_model_rtf("small.en", 10.0)
            self.assertLessEqual(cfg.get_model_rtf("small.en"), 3.0)

            cfg.update_model_rtf("small.en", 0.0001)
            self.assertGreaterEqual(cfg.get_model_rtf("small.en"), 0.05)

    def test_crash_logger_and_diagnostics(self):
        with tempfile.TemporaryDirectory() as td:
            fake_log_path = Path(td) / "test_crash.log"
            import faery_app.lifecycle.crash_logger as cl

            try:
                with patch.object(cl, "CRASH_LOG_PATH", fake_log_path):
                    # Reset module initialized state for clean test run
                    cl._initialized = False
                    cl._logger.handlers.clear()

                    cl.init_crash_logging()
                    self.assertTrue(cl._initialized)

                    # Log string message
                    cl.log_exception("Manual test log failure", context="TranscribeTest")
                    self.assertTrue(fake_log_path.exists())
                    content = cl.get_diagnostic_log_content()
                    self.assertIn("Manual test log failure", content)
                    self.assertIn("[TranscribeTest]", content)

                    # Log exception instance
                    try:
                        raise ValueError("Simulated invalid parameter exception")
                    except ValueError as exc:
                        cl.log_exception(exc, context="ExceptionTest")

                    content2 = cl.get_diagnostic_log_content()
                    self.assertIn("Simulated invalid parameter exception", content2)
                    self.assertIn("ValueError", content2)

                # Test fallback diagnostic summary when log file is missing
                missing_log = Path(td) / "does_not_exist.log"
                with patch.object(cl, "CRASH_LOG_PATH", missing_log):
                    summary = cl.get_diagnostic_log_content()
                    self.assertIn("Faery Transcriber Diagnostic Summary", summary)
                    self.assertIn("Python Version:", summary)
                    self.assertIn("OS:", summary)
            finally:
                cl.shutdown_crash_logging()

    def test_transcription_engine_rtf_updating(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "engine_cfg.json"
            cfg = ConfigManager(cfg_path)
            engine = TranscriptionEngine(config_manager=cfg)

            mock_meta = MediaMetadata(
                path=Path(td) / "sample_audio.mp4",
                file_size_bytes=2048,
                duration_seconds=30.0,
                has_audio=True,
                format_name="mp4",
            )

            class MockSegment:
                def __init__(self, start, end, text):
                    self.start = start
                    self.end = end
                    self.text = text

            mock_segments = [
                MockSegment(0.0, 15.0, "First segment"),
                MockSegment(15.0, 30.0, "Second segment"),
            ]
            mock_info = MagicMock(duration=30.0)
            mock_model = MagicMock()
            mock_model.transcribe.return_value = (iter(mock_segments), mock_info)

            status_messages = []
            progress_values = []

            with patch.object(engine, "get_model", return_value=mock_model), \
                 patch("faery_app.media.processor.MediaProcessor.extract_16k_mono_wav"), \
                 patch("faery_app.utils.system.check_free_disk_space", return_value=True):

                cancel_ev = threading.Event()
                # Simulate 30s audio taking 6.0s wall clock time (observed RTF = 0.20)
                # Call sequence: t_start = 100.0, loop seg1 = 103.0, loop seg2 = 106.0, complete = 106.0
                with patch("time.monotonic", side_effect=[100.0, 100.0, 103.0, 106.0, 106.0]):
                    engine.run_transcription(
                        media_file=Path(td) / "sample_audio.mp4",
                        media_meta=mock_meta,
                        model_name="small.en",
                        output_dir=Path(td),
                        cancel_event=cancel_ev,
                        status_cb=status_messages.append,
                        progress_cb=progress_values.append,
                        segment_cb=lambda s: None,
                        overwrite=True,
                    )

            # Verify countdown ETA was emitted in status updates
            self.assertTrue(any("remaining" in msg for msg in status_messages))
            # Verify RTF updated: 0.7 * 0.35 + 0.3 * (6.0 / 30.0 = 0.20) = 0.305
            self.assertAlmostEqual(cfg.get_model_rtf("small.en"), 0.305, places=3)

            # Verify transcribe received initial_prompt and condition_on_previous_text
            mock_model.transcribe.assert_called_once()
            _, kwargs = mock_model.transcribe.call_args
            self.assertEqual(kwargs.get("initial_prompt"), DEFAULT_PUNCTUATION_PROMPT)
            self.assertTrue(kwargs.get("condition_on_previous_text"))

    def test_dynamic_metadata_display_and_model_switching(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "ui_cfg.json"
            cfg = ConfigManager(cfg_path)
            meta = MediaMetadata(
                path=Path(td) / "tea_session.mp4",
                file_size_bytes=15 * 1024 * 1024,
                duration_seconds=600.0,  # 10 minutes -> 600 * 0.35 = 210s >= 120s -> tea hint!
                has_audio=True,
                format_name="mp4",
            )

            app = FaeryTranscriberApp()
            app.withdraw()
            try:
                app.config = cfg
                app.config_manager = cfg
                app.selected_file = meta.path
                app.current_media_meta = meta

                # Test High Accuracy initial metadata display
                app.model_dropdown.set("High Accuracy (small.en - Recommended)")
                app._update_file_metadata_display(meta)

                label_text_high = app.file_meta_label.cget("text")
                self.assertIn("10:00", label_text_high)
                self.assertIn("Est. time:", label_text_high)
                self.assertIn("☕ (time for tea!)", label_text_high)

                # Dynamically switch model to Standard (base.en)
                app.model_dropdown.set("Standard (base.en - Fast)")
                app._on_model_changed("Standard (base.en - Fast)")

                label_text_base = app.file_meta_label.cget("text")
                self.assertIn("Est. time:", label_text_base)
                # Estimated time should have changed dynamically
                self.assertNotEqual(label_text_high, label_text_base)
            finally:
                app.radio_controller.stop()
                app.destroy()


class TestFormattersAndEdgeCases(unittest.TestCase):
    """
    Test suite for Punctuation & Model Accuracy Optimization:
    1. TranscriptFormatter.to_paragraphs boundary healing:
       - Trailing commas, colons, semicolons converted to periods on paragraph closure.
       - Unpunctuated paragraph ends closed with periods when ending in alphanumeric characters.
       - Paragraph starts capitalized when beginning with lowercase.
       - Terminal punctuation preserved (. ! ? ." !" ?" ” …).
    2. MODEL_DISPLAY_NAMES and DEFAULT_MODEL_DISPLAY contain large-v3-turbo.
    3. ConfigManager RTF lookup for large-v3-turbo and turbo aliases.
    4. TranscriptionEngine uses initial_prompt=DEFAULT_PUNCTUATION_PROMPT.
    """

    def test_model_constants_and_displays(self):
        self.assertIn("Maximum Accuracy (large-v3-turbo - Best Punctuation)", MODEL_DISPLAY_NAMES)
        self.assertEqual(
            MODEL_DISPLAY_NAMES["Maximum Accuracy (large-v3-turbo - Best Punctuation)"],
            "large-v3-turbo",
        )
        self.assertEqual(
            DEFAULT_MODEL_DISPLAY,
            "Maximum Accuracy (large-v3-turbo - Best Punctuation)",
        )
        self.assertIn("large-v3-turbo", DEFAULT_MODEL_DISPLAY)
        self.assertIn("Best Punctuation", DEFAULT_MODEL_DISPLAY)
        self.assertTrue(len(DEFAULT_PUNCTUATION_PROMPT) > 20)
        self.assertIn("punctuation", DEFAULT_PUNCTUATION_PROMPT.lower())

    def test_config_manager_large_v3_turbo_rtf_lookup(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = ConfigManager(Path(td) / "test_cfg.json")
            # Default lookup
            self.assertAlmostEqual(cfg.get_model_rtf("large-v3-turbo"), 0.48)
            self.assertAlmostEqual(cfg.get_model_rtf("turbo"), 0.48)
            self.assertAlmostEqual(cfg.get_model_rtf("Maximum Accuracy"), 0.48)
            self.assertAlmostEqual(cfg.get_model_rtf(DEFAULT_MODEL_DISPLAY), 0.48)
            # Canonical normalization
            self.assertEqual(ConfigManager._canonical_model_key("large-v3-turbo"), "large-v3-turbo")
            self.assertEqual(ConfigManager._canonical_model_key("turbo"), "large-v3-turbo")
            self.assertEqual(ConfigManager._canonical_model_key("Maximum Accuracy"), "large-v3-turbo")
            self.assertEqual(ConfigManager._canonical_model_key(DEFAULT_MODEL_DISPLAY), "large-v3-turbo")

    def test_to_paragraphs_boundary_healing_trailing_punctuation(self):
        from app import TranscriptFormatter
        # Trailing comma, colon, semicolon converted to period on boundary close
        segs = [
            TranscriptSegment(start=0.0, end=2.0, text="First introductory clause,"),
            TranscriptSegment(start=4.0, end=6.0, text="second section follows:"),
            TranscriptSegment(start=8.0, end=10.0, text="third section note;"),
            TranscriptSegment(start=12.0, end=14.0, text="final clause without punctuation"),
        ]
        result = TranscriptFormatter.to_paragraphs(segs, pause_threshold_sec=1.0)
        paras = result.split("\n\n")
        self.assertEqual(len(paras), 4)
        # Comma replaced with period
        self.assertEqual(paras[0], "First introductory clause.")
        # Colon replaced with period, lowercase capitalized
        self.assertEqual(paras[1], "Second section follows.")
        # Semicolon replaced with period, lowercase capitalized
        self.assertEqual(paras[2], "Third section note.")
        # Alphanumeric end closed with period, lowercase capitalized
        self.assertEqual(paras[3], "Final clause without punctuation.")

    def test_to_paragraphs_boundary_healing_capitalization_and_preservation(self):
        from app import TranscriptFormatter
        # Paragraph starts capitalized; valid terminal punctuation preserved
        segs = [
            TranscriptSegment(start=0.0, end=2.0, text="good morning to the faery apothecary!"),
            TranscriptSegment(start=4.0, end=6.0, text="are these herbs fresh?"),
            TranscriptSegment(start=8.0, end=10.0, text="she whispered, \"whimsy is power.\""),
            TranscriptSegment(start=12.0, end=14.0, text="and the journey continues…"),
        ]
        result = TranscriptFormatter.to_paragraphs(segs, pause_threshold_sec=1.0)
        paras = result.split("\n\n")
        self.assertEqual(len(paras), 4)
        self.assertEqual(paras[0], "Good morning to the faery apothecary!")
        self.assertEqual(paras[1], "Are these herbs fresh?")
        self.assertEqual(paras[2], "She whispered, \"whimsy is power.\"")
        self.assertEqual(paras[3], "And the journey continues…")

    def test_to_paragraphs_boundary_healing_trailing_whitespace_and_empty(self):
        from app import TranscriptFormatter
        self.assertEqual(TranscriptFormatter.to_paragraphs([]), "")
        segs = [
            TranscriptSegment(start=0.0, end=2.0, text="  hello world,   "),
        ]
        result = TranscriptFormatter.to_paragraphs(segs)
        self.assertEqual(result, "Hello world.")

    def test_transcription_engine_uses_punctuation_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = ConfigManager(Path(td) / "prompt_cfg.json")
            engine = TranscriptionEngine(config_manager=cfg)

            mock_meta = MediaMetadata(
                path=Path(td) / "audio.mp4",
                file_size_bytes=1024,
                duration_seconds=5.0,
                has_audio=True,
                format_name="mp4",
            )
            mock_model = MagicMock()
            mock_model.transcribe.return_value = (iter([]), MagicMock(duration=5.0))

            with patch.object(engine, "get_model", return_value=mock_model), \
                 patch("faery_app.media.processor.MediaProcessor.extract_16k_mono_wav"), \
                 patch("faery_app.utils.system.check_free_disk_space", return_value=True):

                engine.run_transcription(
                    media_file=Path(td) / "audio.mp4",
                    media_meta=mock_meta,
                    model_name="large-v3-turbo",
                    output_dir=Path(td),
                    cancel_event=threading.Event(),
                    status_cb=lambda s: None,
                    progress_cb=lambda p: None,
                    segment_cb=lambda s: None,
                    overwrite=True,
                )

            mock_model.transcribe.assert_called_once()
            _, kwargs = mock_model.transcribe.call_args
            self.assertEqual(kwargs.get("initial_prompt"), DEFAULT_PUNCTUATION_PROMPT)
            self.assertTrue(kwargs.get("condition_on_previous_text"))


class TestLauncherScripts(unittest.TestCase):
    """
    Verifies launcher script invariants for macOS (Run_Mac.command)
    and Windows (Run_Windows.bat), ensuring Python >= 3.10 enforcement,
    stale virtual environment auto-reset, and seamless installer flows.
    """

    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).parent
        cls.mac_script = cls.repo_root / "Run_Mac.command"
        cls.win_script = cls.repo_root / "Run_Windows.bat"

    def test_run_mac_script_exists_and_invariants(self):
        self.assertTrue(self.mac_script.exists(), "Run_Mac.command must exist")
        content = self.mac_script.read_text(encoding="utf-8")

        # 1. is_valid_python function definition
        self.assertIn("is_valid_python()", content)
        self.assertIn("sys.version_info >= (3, 10)", content)

        # 2. Prioritized Python candidate paths
        expected_candidates = [
            "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
            "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
            "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
            "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3",
            "/usr/local/bin/python3.13",
            "/usr/local/bin/python3.12",
            "/usr/local/bin/python3.11",
            "/usr/local/bin/python3.10",
            "/opt/homebrew/bin/python3.13",
            "/opt/homebrew/bin/python3.12",
            "/opt/homebrew/bin/python3.11",
            "/opt/homebrew/bin/python3.10",
            ".pyenv/shims/python3",
            "miniforge3/bin/python3",
            "miniconda3/bin/python3",
            "which python3.13",
            "which python3.12",
            "which python3.11",
            "which python3.10",
        ]
        for cand in expected_candidates:
            self.assertIn(cand, content, f"Missing expected candidate: {cand}")

        # 3. Candidate evaluation loop must invoke is_valid_python
        self.assertIn('if is_valid_python "$cmd"; then', content)

    def test_run_mac_stale_venv_reset_logic(self):
        content = self.mac_script.read_text(encoding="utf-8")

        # Must verify .venv/bin/python and remove stale .venv
        self.assertIn('if [ -d ".venv" ]; then', content)
        self.assertIn('! is_valid_python ".venv/bin/python"', content)
        self.assertIn('rm -rf ".venv"', content)

    def test_run_mac_frictionless_installer_flow(self):
        content = self.mac_script.read_text(encoding="utf-8")

        # Verify friendly AppleScript prompt and download target
        self.assertIn("Python 3.12 Required", content)
        self.assertIn("Apple's older built-in Python 3.9", content)
        self.assertIn("https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg", content)
        self.assertIn("/tmp/python-3.12.10-macos11.pkg", content)
        self.assertIn("https://www.python.org/downloads/macos/", content)
        self.assertIn('open "$PKG_PATH"', content)
        self.assertIn("Python 3.12 Installer Started", content)

    def test_run_windows_script_exists_and_invariants(self):
        self.assertTrue(self.win_script.exists(), "Run_Windows.bat must exist")
        content = self.win_script.read_text(encoding="utf-8")

        # 1. Enforce sys.version_info >= (3, 10) in PATH and py launcher
        self.assertIn("sys.version_info >= (3, 10)", content)
        self.assertNotIn("sys.version_info.major == 3", content)

        # 2. Candidate scans must only search 313, 312, 311, 310 (39 and 38 removed)
        self.assertIn("(313 312 311 310)", content)
        self.assertNotIn("39 38", content)

        # 3. Stale virtual environment detection & reset
        self.assertIn('rmdir /s /q ".venv"', content)

        # 4. Prompt specifies Python 3.10+
        self.assertIn("Python 3.10 or newer", content)
        self.assertIn("Python 3.10+ Required", content)

    def test_python_version_comparison_logic(self):
        """Validates that sys.version_info >= (3, 10) correctly categorizes Python versions."""
        def check_version(v_tuple):
            return v_tuple >= (3, 10)

        # Outdated / EOL versions that should be rejected
        self.assertFalse(check_version((2, 7, 18)))
        self.assertFalse(check_version((3, 7, 17)))
        self.assertFalse(check_version((3, 8, 18)))
        self.assertFalse(check_version((3, 9, 6)))   # macOS Sonoma default Xcode stub
        self.assertFalse(check_version((3, 9, 18)))

        # Supported versions (Python 3.10+)
        self.assertTrue(check_version((3, 10, 0)))
        self.assertTrue(check_version((3, 10, 13)))
        self.assertTrue(check_version((3, 11, 0)))
        self.assertTrue(check_version((3, 11, 8)))
        self.assertTrue(check_version((3, 12, 0)))
        self.assertTrue(check_version((3, 12, 10)))
        self.assertTrue(check_version((3, 13, 0)))

    def test_stale_venv_detection_simulation(self):
        """Simulates checking a virtual environment interpreter's version tuple."""
        with tempfile.TemporaryDirectory() as td:
            venv_dir = Path(td) / ".venv"
            venv_dir.mkdir()

            def evaluate_venv_staleness(version_tuple):
                is_valid = version_tuple >= (3, 10)
                if not is_valid:
                    return "RESET"
                return "KEEP"

            self.assertEqual(evaluate_venv_staleness((3, 9, 6)), "RESET")
            self.assertEqual(evaluate_venv_staleness((3, 8, 10)), "RESET")
            self.assertEqual(evaluate_venv_staleness((3, 12, 2)), "KEEP")

    def test_prepare_audio_input_bypasses_pyav(self):
        """Verifies 16kHz mono PCM WAV files decode directly to float32 numpy arrays without PyAV."""
        import wave
        import numpy as np
        from app import TranscriptionEngine

        with tempfile.TemporaryDirectory() as td:
            wav_path = Path(td) / "test_16k.wav"
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                samples = np.array([0, 16384, -16384, 32767], dtype="<i2")
                wf.writeframes(samples.tobytes())

            arr = TranscriptionEngine._prepare_audio_input(wav_path)
            self.assertIsInstance(arr, np.ndarray)
            self.assertEqual(arr.dtype, np.float32)
            self.assertEqual(len(arr), 4)
            self.assertAlmostEqual(float(arr[1]), 0.5, places=4)
            self.assertAlmostEqual(float(arr[2]), -0.5, places=4)

            # Non-existent path falls back gracefully to string path
            missing = Path(td) / "missing.wav"
            self.assertEqual(TranscriptionEngine._prepare_audio_input(missing), str(missing))


if __name__ == "__main__":
    unittest.main()



