Turn a raw idea, bug, or chore into a well-formed, classified GitHub issue on the board.

## Input

$ARGUMENTS

If empty, ask the user for a one-line description before continuing.

## Config

Read `.github/dev-workflow.yml` for `repo.owner`, `repo.name`, `project.number`, and the
`taxonomy` (type / priority / effort / area). All `gh` calls target `owner/name`.

## Process

1. **Classify.** From the description, decide:
   - **type** — one of `feature | bug | chore | refactor | docs | spike`
   - **priority** — `p0` (critical) · `p1` (high) · `p2` (medium) · `p3` (low)
   - **effort** — `XS | S | M | L | XL`
   - **area** — one or more from the taxonomy
2. **Draft the issue.** Title = concise, imperative, no type prefix. Body follows the matching
   issue form's shape (Problem / Proposal / Acceptance for features; Repro / Expected for bugs).
   Always include checkbox **acceptance criteria**.
3. **Show the draft** (title, body, proposed labels) and **ask the user to confirm or edit.**
   Creating an issue is outward-facing — do NOT create it without an explicit go-ahead.
4. **Create it** once confirmed:
   ```bash
   gh issue create --repo <owner>/<name> --title "<title>" --body "<body>" \
     --label "type:<t>" --label "priority:<p>" --label "area:<a>" [--label "area:<a2>"]
   ```
5. **Add to the board** (skip if `project.number` is 0 — tell the user to run the bootstrap):
   ```bash
   gh project item-add <number> --owner <owner> --url <issue-url>
   ```
6. **Report** the issue number + URL, and note it's in `Backlog` awaiting `/triage` (or, if you
   set priority confidently, say it's ready to `/start`).

## Rules

- One issue per call unless the user lists several distinct items.
- If the description implies sensitive areas (auth, payments, Convex schema/migrations, destructive
  ops), note that in the body so reviewers know early.
- Never invent acceptance criteria the user would disagree with — keep them faithful to the ask.
