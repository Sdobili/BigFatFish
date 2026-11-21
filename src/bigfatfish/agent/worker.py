"""Agent worker. This stub runs the loop and proposer on the caller thread."""

from typing import Protocol

from bigfatfish.agent.loop import LoopEvent, initial, step


class Proposer(Protocol):
    def propose(self, text: str) -> str:
        """Return a proposal for the observed text."""
        ...


class AgentWorker:
    """Handles each submitted event before submit returns."""

    def __init__(self, proposer: Proposer, *, maxsize: int = 300) -> None:
        self._proposer = proposer
        self._state = initial()

    def start(self) -> None:
        """The stub has no thread."""

    def submit(self, ev: LoopEvent) -> bool:
        self._process(ev)
        return True

    def close(self) -> None:
        """The stub has nothing to stop."""

    def _process(self, ev: LoopEvent) -> None:
        self._state, _ = step(self._state, ev)
        self._proposer.propose(self._state.text)
