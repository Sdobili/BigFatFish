"""Propose a card from OCR text. Offline tests do not call the network."""

import json
import logging
import os
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

_LOG = logging.getLogger(__name__)
_DEFAULT_MODEL = "qwen-plus"
_MAX_TOKENS = 256
_SYSTEM = (
    "You turn the text from one screen region into one small card: "
    "a note, a todo, or a translation."
)


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
    body: dict[str, object] = {
        "model": model,
        "messages": [dict(message) for message in messages],
        "max_tokens": max_tokens,
        "enable_thinking": False,
    }
    return {
        "url": base_url.rstrip("/") + "/chat/completions",
        "method": "POST",
        "headers": {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        "body": body,
    }


def request_for_log(request: Mapping[str, object]) -> dict[str, object]:
    logged = dict(request)
    headers = logged.get("headers")
    if isinstance(headers, dict):
        copied = dict(headers)
        copied.pop("Authorization", None)
        logged["headers"] = copied
    return logged


def parse_response(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) == 0:
        raise ProposalFailed("response has no choices")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise ProposalFailed("response choice is not an object")
    if choice["finish_reason"] == "length":
        raise ProposalFailed("truncated reply must fail")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ProposalFailed("response has no message")
    content = message.get("content")
    if not isinstance(content, str) or content == "":
        raise ProposalFailed("response has no content")
    return content


class RecordedProposer:
    """Replays proposals recorded for a fixture."""

    def __init__(self, replies: Sequence[str]) -> None:
        self._replies = list(replies)
        self._index = 0

    def propose(self, text: str) -> str:
        del text
        if self._index >= len(self._replies):
            raise ProposalFailed("no recorded proposal left")
        reply = self._replies[self._index]
        self._index += 1
        return reply


class QwenProposer:
    """Qwen chat completion. The key and base URL come from the environment."""

    def __init__(self, opener: _Opener | None = None) -> None:
        self._opener = _urlopen if opener is None else opener

    def propose(self, text: str) -> str:
        api_key = os.environ.get("QWEN_API_KEY")
        base_url = os.environ.get("QWEN_BASE_URL")
        if not api_key or not base_url:
            raise ProposalFailed("QWEN_API_KEY or QWEN_BASE_URL is not set")
        model = os.environ.get("QWEN_MODEL") or _DEFAULT_MODEL
        request = build_request(
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=(
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": text},
            ),
            max_tokens=_MAX_TOKENS,
        )
        _LOG.info("%s", request_for_log(request))
        raw = self._opener(request)
        decoded = json.loads(raw.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ProposalFailed("response is not an object")
        return parse_response(decoded)


def _urlopen(request: Mapping[str, object]) -> bytes:
    headers = request.get("headers")
    if not isinstance(headers, dict):
        raise ProposalFailed("request has no headers")
    outgoing = urllib.request.Request(
        str(request.get("url")),
        data=json.dumps(request.get("body")).encode("utf-8"),
        headers={str(key): str(value) for key, value in headers.items()},
        method=str(request.get("method") or "POST"),
    )
    with urllib.request.urlopen(outgoing, timeout=60) as response:
        data = response.read()
    if not isinstance(data, bytes):
        raise ProposalFailed("response body is not bytes")
    return data
