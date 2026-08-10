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
python3 -m pip install -e .     # installs the pinned Python MCP SDK
cp .env.example .env           # fill in only what you use; .env.template is exhaustive
python3 .agents/plugins/plugins/connector-hub/scripts/sync_upstreams.py
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

`mcp/mcp.json` contains `omni-hub` plus the official github/filesystem/fetch/puppeteer/memory servers. Merge its `mcpServers` block into your client's config. Each validated action is discovered as a generated tool named `hub__<connector>__<action>`. Tool annotations identify read-only and destructive operations.

The SDK server bounds concurrent work and applies a deadline to every connector call. Configure these production safeguards with `HUB_MCP_MAX_CONCURRENCY` (default `8`) and `HUB_MCP_CALL_TIMEOUT` in seconds (default `30`). Diagnostic logs include an internal request ID; client errors are categorized and sanitized.

## Security model

- Secrets live only in `.env` (git-ignored). The base response contract never
  echoes parameters because message bodies and customer data can be sensitive
  even when their field names do not look like secrets.
- `ops_ssh` and system-level `ops_network` commands do **nothing real** until `HUB_ALLOW_LOCAL_EXEC=1`.
- Secrets live only in `.env` (git-ignored). Logs redact anything matching KEY/TOKEN/SECRET/PASS.
- Ops commands require deployment capabilities, allowlisted actions, destructive-action enablement, and an auditable approval identifier.
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

## Plugin manifests and static loading

Connector Hub accepts only reviewed local plugins described by the closed
[`connector-hub.plugin/v1` schema](schemas/plugin-manifest.schema.json). A
manifest declares its ID, semantic version, capabilities, required secret names,
allowed network hosts, and destructive-action support. `hub.plugins.PluginLoader`
validates these values and operator-enabled capabilities before registration.
It rejects unknown fields, duplicate IDs, unsupported API versions, absolute or
traversing paths, symlink escapes, and capabilities disabled by policy. Discovery
registers metadata only: it never imports plugin files or downloads source.
See [ADR 0001](docs/adr/0001-static-third-party-plugin-sources.md) for the trust
boundary, auditing, updates, and license decision.

## Data Sources and Third-Party Source Code

- **Hikmah Labs plugins** — authoritative upstream source:
  https://github.com/hikmahlabs/plugins ; pinned Git commit:
  `f028fb87ecb64de0e284b3b233150da41d938ebf`; MIT license. The audited source
  snapshot is in `vendor/hikmah/` with its upstream license and provenance.
  Supported upstream formats are Claude Code marketplace manifests, plugin
  manifests, Markdown skills/references, and Markdown slash commands. They are
  reference/instruction content and are not loaded or executed by Connector Hub.
- **Hikmah pinned commit API record** —
  https://api.github.com/repos/hikmahlabs/plugins/commits/f028fb87ecb64de0e284b3b233150da41d938ebf
  (used only by the opt-in provenance integration test; never at runtime).
- **Forgkit** — no authoritative public source URL, immutable revision, license,
  or plugin API could be verified for that exact name as of 2026-08-10. Public
  discovery endpoints checked were https://api.github.com/search/repositories,
  https://api.github.com/search/users, https://registry.npmjs.org/-/v1/search,
  and https://pypi.org/pypi/forgkit/json. It is not a dependency, is not
  executable, and is denied pending owner-confirmed provenance. The quarantine
  record is `vendor/forgkit/NOT_VENDORED.md`.
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

## Pull-request quality gates

Every pull request runs locked dependency installation, formatting, linting,
strict type checking, unit tests on the oldest and newest supported Python
versions, package builds, runtime dependency auditing, secret scanning, and
CodeQL analysis. Real-provider tests remain opt-in behind the protected
`protected-integration` environment so untrusted pull requests never receive
credentials. Dependency updates are proposed weekly for both Python packages
and GitHub Actions.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the local check sequence and
[SECURITY.md](SECURITY.md) for private vulnerability reporting. Repository
administrators should protect `main`, require the `Quality / Python 3.11`,
`Quality / Python 3.14`, `Security`, and `Analyze Python` checks, require one
review, dismiss stale approvals, require conversation resolution, and disallow
force pushes and branch deletion.
