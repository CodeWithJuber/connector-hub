"""Real-data test against GitHub's no-auth public API."""

import os

import pytest

from hub.http_client import SharedHttpClient


@pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1")
def test_real_github_api():
    # Data source: https://api.github.com/repos/modelcontextprotocol/python-sdk
    result = SharedHttpClient().request_json(
        "github-public", "GET", "https://api.github.com/repos/modelcontextprotocol/python-sdk"
    )
    assert result["status"] == 200
    assert result["data"].get("full_name") == "modelcontextprotocol/python-sdk"
