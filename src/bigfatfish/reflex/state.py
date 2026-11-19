"""Reflex state stepped from GestureEvent timestamps, never the wall clock."""

from dataclasses import dataclass

from bigfatfish.core.events import GestureEvent

_NOD_KINDS = frozenset({"Thumb_Up"})


@dataclass(frozen=True, slots=True)
class ReflexState:
    t: float
    gaze_hand: str
    nodding: bool
    nods: int
    follow_x: float | None
    follow_y: float | None

    def to_dict(self) -> dict[str, object]:
        if self.follow_x is None or self.follow_y is None:
            follow: object = None
        else:
            follow = [self.follow_x, self.follow_y]
        return {
            "gaze_hand": self.gaze_hand,
            "nodding": self.nodding,
            "nods": self.nods,
            "follow": follow,
        }


def initial() -> ReflexState:
    return ReflexState(
        t=0.0,
        gaze_hand="",
        nodding=False,
        nods=0,
        follow_x=None,
        follow_y=None,
    )


def step(state: ReflexState, event: GestureEvent) -> ReflexState:
    follow_x, follow_y = _follow(event.landmarks)
    nodding = event.kind in _NOD_KINDS
    nods = state.nods + 1 if nodding else state.nods
    return ReflexState(
        t=event.t,
        gaze_hand=event.hand,
        nodding=nodding,
        nods=nods,
        follow_x=follow_x,
        follow_y=follow_y,
    )


def _follow(
    landmarks: tuple[tuple[float, ...], ...] | None,
) -> tuple[float | None, float | None]:
    if not landmarks:
        return None, None
    point = landmarks[0]
    if len(point) < 2:
        return None, None
    return point[0], point[1]
