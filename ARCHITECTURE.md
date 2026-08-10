# ARCHITECTURE.md — Omni Connector Hub

One hub. Every external service behind one interface. Credentials in env, never in code.
Connectors fail closed when credentials are unavailable; configuration failure is never represented as successful execution.

## Contract (every connector must implement)

```python
from hub.base import BaseConnector

class SomeConnector(BaseConnector):
    name = "servicename"          # registry key, lowercase
    def __init__(self, config=None): ...
    def actions(self) -> list[str]        # supported action names
    def call(self, action: str, **params) -> dict  # {"ok": bool, ...}
    read_only_actions = frozenset({...})
    mutating_actions = frozenset({...})
    destructive_actions = frozenset({...})
    dry_run_actions = frozenset({...})
```

- Inherit `self.env("VAR")`, `self.mock` (auto True when required env missing),
  `self.http_json(method, url, headers, payload)` (stdlib urllib, JSON in/out),
  and `self.require(action)` guard.
- Every declared action belongs to exactly one of `read_only_actions`,
  `mutating_actions`, or `destructive_actions`; registration status fails closed
  for missing, extra, or overlapping classifications. `dry_run_actions` is an
  explicit capability layered on those classifications.
- Missing credentials return a typed `configuration_required` result with
  `ok: false` and `executed: false`. No parameters are echoed.
- `dry_run=true` is intercepted before connector execution and is accepted only
  for actions in `dry_run_actions`. Its `state` is `dry_run`, never success.
- Real success sets `ok: true`, `executed: true`, `state: succeeded`. Connector
  and HTTP failures are normalized to `ok: false`, `state: upstream_failure`.
- Destructive execution requires `CONFIRM:<connector>:<action>` as the
  `confirmation_token`, or `policy_approved=true` from a trusted policy layer.
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
2. `call()` never echoes generic input parameters. Key-name redaction is not a
   sufficient defense for arbitrary message bodies, customer details, or secrets.
3. Destructive actions require an explicit confirmation token or policy approval.
4. Ops connectors (ssh_bash) require `HUB_ALLOW_LOCAL_EXEC=1` to run real commands.
