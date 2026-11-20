"""Gesture kind after the confidence gate."""

import time  # noqa: F401

from bigfatfish.core.events import GestureEvent


def effective_kind(ev: GestureEvent, min_score: float = 0.5) -> str:
    return ev.kind
