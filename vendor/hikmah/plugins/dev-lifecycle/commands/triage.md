Review untriaged issues, confirm their classification, and mark them ready to work.

## Input

$ARGUMENTS

Optional: a specific issue number, or a filter (e.g. "bugs only"). If empty, triage all open,
untriaged issues.

## Config

Read `.github/dev-workflow.yml` for `repo.owner`, `repo.name`, `project.number`, `taxonomy`.

## Process

1. **Find untriaged issues** — open issues missing a `priority:*` label or the `ready` label:
   ```bash
   gh issue list --repo <owner>/<name> --state open --limit 100 \
     --json number,title,labels,body
   ```
   Treat any issue without a `priority:*` label as untriaged.
2. **For each**, read the body and propose: confirmed **type**, **priority**, **effort**, **area**,
   and a one-line rationale. If it overlaps an existing issue, flag as possible duplicate.
3. **Present a compact table** of your proposals and **ask the user to confirm or adjust** (batch is
   fine — let them reply "all good" or correct specific rows). Do not relabel without confirmation.
4. **Apply**, per confirmed issue:

   ```bash
   gh issue edit <n> --repo <owner>/<name> \
     --add-label "priority:<p>" --add-label "area:<a>" --add-label "ready"
   ```

   Then move the board card — set **BOTH** single-select fields (the board has two: the built-in
   **Status** that the default column view groups by, and the custom **Stage**):
   - **Stage** (custom) → **Ready**.
   - **Status** (built-in — only Todo / In Progress / Done) → **Todo**. "Ready" isn't a Status
     option; a triaged-but-not-started issue belongs in the Todo column. Stage→Status mapping:
     **Backlog/Ready → Todo · In Progress/In Review/Needs Human Review → In Progress · Done → Done.**

   Resolve field + option IDs via `gh project field-list <number> --owner <owner> --format json`,
   then run one `gh project item-edit --id <item> --project-id <proj> --field-id <field>
--single-select-option-id <opt>` **per field**. If field resolution fails, the `ready` label is
   the source of truth — note the board needs a manual nudge.

5. **Flag sensitive issues** — if an issue's scope touches auth, payments, Convex schema/migrations,
   or destructive ops, add the `needs-human-review` label now so it's visible from the start.
6. **Report** what changed and what's now ready to `/start`.

## Rules

- Read-proportional: cap at 100 issues per pass; if more, say so and offer to continue.
- Never close or delete issues here — triage only classifies.
