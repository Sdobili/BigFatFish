"""Revise limit, cancel, and idle timeout on the closed loop."""

from bigfatfish.agent.loop import Capture, Discard, initial, run_wake, step
from bigfatfish.core.events import GestureEvent, Observation, ProposalReady, Tick
from bigfatfish.perception.capture import FakeCapturer
from bigfatfish.perception.ocr import FakeOcr


def test_third_revise_is_ignored() -> None:
    state = initial()
    for event in (
        GestureEvent(t=0.0, kind="Wave", hand="right"),
        *_points(1.0, (0.2, 0.2), (0.8, 0.6)),
        GestureEvent(t=5.0, kind="Thumb_Up", hand="right"),
        GestureEvent(t=6.0, kind="Thumb_Up", hand="right"),
        ProposalReady(t=6.5, text="card"),
    ):
        state, _ = step(state, event)
    assert state.phase == "REVIEW"
    assert state.revisions == 0

    state, _ = step(state, GestureEvent(t=7.0, kind="Thumb_Down", hand="right"))
    assert state.phase == "EXECUTING"
    assert state.revisions == 1
    state, _ = step(state, ProposalReady(t=7.5, text="card-2"))
    assert state.phase == "REVIEW"

    state, _ = step(state, GestureEvent(t=8.0, kind="Thumb_Down", hand="right"))
    assert state.phase == "EXECUTING"
    assert state.revisions == 2
    state, _ = step(state, ProposalReady(t=8.5, text="card-3"))
    assert state.phase == "REVIEW"

    state, effects = step(state, GestureEvent(t=9.0, kind="Thumb_Down", hand="right"))
    assert effects == [], "third revise must be ignored"
    assert state.revisions == 2, "third revise must be ignored"
    assert state.phase == "REVIEW", "third revise must be ignored"


def test_cancel_discards_capture() -> None:
    state, woke = step(initial(), GestureEvent(t=0.0, kind="Wave", hand="right"))
    assert state.phase == "ATTENDING"
    assert any(isinstance(effect, Capture) for effect in woke)
    state, _ = step(state, GestureEvent(t=1.0, kind="Closed_Fist", hand="right"))
    state, effects = step(state, GestureEvent(t=2.0, kind="Closed_Fist", hand="right"))
    assert state.phase == "IDLE"
    assert any(isinstance(effect, Discard) for effect in effects), (
        "cancel must discard capture"
    )


def test_idle_timeout_after_20s() -> None:
    state, _ = step(initial(), GestureEvent(t=0.0, kind="Wave", hand="right"))
    assert state.phase == "ATTENDING"
    stayed, stayed_effects = step(state, Tick(t=19.9))
    assert stayed == state
    assert stayed_effects == []
    left, _ = step(stayed, Tick(t=20.0))
    assert left.phase == "IDLE", "must return to IDLE at 20s"


def test_capture_once_per_wake() -> None:
    capturer = FakeCapturer()
    ocr = FakeOcr("noted")
    events = (
        GestureEvent(t=0.0, kind="Wave", hand="right"),
        Tick(t=1.0),
        GestureEvent(t=2.0, kind="Open_Palm", hand="right"),
        Observation(t=3.0, window_title="Notes", text="hello"),
        GestureEvent(t=4.0, kind="Closed_Fist", hand="right"),
        GestureEvent(t=5.0, kind="Closed_Fist", hand="right"),
    )
    state, effects = run_wake(capturer, ocr, events)
    captures = [effect for effect in effects if isinstance(effect, Capture)]
    discards = [effect for effect in effects if isinstance(effect, Discard)]
    assert len(captures) == 1, "capture must happen once per wake"
    assert capturer.calls == 1, "capture must happen once per wake"
    assert ocr.calls == 1, "capture must happen once per wake"
    assert state.phase == "IDLE"
    assert len(discards) == 1
    assert discards[0].capture_id == captures[0].capture_id, (
        "capture must happen once per wake"
    )


def _points(
    t0: float,
    first: tuple[float, float],
    second: tuple[float, float],
) -> list[GestureEvent]:
    return [
        GestureEvent(t=t0, kind="Pointing_Up", hand="right", landmarks=(first,)),
        GestureEvent(t=t0 + 1.0, kind="Pointing_Up", hand="right", landmarks=(first,)),
        GestureEvent(
            t=t0 + 2.0,
            kind="Pointing_Up",
            hand="right",
            landmarks=(second,),
        ),
        GestureEvent(
            t=t0 + 3.0,
            kind="Pointing_Up",
            hand="right",
            landmarks=(second,),
        ),
    ]
