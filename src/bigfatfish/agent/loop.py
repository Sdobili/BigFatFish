"""Hold timing for gestures that must stay steady before they count."""

from dataclasses import dataclass

from bigfatfish.core.events import GestureEvent, Observation, ProposalReady, Tick
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


LoopEvent = GestureEvent | Tick | Observation | ProposalReady
Box = tuple[tuple[float, float], tuple[float, float]]


@dataclass(frozen=True, slots=True)
class Capture:
    capture_id: str


@dataclass(frozen=True, slots=True)
class Discard:
    capture_id: str


@dataclass(frozen=True, slots=True)
class Deliver:
    capture_id: str
    box: Box
    window_title: str
    text: str
    proposal: str
    revisions: int


Effect = Capture | Discard | Deliver


@dataclass(frozen=True, slots=True)
class LoopState:
    phase: str = "IDLE"
    hold_kind: str | None = None
    hold_since: float | None = None
    last_gesture_t: float | None = None
    corner1: tuple[float, float] | None = None
    corner2: tuple[float, float] | None = None
    revisions: int = 0
    capture_id: str = ""
    window_title: str = ""
    text: str = ""
    proposal: str = ""
    hint: Box | None = None


def initial() -> LoopState:
    return LoopState()


def step(state: LoopState, ev: LoopEvent) -> tuple[LoopState, list[Effect]]:
    return state, []
