# draft-plugin

Claude Code plugin that scaffolds a new plugin into the local `hikmahlabs/plugins` marketplace from a pattern in the current session. Drop into any project, ask "turn this into a plugin", and the skill writes a fully populated `plugins/<slug>/` tree (manifest, README, router skill, references) and updates both `marketplace.json` and the root `README.md` table — without ever touching git.

## Install

```
/plugin marketplace add hikmahlabs/plugins
/plugin install draft-plugin
```

## What it covers

- **The 9-step scaffold flow** — summarise candidate, confirm slug + reference list, pre-flight, scaffold tree, update marketplace, update root README, validate JSON, hand off
- **The router-skill convention** — frontmatter with auto-invoke triggers, always-apply rules, decision-tree table mapping intent → reference, scope/when-to-apply
- **File templates** — `plugin.json`, per-plugin `README.md`, `SKILL.md` router, `references/<topic>.md` (with the standard reference header)
- **Marketplace conventions** — `marketplace.json` entry shape and insertion point, root README `## Plugins` table row format
- **The U+2011 non-breaking-hyphen rule** — root README link text uses `‑` (non-breaking) so GitHub renders the slug as one indivisible token; URL targets stay ASCII
- **Two-READMEs reminder** — the per-plugin README and the root README must both be touched on every scaffold
- **Hard guardrails** — no git/gh state-changing commands, no overwriting existing plugin dirs, no edits outside the marketplace repo, no skipping confirmation steps

## How it works

The skill is auto-discoverable. When you ask Claude something like:

- "Turn this into a plugin"
- "Create a plugin from this"
- "Draft this as a plugin"
- "Package this as a hikmah-labs plugin"
- "Save this as a plugin so I can reuse it"

…Claude loads `SKILL.md` (the router with the critical rules + decision tree), then fetches the relevant reference file from `references/`:

| Reference                   | Topic                                                                                  |
| --------------------------- | -------------------------------------------------------------------------------------- |
| `flow.md`                   | The 9-step scaffold procedure (Step A summarise → Step I report and stop)              |
| `templates.md`              | Templates for `plugin.json`, per-plugin `README.md`, `SKILL.md` router, `references/*` |
| `marketplace-conventions.md`| `marketplace.json` entry shape + root README table row format (incl. the U+2011 rule)  |

## Origin

Distilled from the actual scaffold flow used to create the other plugins in this very repo (`general-translation`, `stripe-convex-webhook`). The 9-step procedure, hard rules, and template content all come from the lived experience of authoring those plugins — including the non-obvious bits like reading author info from an existing `plugin.json` so it propagates, and using a non-breaking hyphen in the root README so GitHub's table renderer doesn't wrap the plugin name.

## License

MIT
