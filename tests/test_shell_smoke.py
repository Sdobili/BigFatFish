"""The shell window is frameless, translucent, and always on top."""

import os
import subprocess
import sys
from pathlib import Path

from pytestqt.qtbot import QtBot

_PLACEHOLDER = (
    Path(__file__).resolve().parents[1] / "assets" / "placeholder" / "placeholder.png"
)
# Hang guard only, same role as the one-second join in test_bus_never_blocks.
# The assertion is the process exit code, not elapsed time.
_SMOKE_HANG_GUARD_SECONDS = 60.0


def test_window_is_frameless_translucent_and_stays_on_top(qtbot: QtBot) -> None:
    from PySide6.QtCore import Qt

    from bigfatfish.shell.window import ShellWindow

    window = ShellWindow()
    qtbot.addWidget(window)

    flags = window.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint != 0
    assert flags & Qt.WindowType.WindowStaysOnTopHint != 0
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def test_window_loads_placeholder_pixmap(qtbot: QtBot) -> None:
    from PySide6.QtGui import QPixmap

    from bigfatfish.shell.window import ShellWindow

    window = ShellWindow()
    qtbot.addWidget(window)

    pixmap = window.pixmap()
    expected = QPixmap(str(_PLACEHOLDER))
    assert not pixmap.isNull()
    assert not expected.isNull()
    assert pixmap.toImage() == expected.toImage()


def test_smoke_exits_zero() -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.Popen(
        [sys.executable, "-m", "bigfatfish", "--smoke"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = proc.communicate(timeout=_SMOKE_HANG_GUARD_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
    assert proc.returncode == 0, stderr
    assert b"SMOKE OK" in stdout, stdout
