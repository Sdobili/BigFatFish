"""Hold timing for gestures that must stay steady before they count."""

from dataclasses import dataclass

from bigfatfish.core.events import GestureEvent
from bigfatfish.core.gestures import effective_kind

_HOLD_S: dict[str, float] = {
    "Pointing_Up": 0.8,
    "Thumb_Up": 0.5,
    "Closed_Fist": 1.0,
}


@dataclass(frozen=True, slots=True)
class HoldState:
    kind: str | None = None
    since: float | None = None


def update_hold(state: HoldState, ev: GestureEvent) -> tuple[HoldState, str | None]:
    effective_kind(ev)
    return HoldState(), None
