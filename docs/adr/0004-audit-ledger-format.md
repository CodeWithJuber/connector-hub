# ADR 0004: Hash-chained JSONL audit ledger

- Status: Accepted
- Date: 2026-08-11
- Decision owners: Connector Hub maintainers

## Context

connector-hub is the only one of the three sibling repositories that causes
irreversible side effects in the real world (deleting servers, terminating
accounts, sending mail). Every permission decision — granted or refused — needs
a tamper-evident record.

## Decision

Every policy decision is appended to a hash-chained JSONL audit ledger at
`audit.jsonl`. Each entry contains:

```json
{
  "timestamp": "2026-08-11T12:00:00Z",
  "provider": "hetzner",
  "operation": "hetzner.servers.delete",
  "account": "production",
  "mutation_class": "destructive",
  "decision": "granted",
  "prev_hash": "<BLAKE3 hash of the previous entry>",
  "hash": "<BLAKE3 hash of this entry>"
}
```

The hash chain uses BLAKE3 for speed and resistance to length-extension attacks.
The first entry's `prev_hash` is the string `"genesis"`. Verification walks the
file and confirms each entry's `prev_hash` matches the preceding entry's `hash`,
and each `hash` is the correct BLAKE3 digest of the entry's content (with the
`hash` field itself zeroed during computation).

## Format compatibility

The format is intentionally compatible with hikmah-stack's TraceWeave ledger
(`runtime/hikmah-kernel/src/ledger.rs`), which also uses BLAKE3 hash-chained
JSONL. `hikmah verify-ledger` can validate a connector-hub audit file, and vice
versa. The implementation is self-contained in the `hub-policy` crate (~150
lines); there is no code dependency on hikmah-stack.

## Verification

`connector-hub audit-verify [path]` walks the ledger and reports the entry count
and chain integrity. It exits non-zero on any chain break, missing entry, or
hash mismatch.

## Consequences

- Every dispatched operation is recorded, whether it succeeded or was refused.
- The ledger is append-only by convention; the file format does not enforce this,
  but any tampering (insertion, deletion, reordering) is detectable by
  verification.
- The ledger file grows without bound. Rotation is the operator's responsibility;
  `connector-hub audit-verify` works on any contiguous segment.
