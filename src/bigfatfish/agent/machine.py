"""Minimal agent machine. It consumes Intent and emits Status."""

from dataclasses import dataclass

from bigfatfish.core.events import Intent, Status

_TRANSITIONS: dict[tuple[str, str], str] = {
    ("greet", "greet"): "greet",
    ("greet", "notice"): "look",
    ("greet", "rest"): "idle",
    ("idle", "greet"): "greet",
    ("idle", "notice"): "look",
    ("idle", "rest"): "idle",
    ("look", "greet"): "greet",
    ("look", "notice"): "look",
    ("look", "rest"): "idle",
}


@dataclass(frozen=True, slots=True)
class AgentState:
    t: float
    mode: str


def initial() -> AgentState:
    return AgentState(t=0.0, mode="idle")


def step(state: AgentState, intent: Intent) -> tuple[AgentState, Status]:
    mode = _TRANSITIONS.get((state.mode, intent.kind), state.mode)
    return AgentState(t=intent.t, mode=mode), Status(t=intent.t, kind=mode)
