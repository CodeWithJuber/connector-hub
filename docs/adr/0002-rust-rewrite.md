# ADR 0002: Rewrite in Rust with spec-driven connectors

- Status: Accepted
- Date: 2026-08-11
- Decision owners: Connector Hub maintainers

## Context

The Python implementation shipped 21 connectors with 142 hand-written actions
against provider surfaces totalling thousands of endpoints. Coverage was
structurally incomplete: adding a provider endpoint meant writing a new Python
method, registering it, and keeping docs in sync. Three declared runtime
dependencies (httpx, pydantic, structlog) were exercised only by the test suite.
The safety contract (dry-run, confirmation tokens, mutation classification) was
built, then silently reverted while the documentation continued to advertise it.
CI was red on main due to a Python 3.14 incompatibility in a pinned dependency.

## Decision

Replace the Python implementation with a Rust workspace using the official MCP
SDK (`rmcp`). Connectors are expressed as declarative JSON spec files (OpenAPI
3.x or Google Discovery format) compiled into an operation catalogue at startup.
The MCP tool surface is small and fixed (search, describe, call, list, validate)
while the reachable surface is complete — determined by the spec, not by
hand-written code.

## Rationale

- **Completeness by construction**: a spec-derived catalogue includes every
  endpoint the provider publishes. Adding coverage means updating a JSON file,
  not writing Rust.
- **Single execution path**: one `NetClient` through one SSRF-validated HTTP
  stack. The Python tree had two HTTP stacks (urllib in base.py, httpx in
  http_client.py) with 17 of 21 connectors bypassing the policy layer.
- **Type-safe safety contract**: the execution result is an enum
  (`Succeeded | DryRun | ConfirmationRequired | ...`). Non-execution states
  cannot carry `executed: true` because there is no code path that constructs it.
- **Single static binary**: no version matrix, no virtualenv, no runtime
  dependency conflicts. The class of CI failure that broke main (Pydantic under
  Python 3.14) becomes impossible.
- **Toolchain**: `rmcp` 3.1.2 (Apache-2.0, MSRV 1.88, actively maintained).
  The environment has rustc 1.94.1.

## Crate layout

| Crate | Responsibility |
|---|---|
| `connector-hub` (bin) | CLI + rmcp stdio server |
| `hub-core` | Operation catalogue, dispatch, execution-state envelope |
| `hub-spec` | Spec ingestion: OpenAPI 3.x + Google Discovery → operations |
| `hub-auth` | Credential store, OAuth, token refresh |
| `hub-policy` | Permission model, capability grants, hash-chained audit ledger |
| `hub-net` | HTTP execution: SSRF validation, IP pinning, retries, redaction |

## Consequences

- Python tree is removed. Migration is parity-verified: a test asserts every one
  of the 142 original actions has a corresponding operation in the catalogue.
- Provider endpoint knowledge (auth schemes, URL patterns, header formats) is
  preserved in spec files, not discarded.
- Hand-written specs (WHMCS, cPanel, WHM, OVH, tawk.to, OneProvider) are
  complete by inspection, not by construction. Per-provider coverage is stated
  explicitly.
- The `hub/security/policy.py` SSRF defense and its adversarial tests are ported
  to `hub-net`.
