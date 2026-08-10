# Verifier index (append-only)

## v1 — 2026-08-11
- **What it measures:** (1) all connector modules import & register (≥20, all 21 required channels present); (2) `status()` valid per channel; (3) no-arg `call()` on first action returns `ok:true`; (4) `mcp/mcp.json` valid JSON with `mcpServers`; (5) `.env.template` covers every `required_env`; (6) no hard-coded secret patterns in repo.
- **Run:** `python3 verifier/v1/verify.py` from repo root. Logged in `verifier/runs/`.

## v2 — 2026-08-11
- **Differs from v1:** smoke call now uses per-channel sample params (ops_browser.fetch https://example.com, ops_network.dns_lookup example.com, ops_security.generate_secret) and treats a clean param-requirement `ConnectorError` on a live-mode connector as PASS. v1 assumed no-arg calls must succeed for all connectors; that assumption was wrong for always-live ops connectors (`required_env=[]`), producing 3 false FAILs on correct code.
- **Run:** `python3 verifier/v2/verify.py` from repo root.

## v2 contract revision — execution safety
- **Current expectations:** credential absence must be `configuration_required`
  with `ok:false` and `executed:false`; action safety metadata must be complete;
  dry runs must be explicit non-execution and never echo input parameters.
  Real execution, upstream failure, and destructive confirmation are distinct
  states rather than variants of a successful mock response.
