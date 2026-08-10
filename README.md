# Omni Connector Hub

One channel for everything: AI providers, email (multi-Gmail OAuth), hosting panels, VPS clouds, chat, GitHub, and server ops — behind **one interface**, with safe dry-run behavior before you add credentials.

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

Anything without credentials answers in **mock mode** (dry-run echo) — the hub is fully usable for testing workflows before secrets exist.

For a reproducible developer install (Python 3.11–3.14), install
[uv](https://docs.astral.sh/uv/getting-started/installation/) and run:

```bash
uv sync --frozen --all-groups
uv run connector-hub list
```

## Safe configuration and secret acquisition

Copy `.env.template` to `.env` only for local development; `.env` is ignored by
Git. In production, inject individual variables using the platform's secret
manager. Create provider credentials in the provider console, select the
smallest possible scopes, prefer read-only permissions, set an expiry, and
rotate immediately if a credential reaches logs or version control. The links
and console paths in `.env.template` and the channel table identify each source.
Never use production credentials in pull-request CI.

Network requests have bounded timeouts, retry transient GET failures with
exponential backoff and jitter, honor numeric `Retry-After`, and normalize
errors. Connector base URLs are fixed in code; do not pass untrusted URLs to
operations connectors without an outbound allowlist at the deployment layer.

## Tests

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -m "not integration" tests/unit
RUN_INTEGRATION=1 uv run pytest -m integration tests/integration
```

Integration tests contact real, documented endpoints and are read-only. They
are opt-in via `RUN_INTEGRATION=1`, use five-second request timeouts, and make
one request per endpoint. Credentialed cases skip with acquisition guidance
when a required variable is absent. CI runs credentialed cases only through
the protected `protected-integration` environment; configure required secrets
and reviewers there. Recorded fixtures, if later added, belong only in unit
tests and must state their exact public URL and UTC retrieval date; they must
never be described as live integration coverage.

## Production container, deployment, and rollback

The container uses a digest-pinned Python base, runs as UID/GID 10001, contains
no credentials, and exposes a process health check. Build and deploy by immutable
image digest:

```bash
docker build --pull -t connector-hub:1.1.0 .
docker run --rm --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --env-file /run/secrets/connector-hub.env connector-hub:1.1.0 list
```

The read-only filesystem is a runtime control and must remain enabled in the
orchestrator. Permit outbound HTTPS only to configured providers. Deploy to a
canary, verify `connector-hub health` and a read-only provider call, then roll
out gradually. To roll back, redeploy the last known-good image digest and its
matching secret/config version; do not rebuild an old tag. Revoke credentials
if the rollback follows a suspected exposure.

## Data Sources

Live integration coverage uses these documented public/provider endpoints:

```text
https://api.github.com/meta
https://docs.github.com/en/rest/meta/meta
https://api.hetzner.cloud/v1/locations
https://docs.hetzner.cloud/reference/cloud#locations
```

## Gmail OAuth (multiple accounts)

```bash
python3 scripts/setup_oauth.py    # per account: opens consent URL, mints refresh token into .env
python3 -m hub.gateway call gmail send '{"label":"main","to":"x@y.com","subject":"hi","body":"test"}'
```

## Use as MCP server (Claude Desktop / Kimi Code / any MCP client)

`mcp/mcp.json` contains `omni-hub` plus the official github/filesystem/fetch/puppeteer/memory servers. Merge its `mcpServers` block into your client's config. The hub exposes three stable tools — `hub_channels`, `hub_status`, `hub_call` — so every future connector appears automatically.

## Security model

- Secrets live only in `.env` (git-ignored). Logs redact anything matching KEY/TOKEN/SECRET/PASS.
- `ops_ssh` and system-level `ops_network` commands do **nothing real** until `HUB_ALLOW_LOCAL_EXEC=1`.
- OAuth refresh tokens are minted only by the script you run yourself.

## Layout

```
hub/            base contract, registry, gateway CLI, stdio MCP server
connectors/     one module per service, grouped by domain
mcp/mcp.json    drop-in MCP client config
scripts/        OAuth setup wizard
verifier/       acceptance checks + run log
```
