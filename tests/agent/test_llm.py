"""Offline Qwen request and response checks. No network."""

import json
import logging
from collections.abc import Mapping

import pytest

from bigfatfish.agent.llm import (
    ProposalFailed,
    QwenProposer,
    RecordedProposer,
    build_request,
    parse_response,
    request_for_log,
)

# Curl non-streaming example from the OpenAI-compatible Qwen doc:
# https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope
_DOC_CONTENT = "我是来自阿里云的大规模语言模型，我叫千问。"
_DOC_EXAMPLE: dict[str, object] = {
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": _DOC_CONTENT,
            },
            "finish_reason": "stop",
            "index": 0,
            "logprobs": None,
        }
    ],
    "object": "chat.completion",
    "usage": {
        "prompt_tokens": 11,
        "completion_tokens": 16,
        "total_tokens": 27,
    },
    "created": 1715252778,
    "system_fingerprint": "",
    "model": "qwen3.8-max",
    "id": "chatcmpl-xxx",
}


def test_build_request_matches_doc() -> None:
    api_key = "test-key"
    base_url = "https://example.invalid/compatible-mode/v1"
    model = "qwen-plus"
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "你是谁？"},
    ]
    request = build_request(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=messages,
        max_tokens=128,
    )
    headers = _dict(request.get("headers"))
    authorization = headers.get("Authorization", "")
    assert authorization == f"Bearer {api_key}", "Authorization must be Bearer"
    assert request.get("url") == f"{base_url}/chat/completions"
    assert request.get("method") == "POST"
    assert headers.get("Content-Type") == "application/json"
    body = request.get("body")
    assert isinstance(body, dict)
    assert body.get("model") == model
    assert body.get("enable_thinking") is False
    assert body.get("messages") == messages
    assert body.get("max_tokens") == 128
    logged = request_for_log(request)
    logged_headers = _dict(logged.get("headers"))
    assert "Authorization" not in logged_headers
    assert api_key not in str(logged)


def test_parse_doc_example() -> None:
    text = parse_response(_DOC_EXAMPLE)
    assert text == _DOC_CONTENT, "content must come from the documented response"


def test_length_is_failure() -> None:
    payload = {
        "choices": [
            {
                "finish_reason": "length",
                "index": 0,
                "message": {"role": "assistant", "content": "half a card"},
            }
        ]
    }
    text: str | None
    try:
        text = parse_response(payload)
    except ProposalFailed as exc:
        assert "truncated reply must fail" in str(exc)
        text = None
    assert text is None, "truncated reply must fail"


def test_recorded_proposer_replays_in_order() -> None:
    proposer = RecordedProposer(["first card", "second card"])
    assert proposer.propose("region") == "first card"
    assert proposer.propose("region again") == "second card"


def test_qwen_proposer_posts_documented_request(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("QWEN_BASE_URL", "https://example.invalid/compatible-mode/v1")
    monkeypatch.delenv("QWEN_MODEL", raising=False)
    captured: dict[str, object] = {}

    def opener(request: Mapping[str, object]) -> bytes:
        captured["request"] = dict(request)
        return json.dumps(_DOC_EXAMPLE).encode("utf-8")

    proposer = QwenProposer(opener=opener)
    with caplog.at_level(logging.INFO):
        text = proposer.propose("region text")
    request = captured.get("request")
    headers = _dict(request.get("headers") if isinstance(request, dict) else None)
    authorization = headers.get("Authorization", "")
    assert authorization == "Bearer test-key", "Authorization must be Bearer"
    assert text == _DOC_CONTENT
    body = request.get("body") if isinstance(request, dict) else None
    assert isinstance(body, dict)
    assert body.get("model") == "qwen-plus"
    assert body.get("enable_thinking") is False
    assert "test-key" not in caplog.text
    assert "Authorization" not in caplog.text


def _dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return value
