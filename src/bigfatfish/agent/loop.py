"""Closed-loop phases and hold timing. Durations use event timestamps."""

import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import NoReturn, Protocol, SupportsIndex

from bigfatfish.core.events import GestureEvent, Observation, ProposalReady, Tick
from bigfatfish.core.gestures import effective_kind

_HOLD_S: dict[str, float] = {
    "Pointing_Up": 0.8,
    "Thumb_Up": 0.5,
    "Closed_Fist": 1.0,
}
_HOLD_EPS = 1e-6
_IDLE_TIMEOUT_S = 20.0
_MAX_REVISIONS = 2
_ON_CONFIRM: dict[tuple[str, str], str] = {
    ("PROPOSED", "Thumb_Up"): "EXECUTING",
    ("REVIEW", "Thumb_Up"): "DELIVERED",
}


@dataclass(frozen=True, slots=True)
class HoldState:
    kind: str | None = None
    since: float | None = None


def _held_long_enough(held: float, threshold: float) -> bool:
    # Shortfalls within _HOLD_EPS count. Exact equality stays on >=.
    if held < threshold:
        return held + _HOLD_EPS >= threshold
    return held >= threshold


def update_hold(state: HoldState, ev: GestureEvent) -> tuple[HoldState, str | None]:
    kind = effective_kind(ev)
    if kind not in _HOLD_S:
        return HoldState(), None
    since = ev.t if state.kind != kind or state.since is None else state.since
    held = ev.t - since
    confirmed = kind if _held_long_enough(held, _HOLD_S[kind]) else None
    return HoldState(kind=kind, since=since), confirmed


LoopEvent = GestureEvent | Tick | Observation | ProposalReady
Box = tuple[tuple[float, float], tuple[float, float]]


class ConfirmationToken:
    """Issued when a confirmation gesture completes. Bound to that capture."""

    def __init__(self, capture_id: str) -> None:
        caller = sys._getframe(1).f_globals.get("__name__")
        if caller != __name__:
            raise TypeError("ConfirmationToken is sealed")
        self._capture_id = capture_id
        self._minted = True

    @property
    def capture_id(self) -> str:
        return self._capture_id

    def __copy__(self) -> NoReturn:
        _reject_token_replica()

    def __deepcopy__(self, _memo: object) -> NoReturn:
        _reject_token_replica()

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        _reject_token_replica()


def _reject_token_replica() -> NoReturn:
    raise TypeError("ConfirmationToken cannot be copied")


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
    token: ConfirmationToken


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
    now = ev.t
    if _idle_expired(state, ev, now):
        return LoopState(), []
    if isinstance(ev, Observation):
        return replace(state, window_title=ev.window_title, text=ev.text), []
    if isinstance(ev, ProposalReady):
        if state.phase == "EXECUTING":
            return replace(state, phase="REVIEW", proposal=ev.text), []
        return replace(state, proposal=ev.text), []
    if isinstance(ev, Tick):
        return state, []
    return _on_gesture(state, ev, now)


def _idle_expired(state: LoopState, ev: LoopEvent, now: float) -> bool:
    if isinstance(ev, GestureEvent) or state.phase == "IDLE":
        return False
    if state.last_gesture_t is None:
        return False
    return _held_long_enough(now - state.last_gesture_t, _IDLE_TIMEOUT_S)


def _on_gesture(
    state: LoopState,
    ev: GestureEvent,
    now: float,
) -> tuple[LoopState, list[Effect]]:
    state = replace(state, last_gesture_t=now)
    kind = effective_kind(ev)
    if kind == "Wave" and state.phase == "IDLE":
        capture_id = f"cap-{now}"
        woke = replace(
            state,
            phase="ATTENDING",
            capture_id=capture_id,
            hold_kind=None,
            hold_since=None,
        )
        return woke, [Capture(capture_id)]
    if kind == "Thumb_Down":
        return _on_thumb_down(state)
    if _waiting_to_move(state, ev, kind):
        return replace(state, hold_kind=None, hold_since=None), []
    hold, confirmed = update_hold(HoldState(state.hold_kind, state.hold_since), ev)
    state = replace(state, hold_kind=hold.kind, hold_since=hold.since)
    if confirmed == "Closed_Fist" and state.phase not in {"IDLE", "DELIVERED"}:
        effects: list[Effect] = []
        effects.append(Discard(state.capture_id))
        return LoopState(last_gesture_t=now), effects
    if confirmed == "Pointing_Up":
        return _lock_corner(state, ev)
    if confirmed == "Thumb_Up":
        return _on_thumb_up(state)
    return state, []


def _waiting_to_move(state: LoopState, ev: GestureEvent, kind: str) -> bool:
    if kind != "Pointing_Up" or state.phase != "SELECTING" or state.corner1 is None:
        return False
    point = _xy(ev)
    return point is None or point == state.corner1


def _on_thumb_down(state: LoopState) -> tuple[LoopState, list[Effect]]:
    state = replace(state, hold_kind=None, hold_since=None)
    if state.phase == "PROPOSED":
        hinted = _box_tuple(state)
        return (
            replace(
                state,
                phase="SELECTING",
                corner1=None,
                corner2=None,
                hint=hinted if hinted is not None else state.hint,
            ),
            [],
        )
    if state.phase == "REVIEW":
        if state.revisions >= _MAX_REVISIONS:
            return state, []
        revisions = state.revisions + 1
        return replace(state, phase="EXECUTING", revisions=revisions), []
    return state, []


def _lock_corner(state: LoopState, ev: GestureEvent) -> tuple[LoopState, list[Effect]]:
    point = _xy(ev)
    cleared = replace(state, hold_kind=None, hold_since=None)
    if point is None:
        return cleared, []
    if state.phase == "ATTENDING" or (
        state.phase == "SELECTING" and state.corner1 is None
    ):
        return replace(cleared, phase="SELECTING", corner1=point, corner2=None), []
    if state.phase == "SELECTING" and point != state.corner1:
        return replace(cleared, phase="PROPOSED", corner2=point), []
    return cleared, []


def _on_thumb_up(state: LoopState) -> tuple[LoopState, list[Effect]]:
    phase = _ON_CONFIRM.get((state.phase, "Thumb_Up"))
    cleared = replace(state, hold_kind=None, hold_since=None)
    if phase is None:
        return cleared, []
    moved = replace(cleared, phase=phase)
    if phase != "DELIVERED":
        return moved, []
    box = _box_tuple(state)
    if box is None:
        return moved, []
    return moved, [
        Deliver(
            capture_id=state.capture_id,
            box=box,
            window_title=state.window_title,
            text=state.text,
            proposal=state.proposal,
            revisions=state.revisions,
            token=ConfirmationToken(state.capture_id),
        )
    ]


def _box_tuple(state: LoopState) -> Box | None:
    if state.corner1 is None or state.corner2 is None:
        return None
    return (state.corner1, state.corner2)


def _xy(ev: GestureEvent) -> tuple[float, float] | None:
    if not ev.landmarks:
        return None
    point = ev.landmarks[0]
    if len(point) < 2:
        return None
    return (point[0], point[1])


class _Capturer(Protocol):
    def capture(self) -> bytes:
        """Return the active-window image."""
        ...


class _Reader(Protocol):
    def read(self, image: bytes) -> str:
        """Read text from one captured image."""
        ...


def run_wake(
    capturer: _Capturer,
    ocr: _Reader,
    events: Sequence[LoopEvent],
) -> tuple[LoopState, list[Effect]]:
    # Red stub: the wake does not capture or read yet.
    del capturer, ocr, events
    return initial(), []
