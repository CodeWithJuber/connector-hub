"""Protocol-level coverage using the MCP SDK's real client/session transport."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import timedelta

import anyio
import pytest
from mcp.client._memory import InMemoryTransport
from mcp.client.session import ClientSession

from hub.mcp_server import create_server


@pytest.mark.anyio
async def test_initialize_discovery_and_valid_call() -> None:
    server = create_server()
    async with InMemoryTransport(server) as streams:
        async with ClientSession(*streams) as client:
            await client.initialize()
            tools = (await client.list_tools()).tools
            names = {tool.name for tool in tools}
            assert "hub__openai__list_models" in names
            tool = next(item for item in tools if item.name == "hub__openai__list_models")
            assert tool.inputSchema["type"] == "object"
            assert tool.annotations.readOnlyHint is True

            result = await client.call_tool("hub__openai__list_models", {})
            assert result.isError is not True
            body = json.loads(result.content[0].text)
            assert body["connector"] == "openai"
            assert body["action"] == "list_models"


@pytest.mark.anyio
async def test_invalid_arguments_and_unknown_connector_action_are_sanitized() -> None:
    server = create_server()
    async with InMemoryTransport(server) as streams:
        async with ClientSession(*streams) as client:
            await client.initialize()
            invalid = await client.call_tool("hub__openai__chat", {"messages": "not-a-list"})
            assert invalid.isError is True
            assert "Input validation error" in invalid.content[0].text

            unknown_action = await client.call_tool("hub__openai__does_not_exist", {})
            assert unknown_action.isError is True
            assert json.loads(unknown_action.content[0].text)["error"]["type"] == "unknown_action"

            unknown_connector = await client.call_tool("hub__does_not_exist__status", {})
            assert unknown_connector.isError is True
            assert "does not exist" in unknown_connector.content[0].text


@pytest.mark.anyio
async def test_call_deadline_cancels_waiting_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from hub import mcp_server

    original = mcp_server.get_connector

    class SlowConnector:
        def actions(self):
            return ["wait"]

        def call(self, action, **arguments):
            import time

            time.sleep(1)
            return {"ok": True}

    def connector(name, config=None):
        return SlowConnector() if name == "openai" else original(name, config)

    monkeypatch.setattr(mcp_server, "get_connector", connector)
    server = create_server(timeout_seconds=0.02)
    async with InMemoryTransport(server) as streams:
        async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=1)) as client:
            await client.initialize()
            result = await client.call_tool("hub__openai__wait", {})
            assert result.isError is True
            assert json.loads(result.content[0].text)["error"]["type"] == "timeout"


def test_malformed_input_and_graceful_eof_termination() -> None:
    env = {**os.environ, "HUB_ALLOW_LOCAL_EXEC": "0"}
    process = subprocess.run(
        [sys.executable, "-m", "hub.gateway", "mcp"],
        input="this is not json\n",
        text=True,
        capture_output=True,
        timeout=10,
        env=env,
        check=False,
    )
    assert process.returncode == 0
    # The SDK drops malformed frames, logs diagnostics to stderr, then shuts
    # down cleanly at EOF without reflecting attacker-controlled input.
    response = json.loads(process.stdout)
    assert response["method"] == "notifications/message"
    assert response["params"]["data"] == "Internal Server Error"
    assert "this is not json" not in process.stdout


@pytest.mark.anyio
async def test_client_cancellation_terminates_call() -> None:
    server = create_server(timeout_seconds=5)
    async with InMemoryTransport(server) as streams:
        async with ClientSession(*streams) as client:
            await client.initialize()
            with anyio.move_on_after(0.001) as scope:
                await client.call_tool("hub__ops_network__ping", {"host": "192.0.2.1", "count": 5})
            assert scope.cancel_called


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
