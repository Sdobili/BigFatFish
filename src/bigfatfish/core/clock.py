"""Injected clocks. Only SystemClock reads the wall clock."""

import time
from typing import Protocol


class Clock(Protocol):
    def monotonic(self) -> float:
        """Monotonic seconds, for ordering frames."""
        ...

    def wall(self) -> float:
        """Wall-clock seconds since the epoch."""
        ...


class FakeClock:
    """Both readings move only when advance() is called."""

    def __init__(self, start_monotonic: float = 0.0, start_wall: float = 0.0) -> None:
        self._monotonic = start_monotonic
        self._wall = start_wall

    def monotonic(self) -> float:
        return self._monotonic

    def wall(self) -> float:
        return self._wall

    def advance(self, seconds: float) -> None:
        """Red stub: the clock stays put."""


class SystemClock:
    """The only caller of time.monotonic and time.time."""

    def monotonic(self) -> float:
        return time.monotonic()

    def wall(self) -> float:
        return time.time()
