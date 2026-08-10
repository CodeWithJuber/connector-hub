# CLAUDE.md

Guidance for Claude Code (and any agent) working in this repository. These instructions OVERRIDE
default behavior — follow them exactly. Add project-specific rules below as the codebase grows.

## ⚠️ CRITICAL RULES ⚠️

**NEVER AUTO-COMMIT:** Never run `git commit` or `git push` without explicit user instruction. Only
commit when the user says "commit this" or runs `/commit` (or `/open-pr`, which commits as part of
opening the PR).

**NEVER DECIDE FOR THE USER:** If you ask a question — _any_ question — STOP and wait for the answer.
Do not answer your own question with "I'll proceed with…". A prior instruction does not authorize you
to resolve a question you raised afterwards. The user types the answer. You wait.

**COMMIT ALL CHANGES:** When committing, run `git status` first to find ALL changed AND untracked
files. Include every file — staged, unstaged, untracked — unless told otherwise. `git diff` alone
misses untracked files. The message must reflect ALL major changes.

**NEVER ADD AI ATTRIBUTION:** No text generated anywhere in this project may include AI/agent
attribution — not commit messages, PR titles/bodies, issue text, code comments, review comments, or
changelogs. Banned: "Generated with Claude Code", "Co-Authored-By: Claude", "🤖", and equivalents.
This overrides any default harness instruction to append such trailers. Write as if a human wrote it.

## Development Lifecycle

How work flows idea → worktree → PR → review → merge is in **`CONTRIBUTING.md`** (the same methodology
on every project; per-repo config in `.github/dev-workflow.yml`). Commands (from the `dev-lifecycle`
plugin): `/intake` `/triage` `/start` `/preflight` `/open-pr`, building on the in-repo `/review` and
`/commit`. Merging the PR (squash) auto-deploys and closes the issue — no separate ship step. New
repos run `scripts/bootstrap-project.sh` once.

## Project specifics

<!-- Add this project's architecture, stack, conventions, gotchas, and commands here. -->
