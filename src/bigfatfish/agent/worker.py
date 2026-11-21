"""Agent thread. submit only enqueues; the loop and proposer run there."""

import threading
from typing import Protocol

from bigfatfish.agent.loop import LoopEvent, initial, step
from bigfatfish.core.bus import Channel

_DEFAULT_MAXSIZE = 300
_POLL_S = 0.01


class Proposer(Protocol):
    def propose(self, text: str) -> str:
        """Return a proposal for the observed text."""
        ...


class AgentWorker:
    """Runs loop.step and the proposer on a private thread."""

    def __init__(self, proposer: Proposer, *, maxsize: int = _DEFAULT_MAXSIZE) -> None:
        self._proposer = proposer
        self._inbox: Channel[LoopEvent] = Channel(maxsize=maxsize)
        self._state = initial()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def submit(self, ev: LoopEvent) -> bool:
        return self._inbox.put_nowait(ev)

    def close(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            event = self._inbox.get_nowait()
            if event is None:
                self._stop.wait(_POLL_S)
                continue
            self._process(event)

    def _process(self, ev: LoopEvent) -> None:
        self._state, _ = step(self._state, ev)
        self._proposer.propose(self._state.text)
