"""Capture the active window once. CI uses FakeCapturer.

The macOS path uses ScreenCaptureKit's SCStream: one complete frame, then
stop. SCScreenshotManager is macOS 14 or newer; this product's floor is
12.3, so the stream is the capture that stays inside that floor.
"""

import sys
import threading
from pathlib import Path
from typing import Any, Protocol

_FRAME_WAIT_S = 5.0
_SPIN_S = 0.05
_BGRA = 0x42475241
_USAGE = (
    "大肥鱼只在你挥手唤醒时截取当前活动窗口，用来做一张卡片。"
    "不会截取整个桌面，也不会在后台录屏。"
)


class ScreenCaptureError(RuntimeError):
    """The active window was not captured."""


class ScreenCapturePermissionError(ScreenCaptureError):
    """Screen Recording was not granted. An empty image is not success."""


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
    """ScreenCaptureKit capture of the frontmost on-screen window."""

    def capture(self) -> bytes:
        if sys.platform != "darwin":
            raise ScreenCaptureError(
                "active-window capture is only implemented on macOS"
            )
        request_screen_capture_access()
        png = _capture_front_window()
        if not png:
            raise ScreenCaptureError(
                "screen capture frame is empty. "
                "An empty or black image is not a successful capture."
            )
        return png


def request_screen_capture_access() -> None:
    """Ask for Screen Recording. Denied access raises; it does not return pixels."""
    if sys.platform != "darwin":
        raise ScreenCaptureError("active-window capture is only implemented on macOS")
    from Quartz import (  # type: ignore[import-not-found]
        CGPreflightScreenCaptureAccess,
        CGRequestScreenCaptureAccess,
    )

    if CGPreflightScreenCaptureAccess():
        return
    CGRequestScreenCaptureAccess()
    if CGPreflightScreenCaptureAccess():
        return
    raise ScreenCapturePermissionError(
        "Screen Recording permission was denied. "
        "An empty or black image is not a successful capture. "
        "Grant access in System Settings, then restart the app."
    )


def write_permission_app(destination: Path) -> Path:
    """Write a minimal .app so macOS can show NSScreenCaptureUsageDescription.

    This is not a disk image. Launch the bundle, grant Screen Recording, then
    restart it before capturing.
    """
    root = destination / "BigFatFish.app"
    macos = root / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    (root / "Contents" / "Info.plist").write_text(_info_plist(), encoding="utf-8")
    exe = macos / "BigFatFish"
    exe.write_text(_launcher(), encoding="utf-8")
    exe.chmod(0o755)
    return root


def _info_plist() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>BigFatFish</string>
  <key>CFBundleIdentifier</key>
  <string>local.bigfatfish.capture</string>
  <key>CFBundleName</key>
  <string>BigFatFish</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.0.1</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.3</string>
  <key>NSScreenCaptureUsageDescription</key>
  <string>{_USAGE}</string>
</dict>
</plist>
"""


def _launcher() -> str:
    return "#!/bin/sh\nexec python3 -m bigfatfish.perception.capture\n"


def _capture_front_window() -> bytes:
    import ScreenCaptureKit  # type: ignore[import-not-found]
    from AppKit import NSScreen, NSWorkspace  # type: ignore[import-not-found]
    from Foundation import (  # type: ignore[import-not-found]
        NSObject,
        NSOperationQueue,
    )

    content = _shareable_content(ScreenCaptureKit)
    window = _front_window(content, NSWorkspace)
    frame = window.frame
    width = int(frame.size.width)
    height = int(frame.size.height)
    if width < 1 or height < 1:
        raise ScreenCaptureError("active window has an empty frame")
    scale = _scale(NSScreen)
    config = ScreenCaptureKit.SCStreamConfiguration.alloc().init()
    config.setWidth_(width * scale)
    config.setHeight_(height * scale)
    config.setPixelFormat_(_BGRA)
    config.setShowsCursor_(False)
    config.setCapturesAudio_(False)
    config.setQueueDepth_(1)
    filt = ScreenCaptureKit.SCContentFilter.alloc().initWithDesktopIndependentWindow_(
        window
    )
    box: dict[str, object] = {"png": None, "error": None}
    ready = threading.Event()

    class _Sink(NSObject):  # type: ignore[misc]
        def stream_didOutputSampleBuffer_ofType_(
            self, _stream: object, sample: object, _kind: object
        ) -> None:
            if box["png"] is not None or box["error"] is not None:
                return
            try:
                png = _png_if_complete(sample, ScreenCaptureKit)
            except ScreenCaptureError as exc:
                box["error"] = exc
                ready.set()
                return
            if png is None:
                return
            box["png"] = png
            ready.set()

        def stream_didStopWithError_(self, _stream: object, error: object) -> None:
            if error is not None and box["png"] is None and box["error"] is None:
                box["error"] = ScreenCaptureError(_message(error))
                ready.set()

    sink = _Sink.alloc().init()
    stream = ScreenCaptureKit.SCStream.alloc().initWithFilter_configuration_delegate_(
        filt, config, sink
    )
    queue = NSOperationQueue.alloc().init()
    try:
        added = stream.addStreamOutput_type_sampleHandlerQueue_error_(
            sink,
            ScreenCaptureKit.SCStreamOutputTypeScreen,
            queue,
            None,
        )
        _raise_if_error(added)
        _start(stream)
        if not _pump(ready, _FRAME_WAIT_S):
            raise ScreenCaptureError(
                "screen capture produced no frame. "
                "An empty or black image is not a successful capture."
            )
        problem = box["error"]
        if isinstance(problem, ScreenCaptureError):
            raise problem
        png = box["png"]
        if not isinstance(png, bytes) or png == b"":
            raise ScreenCaptureError(
                "screen capture frame is empty. "
                "An empty or black image is not a successful capture."
            )
        return png
    finally:
        _stop(stream)


def _shareable_content(screen_capture_kit: Any) -> Any:
    loaded: dict[str, object] = {"content": None, "error": None}
    done = threading.Event()

    def handler(content: object, error: object) -> None:
        loaded["content"] = content
        loaded["error"] = error
        done.set()

    getter = screen_capture_kit.SCShareableContent
    getter.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
        False,
        True,
        handler,
    )
    if not _pump(done, _FRAME_WAIT_S):
        raise ScreenCaptureError("listing windows timed out")
    if loaded["error"] is not None or loaded["content"] is None:
        detail = _message(loaded["error"]) if loaded["error"] is not None else ""
        raise ScreenCaptureError(detail or "could not list windows")
    return loaded["content"]


def _front_window(content: Any, workspace: Any) -> Any:
    front = workspace.sharedWorkspace().frontmostApplication
    if front is None:
        raise ScreenCaptureError("no frontmost application")
    pid = int(front.processIdentifier)
    windows = list(content.windows)
    chosen = _pick(windows, pid, normal_layer=True)
    if chosen is None:
        chosen = _pick(windows, pid, normal_layer=False)
    if chosen is None:
        raise ScreenCaptureError("frontmost app has no on-screen window")
    return chosen


def _pick(windows: list[Any], pid: int, *, normal_layer: bool) -> Any | None:
    matches: list[object] = []
    for window in windows:
        owner = window.owningApplication
        if owner is None or int(owner.processID) != pid:
            continue
        if not bool(window.isOnScreen):
            continue
        if normal_layer and int(window.windowLayer) != 0:
            continue
        matches.append(window)
    if not matches:
        return None
    return max(matches, key=_area)


def _area(window: Any) -> float:
    size = window.frame.size
    return float(size.width) * float(size.height)


def _scale(ns_screen: Any) -> int:
    screen = ns_screen.mainScreen
    if screen is None:
        return 1
    factor = int(screen.backingScaleFactor)
    if factor < 1:
        return 1
    return factor


def _png_if_complete(sample: Any, screen_capture_kit: Any) -> bytes | None:
    from CoreMedia import (  # type: ignore[import-not-found]
        CMSampleBufferGetImageBuffer,
        CMSampleBufferGetSampleAttachmentsArray,
        CMSampleBufferIsValid,
    )

    if not CMSampleBufferIsValid(sample):
        return None
    status = _frame_status(
        sample, screen_capture_kit, CMSampleBufferGetSampleAttachmentsArray
    )
    blank = getattr(screen_capture_kit, "SCFrameStatusBlank", None)
    complete = getattr(screen_capture_kit, "SCFrameStatusComplete", None)
    if blank is not None and status is not None and int(status) == int(blank):
        raise ScreenCaptureError(
            "screen capture frame is blank. "
            "An empty or black image is not a successful capture. "
            "If Screen Recording was just granted, restart the app."
        )
    if complete is not None and status is not None and int(status) != int(complete):
        return None
    pixel = CMSampleBufferGetImageBuffer(sample)
    if pixel is None:
        raise ScreenCaptureError("screen capture frame is empty")
    return _png_from_pixel_buffer(pixel)


def _frame_status(
    sample: Any,
    screen_capture_kit: Any,
    attachments_of: Any,
) -> Any:
    attachments = attachments_of(sample, False)
    if not attachments:
        return None
    info = attachments[0]
    key = getattr(screen_capture_kit, "SCStreamFrameInfoStatus", None)
    if key is None or not hasattr(info, "objectForKey_"):
        return None
    return info.objectForKey_(key)


def _png_from_pixel_buffer(pixel: Any) -> bytes:
    from Foundation import NSMutableData
    from Quartz import (
        CGImageDestinationAddImage,
        CGImageDestinationCreateWithData,
        CGImageDestinationFinalize,
        CIContext,
        CIImage,
    )

    image = CIImage.imageWithCVPixelBuffer_(pixel)
    extent = image.extent()
    if int(extent.size.width) < 1 or int(extent.size.height) < 1:
        raise ScreenCaptureError("screen capture frame is empty")
    rendered = CIContext.contextWithOptions_(None).createCGImage_fromRect_(
        image, extent
    )
    if rendered is None:
        raise ScreenCaptureError("screen capture frame is empty")
    data = NSMutableData.data()
    dest = CGImageDestinationCreateWithData(data, "public.png", 1, None)
    if dest is None or not CGImageDestinationAddImage(dest, rendered, None):
        raise ScreenCaptureError("could not encode the capture")
    if not CGImageDestinationFinalize(dest):
        raise ScreenCaptureError("could not encode the capture")
    raw = data.bytes()
    png = raw.tobytes() if hasattr(raw, "tobytes") else bytes(raw)
    if not png:
        raise ScreenCaptureError("screen capture frame is empty")
    return png


def _start(stream: Any) -> None:
    done = threading.Event()
    failure: dict[str, object] = {"error": None}

    def handler(error: object) -> None:
        failure["error"] = error
        done.set()

    stream.startCaptureWithCompletionHandler_(handler)
    if not _pump(done, _FRAME_WAIT_S):
        raise ScreenCaptureError("screen capture did not start")
    if failure["error"] is not None:
        raise ScreenCaptureError(_message(failure["error"]))


def _stop(stream: Any) -> None:
    done = threading.Event()

    def handler(_error: object) -> None:
        done.set()

    try:
        stream.stopCaptureWithCompletionHandler_(handler)
        _pump(done, _FRAME_WAIT_S)
    except Exception:
        return


def _raise_if_error(added: object) -> None:
    if isinstance(added, tuple) and len(added) >= 2 and added[1] is not None:
        raise ScreenCaptureError(_message(added[1]))


def _pump(done: threading.Event, seconds: float) -> bool:
    from Foundation import NSDate, NSRunLoop

    spins = int(seconds / _SPIN_S)
    for _ in range(spins):
        if done.is_set():
            return True
        until = NSDate.dateWithTimeIntervalSinceNow_(_SPIN_S)
        NSRunLoop.currentRunLoop().runUntilDate_(until)
    return done.is_set()


def _message(error: object) -> str:
    if error is None:
        return "screen capture failed"
    text = getattr(error, "localizedDescription", None)
    if callable(text):
        text = text()
    if text:
        return str(text)
    return str(error)


if __name__ == "__main__":
    request_screen_capture_access()
