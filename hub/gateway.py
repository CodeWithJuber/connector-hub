"""Channel gateway CLI — route one command to any connector.

Usage:
  python3 -m hub.gateway list                          # all channels + mode
  python3 -m hub.gateway status <channel>
  python3 -m hub.gateway call <channel> <action> '{"k": "v"}'
  python3 -m hub.gateway mcp                           # stdio MCP server
"""

import json
import os
import sys

# load .env if present (KEY=VALUE lines, no quotes needed)
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from . import get_connector, list_connectors, load_connectors  # noqa: E402


def main(argv=None):
    argv = argv or sys.argv[1:]
    load_connectors()

    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0

    cmd = argv[0]

    if cmd == "list":
        for name, desc in list_connectors().items():
            conn = get_connector(name)
            mode = "MOCK" if conn.mock else "LIVE"
            print(f"[{mode:4}] {name:14} {desc}")
        return 0

    if cmd == "health":
        print(json.dumps({"ok": True, "service": "omni-connector-hub"}))
        return 0

    if cmd == "status":
        conn = get_connector(argv[1])
        print(json.dumps(conn.status(), indent=2))
        return 0

    if cmd == "call":
        if len(argv) < 3:
            print("usage: call <channel> <action> '{json params}'", file=sys.stderr)
            return 2
        params = json.loads(argv[3]) if len(argv) > 3 else {}
        conn = get_connector(argv[1])
        result = conn.call(argv[2], **params)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 1

    if cmd == "mcp":
        from .mcp_server import serve

        serve()
        return 0

    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
