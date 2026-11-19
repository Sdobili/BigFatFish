"""Bounded channel that never blocks the caller."""

import queue
from typing import Generic, TypeVar

T = TypeVar("T")


class Channel(Generic[T]):
    """Drop a new event when the queue is full and return False."""

    def __init__(self, maxsize: int) -> None:
        self._items: queue.Queue[T] = queue.Queue(maxsize=maxsize)

    def put_nowait(self, ev: T) -> bool:
        try:
            self._items.put_nowait(ev)
        except queue.Full:
            return False
        return True
