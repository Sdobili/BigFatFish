"""Drive reflex and agent from recorded gestures. Time comes from event.t."""

import json

from bigfatfish.agent import machine as agent_machine
from bigfatfish.core.events import GestureEvent, Intent
from bigfatfish.reflex import state as reflex_state

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
