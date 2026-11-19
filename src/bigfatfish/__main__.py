"""`python -m bigfatfish --smoke` draws one placeholder frame and exits."""

import argparse
import sys

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from bigfatfish.shell.window import ShellWindow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bigfatfish")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="show the placeholder for one frame and exit",
    )
    args = parser.parse_args(argv)
    if not args.smoke:
        parser.error("missing --smoke")
    return _render_one_frame()


def _render_one_frame() -> int:
    app = QApplication([])
    window = ShellWindow()
    window.show()
    app.processEvents()
    reasons: list[str] = []
    if not window.isVisible():
        reasons.append("window is not visible")
    if window.pixmap().isNull():
        reasons.append("pixmap is empty")
    if not _has_visible_pixel(window.grab().toImage()):
        reasons.append("grabbed frame has no pixel with alpha > 0")
    if reasons:
        print("\n".join(reasons), file=sys.stderr)
        return 1
    print("SMOKE OK")
    return 0


def _has_visible_pixel(image: QImage) -> bool:
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() > 0:
                return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
