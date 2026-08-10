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

PROTOCOL_VERSION = "2024-11-05"

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
    },
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
    },
]


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


def _send(payload):
    body = json.dumps(payload).encode()
    sys.stdout.buffer.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
    sys.stdout.buffer.flush()


def _result(msg_id, result):
    _send({"jsonrpc": "2.0", "id": msg_id, "result": result})


def _error(msg_id, code, message):
    _send({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}})


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
    raise ValueError(f"unknown tool {name}")


def serve():
    load_connectors()
    while True:
        msg = _read_message()
        if msg is None:
            break
        method = msg.get("method", "")
        msg_id = msg.get("id")
        try:
            if method == "initialize":
                _result(msg_id, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "omni-connector-hub", "version": "1.0.0"},
                })
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                _result(msg_id, {"tools": TOOLS})
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
