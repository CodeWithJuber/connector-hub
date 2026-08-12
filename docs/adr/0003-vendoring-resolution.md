# ADR 0003: Resolve the vendoring conflict — reference, don't vendor

- Status: Accepted
- Date: 2026-08-11
- Supersedes: ADR 0001 (partially)
- Decision owners: Connector Hub maintainers

## Context

Two incompatible vendoring systems shipped simultaneously:

1. `docs/adr/0001-static-third-party-plugin-sources.md` governed `vendor/` with
   pinned SHA, licence checks, and a Forgkit quarantine.
2. `.agents/plugins/plugins/connector-hub/scripts/sync_upstreams.py` hardcoded
   `CodeWithJuber/forgekit` and `CodeWithJuber/hikmah-stack`, cloned them into a
   different gitignored `.vendor/` directory with none of the ADR's diligence.

The `vendor/hikmah/UPSTREAM.md` recorded upstream as `hikmahlabs/plugins` — a
different project. The `vendor/forgkit/NOT_VENDORED.md` stated that no project
named Forgkit exists, while `CodeWithJuber/forgekit` is a public repo published
to npm. The README simultaneously listed forgekit as a data source and told
users to run `sync_upstreams.py`.

## Decision

Neither sibling repository is vendored. Both are **referenced** as related
projects in the README and this ADR. The `vendor/` directory, the
`sync_upstreams.py` script, and the `.agents/` plugin scaffold are deleted.

The three repositories form one system:

| Repo | Role |
|---|---|
| `CodeWithJuber/forgekit` | Delivery + substrate (memory, foresight, guardrail hooks) |
| `CodeWithJuber/hikmah-stack` | Judgment (deterministic cognitive kernel, audit ledger) |
| `CodeWithJuber/connector-hub` | Actuation (the hands — reaches external services) |

Each stands alone. connector-hub's audit ledger uses the same hash-chained JSONL
format as hikmah-stack's TraceWeave for format compatibility, but there is no
code dependency. The ~150-line implementation is self-contained in `hub-policy`.

## Consequences

- ADR 0001 remains as historical record. Its trust-boundary analysis and update
  policy are sound principles; the vendoring it governed is no longer present.
- No vendored code ships. No `sync_upstreams.py` or equivalent auto-fetcher.
- Future integration with forgekit or hikmah-stack (if desired) would be through
  explicit, versioned dependencies or well-defined IPC, not by copying source
  trees.
