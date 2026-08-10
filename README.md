# Omni Connector Hub

One channel for everything: AI providers, email (multi-Gmail OAuth), hosting panels, VPS clouds, chat, GitHub, and server ops — behind one interface with explicit execution states and fail-closed safety policies.

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
- OAuth refresh tokens are minted only by the script you run yourself.

## Layout

```
hub/            base contract, registry, gateway CLI, stdio MCP server
connectors/     one module per service, grouped by domain
mcp/mcp.json    drop-in MCP client config
scripts/        OAuth setup wizard
verifier/       acceptance checks + run log
```
