#!/usr/bin/env python3
"""Launch the repository's Connector Hub MCP service from any working directory."""
from __future__ import annotations

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[5]
if not (ROOT / "hub" / "mcp_server.py").is_file():
    print(f"Connector Hub package was not found at {ROOT}", file=sys.stderr)
    raise SystemExit(78)

os.environ.setdefault("HUB_ALLOW_LOCAL_EXEC", "0")
sys.path.insert(0, str(ROOT))

from hub.mcp_server import serve  # noqa: E402

serve()
