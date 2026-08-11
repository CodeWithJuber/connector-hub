# Omni Connector Hub

One channel for AI providers, email, hosting panels, VPS clouds, chat, GitHub,
and server operations — behind one interface, with mock behavior when
credentials are absent.

> **Status**: The Python connector library is functional and serves 21
> connectors with 142 actions. A Rust rewrite (`crates/`) is in progress to
> provide spec-driven full-surface coverage, a type-safe execution contract,
> and an encrypted credential store.

## Channels

| Channel | What it does | Goes live when you set |
|---|---|---|
| `openai` | ChatGPT chat / models / embeddings | `OPENAI_API_KEY` |
| `claude` | Claude messages | `ANTHROPIC_API_KEY` |
| `kimi` | Kimi (Moonshot) chat | `MOONSHOT_API_KEY` |
| `cloudflare` | Workers AI models | `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN` |
| `email` | Multi-account IMAP/SMTP (read, search, send) | `EMAIL_ACCOUNTS` (JSON) |
| `gmail` | Gmail REST, multi-account OAuth2 | `GOOGLE_CLIENT_ID/SECRET` + refresh tokens |
| `whmcs` | Clients, invoices, tickets, service module actions | `WHMCS_URL` + API identifier/secret |
| `whm` | cPanel accounts, suspend/terminate, DNS zones, server status | `WHM_HOST` + root token |
| `cpanel` | Domains, email accounts, DBs, files, cron | `CPANEL_HOST` + user token |
| `hetzner` | Servers lifecycle, images, locations | `HETZNER_API_TOKEN` |
| `linode` | Linodes lifecycle, regions, types | `LINODE_API_TOKEN` |
| `contabo` | Instances lifecycle, images, snapshots | OAuth client + user creds |
| `ovh` | VPS/dedicated, IPs, account | OVH app key/secret/consumer key |
| `oneprovider` | Servers, reboots, locations | `ONEPROVIDER_API_KEY` |
| `ultrahost` | Services via WHMCS bridge | `ULTRAHOST_*` |
| `tawk` | tawk.to chats, tickets, agents | `TAWK_API_KEY` + property ID |
| `github` | Full repo/issue/PR/workflow/code-search control | `GITHUB_TOKEN` |
| `ops_ssh` | Local bash + SSH fleet commands | `HUB_SECURITY_POLICY` with capability grants |
| `ops_browser` | Fetch pages, status checks | none |
| `ops_network` | ping, DNS, ports, traceroute, headers | `HUB_SECURITY_POLICY` |
| `ops_security` | SSL expiry, risky ports, sshd audit, secret gen | `HUB_SECURITY_POLICY` |

## Quick start

```bash
cd connector-hub
cp .env.template .env          # fill in what you use
pip install -e '.[test]'       # or: uv sync --frozen --all-groups
python3 -m hub.gateway list    # see every channel, MOCK vs LIVE
python3 -m hub.gateway status gmail
python3 -m hub.gateway call hetzner list_servers
```

For a reproducible developer install (Python 3.11–3.13), install
[uv](https://docs.astral.sh/uv/getting-started/installation/) and run:

```bash
uv sync --frozen --all-groups
uv run connector-hub list
```

## Mock vs Live

Missing credentials select mock mode — calls return `{"ok": True, "mock": True}`
with the action echoed. This is for development only. When credentials are set
in `.env`, the connector goes live and makes real HTTP calls.

## Use as MCP server

```bash
python3 -m hub.gateway mcp
```

Each action is exposed as a tool named `hub__<connector>__<action>`.
The server bounds concurrent work (default 8, `HUB_MCP_MAX_CONCURRENCY`) and
applies a deadline to every call (default 30s, `HUB_MCP_CALL_TIMEOUT`).

## Gmail OAuth (multiple accounts)

```bash
python3 scripts/setup_oauth.py    # per account: opens consent URL, mints refresh token
python3 -m hub.gateway call gmail send '{"label":"main","to":"x@y.com","subject":"hi","body":"test"}'
```

## Security model

- Secrets live in `.env` (git-ignored) or platform secret managers. Never pass
  them as action parameters.
- Logs redact values matching KEY/TOKEN/SECRET/PASS patterns.
- Ops connectors (`ops_ssh`, `ops_network`) require deployment capabilities,
  allowlisted actions, and approval identifiers configured in `HUB_SECURITY_POLICY`.
  See `hub/security/policy.py` for SSRF defense, IP pinning, redirect validation,
  and bounded subprocess execution.
- OAuth refresh tokens are minted only by the setup script you run yourself.

## Tests

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -m "not integration"
RUN_INTEGRATION=1 uv run pytest -m integration tests/integration
```

## Data Sources

- https://github.com/CodeWithJuber/forgekit
- https://github.com/CodeWithJuber/hikmah-stack

Provider endpoints used by individual connectors are documented in their source
modules.

## Layout

```
crates/           Rust workspace (in progress)
hub/              Python registry, gateway CLI, MCP server
connectors/       Python connector implementations (one module per service)
mcp/mcp.json      drop-in MCP client config
scripts/          OAuth setup wizard
tests/            unit and opt-in integration tests
```

## CI

Every pull request runs: formatting, linting, type checking, non-integration
tests on Python 3.11 and 3.13, package builds, dependency auditing, and secret
scanning. Real-provider tests are opt-in behind the protected
`protected-integration` environment.
