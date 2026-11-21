"""Capture the active window once. CI uses FakeCapturer."""

import sys
from typing import Protocol


class ScreenCaptureError(RuntimeError):
    """The active window was not captured."""


class ActiveWindowCapturer(Protocol):
    def capture(self) -> bytes:
        """Return a PNG of the current active window."""
        ...


class FakeCapturer:
    """Records how many times the wake asked for a window."""

    def __init__(self, image: bytes = b"\x89PNG\r\n") -> None:
        self.calls = 0
        self.image = image

    def capture(self) -> bytes:
        self.calls += 1
        return self.image


class MacOSActiveWindowCapturer:
    """ScreenCaptureKit capture. Manual on macOS; refused elsewhere."""

    def capture(self) -> bytes:
        if sys.platform != "darwin":
            raise ScreenCaptureError(
                "active-window capture is only implemented on macOS"
            )
        raise ScreenCaptureError("screen capture is not available")
