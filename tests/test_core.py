"""Core events and the non-blocking bus."""

import json
import threading

import pytest


def test_bus_never_blocks() -> None:
    from bigfatfish.core.bus import Channel

    channel = Channel(maxsize=1)
    assert channel.put_nowait("kept") is True

    result: list[bool] = []

    def put_when_full() -> None:
        result.append(channel.put_nowait("dropped"))

    worker = threading.Thread(target=put_when_full, daemon=True)
    worker.start()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert result == [False]


def test_channel_rejects_non_positive_maxsize() -> None:
    from bigfatfish.core.bus import Channel

    for maxsize in (0, -1):
        with pytest.raises(ValueError):
            Channel(maxsize=maxsize)


def test_event_roundtrip() -> None:
    from bigfatfish.core.events import GestureEvent, Intent, Status, load_event

    events = [
        GestureEvent(
            t=1.25,
            kind="pinch",
            hand="left",
            landmarks=((0.1, 0.2), (0.3, 0.4, 0.5)),
        ),
        GestureEvent(t=0.0, kind="open", hand="right"),
        Intent(t=2.0, kind="greet"),
        Status(t=3.5, kind="idle"),
    ]
    for event in events:
        payload = json.dumps(event.to_dict())
        assert load_event(json.loads(payload)) == event
