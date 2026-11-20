"""Turn a gesture-recognizer result into GestureEvents."""

from bigfatfish.core.events import GestureEvent


def to_events(result: object, t: float, min_hand_score: float) -> list[GestureEvent]:
    return []
