"""Active-window capture stays explicit when the platform cannot do it."""

import sys

import pytest

from bigfatfish.perception.capture import (
    MacOSActiveWindowCapturer,
    ScreenCaptureError,
)


def test_macos_capturer_does_not_return_empty_image() -> None:
    capturer = MacOSActiveWindowCapturer()
    if sys.platform == "darwin":
        pytest.skip("screen recording is checked manually")
    with pytest.raises(ScreenCaptureError, match="macOS"):
        image = capturer.capture()
        assert image == b"", "empty image must not count as a capture"
