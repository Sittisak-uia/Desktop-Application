"""Audio player controller for Media Player PRO.

Wraps PyQt6's QMediaPlayer + QAudioOutput and drives media selection via
the Playlist model from Step 1. The GUI layer talks to this controller and
receives state updates through Qt signals.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

from media_player.playlist import Playlist


class Player(QObject):
    """Thin controller over QMediaPlayer/QAudioOutput.

    Owns the media state machine (play / pause / stop / change track).
    Playlist navigation (next/previous) is delegated to the Playlist model.
    """

    # Signals emitted to update the GUI.
    track_changed = pyqtSignal(str)          # now-playing track path
    state_changed = pyqtSignal(str)          # human-readable playback state
    progress_changed = pyqtSignal(int)       # current position in ms
    duration_changed = pyqtSignal(int)       # total duration in ms
    volume_changed = pyqtSignal(int)         # volume in percent (0-100)
    muted_changed = pyqtSignal(bool)         # mute state
    error_occurred = pyqtSignal(str)         # human-readable error message

    def __init__(self) -> None:
        super().__init__()
        self._playlist: Playlist = Playlist()
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        self._player.mediaStatusChanged.connect(self._on_media_status)
        self._player.positionChanged.connect(
            lambda pos: self.progress_changed.emit(int(pos))
        )
        self._player.durationChanged.connect(
            lambda dur: self.duration_changed.emit(int(dur))
        )
        self._audio_output.volumeChanged.connect(
            lambda v: self.volume_changed.emit(int(round(v * 100)))
        )
        self._audio_output.mutedChanged.connect(self.muted_changed)
        self._player.errorOccurred.connect(self._on_error)

    # ---- playlist accessor ----------------------------------------------

    @property
    def playlist(self) -> Playlist:
        """The shared Playlist model (no copy - single source of truth)."""
        return self._playlist

    # ---- track loading / navigation -------------------------------------

    def load_track(self, path: str | None) -> None:
        """Load a track into the player (does not auto-play)."""
        if not path:
            return
        self._player.setSource(QUrl.fromLocalFile(path))
        self.track_changed.emit(path)

    def play_current(self) -> None:
        """Load and play the current track from the playlist."""
        current = self._playlist.current()
        if current is None:
            self.state_changed.emit("idle - no song selected")
            return
        self.load_track(current)
        self._player.play()
        self.state_changed.emit("playing")

    def play_selected(self, index: int | None) -> None:
        """Select a track by index and play it.

        If the selected track is already loaded, resume playback from the
        current position. Otherwise load the track and start it.
        """
        if index is None:
            return
        current_track = self._playlist.current()
        selected = self._playlist.select(index)
        if selected is None:
            return
        if current_track == selected and not self._player.source().isEmpty():
            # Same track already loaded (e.g. paused) -> resume, keep position.
            self._player.play()
            self.state_changed.emit("playing")
            return
        self.load_track(selected)
        self._player.play()
        self.state_changed.emit("playing")

    def pause(self) -> None:
        """Pause playback, keeping the current position."""
        if self._playlist.is_empty:
            return
        self._player.pause()
        self.state_changed.emit("paused")

    def stop(self) -> None:
        """Stop playback and reset the position to 0."""
        if self._playlist.is_empty:
            return
        self._player.stop()
        self.state_changed.emit("stopped")

    def seek(self, position_ms: int) -> None:
        """Seek to an absolute position (in milliseconds)."""
        if self._playlist.is_empty:
            return
        self._player.setPosition(position_ms)

    # ---- volume / mute ---------------------------------------------------

    def set_volume(self, percent: int) -> None:
        """Set the output volume. ``percent`` is clamped to 0-100."""
        percent = max(0, min(100, percent))
        self._audio_output.setVolume(percent / 100.0)

    def toggle_mute(self) -> None:
        """Flip the muted state without changing the stored volume level."""
        self._audio_output.setMuted(not self._audio_output.isMuted())

    def volume(self) -> int:
        """Return the current volume as a percentage (0-100)."""
        return int(round(self._audio_output.volume() * 100))

    def play_previous(self) -> None:
        """Play the previous track (wraps to the last)."""
        if self._playlist.is_empty:
            self.state_changed.emit("idle - playlist empty")
            return
        previous = self._playlist.previous()
        self.load_track(previous)
        self._player.play()
        self.state_changed.emit("playing")

    def play_next(self) -> None:
        """Play the next track (wraps to the first)."""
        if self._playlist.is_empty:
            self.state_changed.emit("idle - playlist empty")
            return
        following = self._playlist.next()
        self.load_track(following)
        self._player.play()
        self.state_changed.emit("playing")

    # ---- media state handling -------------------------------------------

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        """Handle auto-play on EndOfMedia; LoadedMedia stays a no-op."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._playlist.is_empty:
                return
            next_track = self._playlist.next()
            self.load_track(next_track)
            self._player.play()

    def _on_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """Handle QMediaPlayer errors without crashing the app."""
        self.state_changed.emit("error")
        if error != QMediaPlayer.Error.NoError:
            self.error_occurred.emit(error_string)
