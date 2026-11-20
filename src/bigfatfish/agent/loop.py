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
    kind = effective_kind(ev)
    if kind not in _HOLD_S:
        return HoldState(), None
    since = ev.t if state.kind != kind or state.since is None else state.since
    held = ev.t - since
    confirmed = kind if held >= _HOLD_S[kind] else None
    return HoldState(kind=kind, since=since), confirmed
