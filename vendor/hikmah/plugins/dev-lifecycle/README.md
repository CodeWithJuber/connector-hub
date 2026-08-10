# dev-lifecycle

A flexible, project-adjustable **development lifecycle** for any repo — idea → classified GitHub
issue → worktree → PR → squash-merge, with AI doing the heavy lifting and a human at the gates
(merging, anything sensitive). Self-contained: it ships both the per-feature commands **and** the
repo-side scaffolding they operate on.

## Install

```
/plugin marketplace add hikmahlabs/plugins
/plugin install dev-lifecycle
```

## Set up a repo (once)

Run **`/adopt`** in the repo (new or existing). It lays down the GitHub + config scaffolding
(non-destructively — never overwrites existing files), helps you fill in
`.github/dev-workflow.yml`, and runs the bootstrap that creates your labels, merge settings, branch
ruleset, and Projects v2 board.

```
/adopt
```

## The flow

```
/intake "<idea>"  →  /start <#>  →  build  →  /open-pr  →  "merge it"
   (file issue)      (begin work)           (preflight+review+commit+PR)   (auto-deploys)
```

~3 commands per feature, or just say it in plain English.

## Commands

| Command      | What it does                                                                                                  |
| ------------ | ------------------------------------------------------------------------------------------------------------ |
| `/adopt`     | One-time: lays the GitHub scaffolding into the current repo and runs the bootstrap. New or existing repos.    |
| `/intake`    | Turns an idea/bug/chore into a classified GitHub issue (type/priority/effort/area) on the board.             |
| `/triage`    | Reviews untriaged issues, confirms classification, marks them `ready`.                                        |
| `/start`     | `/start <issue#>` — loads the issue in the current worktree, assigns you, moves it to **In Progress**.        |
| `/preflight` | Quick local gate: typecheck + lint + tests + the local `/review`. _(Optional — `/open-pr` runs it.)_         |
| `/open-pr`   | One shot: preflight → commit → push → opens a PR from the template, `Closes #`, copies labels, **auto-flags sensitive diffs** `needs-human-review`. |

Merging the PR (squash) is the final human step — it auto-deploys and closes the issue. There's no
separate "ship" command.

## Configuration

Every command reads **`.github/dev-workflow.yml`** in the repo (created by `/adopt`): repo
coordinates, the Projects board number, the classification taxonomy, the `sensitivePaths` globs that
trigger `needs-human-review`, and the local review command. The same plugin behaves correctly on
every project because only that file changes. The bundled scaffolding lives under this plugin's
`template/`.

## Conventions enforced

- Conventional-Commit titles; squash merges.
- **No AI attribution** anywhere (commits, PR bodies, issues) — written as a human would.
- Reviews are **local only**; sensitive diffs (auth, payments, schema/migrations, destructive ops)
  always get a human before merge.

See the bundled `template/CONTRIBUTING.md` (copied into your repo by `/adopt`) for the full methodology.
