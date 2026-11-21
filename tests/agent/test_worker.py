"""A hanging proposer must not stall the reflex path."""

import threading

from bigfatfish.agent.worker import AgentWorker
from bigfatfish.core.events import GestureEvent
from bigfatfish.reflex.state import ReflexState, initial, step

_EVENT_COUNT = 300


class _HangingProposer:
    """Waits forever on the worker thread and fails on the caller thread."""

    def __init__(self, caller: threading.Thread) -> None:
        self._caller = caller
        self._release = threading.Event()

    def propose(self, text: str) -> str:
        assert threading.current_thread() is not self._caller, (
            "proposer called on caller thread"
        )
        self._release.wait()
        return text

    def release(self) -> None:
        self._release.set()


def test_hanging_llm_does_not_block_reflex() -> None:
    proposer = _HangingProposer(threading.current_thread())
    worker = AgentWorker(proposer, maxsize=_EVENT_COUNT)
    events = _events(_EVENT_COUNT)
    expected = _reflex_trace(events)
    produced: list[ReflexState] = []
    state = initial()
    worker.start()
    try:
        for event in events:
            assert worker.submit(event) is True
            state = step(state, event)
            produced.append(state)
        assert len(produced) == _EVENT_COUNT
        assert produced == expected
        assert [item.t for item in produced] == [event.t for event in events]
    finally:
        proposer.release()
        worker.close()


def _events(count: int) -> list[GestureEvent]:
    events: list[GestureEvent] = []
    for index in range(count):
        events.append(
            GestureEvent(
                t=index / 10,
                kind="Thumb_Up" if index % 2 else "Open_Palm",
                hand="left" if index % 3 else "right",
                landmarks=((index / count, (count - index) / count),),
            )
        )
    return events


def _reflex_trace(events: list[GestureEvent]) -> list[ReflexState]:
    state = initial()
    trace: list[ReflexState] = []
    for event in events:
        state = step(state, event)
        trace.append(state)
    return trace
