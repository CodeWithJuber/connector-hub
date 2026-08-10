# Omni Connector Hub Plugin

One channel for AI providers, email, hosting panels, VPS clouds, chat, GitHub,
and server operations. The repository now includes a local Codex plugin that
combines this MCP gateway with source-synchronized ForgeKit delivery and
Hikmah problem-solving workflows.

## Plan

1. Install the local plugin and keep destructive capabilities disabled.
2. Synchronize ForgeKit and Hikmah Stack from their authoritative Git sources.
3. Record the exact resolved commits for reproducibility and review upstream instructions.
4. Configure only the connector credentials required for your use case.
5. Validate the plugin and run unit tests before enabling real integrations.

## Assumptions

- Python remains the smallest reliable choice for this I/O-bound connector library.
- ForgeKit and Hikmah Stack are trusted only after their fetched revisions are reviewed.
- Missing credentials select the existing dry-run/mock behavior; they never prove an external action succeeded.

## Data Sources

https://github.com/CodeWithJuber/forgekit

https://github.com/CodeWithJuber/hikmah-stack

Provider endpoints used by individual connectors are documented in their source modules.

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
cp .env.example .env           # fill in only what you use; .env.template is exhaustive
python3 .agents/plugins/plugins/connector-hub/scripts/sync_upstreams.py
python3 -m hub.gateway list    # see every channel, MOCK vs LIVE
python3 -m hub.gateway status gmail
python3 -m hub.gateway call hetzner list_servers
```

Anything without credentials answers in **mock mode** (dry-run echo) — the hub is fully usable for testing workflows before secrets exist.

## Codex plugin setup

The repository-local marketplace is `.agents/plugins/marketplace.json`; the
plugin is `.agents/plugins/plugins/connector-hub`. Add the marketplace root to Codex:

```bash
codex plugin marketplace add .agents/plugins
codex plugin install connector-hub@personal
```

The plugin launches the local hub with `HUB_ALLOW_LOCAL_EXEC=0`. Restart Codex
after installation. Upstream source is stored in the ignored `.vendor/`
directory, while `vendor-manifest.json` records the exact commits. Review both
trees before running any upstream-provided script.

To request a specific audited revision:

```bash
python3 .agents/plugins/plugins/connector-hub/scripts/sync_upstreams.py \
  --forgekit-ref <commit-or-tag> --hikmah-ref <commit-or-tag>
```

The synchronizer accepts only the two declared HTTPS GitHub repositories, uses
non-interactive Git, retries transient clone failures with exponential backoff
and jitter, applies timeouts, validates resolved commit IDs, and atomically
replaces prior checkouts.

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
- Source synchronization rejects alternate hosts, embedded credentials, custom
  ports, and unapproved repository URLs.
- Upstream source is not executed automatically. Review its license and code at
  the commit recorded in `vendor-manifest.json`.

## UX flow summary

This is a CLI and MCP plugin rather than a web UI. In Codex, install the plugin,
ask it to list channels, inspect a channel's status, then invoke a validated
action. Calls expose explicit loading, tool-result, and error states through the
Codex host. Terminal flows print structured JSON and actionable stderr errors.

## Component inventory

- **Codex manifest** — discovery metadata and safe starter prompts.
- **Connector Hub skill** — operational and security workflow.
- **MCP launcher** — working-directory-independent server startup.
- **Upstream synchronizer** — allowlisted, retrying source acquisition.
- **Gateway and registry** — connector discovery and routing.
- **Provider connectors** — service-specific actions and authentication.

## Responsive and accessibility strategy

The plugin has no custom visual surface. It uses Codex's native responsive and
accessible tool UI. CLI output is plain text/JSON, contains no color-only
meaning or animation, and remains usable with keyboard and screen readers.

## File structure

```text
.agents/plugins/marketplace.json
.agents/plugins/plugins/connector-hub/
├── .codex-plugin/plugin.json
├── .mcp.json
├── scripts/run_mcp.py
├── scripts/sync_upstreams.py
└── skills/connector-hub/SKILL.md
connectors/                 provider implementations
hub/                        registry, gateway, and MCP server
tests/                      unit and opt-in integration tests
```

## Testing

Unit tests require no network:

```bash
python3 -m unittest discover -s tests -v
```

The integration test fetches real source and is intentionally opt-in:

```bash
RUN_INTEGRATION=1 python3 -m unittest tests/test_sync_upstreams_integration.py -v
```

Validate the Codex plugin with the bundled Codex plugin validator:

```bash
python3 /opt/codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  .agents/plugins/plugins/connector-hub
```

## Key design decisions

- **Keep Python:** connector work is network-bound, and retaining the existing
  implementation avoids an unnecessary Rust rewrite.
- **Fetch, do not silently execute:** upstream source is installed locally and
  pinned by resolved commit metadata, but remains inert pending review.
- **Safe defaults:** local execution is off, secrets stay in environment files,
  and source URLs are strict allowlist entries.

## Layout

```
hub/            base contract, registry, gateway CLI, stdio MCP server
connectors/     one module per service, grouped by domain
mcp/mcp.json    drop-in MCP client config
scripts/        OAuth setup wizard
verifier/       acceptance checks + run log
```
