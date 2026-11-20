"""One Qwen chat completion. Needs --live and the two env vars."""

import json
import os
import urllib.request

import pytest

pytestmark = pytest.mark.live

_PROMPT = "Reply with the single word ok."


def test_qwen_chat_completion() -> None:
    api_key = os.environ.get("QWEN_API_KEY")
    base_url = os.environ.get("QWEN_BASE_URL")
    if not api_key or not base_url:
        pytest.fail("QWEN_API_KEY 或 QWEN_BASE_URL 未设置")
    model = os.environ.get("QWEN_MODEL") or "qwen-plus"
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a test probe."},
            {"role": "user", "content": _PROMPT},
        ],
        "max_tokens": 32,
        "enable_thinking": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    content = payload["choices"][0]["message"]["content"]
    assert content
    assert payload["usage"]["total_tokens"] > 0
