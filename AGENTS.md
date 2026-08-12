# AGENTS.md — Connector Hub

## Pre-completion verification

Before reporting any task as complete, run:

```bash
cd crates && cargo fmt --check
cd crates && cargo clippy --all-targets -- -D warnings
cd crates && cargo test --workspace
cd crates && cargo run -- validate
```

All four must pass.

## Commit conventions

Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.

## Repository layout

```
crates/                 Rust workspace (the runtime)
  connector-hub/        CLI binary + MCP stdio server
  hub-core/             Operation catalogue, dispatch, execution contract
  hub-spec/             Spec ingestion (OpenAPI 3.x + Google Discovery)
  hub-auth/             Credential store, OAuth, token refresh
  hub-policy/           Permission model, audit ledger
  hub-net/              HTTP execution, SSRF defense
specs/                  Provider spec files (JSON)
docs/adr/               Architecture Decision Records
.claude-plugin/         Claude Code plugin manifest
.codex-plugin/          Codex plugin manifest
kimi.plugin.json        Kimi plugin manifest
```

## Adding a provider

1. Create `specs/<provider>.json` in OpenAPI 3.0.3 or Google Discovery format.
2. Add auth entry in `crates/hub-auth/src/store.rs` `from_env()`.
3. Run `cargo run -- list` to verify operations load.
4. Run `cargo run -- validate` to confirm no duplicate IDs.

## Plugin manifests

Four manifests must stay version-synchronized:
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.codex-plugin/plugin.json`
- `kimi.plugin.json`

`connector-hub validate` checks this.
