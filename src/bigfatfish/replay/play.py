"""Drive reflex and agent from recorded gestures. Time comes from event.t."""

import json

from bigfatfish.agent.machine import (
    AgentState,
    initial as initial_agent,
    step as step_agent,
)
from bigfatfish.core.events import GestureEvent, Intent
from bigfatfish.reflex.state import (
    ReflexState,
    initial as initial_reflex,
    step as step_reflex,
)

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
    reflex: ReflexState = initial_reflex()
    agent: AgentState = initial_agent()
    lines: list[str] = []
    for event in events:
        reflex = step_reflex(reflex, event)
        agent, status = step_agent(agent, _intent(event))
        payload: dict[str, object] = {
            "t": event.t,
            "reflex": reflex.to_dict(),
            "status": status.kind,
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
    return lines


def _intent(event: GestureEvent) -> Intent:
    return Intent(t=event.t, kind=_INTENTS.get(event.kind, "notice"))
