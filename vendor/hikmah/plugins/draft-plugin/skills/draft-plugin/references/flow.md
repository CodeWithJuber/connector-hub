# The 9-step scaffold flow

> Reference loaded by the `draft-plugin` skill. For the rule list and
> decision tree see `../SKILL.md`. For file templates see `templates.md`.
> For `marketplace.json` and root README format see `marketplace-conventions.md`.

This is the full procedure. Execute Steps A through I **in order**. The hard rules in `SKILL.md` apply at every step — most importantly, no git/gh commands and no edits outside `~/HikmahLabsProjects/plugins/`.

## Step A — Summarise the candidate

Read the recent session context. What pattern has the user been working on? What problem does it solve? What sub-topics naturally split it into reference files?

Compose a 2–3 sentence candidate. Example:

> "I think you want to package the **Stripe-on-Convex webhook** pattern, which lets Stripe deliver webhooks directly to a Convex `httpAction` so `stripe listen` isn't needed in dev. Suggested slug: `stripe-convex-webhook`. Suggested reference topics: `setup`, `dashboard`, `troubleshooting`."

## Step B — Confirm the candidate

Use `AskUserQuestion` with these three options:

- **"Yes, that's right"** — proceed to Step C.
- **"Close — let me edit"** — ask for free-text correction, then re-summarise and re-confirm.
- **"No, different idea"** — ask for free-text description of what they actually want, then re-summarise and re-confirm.

Do not proceed without explicit confirmation.

## Step C — Confirm structure

Use `AskUserQuestion` to confirm:

- The plugin **slug** (kebab-case, must match `^[a-z][a-z0-9-]*$`).
- The list of **reference filenames** (typically 3–5, kebab-case, no extension shown).

Show the proposed values and offer "Accept", "Rename slug", "Edit reference list" as options. Loop until the user accepts.

## Step D — Pre-flight checks

```bash
test -d ~/HikmahLabsProjects/plugins
```

If this fails, abort with: "The plugins repo isn't checked out at `~/HikmahLabsProjects/plugins`. Clone it there first: `git clone git@github.com:hikmahlabs/plugins.git ~/HikmahLabsProjects/plugins`."

```bash
test ! -e ~/HikmahLabsProjects/plugins/plugins/<slug>
```

If this fails, abort with: "Plugin `<slug>` already exists at `~/HikmahLabsProjects/plugins/plugins/<slug>/`. Pick a different slug or delete the existing one first." Loop back to Step C.

Read `~/HikmahLabsProjects/plugins/plugins/general-translation/.claude-plugin/plugin.json` to grab the `author` block — use the same `name` and `email` for the new plugin (hard rule #5).

## Step E — Scaffold the plugin tree

Create the directory tree:

```bash
mkdir -p ~/HikmahLabsProjects/plugins/plugins/<slug>/.claude-plugin \
         ~/HikmahLabsProjects/plugins/plugins/<slug>/skills/<slug>/references
```

Then use the **Write** tool (not bash heredocs) to create:

- `plugins/<slug>/.claude-plugin/plugin.json` — see `templates.md`
- `plugins/<slug>/README.md` — see `templates.md`
- `plugins/<slug>/skills/<slug>/SKILL.md` — router (see `templates.md`)
- `plugins/<slug>/skills/<slug>/references/<topic>.md` — one file per topic confirmed in Step C

**Fill in substantive content** from the session context. Don't leave `TODO` placeholders. The whole point of capturing-from-session is that the source material is already there.

## Step F — Update marketplace.json

See `marketplace-conventions.md` for the entry shape and insertion rules. Use the **Edit** tool on `~/HikmahLabsProjects/plugins/.claude-plugin/marketplace.json`.

## Step G — Update the project README (REQUIRED — never skip)

See `marketplace-conventions.md` for the row format, including the **U+2011 non-breaking hyphen** requirement in the display text. Use the **Edit** tool on `~/HikmahLabsProjects/plugins/README.md`.

This step is the single most common scaffold gap. The marketplace listing in `marketplace.json` makes the plugin installable, but the root README is what humans actually read on GitHub. Skipping it means the plugin is invisible in the catalog.

## Step H — Validate JSON

```bash
python3 -m json.tool < ~/HikmahLabsProjects/plugins/.claude-plugin/marketplace.json > /dev/null && echo "marketplace.json OK"
python3 -m json.tool < ~/HikmahLabsProjects/plugins/plugins/<slug>/.claude-plugin/plugin.json > /dev/null && echo "plugin.json OK"
```

If either fails, surface the error and stop. Do not attempt to fix without telling the user what broke.

## Step I — Report and stop

Print to the user:

```bash
find ~/HikmahLabsProjects/plugins/plugins/<slug> -type f | sort
```

Then a short summary: "Created plugin `<slug>` with N reference files. Updated `.claude-plugin/marketplace.json` (new entry) AND root `README.md` (new row in the `## Plugins` table). **Review with `git status` in `~/HikmahLabsProjects/plugins` and commit when ready** — I haven't touched git."

**Stop here.** Do not run `git status` yourself, do not stage, do not commit. Hand off entirely to the user (hard rule #1).
