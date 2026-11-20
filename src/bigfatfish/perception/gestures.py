"""Turn a gesture-recognizer result into GestureEvents.

The result is duck-typed to match MediaPipe's GestureRecognizerResult.
"""

from collections.abc import Sequence
from typing import Protocol

from bigfatfish.core.events import GestureEvent


class _Category(Protocol):
    category_name: str
    score: float


class _Landmark(Protocol):
    x: float
    y: float
    z: float


class _RecognizerResult(Protocol):
    gestures: Sequence[Sequence[_Category]]
    handedness: Sequence[Sequence[_Category]]
    hand_landmarks: Sequence[Sequence[_Landmark]]


def to_events(
    result: _RecognizerResult, t: float, min_hand_score: float
) -> list[GestureEvent]:
    events: list[GestureEvent] = []
    for index, categories in enumerate(result.gestures):
        if len(categories) == 0:
            continue
        top = categories[0]
        if top.score < min_hand_score:
            continue
        events.append(
            GestureEvent(
                t=t,
                kind=top.category_name,
                hand=_hand(result, index),
                landmarks=_landmarks(result, index),
                score=float(top.score),
            )
        )
    return events


def _hand(result: _RecognizerResult, index: int) -> str:
    if index >= len(result.handedness):
        return ""
    labels = result.handedness[index]
    if len(labels) == 0:
        return ""
    return labels[0].category_name.lower()


def _landmarks(
    result: _RecognizerResult, index: int
) -> tuple[tuple[float, ...], ...] | None:
    if index >= len(result.hand_landmarks):
        return None
    points = result.hand_landmarks[index]
    if len(points) == 0:
        return None
    return tuple((point.x, point.y, point.z) for point in points)
