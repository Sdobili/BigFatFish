"""Drive reflex and agent from recorded gestures. Time comes from event.t."""

import json

from bigfatfish.agent import loop as agent_loop
from bigfatfish.agent import machine as agent_machine
from bigfatfish.agent.loop import Capture, Deliver, Discard, Effect, LoopState
from bigfatfish.core.events import GestureEvent, Intent
from bigfatfish.perception.wave import WaveDetector
from bigfatfish.reflex import state as reflex_state
from bigfatfish.replay.format import SessionEvent

_INTENTS = {
    "Closed_Fist": "rest",
    "ILoveYou": "notice",
    "Open_Palm": "notice",
    "Pointing_Up": "notice",
    "Thumb_Down": "rest",
    "Thumb_Up": "greet",
    "Victory": "greet",
}


def render_trace(events: list[GestureEvent]) -> list[str]:
    reflex: reflex_state.ReflexState = reflex_state.initial()
    agent: agent_machine.AgentState = agent_machine.initial()
    lines: list[str] = []
    for event in events:
        reflex = reflex_state.step(reflex, event)
        agent, status = agent_machine.step(agent, _intent(event))
        payload: dict[str, object] = {
            "t": event.t,
            "reflex": reflex.to_dict(),
            "status": status.kind,
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
    return lines


def _intent(event: GestureEvent) -> Intent:
    return Intent(t=event.t, kind=_INTENTS.get(event.kind, "notice"))


def render_loop_trace(events: list[SessionEvent]) -> list[str]:
    detector = WaveDetector()
    state = agent_loop.initial()
    lines: list[str] = []
    for recorded in events:
        incoming: agent_loop.LoopEvent = recorded
        if isinstance(recorded, GestureEvent):
            wave = detector.feed(recorded)
            if wave is not None:
                incoming = wave
        state, effects = agent_loop.step(state, incoming)
        payload = _loop_line(recorded.t, state, effects)
        lines.append(json.dumps(payload, ensure_ascii=False))
    return lines


def _loop_line(
    t: float,
    state: LoopState,
    effects: list[Effect],
) -> dict[str, object]:
    return {
        "t": t,
        "phase": state.phase,
        "revisions": state.revisions,
        "box": _corners(state.corner1, state.corner2),
        "hint": _box(state.hint),
        "effects": [_effect_payload(effect) for effect in effects],
    }


def _effect_payload(effect: Effect) -> dict[str, object]:
    if isinstance(effect, Capture):
        return {"kind": "Capture", "capture_id": effect.capture_id}
    if isinstance(effect, Discard):
        return {"kind": "Discard", "capture_id": effect.capture_id}
    if isinstance(effect, Deliver):
        return {
            "kind": "Deliver",
            "capture_id": effect.capture_id,
            "box": _box(effect.box),
            "window_title": effect.window_title,
            "text": effect.text,
            "proposal": effect.proposal,
            "revisions": effect.revisions,
        }
    raise TypeError(f"unknown effect: {type(effect).__name__}")


def _corners(
    corner1: tuple[float, float] | None,
    corner2: tuple[float, float] | None,
) -> list[list[float]] | None:
    if corner1 is None or corner2 is None:
        return None
    return [[corner1[0], corner1[1]], [corner2[0], corner2[1]]]


def _box(
    box: tuple[tuple[float, float], tuple[float, float]] | None,
) -> list[list[float]] | None:
    if box is None:
        return None
    return [[box[0][0], box[0][1]], [box[1][0], box[1][1]]]
