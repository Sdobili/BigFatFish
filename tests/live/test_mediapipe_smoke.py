"""MediaPipe gesture recognizer against the pinned model. Needs --live."""

import hashlib
import os
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

pytestmark = pytest.mark.live

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
    "gesture_recognizer/float16/1/gesture_recognizer.task"
)
_MODEL_SHA256 = "97952348cf6a6a4915c2ea1496b4b37ebabc50cbbf80571435643c455f2b0482"
_CALLBACK_LIMIT_S = 10


def test_model_sha256_and_empty_frame() -> None:
    import mediapipe as mp
    import numpy as np

    model = _model_path()
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    assert digest == _MODEL_SHA256
    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    result = _recognize(mp, frame, timestamp_ms=1, model=model)
    assert list(result.gestures) == []
    assert list(result.handedness) == []
    assert list(result.hand_landmarks) == []
    assert list(result.hand_world_landmarks) == []


def test_camera_one_frame() -> None:
    import cv2
    import mediapipe as mp

    capture = cv2.VideoCapture(0)
    try:
        ok, frame = capture.read()
    finally:
        capture.release()
    assert ok, "camera 0 did not return a frame"
    assert frame is not None
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = _recognize(mp, rgb, timestamp_ms=1, model=_model_path())
    assert result is not None


def _user_data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "bigfatfish" / "models"


def _model_path() -> Path:
    destination = _user_data_dir() / "gesture_recognizer.task"
    if destination.is_file():
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        if digest != _MODEL_SHA256:
            raise AssertionError(
                f"cached model sha256 {digest} != {_MODEL_SHA256}; refusing to load"
            )
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(_MODEL_URL, timeout=60) as response:
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != _MODEL_SHA256:
        raise AssertionError(
            f"downloaded model sha256 {digest} != {_MODEL_SHA256}; refusing to load"
        )
    destination.write_bytes(payload)
    return destination


def _recognize(mp: object, frame: object, *, timestamp_ms: int, model: Path) -> object:
    import mediapipe as real_mp

    del mp
    arrived = threading.Event()
    holder: list[object] = []

    def callback(result: object, output_image: object, timestamp: int) -> None:
        del output_image, timestamp
        holder.append(result)
        arrived.set()

    options = real_mp.tasks.vision.GestureRecognizerOptions(
        base_options=real_mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=real_mp.tasks.vision.RunningMode.LIVE_STREAM,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        result_callback=callback,
    )
    recognizer = real_mp.tasks.vision.GestureRecognizer.create_from_options(options)
    try:
        image = real_mp.Image(image_format=real_mp.ImageFormat.SRGB, data=frame)
        recognizer.recognize_async(image, timestamp_ms)
        assert arrived.wait(_CALLBACK_LIMIT_S), "callback did not arrive within 10s"
    finally:
        recognizer.close()
    return holder[0]
