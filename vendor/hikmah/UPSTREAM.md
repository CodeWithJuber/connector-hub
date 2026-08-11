# Vendored upstream record

- Upstream: https://github.com/CodeWithJuber/hikmah-stack
- Description: Rust cognitive kernel — TraceWeave hash-chained memory, decision
  scoring, deliberation lanes, Truth Gate completion hook. Sibling project.
- License: MIT

Connector Hub references hikmah-stack conventions (hash-chained audit ledger,
self-validation binary, plugin manifest version parity) but does not vendor or
execute its code at runtime. The `vendor/hikmah/` directory previously pointed
at a different upstream (`hikmahlabs/plugins`); this record corrects the
provenance.

Note: the hikmahlabs/plugins content previously stored here was a Claude Code
plugin marketplace by a different author. It has been removed.
