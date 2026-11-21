"""Hypothesis profiles for the full suite and the mutation-gate child."""

import os

import pytest
from hypothesis import settings
from hypothesis.errors import InvalidArgument


def test_profiles() -> None:
    try:
        full = settings.get_profile("bigfatfish-full")
    except InvalidArgument:
        pytest.fail("profile bigfatfish-full must be registered")
    try:
        gate = settings.get_profile("bigfatfish-gate")
    except InvalidArgument:
        pytest.fail("profile bigfatfish-gate must be registered")
    message = "full profile must run " + "1000 examples"
    assert full.max_examples == 1000, message
    assert gate.max_examples == 100
    assert full.derandomize is True
    assert gate.derandomize is True
    assert full.deadline is None
    assert gate.deadline is None
    assert full.database is None
    assert gate.database is None
    if os.environ.get("BIGFATFISH_HYPOTHESIS_PROFILE") is None:
        assert settings().max_examples == 1000
