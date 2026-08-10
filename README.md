# Omni Connector Hub

One channel for everything: AI providers, email (multi-Gmail OAuth), hosting panels, VPS clouds, chat, GitHub, and server ops — behind one interface with explicit execution states and fail-closed safety policies.
## Production request pipeline

Python 3.11–3.14 is supported. Every CLI, Python, and MCP action is validated by
the same strict Pydantic v2 request model before mock or live connector code is
entered. Unknown fields, malformed URLs, invalid ranges, missing values, and
conflicting provider options are rejected. MCP publishes a dedicated
`<connector>__<action>` tool whose JSON Schema is generated from that model.

The shared `httpx` transport uses separate connect/read/write/pool timeouts,
bounded streamed bodies, per-provider concurrency limits, and exponential
backoff with jitter. Retries are limited to idempotent methods (or requests with
an explicit idempotency key), honor `Retry-After`, and surface normalized error
categories. Public safe GETs use bounded ETag/Last-Modified caching. Requests
with credential headers are not cached; redirects are disabled to reduce secret
leakage and SSRF pivot risk.

Logs are structured JSON on stderr and include request ID, connector/action,
latency, attempt count, and upstream status. Authorization/cookie/API-key
headers and Pydantic `SecretStr` fields are redacted. Keep credentials in
environment variables; never pass them as action parameters.

### Setup and tests

```bash
python -m pip install -e '.[test]'
pytest -q
RUN_INTEGRATION=1 pytest -q tests/test_integration.py
python -m hub.gateway mcp
```

The opt-in integration test reads real public repository metadata and requires
no credentials.

## Data Sources

https://api.github.com/repos/modelcontextprotocol/python-sdk

One channel for everything: AI providers, email (multi-Gmail OAuth), hosting panels, VPS clouds, chat, GitHub, and server ops — behind **one interface**, with **mock mode** so nothing explodes before you add credentials.

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
| `ops_ssh` | Local bash + SSH fleet commands | `HUB_ALLOW_LOCAL_EXEC=1` (+ `SSH_HOSTS`) |
| `ops_browser` | Fetch pages, status checks, screenshots | none (playwright for screenshots) |
| `ops_network` | ping, DNS, ports, traceroute, headers | partial gate |
| `ops_security` | SSL expiry, risky ports, sshd audit, secret gen | partial gate |

## 60-second start

```bash
cd connector-hub
cp .env.template .env          # fill in what you use
python3 -m hub.gateway list    # see every channel, MOCK vs LIVE
python3 -m hub.gateway status gmail
python3 -m hub.gateway call hetzner list_servers
```

Missing credentials return `ok: false`, `executed: false`, `state: "configuration_required"`, and a typed `error`. Request parameters are never echoed. This is distinct from an explicit dry run and cannot be mistaken for successful execution.

## Execution contract and dry runs

`hub_status` (or `python3 -m hub.gateway status <channel>`) reports every action's
`classification`, `dry_run_capable`, and `confirmation_required` values.

- A real success has `ok: true`, `executed: true`, and `state: "succeeded"`.
- Add `"dry_run": true` to preview a supported mutating/destructive action. The
  result has `ok: false`, `executed: false`, and `state: "dry_run"`; it contains
  no request-parameter echo.
- Missing credentials have `state: "configuration_required"`. A rejected or
  failed provider call has `state: "upstream_failure"` and a typed error.
- Destructive actions fail with `state: "confirmation_required"` unless passed
  `"confirmation_token": "CONFIRM:<channel>:<action>"` or
  `"policy_approved": true` from a trusted policy engine.

```bash
python3 -m hub.gateway call hetzner create_server '{"dry_run":true,"name":"example","server_type":"cx22","image":"ubuntu-24.04"}'
python3 -m hub.gateway call hetzner delete_server '{"id":123,"confirmation_token":"CONFIRM:hetzner:delete_server"}'
```

## Gmail OAuth (multiple accounts)

```bash
python3 scripts/setup_oauth.py    # per account: opens consent URL, mints refresh token into .env
python3 -m hub.gateway call gmail send '{"label":"main","to":"x@y.com","subject":"hi","body":"test"}'
```

## Use as MCP server (Claude Desktop / Kimi Code / any MCP client)

`mcp/mcp.json` contains `omni-hub` plus the official github/filesystem/fetch/puppeteer/memory servers. Merge its `mcpServers` block into your client's config. The hub exposes three stable tools — `hub_channels`, `hub_status`, `hub_call` — so every future connector appears automatically.

## Security model

- Secrets live only in `.env` (git-ignored). The base response contract never
  echoes parameters because message bodies and customer data can be sensitive
  even when their field names do not look like secrets.
- `ops_ssh` and system-level `ops_network` commands do **nothing real** until `HUB_ALLOW_LOCAL_EXEC=1`.
- Secrets live only in `.env` (git-ignored). Logs redact anything matching KEY/TOKEN/SECRET/PASS.
- Ops commands require deployment capabilities, allowlisted actions, destructive-action enablement, and an auditable approval identifier.
- OAuth refresh tokens are minted only by the script you run yourself.

## Layout

```
hub/            base contract, registry, gateway CLI, stdio MCP server
connectors/     one module per service, grouped by domain
mcp/mcp.json    drop-in MCP client config
scripts/        OAuth setup wizard
verifier/       acceptance checks + run log
```
## Security policy

Operations connectors share the fail-closed policy in `hub/security`. Configure
it through a connector's `config["security"]` object or the
`HUB_SECURITY_POLICY` JSON environment variable. URL policy defaults to HTTP(S)
on ports 80 and 443, resolves every initial and redirect host, blocks non-public
and cloud-metadata addresses, and connects to the validated address while
retaining the original HTTP Host and TLS SNI values.

Local and SSH execution no longer accepts free-form commands. A deployment must
enable the plugin capability, define an executable/action allowlist, list the
action under `destructive_actions`, and supply an identifier found in the
deployment `approvals` list. `HUB_ALLOW_LOCAL_EXEC` is not an authorization
mechanism and is ignored. Output is bounded and credentials are redacted.

See `.env.template` for a minimal policy example. Keep approval identifiers in
your change-management system and inject policy through deployment secrets;
never commit live approvals or credentials.
