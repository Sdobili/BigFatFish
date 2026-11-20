"""Schema v2 round-trips four line types and v1 rejects a tick line."""

from pathlib import Path

import pytest


def test_v2_roundtrip_four_line_types(tmp_path: Path) -> None:
    from bigfatfish.core.events import GestureEvent, Observation, ProposalReady, Tick
    from bigfatfish.replay.format import load_session, write_session

    events = [
        GestureEvent(
            t=0.0,
            kind="Open_Palm",
            hand="right",
            landmarks=((0.1, 0.2, 0.0),),
            score=0.91,
        ),
        Tick(t=1.5),
        Observation(t=2.0, window_title="Notes", text="hello"),
        ProposalReady(t=3.0, text="a card"),
    ]
    path = tmp_path / "session.jsonl"
    write_session(path, events)
    text = path.read_text(encoding="utf-8")
    assert '"schema": "v2"' in text
    assert load_session(path) == events


def test_v1_file_with_tick_line_is_rejected(tmp_path: Path) -> None:
    from bigfatfish.replay.format import load_session

    path = tmp_path / "v1-tick.jsonl"
    path.write_text(
        '{"schema": "v1", "type": "tick", "t": 1.0}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="gesture"):
        load_session(path)
