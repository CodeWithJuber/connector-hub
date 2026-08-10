"""MCP SDK based stdio server for the validated connector action registry."""
"""Minimal stdio MCP server exposing every connector as tools.

Framing: LSP-style 'Content-Length: N\\r\\n\\r\n{json}' per message.
Tools:
  - hub_channels            -> list channels + live/mock mode
  - hub_status              -> {channel}
  - hub_call                -> {channel, action, params, dry_run, authorization}
This keeps the MCP surface stable even as connectors are added.
"""
import json
import sys

from . import get_connector, list_connectors, load_connectors
from .schemas import action_json_schema

from __future__ import annotations

import inspect
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool, ToolAnnotations

from . import ConnectorError, get_connector, list_connectors, load_connectors

LOG = logging.getLogger("connector_hub.mcp")
_SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_READ_PREFIXES = ("list", "get", "check", "search", "status", "fetch", "audit", "resolve")
_DESTRUCTIVE_PREFIXES = ("delete", "terminate", "remove", "revoke", "suspend")
_ACTION_SCHEMAS: dict[tuple[str, str], dict[str, Any]] = {
    ("openai", "chat"): {
        "type": "object",
        "properties": {
            "messages": {"type": "array", "items": {"type": "object"}},
            "model": {"type": "string"},
            "temperature": {"type": "number", "minimum": 0, "maximum": 2},
TOOLS = [
    {
        "name": "hub_channels",
        "description": "List every connector channel. Use hub_status for configuration and action safety metadata.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "hub_status",
        "description": "Status of one channel, including missing configuration and per-action read-only, mutating, destructive, dry-run, and confirmation policies.",
        "inputSchema": {
            "type": "object",
            "properties": {"channel": {"type": "string"}},
            "required": ["channel"],
        },
        "required": ["messages"],
        "additionalProperties": True,
    },
    ("openai", "embeddings"): {
        "type": "object",
        "properties": {
            "input": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
            "model": {"type": "string"},
    {
        "name": "hub_call",
        "description": (
            "Call an action. Inspect ok, executed, and state: succeeded means real "
            "execution; dry_run means no execution; configuration_required and "
            "upstream_failure are typed failures. Destructive actions require the "
            "confirmation token shown by hub_status conventions or policy approval."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string"},
                "action": {"type": "string"},
                "params": {"type": "object"},
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview a dry-run-capable action without performing it.",
                },
                "confirmation_token": {
                    "type": "string",
                    "description": "For destructive actions: CONFIRM:<channel>:<action>.",
                },
                "policy_approved": {
                    "type": "boolean",
                    "description": "True only when an external policy engine approved the destructive action.",
                },
            },
            "required": ["channel", "action"],
        },
        "required": ["input"],
        "additionalProperties": True,
    },
}
]


def _tools():
    """Build MCP schemas directly from the Pydantic action request models."""
    tools = list(TOOLS)
    for channel in list_connectors():
        conn = get_connector(channel)
        for action in conn.actions():
            tools.append({
                "name": f"{channel}__{action}",
                "description": f"Run {action} on the {channel} connector",
                "inputSchema": action_json_schema(conn, action),
            })
    return tools


def _read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        k, _, v = line.partition(b":")
        headers[k.strip().lower()] = v.strip()
    length = int(headers.get(b"content-length", 0))
    if not length:
        return None
    return json.loads(sys.stdin.buffer.read(length))


@dataclass(frozen=True)
class Action:
    connector: str
    name: str

    @property
    def tool_name(self) -> str:
        """Stable namespace; double underscore cannot collide with registry names."""
        return f"hub__{self.connector}__{self.name}"

    @property
    def read_only(self) -> bool:
        return self.name.startswith(_READ_PREFIXES)

    @property
    def destructive(self) -> bool:
        return self.name.startswith(_DESTRUCTIVE_PREFIXES)


def build_action_registry() -> dict[str, Action]:
    """Validate connector/action identifiers and return tools keyed by MCP name."""

def _text(data):
    return {"content": [{"type": "text", "text": json.dumps(data, indent=2, default=str)}]}


def _call_tool(name, args):
    if name == "hub_channels":
        return _text({n: {"description": d} for n, d in list_connectors().items()})
    if name == "hub_status":
        return _text(get_connector(args["channel"]).status())
    if name == "hub_call":
        conn = get_connector(args["channel"])
        params = dict(args.get("params") or {})
        for option in ("dry_run", "confirmation_token", "policy_approved"):
            if option in args:
                params[option] = args[option]
        return _text(conn.call(args["action"], **params))
        return _text(conn.call(args["action"], **(args.get("params") or {})))
    if "__" in name:
        channel, action = name.split("__", 1)
        return _text(get_connector(channel).call(action, **args))
    raise ValueError(f"unknown tool {name}")


def serve():
    load_connectors()
    registry: dict[str, Action] = {}
    for connector in list_connectors():
        if not _SAFE_NAME.fullmatch(connector):
            raise RuntimeError(f"invalid connector identifier: {connector!r}")
        actions = get_connector(connector).actions()
        if not isinstance(actions, (list, tuple)) or not actions:
            raise RuntimeError(f"connector {connector!r} has no validated actions")
        for name in actions:
            if not isinstance(name, str) or not _SAFE_NAME.fullmatch(name):
                raise RuntimeError(f"invalid action identifier for {connector!r}: {name!r}")
            action = Action(connector, name)
            if action.tool_name in registry:
                raise RuntimeError(f"duplicate MCP tool: {action.tool_name}")
            registry[action.tool_name] = action
    return registry


def _tool(action: Action) -> Tool:
    # Existing connectors accept keyword arguments. This schema still provides
    # SDK-level object/type validation while preserving their evolving APIs.
    schema = _ACTION_SCHEMAS.get(
        (action.connector, action.name), {"type": "object", "additionalProperties": True}
    )
    return Tool(
        name=action.tool_name,
        description=f"{action.connector}: {action.name}",
        inputSchema=schema,
        annotations=ToolAnnotations(
            readOnlyHint=action.read_only,
            destructiveHint=action.destructive,
            idempotentHint=action.read_only,
            openWorldHint=not action.read_only,
        ),
    )


def _error(kind: str, message: str) -> RuntimeError:
    """Build the only exception text allowed to cross the MCP boundary."""
    payload = {"error": {"type": kind, "message": message}}
    return RuntimeError(json.dumps(payload, separators=(",", ":")))


def _classify(exc: BaseException) -> tuple[str, str]:
    """Map internal failures to stable messages without reflecting secrets."""
    text = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timed out" in text or "timeout" in text:
        return "timeout", "The connector call exceeded its deadline."
    if "rate" in text and ("limit" in text or "429" in text):
        return "rate_limit", "The upstream service rate limit was reached."
    if any(word in text for word in ("auth", "credential", "401", "403", "token")):
        return "authentication", "Connector authentication failed."
    if "policy" in text or "not allowed" in text or "forbidden" in text:
        return "policy", "The call was denied by connector policy."
    if isinstance(exc, (TypeError, ValueError)) or "requires" in text or "required" in text:
        return "validation", "The connector rejected the supplied arguments."
    if isinstance(exc, ConnectorError):
        return "upstream", "The upstream connector request failed."
    return "internal", "The connector call failed unexpectedly."


class ConnectorRuntime:
    def __init__(self, max_concurrency: int, timeout_seconds: float) -> None:
        self.actions = build_action_registry()
        self.connectors: dict[str, Any] = {}
        self.limiter = anyio.Semaphore(max_concurrency)
        self.timeout_seconds = timeout_seconds

    def connector(self, name: str) -> Any:
        if name not in self.connectors:
            self.connectors[name] = get_connector(name)
        return self.connectors[name]

    async def close(self) -> None:
        for connector in self.connectors.values():
            close = getattr(connector, "aclose", None) or getattr(connector, "close", None)
            if close:
                result = close()
                if inspect.isawaitable(result):
                    await result
        self.connectors.clear()

    async def call(self, action: Action, arguments: dict[str, Any]) -> Any:
        async with self.limiter:
            with anyio.fail_after(self.timeout_seconds):
                # abandon_on_cancel ensures MCP cancellation/deadlines propagate
                # immediately even though legacy connectors are synchronous.
                return await anyio.to_thread.run_sync(
                    lambda: self.connector(action.connector).call(action.name, **arguments),
                    abandon_on_cancel=True,
                )


def create_server(
    *, max_concurrency: int | None = None, timeout_seconds: float | None = None
) -> Server:
    """Create an isolated server instance (also useful for protocol tests)."""
    concurrency = max_concurrency or int(os.getenv("HUB_MCP_MAX_CONCURRENCY", "8"))
    deadline = timeout_seconds or float(os.getenv("HUB_MCP_CALL_TIMEOUT", "30"))
    if concurrency < 1 or deadline <= 0:
        raise ValueError("MCP concurrency and timeout settings must be positive")
    runtime = ConnectorRuntime(concurrency, deadline)

    @asynccontextmanager
    async def lifespan(_server: Server) -> AsyncIterator[ConnectorRuntime]:
        try:
            yield runtime
        finally:
            await runtime.close()

    server = Server("omni-connector-hub", version="2.0.0", lifespan=lifespan)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [_tool(action) for action in runtime.actions.values()]

    @server.call_tool(validate_input=True)
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        request_id = uuid.uuid4().hex
        action = runtime.actions.get(name)
        if action is None:
            LOG.warning("unknown_tool", extra={"request_id": request_id, "tool": name})
            raise _error("unknown_action", "The requested connector action does not exist.")
        try:
            result = await runtime.call(action, arguments)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        except anyio.get_cancelled_exc_class():
            LOG.info("call_cancelled", extra={"request_id": request_id, "tool": name})
            raise
        except BaseException as exc:
            kind, client_message = _classify(exc)
            LOG.exception(
                "connector_call_failed",
                extra={"request_id": request_id, "tool": name, "failure_type": kind},
            )
            raise _error(kind, client_message) from None

    return server


async def serve_async() -> None:
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def serve() -> None:
    """Run until EOF/SIGTERM; AnyIO performs structured graceful shutdown."""
    logging.basicConfig(level=os.getenv("HUB_LOG_LEVEL", "INFO"), stream=os.sys.stderr)
    try:
        anyio.run(serve_async)
    except KeyboardInterrupt:
        LOG.info("server_shutdown")
            if method == "initialize":
                _result(msg_id, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "omni-connector-hub", "version": "1.0.0"},
                })
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                _result(msg_id, {"tools": _tools()})
            elif method == "tools/call":
                p = msg.get("params", {})
                _result(msg_id, _call_tool(p.get("name"), p.get("arguments") or {}))
            elif method == "ping":
                _result(msg_id, {})
            elif msg_id is not None:
                _error(msg_id, -32601, f"method not found: {method}")
        except Exception as e:  # never crash the server loop
            if msg_id is not None:
                _error(msg_id, -32000, str(e))
