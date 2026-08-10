# ADR 0001: Static, pinned third-party plugin sources

- Status: Accepted
- Date: 2026-08-10
- Decision owners: Connector Hub maintainers

## Context and verified sources

The requested names were researched against public upstream registries rather
than inferred from similar names.

**Hikmah** is the Hikmah Labs Claude Code plugin marketplace at
https://github.com/hikmahlabs/plugins. We pin immutable Git commit
`f028fb87ecb64de0e284b3b233150da41d938ebf`. The repository's `LICENSE` grants
the MIT license. Its upstream README and tree support these native plugin APIs:
Claude Code marketplace metadata (`.claude-plugin/marketplace.json` and each
plugin's `.claude-plugin/plugin.json`), skills (`SKILL.md` and reference
Markdown), and slash commands (`commands/*.md`). The upstream also describes
Markdown skills as usable as copied custom rules in other agents. It does not
implement Connector Hub's Python connector API or the manifest API introduced
by this decision.

**Forgkit**, with that exact spelling, has no identifiable authoritative public
upstream as of the decision date. GitHub public repository and user searches,
npm registry search, and PyPI returned no exact project/package. Consequently
there is no truthful URL, commit SHA, license, or supported plugin API to record.
A similarly named project is not evidence of identity. Forgkit remains
quarantined and unavailable rather than silently substituting untrusted code.

## Decision and rationale

Hikmah is retained as reviewed, local reference material because its skills and
workflow commands can inform future, explicit adapters for translation,
Stripe/Convex webhooks, plugin drafting, and development lifecycle work. Its
source snapshot is in `vendor/hikmah/`; it is never imported or executed.
Forgkit is not currently a dependency. `vendor/forgkit/NOT_VENDORED.md` records
the negative provenance result so future maintainers cannot accidentally treat
a name match as authorization.

Connector Hub defines its own closed `connector-hub.plugin/v1` manifest. It
captures identity/version, requested capabilities and secrets, host allowlists,
and destructive behavior. Registration validates local manifests before making
metadata visible. The loader does not import a module, invoke a command, fetch a
URL, or translate a native third-party manifest.

## Trust boundaries

All vendored content and every plugin manifest is untrusted input. Markdown can
contain adversarial agent instructions; templates and shell scripts can modify
projects or invoke external tools. Vendoring confers availability, not trust.
The trusted computing base is limited to the reviewed loader, schema, policy,
and separately authored Connector Hub adapters. Secrets are named in manifests
but never stored in them. A host declaration is audit metadata and must also be
enforced by any future network adapter; it is not, by itself, an SSRF sandbox.
Destructive behavior requires both the manifest flag and the
`actions.destructive` capability enabled by operator policy.

## Update policy

Updates are manual only: inspect the upstream diff from the previously pinned
SHA, verify the Git remote and full 40-character commit, review license changes,
audit instructions/scripts/manifests, run unit and flagged integration tests,
then replace the snapshot and update this ADR, `vendor/hikmah/UPSTREAM.md`, and
README in one pull request. Floating branches, tags alone, runtime downloads,
auto-update jobs, and dependency code execution during discovery are forbidden.
Forgkit can enter only through the same review after its owner and authoritative
source are established.

## License compatibility

Hikmah's MIT license permits use, copying, modification, and distribution and is
compatible with this repository provided its copyright and permission notice
remain with the vendored source; the unmodified upstream `LICENSE` is retained.
No license conclusion is possible for Forgkit, so distributing or using its code
would be unsafe and is prohibited until verified. This is an engineering policy,
not legal advice.

## Consequences

Registration fails closed for duplicate IDs, unknown fields, unsupported API
versions, traversal/symlink escapes, malformed values, and capabilities outside
policy. Native Hikmah plugins cannot register directly. Adding an adapter takes
review work, but runtime behavior remains reproducible and no third-party source
crosses into execution merely because it was discovered.
