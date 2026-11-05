"""
Faery Good Radio (104.9 The Grift FM) - Ambient Music & DJ Engine Controller
"""

from __future__ import annotations

import random
import re
import sys
import time
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from faery_app.config.config_manager import ConfigManager
from faery_app.constants import get_assets_dir, get_music_dir, get_announcer_dir
from faery_app.media.processor import MediaProcessor
from faery_app.radio.types import RadioTrackType


class RadioStationController:
    """Manages audio playback and GTA-style radio scheduling for 104.9 The Grift FM.

    Rules:
    - Songs play in rotation from assets/music (or assets/Audio/music).
    - Between each song, an announcer message plays (preventing recent repeats, GTA style).
    - With a higher chance (35%), the Liability disclaimer plays instead of a standard announcer message.
    - With the same rate (35%), right before a song starts, the Grift message ("You're on the grift.") plays.
    """

    RATE: float = 0.35  # 35% higher chance for Liability & pre-song Grift bumper

    def __init__(self, config: ConfigManager, assets_dir: Optional[Path] = None):
        self.config = config
        self.assets_dir = assets_dir or get_assets_dir()

        self.music_files: List[Path] = []
        self.liability_file: Optional[Path] = None
        self.grift_file: Optional[Path] = None
        self.regular_announcers: List[Path] = []

        self.songs_playlist: List[Path] = []
        self.current_song_idx: int = -1

        self.current_track_path: Optional[Path] = None
        self.current_track_type: str = RadioTrackType.SONG
        self.current_track_title: str = "104.9 The Grift FM"
        self.current_track_subtitle: str = "Faery Good Radio"
        self.current_duration: float = 0.0
        self.current_start_time: float = 0.0
        self.current_seek_offset: float = 0.0

        self.is_playing: bool = False
        self.is_paused: bool = False
        self.is_muted: bool = False
        self._prev_unmuted_volume: float = self.config.radio_volume or 0.7
        self.volume: float = self._prev_unmuted_volume

        self.recent_announcers: deque[str] = deque(maxlen=4)
        self.last_was_liability: bool = False
        self._pending_song: Optional[Tuple[Path, str, str]] = None
        self._duration_cache: Dict[str, float] = {}
        self._mixer_initialized: bool = False

        self.rescan_audio_assets()

    def rescan_audio_assets(self) -> None:
        """Discovers music, announcer, Liability, and Grift audio tracks from assets."""
        music_d = get_music_dir()
        announcer_d = get_announcer_dir()

        # 1. Music files
        if music_d.exists() and music_d.is_dir():
            self.music_files = sorted(
                [p for p in music_d.glob("*") if p.suffix.lower() in [".mp3", ".wav", ".m4a", ".ogg"]],
                key=lambda p: p.name.lower(),
            )
        else:
            self.music_files = []

        # 2. Announcers, Liability & Grift files
        all_announcers: List[Path] = []
        if announcer_d.exists() and announcer_d.is_dir():
            all_announcers = sorted(
                [p for p in announcer_d.glob("*") if p.suffix.lower() in [".mp3", ".wav", ".m4a", ".ogg"]],
                key=lambda p: p.name.lower(),
            )

        self.liability_file = None
        self.grift_file = None
        numbered_announcers: List[Path] = []
        other_announcers: List[Path] = []

        for p in all_announcers:
            stem_low = p.stem.lower()
            if "liability" in stem_low:
                self.liability_file = p
            elif "grift" in stem_low:
                self.grift_file = p
            elif re.search(r"announcer\s*\d+", stem_low):
                numbered_announcers.append(p)
            elif stem_low != "announcer":  # Exclude uncut 2-minute master compilation if numbered exist
                other_announcers.append(p)

        if numbered_announcers:
            self.regular_announcers = numbered_announcers + other_announcers
        elif other_announcers:
            self.regular_announcers = other_announcers
        else:
            # Fallback to any remaining clips if numbered ones aren't present
            self.regular_announcers = [p for p in all_announcers if p not in (self.liability_file, self.grift_file)]

        self._reshuffle_songs()

    def _ensure_mixer(self) -> bool:
        """Initializes pygame.mixer safely on demand."""
        if self._mixer_initialized:
            return True
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.music.set_volume(0.0 if self.is_muted else self.volume)
            self._mixer_initialized = True
            return True
        except Exception as err:
            print(f"[Faery Radio] Audio mixer init error: {err}", file=sys.stderr)
            return False

    def _reshuffle_songs(self) -> None:
        """Creates a fresh randomized playlist without repeating the last played song back-to-back."""
        if not self.music_files:
            self.songs_playlist = []
            self.current_song_idx = -1
            return
        songs = list(self.music_files)
        random.shuffle(songs)
        if len(songs) > 1 and self.current_track_path and songs[0] == self.current_track_path:
            songs[0], songs[-1] = songs[-1], songs[0]
        self.songs_playlist = songs
        self.current_song_idx = 0

    def get_duration(self, path: Optional[Path]) -> float:
        """Returns track duration in seconds with memory caching."""
        if not path or not path.exists():
            return 0.0
        s_path = str(path)
        if s_path in self._duration_cache:
            return self._duration_cache[s_path]
        try:
            meta = MediaProcessor.probe_file(path)
            dur = meta.duration_seconds if meta.duration_seconds > 0 else 0.0
            self._duration_cache[s_path] = dur
            return dur
        except Exception:
            return 0.0

    def _play_file(self, path: Path, track_type: str, title: str, subtitle: str, start_offset: float = 0.0) -> bool:
        """Loads and plays an audio file through pygame.mixer.music with optional start offset."""
        if not self._ensure_mixer():
            return False
        try:
            import pygame
            pygame.mixer.music.load(str(path))
            if start_offset > 0.0:
                pygame.mixer.music.play(start=start_offset)
            else:
                pygame.mixer.music.play()
            self.current_track_path = path
            self.current_track_type = track_type
            self.current_track_title = title
            self.current_track_subtitle = subtitle
            self.current_duration = self.get_duration(path)
            self.current_seek_offset = start_offset
            self.current_start_time = time.time()
            self.is_paused = False
            self.is_playing = True
            return True
        except Exception as err:
            print(f"[Faery Radio] Error playing '{path.name}': {err}", file=sys.stderr)
            return False

    def seek_to(self, target_seconds: float) -> bool:
        """Jumps to a specific timestamp in the current track (0.0 to current_duration)."""
        if not self.is_playing or not self.current_track_path:
            return False
        if not self._ensure_mixer():
            return False
        clamped_pos = max(0.0, min(self.current_duration - 0.2, float(target_seconds)))
        return self._play_file(
            self.current_track_path,
            self.current_track_type,
            self.current_track_title,
            self.current_track_subtitle,
            start_offset=clamped_pos,
        )

    def _pick_next_announcer(self) -> Tuple[Optional[Path], str, str, str]:
        """Selects the next announcer clip.
        - With 35% chance, plays Liability.mp3 (if not played in the immediately preceding interlude).
        - Otherwise, uniformly selects from regular announcer clips not in recent history (GTA radio style).
        """
        # 1. Higher chance for Liability disclaimer
        if self.liability_file and not self.last_was_liability and random.random() < self.RATE:
            self.last_was_liability = True
            return (
                self.liability_file,
                RadioTrackType.LIABILITY,
                "🎙️ Faery Legal Disclaimer",
                "104.9 The Grift FM  ·  Station Advisory",
            )

        # 2. GTA-style anti-repeat pool for regular announcers
        candidates = [p for p in self.regular_announcers if p.name not in self.recent_announcers]
        if not candidates:
            last_name = self.recent_announcers[-1] if self.recent_announcers else None
            candidates = [p for p in self.regular_announcers if p.name != last_name]
        if not candidates:
            candidates = list(self.regular_announcers)

        if not candidates:
            # Fallback if no regular announcers exist but liability does
            if self.liability_file:
                self.last_was_liability = True
                return (
                    self.liability_file,
                    RadioTrackType.LIABILITY,
                    "🎙️ Faery Legal Disclaimer",
                    "104.9 The Grift FM  ·  Station Advisory",
                )
            return (None, RadioTrackType.ANNOUNCER, "🎙️ Station DJ", "104.9 The Grift FM")

        chosen = random.choice(candidates)
        self.recent_announcers.append(chosen.name)
        self.last_was_liability = False
        return (
            chosen,
            RadioTrackType.ANNOUNCER,
            "🎙️ On Air: Station DJ",
            "104.9 The Grift FM  ·  Faery Good Radio",
        )

    def _prepare_and_play_song(self, song_path: Path) -> None:
        """Plays a song, optionally preceded by Grift.mp3 bumper at the same rate."""
        clean_title = song_path.stem
        subtitle = "104.9 The Grift FM  ·  Faery Good Radio"

        # Check if the Grift bumper should play right before this song (same rate: 35%)
        if self.grift_file and random.random() < self.RATE:
            self._pending_song = (song_path, clean_title, subtitle)
            self._play_file(
                self.grift_file,
                RadioTrackType.GRIFT,
                '🎙️ "You\'re on the grift"',
                "104.9 The Grift FM  ·  Station Bumper",
            )
        else:
            self._pending_song = None
            self._play_file(song_path, RadioTrackType.SONG, clean_title, subtitle)

    def start(self) -> None:
        """Starts radio broadcasting."""
        if not self.music_files:
            self.rescan_audio_assets()
        if not self.music_files:
            self.current_track_title = "No Music Files Found"
            self.current_track_subtitle = "Place MP3 files in assets/music"
            self.is_playing = False
            return

        if not self.songs_playlist or self.current_song_idx < 0:
            self._reshuffle_songs()

        if self.current_song_idx >= len(self.songs_playlist):
            self._reshuffle_songs()

        first_song = self.songs_playlist[self.current_song_idx]
        self.current_song_idx += 1
        self._prepare_and_play_song(first_song)

    def stop(self) -> None:
        """Stops radio playback and releases audio output."""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        self.is_playing = False
        self.is_paused = False
        self._pending_song = None

    def toggle_play_pause(self) -> None:
        """Toggles between playing and paused state."""
        if not self._ensure_mixer():
            return
        import pygame
        if not self.is_playing:
            self.start()
            return
        if self.is_paused:
            try:
                pygame.mixer.music.unpause()
                self.is_paused = False
            except Exception:
                pass
        else:
            try:
                pygame.mixer.music.pause()
                self.is_paused = True
            except Exception:
                pass

    def next_song(self) -> None:
        """Skips immediately to the next song in the rotation."""
        if not self.music_files:
            return
        if not self.songs_playlist or self.current_song_idx >= len(self.songs_playlist):
            self._reshuffle_songs()

        next_song = self.songs_playlist[self.current_song_idx]
        self.current_song_idx += 1
        self._pending_song = None
        self._prepare_and_play_song(next_song)

    def prev_song(self) -> None:
        """Restarts current track or skips to the previous song if near start."""
        if not self.music_files:
            return
        elapsed = self.get_elapsed_seconds()
        if elapsed > 3.0 and self.current_track_path:
            # Replay current track from 0:00
            self._play_file(
                self.current_track_path,
                self.current_track_type,
                self.current_track_title,
                self.current_track_subtitle,
            )
            return

        # Step back to previous song
        if len(self.songs_playlist) > 0:
            self.current_song_idx = max(0, self.current_song_idx - 2)
            prev_song = self.songs_playlist[self.current_song_idx]
            self.current_song_idx += 1
            self._pending_song = None
            self._prepare_and_play_song(prev_song)

    def set_volume(self, vol: float) -> None:
        """Updates playback volume (0.0 to 1.0) and persists in user config."""
        clamped = max(0.0, min(1.0, float(vol)))
        self.volume = clamped
        self.config.radio_volume = clamped
        if clamped > 0.0:
            self.is_muted = False
            self._prev_unmuted_volume = clamped
        if self._ensure_mixer():
            import pygame
            try:
                pygame.mixer.music.set_volume(0.0 if self.is_muted else self.volume)
            except Exception:
                pass

    def toggle_mute(self) -> None:
        """Toggles audio mute state."""
        if self.is_muted:
            self.is_muted = False
            self.set_volume(self._prev_unmuted_volume or 0.7)
        else:
            self._prev_unmuted_volume = self.volume if self.volume > 0.05 else 0.7
            self.is_muted = True
            if self._ensure_mixer():
                import pygame
                try:
                    pygame.mixer.music.set_volume(0.0)
                except Exception:
                    pass

    def check_and_advance(self) -> None:
        """Tick handler: detects track completion and advances the radio state machine."""
        if not self.is_playing or self.is_paused:
            return
        if not self._ensure_mixer():
            return
        import pygame
        try:
            busy = pygame.mixer.music.get_busy()
        except Exception:
            busy = False

        if not busy:
            # Current track has finished!
            if self.current_track_type == RadioTrackType.GRIFT:
                # Grift bumper finished -> immediately start the pending song
                if self._pending_song:
                    s_path, s_title, s_sub = self._pending_song
                    self._pending_song = None
                    self._play_file(s_path, RadioTrackType.SONG, s_title, s_sub)
                else:
                    self.next_song()

            elif self.current_track_type in (RadioTrackType.ANNOUNCER, RadioTrackType.LIABILITY):
                # Announcer interlude finished -> transition towards next song (checking Grift bumper)
                if not self.songs_playlist or self.current_song_idx >= len(self.songs_playlist):
                    self._reshuffle_songs()
                next_song = self.songs_playlist[self.current_song_idx]
                self.current_song_idx += 1
                self._prepare_and_play_song(next_song)

            elif self.current_track_type == RadioTrackType.SONG:
                # Song finished -> play an announcer interlude (Liability or DJ clip)
                ann_path, ann_type, ann_title, ann_sub = self._pick_next_announcer()
                if ann_path:
                    self._play_file(ann_path, ann_type, ann_title, ann_sub)
                else:
                    self.next_song()

    def get_elapsed_seconds(self) -> float:
        """Returns current playback position in seconds (incorporating seek offset)."""
        if not self.is_playing:
            return 0.0
        if not self._ensure_mixer():
            return 0.0
        import pygame
        try:
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms >= 0:
                elapsed = self.current_seek_offset + (pos_ms / 1000.0)
            else:
                elapsed = self.current_seek_offset + (time.time() - self.current_start_time)
        except Exception:
            elapsed = self.current_seek_offset + (time.time() - self.current_start_time)

        if self.current_duration > 0:
            return min(self.current_duration, max(0.0, elapsed))
        return max(0.0, elapsed)

    def get_progress(self) -> float:
        """Returns playback progress as a ratio between 0.0 and 1.0."""
        if self.current_duration <= 0.0:
            return 0.0
        return min(1.0, max(0.0, self.get_elapsed_seconds() / self.current_duration))
