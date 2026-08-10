Review code changes for correctness, conventions, type safety, and performance. Read-only — reports, never edits.

This is a generic starter. Tailor the checklist to your codebase's real gotchas — that's where a
review command earns its keep (see your CLAUDE.md for project-specific rules to enforce here).

## Scope

$ARGUMENTS

If no paths are given, determine scope automatically:

1. `git diff --name-only main...HEAD` — changed files on this branch
2. If on main or no diff, `git diff --name-only HEAD~5`
3. Focus on source files (skip generated/vendored)

## Process

Read every in-scope file (parallel reads), check against the rules below, output a report grouped by
priority.

## What to check

### P0 — Bugs & correctness

- Missing/incorrect auth or authorization checks
- Logic that doesn't match the issue's acceptance criteria
- Off-by-one, null/undefined handling, race conditions
- Error paths that swallow failures or leak raw errors to users

### P1 — Conventions & design system

- Project conventions violated (see CLAUDE.md) — imports, component patterns, naming
- Hardcoded values that should be tokens/constants
- Inconsistency with how the rest of the codebase does the same thing

### P2 — Type safety

- `any` / unsafe casts that could be typed
- Duplicate or hand-rolled types where a generated/shared type exists
- Naming-convention drift

### P3 — Performance

- Unbounded reads/queries; N+1 patterns; missing indexes
- Work done per-row that could be batched or pushed into the query
- Re-renders / re-fetches that could be avoided

### P4 — Tech debt

- Duplicated logic that should be shared
- Dead code, unused imports, stale comments
- Inconsistent patterns across similar files

## Output

```
# Code Review: [branch / files]

## Summary
[issue count + severity breakdown]

## P0 — Bugs & Correctness
### [title]
**File:** `path:line`
**Problem:** …
**Fix:** …

## P1 … P4 …

## Files Reviewed
[list]
```

## Rules

- READ-ONLY. Do not modify files.
- Report every issue with a `file:line`. If a category is clean, say "No issues found."
- At the end, ask whether to fix any/all findings — never auto-fix.
