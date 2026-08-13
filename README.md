# Omni Connector Hub

One hub for AI providers, email, hosting panels, VPS clouds, chat, GitHub, and
server operations — 24 providers, 301 operations, behind one type-safe
interface with a hash-chained audit ledger.

## Providers

<!-- GENERATED — do not edit by hand. Regenerate with: connector-hub list -->

| Provider | Operations | Destructive | Auth | Spec source |
|---|---|---|---|---|
| `claude` | 2 | 0 | `ANTHROPIC_API_KEY` | hand-written |
| `cloudflare` | 2 | 0 | `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN` | hand-written |
| `contabo` | 8 | 0 | OAuth client + user creds | hand-written |
| `cpanel` | 11 | 0 | `CPANEL_HOST` + user:token | hand-written |
| `email` | 4 | 0 | `EMAIL_ACCOUNTS` (JSON) | built-in (IMAP/SMTP) |
| `github` | 25 | 2 | `GITHUB_TOKEN` | hand-written |
| `gmail` | 79 | 15 | `GOOGLE_CLIENT_ID/SECRET` + refresh tokens | Google Discovery |
| `hetzner` | 72 | 11 | `HETZNER_API_TOKEN` | OpenAPI 3.0.3 |
| `iherb_apify` | 7 | 0 | `IHERB_APIFY_TOKEN` | hand-written |
| `iherb_impact` | 8 | 0 | `IHERB_IMPACT_ACCOUNT_SID` + `IHERB_IMPACT_AUTH_TOKEN` | hand-written |
| `iherb_partnerize` | 8 | 0 | `IHERB_PARTNERIZE_APP_KEY` + `IHERB_PARTNERIZE_USER_KEY` | hand-written |
| `kimi` | 2 | 0 | `MOONSHOT_API_KEY` | hand-written |
| `linode` | 9 | 1 | `LINODE_API_TOKEN` | hand-written |
| `oneprovider` | 6 | 0 | `ONEPROVIDER_API_KEY` | hand-written |
| `openai` | 3 | 0 | `OPENAI_API_KEY` | hand-written |
| `ops_browser` | 3 | 0 | none | built-in (local) |
| `ops_network` | 5 | 0 | `HUB_SECURITY_POLICY` | built-in (local) |
| `ops_security` | 5 | 0 | `HUB_SECURITY_POLICY` | built-in (local) |
| `ops_ssh` | 3 | 2 | `HUB_SECURITY_POLICY` | built-in (local) |
| `ovh` | 7 | 0 | OVH app key/secret/consumer key | hand-written |
| `tawk` | 8 | 0 | `TAWK_API_KEY` + property ID | hand-written |
| `ultrahost` | 6 | 0 | `ULTRAHOST_*` | hand-written |
| `whm` | 9 | 1 | `WHM_HOST` + root token | hand-written |
| `whmcs` | 9 | 0 | `WHMCS_URL` + API identifier/secret | hand-written |

**Total: 301 operations (32 destructive)**

## Quick start

```bash
# Build from source
cd crates
cargo build --release

# List all providers
connector-hub list

# Search for operations
connector-hub search "delete server"

# Describe a specific operation
connector-hub describe hetzner.servers.delete

# Start the MCP stdio server
connector-hub mcp

# Validate the installation
connector-hub validate
```

### Specs resolution

Provider specs are located in this order:

1. `CONNECTOR_HUB_SPECS_DIR` — explicit override.
2. `./specs` relative to the working directory.
3. `specs/` found by walking up from the executable.

Rule 3 lets an installed binary find its specs without the caller setting a
working directory — MCP hosts launch servers with an arbitrary cwd, so a hub
installed globally would otherwise start with an empty catalogue.

## Architecture

Connectors are **data, not code**. Provider specs (OpenAPI 3.x or Google
Discovery JSON) are compiled into an operation catalogue at startup. The MCP
surface is small and fixed while the reachable surface is complete:

```
provider spec (OpenAPI / Google Discovery / hand-written JSON)
        │  loaded at startup
        ▼
operation catalogue  (every endpoint, typed, classified)
        │
        ├── search_operations(query, provider?)      → find any endpoint
        ├── describe_operation(id)                   → exact JSON Schema
        ├── call_operation(id, args, account, …)     → validated execution
        └── list_providers()                         → provider summary
```

### Crate layout

```
crates/
  connector-hub/   CLI binary + rmcp MCP stdio server
  hub-core/        Operation catalogue, dispatch, execution-state envelope
  hub-spec/        Spec ingestion: OpenAPI 3.x + Google Discovery → operations
  hub-auth/        Credential store, OAuth, token refresh
  hub-policy/      Permission model, capability grants, hash-chained audit ledger
  hub-net/         HTTP execution: SSRF validation, IP pinning, retries, redaction
specs/             Provider spec files (JSON)
```

### Execution contract

Every operation result is a typed enum — non-execution states cannot carry
`executed: true`:

- `Succeeded { executed: true, data }` — the only state with real output
- `DryRun { would_execute, mutation_class }` — what would happen
- `ConfirmationRequired { provider, operation, token_format }` — destructive ops need confirmation
- `ConfigurationRequired { provider, missing }` — credentials or runtime not available
- `PermissionDenied` — policy refused the operation

Destructive operations require an explicit confirmation token or a standing
policy grant. There is no env-var-presence shortcut to liveness.

### Audit ledger

Every policy decision (granted or refused) is appended to a BLAKE3 hash-chained
JSONL audit ledger. Verify integrity with:

```bash
connector-hub audit-verify audit.jsonl
```

See `docs/adr/0004-audit-ledger-format.md` for the format specification.

## Credentials

Connectors read credentials from the environment. MCP hosts launch stdio
servers with a bare environment, so `bin/connector-hub-mcp` sources
`~/.config/connector-hub/env` (override with `CONNECTOR_HUB_ENV`) before exec.
One file, shared by every agent on the machine:

```sh
mkdir -p ~/.config/connector-hub
cat > ~/.config/connector-hub/env <<'EOF'
GITHUB_TOKEN="ghp_..."
HETZNER_API_TOKEN="..."
EOF
chmod 600 ~/.config/connector-hub/env
```

Leave unused variables commented out rather than set to `""` — an empty string
reads as configured, which turns a clean `ConfigurationRequired` into a 401
from the provider.

## Security model

- Credentials live in environment variables or an encrypted store. Never in
  action parameters, never in tool output.
- All HTTP goes through one `NetClient` with SSRF validation, IP pinning,
  redirect control, and bounded retries.
- Ops connectors (`ops_ssh`, `ops_network`) require `HUB_SECURITY_POLICY`
  capability grants.
- OAuth refresh tokens are never serialised into MCP tool results.

## Adding a provider

1. Create `specs/<provider>.json` in OpenAPI 3.0.3 or Google Discovery format.
2. Add auth entry in `crates/hub-auth/src/store.rs` `from_env()`.
3. Run `connector-hub list` to verify operations load.
4. Run `connector-hub validate` to confirm no duplicate IDs.

## Tests

```bash
cd crates
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test --workspace
cargo run -- validate
```

## Related projects

- [CodeWithJuber/forgekit](https://github.com/CodeWithJuber/forgekit) — delivery
  and substrate (memory, foresight, guardrail hooks)
- [CodeWithJuber/hikmah-stack](https://github.com/CodeWithJuber/hikmah-stack) —
  judgment (deterministic cognitive kernel, decision scoring, audit ledger)

## CI

Every pull request runs: Rust formatting, clippy with deny warnings, workspace
tests, installation validation, and secret scanning. Real-provider integration
tests are opt-in behind the protected `protected-integration` environment.

## License

MIT
