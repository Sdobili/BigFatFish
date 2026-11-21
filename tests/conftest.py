"""Pytest options shared by the suite."""

import os
import sys

import pytest
from hypothesis import settings

# Explicit load overrides the built-in ci profile Hypothesis turns on under CI.
settings.register_profile(
    "bigfatfish-full",
    max_examples=1000,
    derandomize=True,
    deadline=None,
    database=None,
)
settings.register_profile(
    "bigfatfish-gate",
    max_examples=100,
    derandomize=True,
    deadline=None,
    database=None,
)
if os.environ.get("BIGFATFISH_HYPOTHESIS_PROFILE") == "gate":
    settings.load_profile("bigfatfish-gate")
else:
    settings.load_profile("bigfatfish-full")

# Windows pipes default to cp1252. Pytest then unicode-escapes the Qwen
# failure text, so the mutation gate never sees the expect string.
# Conftest loads while capture is active, so the original streams are
# sys.__stdout__ / sys.__stderr__, not sys.stdout / sys.stderr.
for _stream in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):
    if _stream is None:
        continue
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is None:
        continue
    try:
        _reconfigure(encoding="utf-8")
    except (OSError, ValueError):
        pass


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="run tests that need network, camera, model, or a key",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not config.getoption("--live"):
        skip = pytest.mark.skip(
            reason="needs network, camera, model or key; skipped unless --live"
        )
        for item in items:
            if item.get_closest_marker("live") is not None:
                item.add_marker(skip)
