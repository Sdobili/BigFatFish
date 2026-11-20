"""Hold duration uses event timestamps and the confidence gate."""

from bigfatfish.agent.loop import HoldState, update_hold
from bigfatfish.core.events import GestureEvent

_HOLD_S = {
    "Pointing_Up": 0.8,
    "Thumb_Up": 0.5,
    "Closed_Fist": 1.0,
}


def _gesture(t: float, kind: str, score: float | None = None) -> GestureEvent:
    return GestureEvent(t=t, kind=kind, hand="right", score=score)


def _confirmed(events: list[GestureEvent]) -> list[str]:
    state = HoldState()
    found: list[str] = []
    for event in events:
        state, kind = update_hold(state, event)
        if kind is not None:
            found.append(kind)
    return found


def test_hold_just_under_threshold_does_not_fire() -> None:
    for kind, hold_s in _HOLD_S.items():
        confirmed = _confirmed(
            [
                _gesture(0.0, kind),
                _gesture(hold_s - 0.001, kind),
            ]
        )
        assert confirmed == []


def test_hold_exactly_at_threshold_fires() -> None:
    for kind, hold_s in _HOLD_S.items():
        confirmed = _confirmed(
            [
                _gesture(0.0, kind, score=0.5),
                _gesture(hold_s, kind, score=0.5),
            ]
        )
        assert confirmed == [kind], "hold at threshold must fire"


def test_hold_past_threshold_fires() -> None:
    for kind, hold_s in _HOLD_S.items():
        confirmed = _confirmed(
            [
                _gesture(0.0, kind, score=0.99),
                _gesture(hold_s + 0.1, kind, score=0.99),
            ]
        )
        assert confirmed == [kind]


def test_thumb_up_short_hold_ignored() -> None:
    single = _confirmed([_gesture(1.25, "Thumb_Up", score=0.99)])
    assert single == [], "short hold must not confirm"
    short = _confirmed(
        [
            _gesture(0.0, "Thumb_Up", score=0.99),
            _gesture(0.1, "Thumb_Up", score=0.99),
        ]
    )
    assert short == [], "short hold must not confirm"


def test_gesture_change_restarts_hold() -> None:
    sequences = [
        [
            _gesture(0.0, "Pointing_Up", score=0.95),
            _gesture(0.7, "Pointing_Up", score=0.95),
            _gesture(0.7, "Thumb_Up", score=0.95),
            _gesture(1.1, "Thumb_Up", score=0.95),
        ],
        [
            _gesture(0.0, "Thumb_Up", score=0.95),
            _gesture(0.4, "Thumb_Up", score=0.95),
            _gesture(0.4, "Closed_Fist", score=0.95),
            _gesture(1.3, "Closed_Fist", score=0.95),
        ],
        [
            _gesture(0.0, "Closed_Fist", score=0.95),
            _gesture(0.9, "Closed_Fist", score=0.95),
            _gesture(0.9, "Pointing_Up", score=0.95),
            _gesture(1.6, "Pointing_Up", score=0.95),
        ],
    ]
    for events in sequences:
        assert _confirmed(events) == []


def test_low_score_breaks_hold() -> None:
    for kind, hold_s in _HOLD_S.items():
        confirmed = _confirmed(
            [
                _gesture(0.0, kind, score=0.95),
                _gesture(hold_s / 2, kind, score=0.49),
                _gesture(hold_s, kind, score=0.95),
            ]
        )
        assert confirmed == [], "low score must break hold"
