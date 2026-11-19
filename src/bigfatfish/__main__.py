"""`python -m bigfatfish --smoke` draws one placeholder frame and exits."""

import argparse

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
    _render_one_frame()
    return 0


def _render_one_frame() -> None:
    app = QApplication([])
    window = ShellWindow()
    window.show()
    app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
