"""Shared test isolation."""

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.getenv("RUN_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="set RUN_INTEGRATION=1 to run live, read-only integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
