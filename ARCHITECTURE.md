# ARCHITECTURE.md — Omni Connector Hub

One hub. Every external service behind one interface. Credentials in env, never in code.
Any connector works in **mock mode** (no credentials) so the hub is fully testable offline.

## Contract (every connector must implement)

```python
from hub.base import BaseConnector

class SomeConnector(BaseConnector):
    name = "servicename"          # registry key, lowercase
    def __init__(self, config=None): ...
    def actions(self) -> list[str]        # supported action names
    def call(self, action: str, **params) -> dict  # {"ok": bool, ...}
```

- Inherit `self.env("VAR")`, `self.mock` (auto True when required env missing),
  `self.http_json(method, url, headers, payload)` (stdlib urllib, JSON in/out),
  and `self.require(action)` guard.
- In mock mode `call()` returns `{"ok": True, "mock": True, "action": action,
  "echo": params, "note": "set <ENV_VARS> to go live"}` — never raises.
- Real mode raises `ConnectorError` with a clear message on auth/HTTP failure.
- Zero third-party dependencies in core. Optional libs (google-api-python-client,
  requests) imported lazily inside functions with a graceful fallback message.

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

## Groups & services
| group | services | auth |
|---|---|---|
| llm | openai (ChatGPT), anthropic (Claude), kimi (Moonshot), cloudflare (Workers AI) | API key / account+token |
| email | gmail OAuth2 multi-account, generic IMAP/SMTP multi-account | OAuth client JSON / app passwords |
| hosting | whmcs, whm, cpanel | API token / user+token |
| cloud | contabo, ovh, linode, hetzner, oneprovider, ultrahost | API tokens / OAuth (contabo, ovh app key) |
| chat | tawk.to REST | API key |
| github_full | github REST full-scope | PAT |
| ops | ssh_bash, browser, network, security | local / ssh keys |

## Security rules
1. No secret ever written to disk by the hub except user-run OAuth flows (scripts/setup_oauth.py writes to .env only).
2. `call()` never logs secret values; base redacts keys matching *KEY|TOKEN|SECRET|PASS*.
3. Ops connectors (ssh_bash) require `HUB_ALLOW_LOCAL_EXEC=1` to run real commands.
