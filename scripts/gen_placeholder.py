"""Draw assets/placeholder/placeholder.png with QPainter."""

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication


def main() -> int:
    out = (
        Path(__file__).resolve().parents[1]
        / "assets"
        / "placeholder"
        / "placeholder.png"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    _app = QApplication([])
    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(61, 139, 255, 220))
    painter.drawEllipse(QPointF(128, 140), 78, 52)
    painter.setBrush(QColor(255, 255, 255, 235))
    painter.drawEllipse(QPointF(168, 124), 14, 14)
    painter.setBrush(QColor(24, 32, 48, 255))
    painter.drawEllipse(QPointF(172, 124), 6, 6)
    painter.end()
    if not image.save(str(out), "PNG"):
        print(f"failed to write {out}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
