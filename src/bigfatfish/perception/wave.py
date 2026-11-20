"""Detect a left-right open-palm wave from wrist motion."""

from bigfatfish.core.events import GestureEvent

_MIN_REVERSALS = 2
_WINDOW_S = 1.5


class WaveDetector:
    def __init__(self) -> None:
        self._last_x: float | None = None
        self._last_sign: int = 0
        self._reversals: list[float] = []

    def feed(self, ev: GestureEvent) -> GestureEvent | None:
        x = _wrist_x(ev)
        if x is None:
            return None
        if self._last_x is None:
            self._last_x = x
            return None
        delta = x - self._last_x
        self._last_x = x
        if delta == 0.0:
            return None
        sign = 1 if delta > 0.0 else -1
        if self._last_sign != 0 and sign != self._last_sign:
            self._reversals.append(ev.t)
        self._last_sign = sign
        self._reversals = [
            stamp for stamp in self._reversals if ev.t - stamp <= _WINDOW_S
        ]
        if len(self._reversals) >= _MIN_REVERSALS:
            self._reset()
            return GestureEvent(
                t=ev.t,
                kind="Wave",
                hand=ev.hand,
                landmarks=ev.landmarks,
                score=ev.score,
            )
        return None

    def _reset(self) -> None:
        self._last_x = None
        self._last_sign = 0
        self._reversals = []


def _wrist_x(ev: GestureEvent) -> float | None:
    if ev.kind != "Open_Palm" or not ev.landmarks:
        return None
    point = ev.landmarks[0]
    if len(point) == 0:
        return None
    return point[0]
