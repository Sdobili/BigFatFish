"""Transparent, frameless, always-on-top window for the placeholder."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget

_PLACEHOLDER = (
    Path(__file__).resolve().parents[3] / "assets" / "placeholder" / "placeholder.png"
)


class ShellWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._pixmap = QPixmap(str(_PLACEHOLDER))
        label = QLabel(self)
        label.setPixmap(self._pixmap)
        if not self._pixmap.isNull():
            self.resize(self._pixmap.size())

    def pixmap(self) -> QPixmap:
        return self._pixmap
