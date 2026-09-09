"""Main window GUI for Media Player PRO.

Implements the approved UI design and wires the Player controller and
Playlist model together. Scope is limited to Step 2 features:
- Show playlist, add songs, select & double-click to play
- Play / Pause / Stop / Previous / Next
- Now Playing + Status display
(Progress slider, volume, mute, auto-play, icon, and error handling are
intentionally deferred to later steps.)
"""

from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from media_player.player import Player


class MainWindow(QMainWindow):
    """Main application window holding all widgets and wiring."""

    def __init__(self) -> None:
        super().__init__()
        self.player = Player()

        self.setWindowTitle("Media Player PRO")
        self.setMinimumSize(480, 520)

        self._slider_pressed = False

        self._build_ui()
        self._connect_signals()

    # ---- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Header
        header = QLabel("MEDIA PLAYER PRO")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            "font-size: 22px; font-weight: bold; padding: 8px;"
        )
        root.addWidget(header)

        # Now playing
        self.now_playing_label = QLabel("Now Playing: -")
        self.now_playing_label.setStyleSheet(
            "font-weight: bold; padding: 4px;"
        )
        root.addWidget(self.now_playing_label)

        # Progress slider + time (Step 3)
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 0)
        self.progress_slider.setEnabled(False)
        root.addWidget(self.progress_slider)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.time_label)

        # Volume + mute (Step 4)
        volume_row = QHBoxLayout()
        self.mute_btn = QPushButton("Mute")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_label = QLabel("100%")
        volume_row.addWidget(self.mute_btn)
        volume_row.addWidget(self.volume_slider, stretch=1)
        volume_row.addWidget(self.volume_label)
        root.addLayout(volume_row)

        # Transport controls
        transport = QHBoxLayout()
        self.prev_btn = QPushButton("Previous")
        self.play_btn = QPushButton("Play")
        self.pause_btn = QPushButton("Pause")
        self.stop_btn = QPushButton("Stop")
        self.next_btn = QPushButton("Next")
        for btn in (
            self.prev_btn,
            self.play_btn,
            self.pause_btn,
            self.stop_btn,
            self.next_btn,
        ):
            transport.addWidget(btn)
        root.addLayout(transport)

        # Playlist
        playlist_label = QLabel("Playlist")
        root.addWidget(playlist_label)
        self.playlist_widget = QListWidget()
        root.addWidget(self.playlist_widget)

        # Playlist actions
        actions = QHBoxLayout()
        self.add_btn = QPushButton("Add Songs")
        self.remove_btn = QPushButton("Remove")
        self.clear_btn = QPushButton("Clear Playlist")
        actions.addWidget(self.add_btn)
        actions.addWidget(self.remove_btn)
        actions.addWidget(self.clear_btn)
        root.addLayout(actions)

        # Status
        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet(
            "color: gray; padding: 4px;"
        )
        root.addWidget(self.status_label)

    # ---- signal wiring ---------------------------------------------------

    def _connect_signals(self) -> None:
        self.add_btn.clicked.connect(self.add_songs)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn.clicked.connect(self.clear_playlist)

        self.play_btn.clicked.connect(self.play_selected)
        self.pause_btn.clicked.connect(self.pause)
        self.stop_btn.clicked.connect(self.stop)
        self.prev_btn.clicked.connect(self.play_previous)
        self.next_btn.clicked.connect(self.play_next)

        self.playlist_widget.itemDoubleClicked.connect(self._on_double_click)

        self.player.track_changed.connect(self._on_track_changed)
        self.player.state_changed.connect(self._on_state_changed)
        self.player.progress_changed.connect(self._on_progress_changed)
        self.player.duration_changed.connect(self._on_duration_changed)

        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)

        self.volume_slider.valueChanged.connect(self._on_volume_slider)
        self.mute_btn.clicked.connect(self._on_mute_clicked)
        self.player.volume_changed.connect(self._on_volume_changed)
        self.player.muted_changed.connect(self._on_muted_changed)
        self.player.error_occurred.connect(self._on_error_occurred)

    # ---- slots -----------------------------------------------------------

    def add_songs(self) -> None:
        """Open a file dialog and add selected songs to the playlist."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Songs",
            "",
            "Audio Files (*.mp3 *.wav *.ogg);;All Files (*)",
        )
        if not files:
            return
        self.player.playlist.add(files)
        for path in files:
            self.playlist_widget.addItem(QListWidgetItem(path))
        self._set_status(f"Added {len(files)} song(s)")

    def remove_selected(self) -> None:
        """Remove the currently selected song from the playlist."""
        row = self.playlist_widget.currentRow()
        if row < 0:
            self._set_status("No song selected to remove")
            return
        removed = self.player.playlist.remove(row)
        if removed is None:
            self._set_status("Nothing to remove")
            return
        self.playlist_widget.takeItem(row)
        self._set_status(f"Removed: {removed}")

    def clear_playlist(self) -> None:
        """Clear the whole playlist (kept simple for Step 2, no confirm)."""
        self.player.playlist.clear()
        self.playlist_widget.clear()
        self._set_status("Playlist cleared")

    def play_selected(self) -> None:
        """Play the song at the selected list row."""
        row = self.playlist_widget.currentRow()
        if row < 0:
            self._set_status("Select a song to play")
            return
        self.player.play_selected(row)

    def pause(self) -> None:
        self.player.pause()

    def stop(self) -> None:
        self.player.stop()

    def play_previous(self) -> None:
        self.player.play_previous()

    def play_next(self) -> None:
        self.player.play_next()

    def _on_double_click(self, _item: QListWidgetItem) -> None:
        """Double-clicking a playlist row plays that track immediately."""
        row = self.playlist_widget.currentRow()
        if row >= 0:
            self.player.play_selected(row)

    # ---- UI updates ------------------------------------------------------

    def _on_track_changed(self, path: str) -> None:
        self.now_playing_label.setText(f"Now Playing: {path}")

    def _on_state_changed(self, state: str) -> None:
        self._set_status(state)

    # ---- progress / seek handlers ----------------------------------------

    def _on_progress_changed(self, position_ms: int) -> None:
        """Update the slider/time from playback, unless the user is dragging."""
        if not self._slider_pressed:
            self.progress_slider.setValue(position_ms)
        self.time_label.setText(f"{_format_time(position_ms)} / {_format_time(self.progress_slider.maximum())}")

    def _on_duration_changed(self, duration_ms: int) -> None:
        """Update the slider range and total time when duration is known."""
        self.progress_slider.setRange(0, max(0, duration_ms))
        self.progress_slider.setEnabled(not self.player.playlist.is_empty)
        self.time_label.setText(f"{_format_time(self.progress_slider.value())} / {_format_time(duration_ms)}")

    def _on_slider_pressed(self) -> None:
        self._slider_pressed = True

    def _on_slider_released(self) -> None:
        self._slider_pressed = False
        self.player.seek(self.progress_slider.value())

    # ---- volume / mute handlers ------------------------------------------

    def _on_volume_slider(self, value: int) -> None:
        self.player.set_volume(value)
        self.volume_label.setText(f"{value}%")

    def _on_volume_changed(self, percent: int) -> None:
        self.volume_slider.setValue(percent)
        self.volume_label.setText(f"{percent}%")

    def _on_mute_clicked(self) -> None:
        self.player.toggle_mute()

    def _on_muted_changed(self, muted: bool) -> None:
        self.mute_btn.setText("Unmute" if muted else "Mute")

    def _on_error_occurred(self, message: str) -> None:
        """Show an error dialog and update status (app keeps running)."""
        self._set_status(f"Error: {message}")
        QMessageBox.warning(
            self,
            "Playback Error",
            f"Could not play the selected file.\n\n{message}",
        )

    def _set_status(self, message: str) -> None:
        self.status_label.setText(f"Status: {message}")


def _format_time(ms: int) -> str:
    """Format milliseconds as MM:SS (e.g. 225000 -> 03:45)."""
    total_seconds = max(0, ms) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"
