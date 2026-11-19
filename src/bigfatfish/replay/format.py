"""JSONL schema v1: one timestamped GestureEvent per line."""

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from bigfatfish.core.events import GestureEvent, load_event

SCHEMA = "v1"


def dumps_event(event: GestureEvent) -> str:
    payload: dict[str, object] = {"schema": SCHEMA}
    payload.update(event.to_dict())
    return json.dumps(payload, ensure_ascii=False)


def write_jsonl(path: Path, events: Iterable[GestureEvent]) -> None:
    text = "".join(f"{dumps_event(event)}\n" for event in events)
    path.write_text(text, encoding="utf-8", newline="\n")


def load_jsonl(path: Path) -> list[GestureEvent]:
    events: list[GestureEvent] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if line.strip() == "":
            continue
        events.append(_load_line(line, line_number))
    return events


def _load_line(line: str, line_number: int) -> GestureEvent:
    parsed = _as_object_dict(json.loads(line), line_number)
    if parsed.get("schema") != SCHEMA:
        raise ValueError(f"line {line_number}: expected schema {SCHEMA!r}")
    event = load_event(parsed)
    if not isinstance(event, GestureEvent):
        raise ValueError(f"line {line_number}: expected a gesture event")
    return event


def _as_object_dict(value: object, line_number: int) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"line {line_number}: expected a JSON object")
    mapped: dict[str, object] = {}
    items: Mapping[object, object] = value
    for key, item in items.items():
        if not isinstance(key, str):
            raise ValueError(f"line {line_number}: expected string keys")
        mapped[key] = item
    return mapped
