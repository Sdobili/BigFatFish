"""Pytest options shared by the suite."""

import pytest


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
