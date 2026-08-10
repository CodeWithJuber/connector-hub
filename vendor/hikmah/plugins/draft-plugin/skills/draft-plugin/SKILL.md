---
name: draft-plugin
description: Scaffold a new plugin in ~/HikmahLabsProjects/plugins based on a pattern from the current session. Use when the user says "turn this into a plugin", "create a plugin from this", "draft this as a plugin", "package this as a hikmah-labs plugin", or any similar request to extract reusable knowledge into the local marketplace repo. Writes files only — never runs git or gh.
version: 1.0.0
license: MIT
---

# Draft a hikmah-labs plugin from session context — Skill router

This skill packages a pattern the user has been working on into a new plugin under `~/HikmahLabsProjects/plugins/plugins/<slug>/`, following the marketplace's established convention (mirrored from `general-translation` and `stripe-convex-webhook`). It does **not** touch git — the user reviews the diff and commits manually. Read THIS file first to identify what you need, then load the relevant reference from `references/` for detail.

## When to apply

- The user asks to turn the current session's work into a reusable plugin (any of the trigger phrases in the frontmatter `description`).
- The marketplace repo is checked out at `~/HikmahLabsProjects/plugins`.
- Works in **any** source project — the destination is always the marketplace checkout, never the current project.

If the user wants to edit an existing plugin (not create a new one), do not apply this skill — edit the plugin's files directly.

## The 5 hard rules (always apply)

1. **NEVER run `git add`, `git commit`, `git push`, `gh pr create`, `gh issue create`, or any git/gh state-changing command.** The user explicitly handles all git operations themselves. File-system writes only.
2. **NEVER overwrite an existing plugin directory.** If `plugins/<slug>/` already exists, abort with a clear message and ask for a different slug.
3. **NEVER skip the confirmation steps.** Even if the candidate looks obvious, the user picked the conversational flow on purpose. Always run Step B and Step C of `flow.md`.
4. **NEVER edit anything outside `~/HikmahLabsProjects/plugins/`.** No edits to the source project the user is currently in.
5. **NEVER hardcode the user's name/email.** Read the `author` block from an existing `plugins/*/.claude-plugin/plugin.json` (e.g. `general-translation`) so future name changes propagate.

## Two READMEs — don't confuse them

- **Plugin README** at `plugins/<slug>/README.md` — created in Step E of the flow. Documents one plugin in detail.
- **Project README** at the repo root (`~/HikmahLabsProjects/plugins/README.md`) — updated in Step G. Appends one row to the `## Plugins` table.

**Both must be touched on every plugin scaffold.** Failing to update the root README is the single most common gap; `marketplace.json` makes the plugin installable, but the root README is what humans actually read on GitHub.

## Decision tree — which reference do I read?

| If you need to...                                                                        | Read                            |
| ---------------------------------------------------------------------------------------- | ------------------------------- |
| Walk through the 9-step scaffold procedure (summarise → confirm → pre-flight → write → validate → stop) | `flow.md`              |
| Write the actual file contents (`plugin.json`, per-plugin `README.md`, `SKILL.md` router, `references/<topic>.md`) | `templates.md` |
| Update `.claude-plugin/marketplace.json` or the root `README.md` `## Plugins` table      | `marketplace-conventions.md`    |

Load only what's relevant — don't pull all references into context at once.

## Quick checklist for a complete scaffold

(Full version in `references/flow.md`.)

- [ ] Candidate summarised in 2–3 sentences and confirmed via `AskUserQuestion` (Step B)
- [ ] Slug + reference filenames confirmed via `AskUserQuestion` (Step C)
- [ ] Pre-flight: marketplace repo exists, target dir does **not** exist (Step D)
- [ ] Author block read from existing `plugin.json` (rule #5)
- [ ] Directory tree created: `plugins/<slug>/.claude-plugin/`, `plugins/<slug>/skills/<slug>/references/`
- [ ] All 4 file types written with substantive content (no `TODO` placeholders)
- [ ] `.claude-plugin/marketplace.json` updated with new entry
- [ ] Root `README.md` `## Plugins` table updated with new row (U+2011 hyphens in display text)
- [ ] Both JSON files validated with `python3 -m json.tool`
- [ ] Reported file list to user with explicit "review with `git status` and commit when ready" — do not run git

## Files in this skill

```
draft-plugin/
├── SKILL.md                       # this file (router)
└── references/
    ├── flow.md                    # 9-step procedure (Step A summarise → Step I report and stop)
    ├── templates.md               # plugin.json / README / SKILL / reference templates
    └── marketplace-conventions.md # marketplace.json entry + root README table row format
```

Each reference is self-contained and readable in isolation. Load only what's relevant to the current step — don't pull all three into context at once.
