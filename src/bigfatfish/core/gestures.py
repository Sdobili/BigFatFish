"""Gesture kind after the confidence gate."""

from bigfatfish.core.events import GestureEvent


def effective_kind(ev: GestureEvent, min_score: float = 0.5) -> str:
    if ev.score is not None and ev.score < min_score:
        return "None"
    return ev.kind
