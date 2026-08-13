---
name: connector-hub
description: Call external services (AI providers, Gmail, GitHub, Hetzner/Linode/Contabo/OVH VPS, cPanel/WHM/WHMCS panels, Cloudflare, tawk.to, SSH and network ops) through the Connector Hub MCP server. Use whenever a task needs a real API call to one of these providers, when you need to discover which operation exists for a provider, or when a destructive operation needs confirmation. Triggers include "list my servers", "send this email", "create a DNS record", "suspend that hosting account", "reboot the VPS", "what can I do with <provider>".
---

# Connector Hub

One MCP surface over 24 providers and 301 operations. The tool surface is fixed
and small; the reachable API surface is complete. Never guess an operation ID —
discover it.

## The four tools

| Tool | Use it for |
|---|---|
| `list_providers` | What providers exist and how many operations each has |
| `search_operations` | Find the operation ID for an intent — free text, optional `provider` filter |
| `describe_operation` | Exact JSON Schema for one operation before calling it |
| `call_operation` | Execute — `id`, `args`, optional `account`, `dry_run`, confirmation token |

## Workflow

Always in this order:

1. **Search** — `search_operations({query: "delete server", provider: "hetzner"})`.
   Search by what you want to do, not by the endpoint name you imagine.
2. **Describe** — `describe_operation({id: "hetzner.servers.delete"})`. Read the
   schema. Do not construct `args` from memory of the provider's REST API.
3. **Dry run** — for anything mutating, call with `dry_run: true` first and show
   the user the `would_execute` payload and `mutation_class`.
4. **Call** — only after the user has seen what will happen.

## Reading the result

Every result is one of five states. Only one of them means something happened:

- `Succeeded { executed: true, data }` — real output, the only executed state.
- `DryRun { would_execute, mutation_class }` — nothing ran.
- `ConfirmationRequired { provider, operation, token_format }` — destructive op.
  Relay the request to the user; pass the token they give back on the retry.
  Never mint or guess a confirmation token.
- `ConfigurationRequired { provider, missing }` — credentials absent. Tell the
  user exactly which env vars are missing; do not retry, and do not attempt the
  same call through curl, a raw HTTP client, or a different tool.
- `PermissionDenied` — policy refused. Report it and stop.

A non-`Succeeded` state never means "probably worked". Do not report success
unless you saw `executed: true`.

## Safety rules

- 32 of the 301 operations are destructive (server deletes, account suspends,
  Gmail deletes, SSH commands). Confirm with the user in plain language — name
  the resource and the provider — before requesting a confirmation token.
- Credentials live in environment variables or the encrypted store. Never put a
  key in `args`, never echo one back to the user, never write one into a file
  the user did not ask for.
- `ops_ssh`, `ops_network`, and `ops_security` need a `HUB_SECURITY_POLICY`
  capability grant. If they are denied, that is the policy working — surface it
  rather than routing around it.
- Every policy decision is appended to a BLAKE3 hash-chained audit ledger.
  Verify with `connector-hub audit-verify audit.jsonl`.

## Provider map

- **AI** — `claude`, `openai`, `kimi`
- **Mail** — `gmail` (79 ops), `email` (IMAP/SMTP)
- **Code** — `github` (25 ops)
- **Cloud / VPS** — `hetzner` (72 ops), `linode`, `contabo`, `ovh`,
  `oneprovider`, `cloudflare`
- **Hosting panels** — `cpanel`, `whm`, `whmcs`, `ultrahost`
- **Chat** — `tawk`
- **Affiliate** — `iherb_apify`, `iherb_impact`, `iherb_partnerize`
- **Local ops** — `ops_ssh`, `ops_network`, `ops_security`, `ops_browser`

## Troubleshooting

- **Zero providers listed** — the specs directory was not found. Set
  `CONNECTOR_HUB_SPECS_DIR` to the repo's `specs/` folder, or launch with the
  repo root as the working directory.
- **Provider missing from `list_providers`** — its spec file failed to parse;
  run `connector-hub validate`.
