"""Detect a left-right open-palm wave from wrist motion."""

from bigfatfish.core.events import GestureEvent

_MIN_REVERSALS = 2
_WINDOW_S = 1.5


class WaveDetector:
    def feed(self, ev: GestureEvent) -> GestureEvent | None:
        return None
