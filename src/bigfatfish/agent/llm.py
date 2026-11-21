"""Propose a card from OCR text. Offline tests do not call the network."""

from collections.abc import Mapping, Sequence
from typing import Protocol


class ProposalFailed(RuntimeError):
    """The model reply cannot become a card."""


class Proposer(Protocol):
    def propose(self, text: str) -> str:
        """Return a proposal for the observed text."""
        ...


class _Opener(Protocol):
    def __call__(self, request: Mapping[str, object]) -> bytes:
        """Send one prepared request and return the response body."""
        ...


def build_request(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: Sequence[Mapping[str, str]],
    max_tokens: int,
) -> dict[str, object]:
    del base_url, api_key, model, messages, max_tokens
    return {}


def request_for_log(request: Mapping[str, object]) -> dict[str, object]:
    del request
    return {}


def parse_response(payload: Mapping[str, object]) -> str:
    del payload
    return ""


class RecordedProposer:
    """Replays proposals recorded for a fixture."""

    def __init__(self, replies: Sequence[str]) -> None:
        self._replies = list(replies)

    def propose(self, text: str) -> str:
        del text
        return ""


class QwenProposer:
    """Qwen chat completion. The red stub does not build a request."""

    def __init__(self, opener: _Opener | None = None) -> None:
        self._opener = opener

    def propose(self, text: str) -> str:
        del text
        return ""
