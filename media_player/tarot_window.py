"""Tarot reading GUI for the Tarot App.

Implements the approved dark-fantasy UI design and wires the existing
TarotDeck model into the view. Features:
- TAROT READING header with "Past • Present • Future"
- Three horizontally arranged card panels (Past / Present / Future)
- Each panel shows a card image, name, and meaning (fallback placeholder
  when an image asset is missing)
- A prominent "DRAW 3 CARDS" button using the existing TarotDeck logic
- A music section with file selection, Play / Pause / Stop, a volume
  slider (0-100%, default 70%), and non-crashing error handling
- A status area
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from media_player.tarot import ReadingPosition, TarotCard, TarotDeck

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_IMAGE_BASE = os.path.join(_PACKAGE_DIR, "resources", "tarot")

_POSITIONS = (
    (ReadingPosition.PAST, "PAST"),
    (ReadingPosition.PRESENT, "PRESENT"),
    (ReadingPosition.FUTURE, "FUTURE"),
)

_STYLE_SHEET = """
QMainWindow {
    background-color: #14101c;
}
QWidget {
    color: #e8dcc8;
    font-family: 'Segoe UI';
}
#header {
    font-size: 34px;
    font-weight: bold;
    color: #f2e3b3;
    letter-spacing: 6px;
    padding: 16px 0 2px 0;
}
#subheader {
    font-size: 15px;
    color: #a08c6f;
    letter-spacing: 3px;
    padding-bottom: 8px;
}
#cardFrame {
    background-color: #241c33;
    border: 2px solid #5a4a76;
    border-radius: 12px;
    padding: 10px;
}
#cardTitle {
    font-size: 16px;
    font-weight: bold;
    color: #f2e3b3;
    letter-spacing: 3px;
}
#cardName {
    font-size: 14px;
    font-weight: bold;
    color: #e8dcc8;
    padding: 4px 0;
}
#cardMeaning {
    font-size: 12px;
    color: #c9bba6;
}
#imgArea {
    background-color: #181226;
    border: 1px solid #5a4a76;
    border-radius: 8px;
    min-height: 180px;
    max-height: 180px;
}
#placeholder {
    font-size: 12px;
    color: #8a7a60;
}
#drawBtn {
    background-color: #7a5a2e;
    color: #14101c;
    font-size: 18px;
    font-weight: bold;
    border: none;
    border-radius: 10px;
    padding: 14px;
    letter-spacing: 3px;
}
#drawBtn:hover {
    background-color: #9c7640;
}
#musicFrame {
    background-color: #1e1828;
    border: 1px solid #5a4a76;
    border-radius: 10px;
    padding: 10px;
}
#musicLabel {
    font-size: 13px;
    font-weight: bold;
    color: #a08c6f;
    letter-spacing: 3px;
}
#musicFileLabel {
    font-size: 11px;
    color: #c9bba6;
    padding: 2px 0;
}
#musicTransportBtn {
    background-color: #2a2140;
    color: #e8dcc8;
    font-size: 13px;
    font-weight: bold;
    border: 1px solid #5a4a76;
    border-radius: 6px;
    padding: 8px 14px;
}
#musicTransportBtn:hover {
    background-color: #3a2f5c;
}
#selectMusicBtn {
    background-color: #4a3a6a;
    color: #f2e3b3;
    font-size: 12px;
    font-weight: bold;
    border: 1px solid #6a5688;
    border-radius: 6px;
    padding: 8px 14px;
}
#selectMusicBtn:hover {
    background-color: #5a4a80;
}
#volumeLabel {
    font-size: 11px;
    color: #a08c6f;
}
#musicError {
    font-size: 11px;
    color: #e08a6a;
}
#status {
    font-size: 12px;
    color: #8a7a60;
    padding: 6px 0;
}
"""


class TarotWindow(QMainWindow):
    """Main application window for the Tarot App."""

    def __init__(self) -> None:
        super().__init__()
        self.deck = TarotDeck()
        self.card_frames: dict[ReadingPosition, QFrame] = {}
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.7)

        self.setWindowTitle("Tarot Reading")
        self.setMinimumSize(920, 680)
        self.setStyleSheet(_STYLE_SHEET)

        self._build_ui()
        self._connect_signals()

    # ---- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(12)

        header = QLabel("TAROT READING")
        header.setObjectName("header")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(header)

        subheader = QLabel("Past • Present • Future")
        subheader.setObjectName("subheader")
        subheader.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subheader)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        for position, title in _POSITIONS:
            frame = self._build_card_panel(position, title)
            self.card_frames[position] = frame
            cards_row.addWidget(frame, stretch=1)
        root.addLayout(cards_row, 1)

        self.draw_btn = QPushButton("DRAW 3 CARDS")
        self.draw_btn.setObjectName("drawBtn")
        self.draw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        root.addWidget(self.draw_btn)

        music_frame = self._build_music_ui()
        root.addWidget(music_frame)

        self.status_label = QLabel("Status: Ready")
        self.status_label.setObjectName("status")
        root.addWidget(self.status_label)

    def _build_card_panel(self, position: ReadingPosition, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("cardFrame")
        layout = QVBoxLayout(frame)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        img_area = QFrame()
        img_area.setObjectName("imgArea")
        img_layout = QVBoxLayout(img_area)
        frame.place = QLabel("Image coming soon")
        frame.place.setObjectName("placeholder")
        frame.place.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame.place.setWordWrap(True)
        frame.image = QLabel()
        frame.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame.image.setScaledContents(False)
        img_layout.addWidget(frame.place)
        img_layout.addWidget(frame.image)
        layout.addWidget(img_area, 1)

        frame.name_label = QLabel("—")
        frame.name_label.setObjectName("cardName")
        frame.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(frame.name_label)

        frame.meaning_label = QLabel("—")
        frame.meaning_label.setObjectName("cardMeaning")
        frame.meaning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame.meaning_label.setWordWrap(True)
        layout.addWidget(frame.meaning_label)

        return frame

    def _build_music_ui(self) -> QFrame:
        music_frame = QFrame()
        music_frame.setObjectName("musicFrame")
        music_layout = QVBoxLayout(music_frame)
        music_layout.setSpacing(8)

        music_label = QLabel("MUSIC")
        music_label.setObjectName("musicLabel")
        music_layout.addWidget(music_label)

        self.music_file_label = QLabel("No music selected")
        self.music_file_label.setObjectName("musicFileLabel")
        music_layout.addWidget(self.music_file_label)

        select_row = QHBoxLayout()
        self.select_music_btn = QPushButton("Select Music")
        self.select_music_btn.setObjectName("selectMusicBtn")
        self.select_music_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_row.addWidget(self.select_music_btn)
        select_row.addStretch(1)
        self.music_status_label = QLabel("Ready")
        self.music_status_label.setObjectName("musicFileLabel")
        select_row.addWidget(self.music_status_label)
        music_layout.addLayout(select_row)

        transport_row = QHBoxLayout()
        self.play_music_btn = QPushButton("Play")
        self.play_music_btn.setObjectName("musicTransportBtn")
        self.pause_music_btn = QPushButton("Pause")
        self.pause_music_btn.setObjectName("musicTransportBtn")
        self.stop_music_btn = QPushButton("Stop")
        self.stop_music_btn.setObjectName("musicTransportBtn")
        for btn in (self.play_music_btn, self.pause_music_btn, self.stop_music_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            transport_row.addWidget(btn)
        transport_row.addStretch(1)
        music_layout.addLayout(transport_row)

        volume_row = QHBoxLayout()
        volume_label = QLabel("Volume")
        volume_label.setObjectName("volumeLabel")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_value_label = QLabel("70%")
        self.volume_value_label.setObjectName("volumeLabel")
        volume_row.addWidget(volume_label)
        volume_row.addWidget(self.volume_slider, 1)
        volume_row.addWidget(self.volume_value_label)
        music_layout.addLayout(volume_row)

        self.music_error_label = QLabel("")
        self.music_error_label.setObjectName("musicError")
        self.music_error_label.setWordWrap(True)
        music_layout.addWidget(self.music_error_label)

        self._set_music_controls_enabled(False)
        return music_frame

    def _set_music_controls_enabled(self, enabled: bool) -> None:
        for btn in (self.play_music_btn, self.pause_music_btn, self.stop_music_btn):
            btn.setEnabled(enabled)

    # ---- signal wiring ---------------------------------------------------

    def _connect_signals(self) -> None:
        self.draw_btn.clicked.connect(self.draw_new_reading)

        self.select_music_btn.clicked.connect(self.select_music)
        self.play_music_btn.clicked.connect(self.play_music)
        self.pause_music_btn.clicked.connect(self.pause_music)
        self.stop_music_btn.clicked.connect(self.stop_music)

        self.volume_slider.valueChanged.connect(self._on_volume_slider)

        self.player.errorOccurred.connect(self._on_player_error)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)

    # ---- slots -----------------------------------------------------------

    def draw_new_reading(self) -> None:
        """Draw a new 3-card reading and update all three panels."""
        reading = self.deck.draw_reading()
        issues: list[str] = []
        for position in (ReadingPosition.PAST, ReadingPosition.PRESENT, ReadingPosition.FUTURE):
            self._populate_card(self.card_frames[position], reading.card(position), issues)
        summary = self._reading_summary(reading)
        if issues:
            self._set_status(f"Reading drawn: {summary} ({'; '.join(issues)})")
        else:
            self._set_status(f"Reading drawn: {summary}")

    # ---- music slots -----------------------------------------------------

    def select_music(self) -> None:
        """Open a file dialog and load the chosen audio file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Music",
            "",
            "Audio Files (*.mp3 *.wav *.ogg);;All Files (*)",
        )
        if not path:
            return
        self._load_music(path)

    def _load_music(self, path: str) -> None:
        """Point the media player at a file and reset error state."""
        self._clear_music_error()
        self.music_file_label.setText(os.path.basename(path))
        try:
            self.player.setSource(self._url_from_path(path))
            self.player.setPosition(0)
        except Exception:
            self.music_status_label.setText("Error")
            self.music_error_label.setText(
                "Could not load the selected music file. The file may be "
                "missing, corrupt, or locked by another program."
            )
            self._set_status("Music error: file could not be loaded")
            self.player.setSource(QUrl())
            self.player.stop()
            self._set_music_controls_enabled(False)
            return
        self._set_music_controls_enabled(True)
        self.music_status_label.setText("Loaded")
        self._set_status(f"Music loaded: {os.path.basename(path)}")

    @staticmethod
    def _url_from_path(path: str):
        return QUrl.fromLocalFile(path)

    def play_music(self) -> None:
        self._clear_music_error()
        self.player.play()
        self.music_status_label.setText("Playing")
        self._set_status("Music playing")

    def pause_music(self) -> None:
        self.player.pause()
        self.music_status_label.setText("Paused")
        self._set_status("Music paused")

    def stop_music(self) -> None:
        self.player.stop()
        self.music_status_label.setText("Stopped")
        self._set_status("Music stopped")

    def _on_volume_slider(self, value: int) -> None:
        self.audio_output.setVolume(value / 100)
        self.volume_value_label.setText(f"{value}%")

    def _on_player_error(self, error, _details) -> None:
        self.music_status_label.setText("Error")
        self.music_error_label.setText(
            "Could not play the selected music file. It may be missing, corrupt, "
            "or in an unsupported format."
        )
        self._set_status("Music error: file could not be played")
        self.player.stop()

    def _on_media_status_changed(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.music_status_label.setText("Finished")
            self._set_status("Music finished")

    def _clear_music_error(self) -> None:
        self.music_error_label.setText("")

    # ---- UI updates ------------------------------------------------------

    def _populate_card(self, frame: QFrame, card: TarotCard, issues: list[str]) -> None:
        frame.name_label.setText(card.name)
        frame.meaning_label.setText(card.meaning)
        self._load_image(frame, card, issues)

    def _load_image(self, frame: QFrame, card: TarotCard, issues: list[str]) -> None:
        image_path = os.path.join(_IMAGE_BASE, os.path.basename(card.image_path))
        try:
            if not os.path.isfile(image_path):
                self._show_image_placeholder(frame, card, "Image not found")
                issues.append("image missing")
                return
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                self._show_image_placeholder(frame, card, "Image could not be loaded")
                issues.append("invalid image")
                return
        except Exception:
            self._show_image_placeholder(frame, card, "Image could not be loaded")
            issues.append("invalid image")
            return

        frame.place.setVisible(False)
        frame.image.setVisible(True)
        frame.image.setPixmap(
            pixmap.scaled(
                frame.image.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _show_image_placeholder(self, frame: QFrame, card: TarotCard, reason: str) -> None:
        frame.image.setPixmap(QPixmap())
        frame.image.setVisible(False)
        frame.place.setText(f"{reason}: {card.name}")
        frame.place.setVisible(True)

    @staticmethod
    def _reading_summary(reading) -> str:
        return " • ".join(
            reading.card(pos).name
            for pos in (ReadingPosition.PAST, ReadingPosition.PRESENT, ReadingPosition.FUTURE)
        )

    def _set_status(self, message: str) -> None:
        self.status_label.setText(f"Status: {message}")
