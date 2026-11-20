"""Timestamped events passed between layers."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GestureEvent:
    t: float
    kind: str
    hand: str
    landmarks: tuple[tuple[float, ...], ...] | None = None
    score: float | None = None

    def to_dict(self) -> dict[str, object]:
        if self.landmarks is None:
            landmarks: object = None
        else:
            landmarks = [list(point) for point in self.landmarks]
        payload = {
            "type": "gesture",
            "t": self.t,
            "kind": self.kind,
            "hand": self.hand,
            "landmarks": landmarks,
        }
        if self.score is not None:
            payload["score"] = self.score
        return payload


@dataclass(frozen=True, slots=True)
class Intent:
    t: float
    kind: str

    def to_dict(self) -> dict[str, object]:
        return {"type": "intent", "t": self.t, "kind": self.kind}


@dataclass(frozen=True, slots=True)
class Status:
    t: float
    kind: str

    def to_dict(self) -> dict[str, object]:
        return {"type": "status", "t": self.t, "kind": self.kind}


@dataclass(frozen=True, slots=True)
class Tick:
    t: float

    def to_dict(self) -> dict[str, object]:
        return {"type": "tick", "t": self.t}


@dataclass(frozen=True, slots=True)
class Observation:
    t: float
    window_title: str
    text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "observation",
            "t": self.t,
            "window_title": self.window_title,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class ProposalReady:
    t: float
    text: str

    def to_dict(self) -> dict[str, object]:
        return {"type": "proposal", "t": self.t, "text": self.text}


Event = GestureEvent | Intent | Status | Tick | Observation | ProposalReady


def load_event(data: Mapping[str, object]) -> Event:
    event_type = data["type"]
    if event_type == "gesture":
        return GestureEvent(
            t=_as_float(data["t"]),
            kind=_as_str(data["kind"]),
            hand=_as_str(data["hand"]),
            landmarks=_as_landmarks(data["landmarks"]),
            score=_as_optional_float(data.get("score")),
        )
    if event_type == "intent":
        return Intent(t=_as_float(data["t"]), kind=_as_str(data["kind"]))
    if event_type == "status":
        return Status(t=_as_float(data["t"]), kind=_as_str(data["kind"]))
    if event_type == "tick":
        return Tick(t=_as_float(data["t"]))
    if event_type == "observation":
        return Observation(
            t=_as_float(data["t"]),
            window_title=_as_str(data["window_title"]),
            text=_as_str(data["text"]),
        )
    if event_type == "proposal":
        return ProposalReady(t=_as_float(data["t"]), text=_as_str(data["text"]))
    raise ValueError(f"unknown event type: {event_type!r}")


def _as_landmarks(value: object) -> tuple[tuple[float, ...], ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise TypeError("landmarks must be a list or null")
    return tuple(_as_point(point) for point in value)


def _as_point(value: object) -> tuple[float, ...]:
    if not isinstance(value, list):
        raise TypeError("landmark must be a list of numbers")
    return tuple(_as_float(item) for item in value)


def _as_optional_float(value: object) -> float | None:
    if value is None:
        return None
    return _as_float(value)


def _as_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("expected a number")
    return float(value)


def _as_str(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("expected a string")
    return value
