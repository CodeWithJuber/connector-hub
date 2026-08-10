# Contributing — the Dev Lifecycle

The single, repeatable way work flows through this project, idea → production. It's **AI-automated
with human gates**: agents do the heavy lifting, a human approves where it matters (merging, anything
sensitive). The same lifecycle runs on every project — only `.github/dev-workflow.yml` changes.

> **Who this is for:** anyone — human or agent — working on the codebase. Follow it as written.

## The lifecycle

```
 Intake → Triage → Start → Develop → PR → Merge (auto-deploys) → Cleanup
```

| Stage          | You run                                         | What it does                                                                                                                       |
| -------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **1. Intake**  | `/intake <idea>`                                | Idea/bug/chore → a classified GitHub issue on the board. _(Skip if the issue exists, or for tiny fixes.)_                          |
| **2. Triage**  | `/triage`                                       | Confirms classification on untriaged issues, marks them `ready`.                                                                   |
| **3. Start**   | new worktree/branch, then `/start <issue#>`     | Each feature gets its own worktree. `/start` loads the issue, assigns you, moves it to **In Progress**.                            |
| **4. Develop** | interactive agent                               | Build it under the `CLAUDE.md` guardrails. `/preflight` _(optional)_ runs a quick local gate.                                      |
| **5. PR**      | `/open-pr`                                       | One command: preflight (incl. local `/review`) → commit → push → opens a PR from the template, `Closes #<issue>`, copies labels, **auto-flags sensitive diffs**. |
| **6. Merge**   | review the PR, then merge (squash)              | Merging is the human gate. It **auto-deploys** and auto-closes the issue. Say "merge it" and the agent runs `gh pr merge --squash --delete-branch`. |
| **7. Cleanup** | —                                               | Archive the workspace.                                                                                                             |

**~3 commands per feature** (`/start` → `/open-pr` → "merge it"), plus `/intake` to file work. Say it
in plain English — the right step runs. Reviews are **local only** (`/review`).

## Conventions

- **Branches / worktrees** — one workspace per feature; name its branch `<user>/<type>-<issue>-<slug>`.
- **Commits & PR titles** — [Conventional Commits](https://www.conventionalcommits.org)
  (`feat:`/`fix:`/`chore:`/`refactor:`/`docs:`). The PR title becomes the squash subject.
- **Merge** — squash only, branch auto-deleted. `main` is protected by a branch ruleset where the plan
  supports it; otherwise it's **soft-enforced** (process + CI-on-PRs + CODEOWNERS). Always go through a PR.
- **No AI attribution** — commits, PR titles/bodies, and issue text never include "Generated with
  Claude", "Co-Authored-By: Claude", 🤖, or similar. Write as a human would.
- **Classification** — every issue carries `type:*`, `priority:p0..p3`, `area:*`; the board mirrors them.

## Needs human review

A PR is auto-flagged `needs-human-review` when (1) its diff touches a **sensitive path**
(`sensitivePaths` in `.github/dev-workflow.yml`), (2) the agent **self-reports** low confidence, or
(3) the local `/review` surfaces a **P0/P1**. Flagged PRs get a close human look before merge.

## Deploy

Merging to `main` (squash) triggers your deploy pipeline. Keep backend/schema changes
backward-compatible (widen → migrate → narrow) so the frontend never races an un-migrated backend.
Any one-off data migration goes in the PR's "Post-merge steps" block.

## Setting this up (already done if you started from the template)

1. Edit `.github/dev-workflow.yml` (owner, name, areas, sensitive paths) + `CODEOWNERS`.
2. `gh auth refresh -s project -s read:project` (one-time, board scope).
3. `scripts/bootstrap-project.sh` — labels, squash-only merge, branch ruleset (if the plan allows),
   Projects v2 board + fields; writes the board number back into the config.
4. Install the command layer: `/plugin marketplace add hikmahlabs/plugins` then
   `/plugin install dev-lifecycle`.

## Optional automation (off by default)

Toggle in `.github/dev-workflow.yml`: `releaseAutomation`, `notifications: telegram`, `nightlyTriage`.
