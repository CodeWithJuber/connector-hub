Run the pre-PR quality gate locally and report blockers before opening a PR.

## Config

Read `.github/dev-workflow.yml` → `review.command` (the local review command to run, default
`review`).

## Process

Run these in order and collect results (do not auto-fix — report):

1. **Typecheck** — `bunx tsc --noEmit`
2. **Lint** — `bun run lint`
3. **Tests** — `bun run test`
4. **Local code review** — run the `review.command` (default `/review`) over the branch diff
   (`git diff main...HEAD`). This is the codebase-tailored P0–P4 pass. Reviews are local-only.

Never run `bun run build` here (it publishes translations and can OOM the dev server) — `tsc`,
`lint`, and `test` are the local gate, exactly as CI runs them.

## Output

A short verdict:

- **✅ Ready for `/open-pr`** — all four clean.
- **⚠️ Blockers** — list each failing check with the file:line and the one-line fix. Then ask the
  user whether to fix them now or open the PR anyway (they decide — don't proceed on your own).

## Rules

- Mirror CI exactly (lint + typecheck + test) so a green preflight means green CI.
- If the diff touches any `sensitivePaths` glob, say so now — `/open-pr` will flag it
  `needs-human-review`, so the user shouldn't be surprised.
