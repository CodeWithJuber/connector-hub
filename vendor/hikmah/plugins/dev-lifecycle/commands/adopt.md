Adopt the Dev Lifecycle into the current repo: lay down the GitHub + config scaffolding, then bootstrap.

Works on a **new or existing** repo. Non-destructive — never overwrites a file that already exists
(it reports those so you can merge by hand). Run this once per project.

## Locate the bundled scaffolding

The files live alongside this plugin under `template/`:

```bash
TPL="${CLAUDE_PLUGIN_ROOT:-}/template"
[ -d "$TPL" ] || TPL=$(find ~/.claude -type d -path '*dev-lifecycle/template' 2>/dev/null | head -1)
echo "$TPL"   # abort with a clear message if empty
```

Confirm the current directory is the root of the target git repo (`git rev-parse --show-toplevel`).

## Lay down the files (non-destructive)

For every file under `$TPL`, copy it to the same relative path in the repo **only if the destination
does not already exist**. Collect two lists: **added** and **skipped (already present)**.

```bash
cd "$(git rev-parse --show-toplevel)"
while IFS= read -r f; do
  rel="${f#$TPL/}"
  if [ -e "$rel" ]; then echo "skip  $rel"; else mkdir -p "$(dirname "$rel")" && cp "$f" "$rel" && echo "add   $rel"; fi
done < <(find "$TPL" -type f)
chmod +x scripts/bootstrap-project.sh 2>/dev/null
```

Bundled scaffolding: `.github/` (issue forms, PR template, CODEOWNERS, labels.yml, dev-workflow.yml,
ci.yml), `scripts/bootstrap-project.sh`, `.claude/commands/review.md`, `CONTRIBUTING.md`, `CLAUDE.md`.
No routine `dependabot.yml` is shipped — the bootstrap enables Dependabot **security updates** instead
(PRs only for real advisories), so projects don't get noisy weekly bump PRs.

### Special handling

- **`CLAUDE.md` already exists** → do NOT overwrite. Instead read it and ensure these are present;
  append any that are missing (don't duplicate): the four CRITICAL RULES (NEVER ADD AI ATTRIBUTION,
  NEVER AUTO-COMMIT, NEVER DECIDE FOR THE USER, COMMIT ALL CHANGES) and a **Development Lifecycle**
  pointer to `CONTRIBUTING.md`. Report what you appended.
- **`.github/dev-workflow.yml` already exists** → leave it; tell the user to reconcile manually.
- Any other skipped file → list it so the user can merge the template version if they want.

## Configure

Tell the user to edit the placeholders before bootstrapping:

- `.github/dev-workflow.yml` → `repo.owner`, `repo.name`, `project.title`, and the `area` taxonomy +
  `sensitivePaths` for this project.
- `.github/CODEOWNERS` → replace `@OWNER` with their handle/team.

Offer to do these edits for them if they give you the values. **Do not guess owner/name** — read them
from `git remote get-url origin` and confirm.

## Bootstrap

Once `dev-workflow.yml` is filled in:

1. If the GitHub token lacks the project scope, have the user run once:
   `gh auth refresh -s project -s read:project`
2. Run `scripts/bootstrap-project.sh` — creates labels, locks merge to squash-only, adds the branch
   ruleset (if the plan supports it), and builds the Projects v2 board (writing its number back into
   `dev-workflow.yml`).

## Finish

- Report the added/skipped files, the board URL, and that the lifecycle commands (`/intake`,
  `/start`, `/open-pr`, …) are ready.
- Remind: tailor `.claude/commands/review.md` to this codebase's real gotchas.
- These files should be committed through the normal flow (they're a `chore`).

## Rules

- Never overwrite an existing file (except appending missing rules to `CLAUDE.md`, never clobbering it).
- Never run `bunx convex deploy` or push to `main`.
- Read owner/name from the git remote — don't assume.
