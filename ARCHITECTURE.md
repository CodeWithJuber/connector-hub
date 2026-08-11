# ARCHITECTURE.md — Omni Connector Hub

One hub. Every external service behind one interface. Credentials in env, never
in code. Connectors return mock responses when credentials are unavailable.

> **Active rewrite**: The `crates/` Rust workspace replaces this Python
> implementation with spec-driven connectors, a type-safe execution contract,
> and an encrypted credential store. See `crates/README.md` for the new
> architecture.

## Current Python contract

```python
from hub.base import BaseConnector

class SomeConnector(BaseConnector):
    name = "servicename"
    def __init__(self, config=None): ...
    def actions(self) -> list[str]
    def call(self, action: str, **params) -> dict  # {"ok": bool, ...}
```

- Inherit `self.env("VAR")`, `self.mock` (True when required env missing),
  `self.http_json(method, url, headers, payload)` (stdlib urllib, JSON in/out).
- Mock mode returns `{"ok": True, "mock": True}` — development convenience only.
- Live mode makes real HTTP calls with per-connector auth.

## Layers

```
CLI / MCP server (hub/gateway.py, hub/mcp_server.py)
        │  route "channel" name → connector
Registry (hub/base.py — auto-discovers connectors/*)
        │
Connectors (connectors/<group>/<service>.py)
        │
Secrets (.env — gitignored; .env.template committed)
```

## Groups and services

| Group | Services | Auth |
|---|---|---|
| llm | openai, anthropic, kimi, cloudflare | API key / account+token |
| email | gmail (OAuth2 multi-account), email (IMAP/SMTP multi-account) | OAuth / app passwords |
| hosting | whmcs, whm, cpanel | API token / user+token |
| cloud | contabo, ovh, linode, hetzner, oneprovider, ultrahost | API tokens / OAuth |
| chat | tawk.to | API key |
| github_full | github REST | PAT |
| ops | ssh_bash, browser, network, security | HUB_SECURITY_POLICY capability grants |

## Security

1. No secret written to disk except user-run OAuth flows (`scripts/setup_oauth.py`).
2. Logs redact credential patterns.
3. Ops connectors require `HUB_SECURITY_POLICY` capability grants — see
   `hub/security/policy.py` for SSRF defense, IP pinning, and bounded execution.
