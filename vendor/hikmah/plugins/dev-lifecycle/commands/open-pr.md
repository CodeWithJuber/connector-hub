Wrap up the current branch and open its PR in one shot: preflight → commit → push → PR → classify → flag.

This is the single "I'm done, open the PR" command. You should not have to run `/preflight` or
`/commit` separately first — this does them. (Those still exist if you want them standalone.)

## Input

$ARGUMENTS — optionally the issue number this closes. If omitted, infer it from the branch name
(`<user>/<type>-<issue>-<slug>`); if still unknown, ask.

## Config

Read `.github/dev-workflow.yml` → `repo.*`, `project.number`, `sensitivePaths`, `review.command`,
`commitConvention`.

## Pipeline

1. **Preflight** — run `bunx tsc --noEmit`, `bun run lint`, `bun run test`, then the local
   `review.command` (`/review`) over `git diff main...HEAD`. If anything fails, STOP, show the
   blockers, and ask whether to fix now or proceed anyway (the user decides). Never run
   `bun run build` (it publishes translations).
2. **Commit any uncommitted work** — if `git status --porcelain` is non-empty, commit it following
   **the exact same rules as `/commit`**: update `tracker.md` if present, do the HIGH-confidence
   security pass (stop + report if something real turns up), then `git add -A` (include untracked)
   and write a **Conventional Commit** (`type: brief subject`, 50–72 chars, 3–6 bullets of what
   matters). **No AI attribution of any kind** — see the CLAUDE.md rule. (Invoking `/open-pr`
   authorizes this commit.)
3. **Push the feature branch** (never main): `git push -u origin HEAD`.
4. **Sensitive-path scan** — `git diff --name-only origin/main...HEAD` matched against
   `sensitivePaths`. If any match, OR you have open questions / low confidence about the change,
   this PR is `needs-human-review`.
5. **Compose the PR** — title = the same Conventional-Commit subject (it becomes the squash subject);
   body = the repo PR template filled in: summary, `Closes #<issue>`, ticked change-type + risk
   boxes, and any **post-merge steps** (e.g. a one-off `convex run migrations/x:run`) — deploy itself
   is automatic. Put open questions in "Reviewer notes". **The PR body must contain no AI
   attribution** (no "Generated with Claude", no 🤖, no Co-Authored-By) — write it as a human would.
   ```bash
   gh pr create --base main --head "$(git branch --show-current)" --title "<title>" --body "<body>"
   ```
6. **Classify** — copy the linked issue's `type:*` / `priority:*` / `area:*` labels onto the PR
   (`gh pr edit <pr#> --add-label ...`). If step 4 flagged it, also `--add-label needs-human-review`.
7. **Board** — add the PR to project `number`, then set **BOTH** single-select fields on the card
   (the board has two: the built-in **Status** that the default column view groups by, and the
   custom **Stage**):
   - **Stage** (custom) → **In Review** (or **Needs Human Review** if step 4 flagged it).
   - **Status** (built-in — only Todo / In Progress / Done) → **In Progress**. "In Review" / "Needs
     Human Review" aren't Status options; the work stays In Progress until the PR merges (merge →
     the board's built-in workflow sets Status = Done). Stage→Status mapping: **Backlog/Ready → Todo
     · In Progress/In Review/Needs Human Review → In Progress · Done → Done.**

   Resolve IDs via `gh project field-list <number> --owner <owner> --format json`, then one
   `gh project item-edit ...` **per field** — setting only Stage leaves the card stuck in its old
   Status column. Non-blocking if field resolution genuinely fails.

8. **Report** — print the PR URL and a one-line summary. If it's `needs-human-review`, say so plainly
   so the human knows to look before merging. Merging the PR (squash) is the final human step — it
   auto-deploys and closes the issue; there is no separate ship command.

## Rules

- Push only the current feature branch; never push to `main`.
- Commit messages AND the PR body follow `/commit`'s style and carry **zero AI attribution**.
- Always include `Closes #<issue>` so merge auto-closes the issue and advances the board.
- If preflight has blockers or the security pass finds something, stop and let the user decide.
