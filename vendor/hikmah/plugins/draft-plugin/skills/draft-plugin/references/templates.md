# File templates

> Reference loaded by the `draft-plugin` skill. For the rule list and
> decision tree see `../SKILL.md`. For the procedure that uses these
> templates see `flow.md`. For `marketplace.json` + root README see
> `marketplace-conventions.md`.

Use the **Write** tool to create each of these files (Step E of `flow.md`). Fill in substantive content from the session context — don't leave `TODO` placeholders.

## `plugins/<slug>/.claude-plugin/plugin.json`

```json
{
  "name": "<slug>",
  "version": "1.0.0",
  "description": "<one-paragraph description — what the plugin does and when to use it. Mention concrete trigger phrases users will say.>",
  "author": {
    "name": "<read from existing plugin.json>",
    "email": "<read from existing plugin.json>"
  },
  "homepage": "https://github.com/hikmahlabs/plugins",
  "license": "MIT"
}
```

The `author` block is **read from `plugins/general-translation/.claude-plugin/plugin.json`** (or any existing plugin), never hardcoded. See hard rule #5 in `SKILL.md`.

## `plugins/<slug>/README.md`

Mirror `plugins/general-translation/README.md` or `plugins/stripe-convex-webhook/README.md`. Sections in order:

```markdown
# <slug>

<one-sentence tagline — what the plugin does>

## Install

\`\`\`
/plugin marketplace add hikmahlabs/plugins
/plugin install <slug>
\`\`\`

## What it covers

- <bullet>
- <bullet>
- ...

## How it works

The skill is auto-discoverable. When you ask Claude something like:

- "<example trigger phrase 1>"
- "<example trigger phrase 2>"
- ...

…Claude loads `SKILL.md` (the router with the critical rules + decision tree), then fetches the relevant reference file from `references/`:

| Reference            | Topic                                            |
| -------------------- | ------------------------------------------------ |
| `<topic1>.md`        | <topic 1 summary>                                |
| `<topic2>.md`        | <topic 2 summary>                                |
| `<topic3>.md`        | <topic 3 summary>                                |

## Origin

<one-paragraph attribution: where the pattern comes from, what shipped use case it was distilled from, what makes it production-grade. Be specific — locale counts, event types, file counts. Do not generalize into something hypothetical.>

## License

MIT
```

**Do not** include an Author section in the README — author lives only in `plugin.json`.

## `plugins/<slug>/skills/<slug>/SKILL.md`

Mirror `plugins/stripe-convex-webhook/skills/stripe-convex-webhook/SKILL.md`. Aim for ~80 lines. The frontmatter `description` is what Claude Code matches against user prompts to auto-invoke the skill — enumerate concrete trigger phrases. Vague descriptions break discoverability.

```markdown
---
name: <slug>
description: <description with embedded auto-invoke trigger phrases — match user phrasing, e.g., "Use when the user says X, Y, or Z" plus one or two error messages they'd paste>
version: 1.0.0
license: MIT
---

# <Plugin title> — Skill router

<2–3 sentence intro: what production use this distills from, what the skill does, and that the reader should load only the relevant reference>

## When to apply

- <condition 1>
- <condition 2>
- ...

If <opposite condition>, do not apply this skill.

## The N rules (always apply)

1. **<short rule>.** <one-sentence why + how>
2. **<short rule>.** ...
...

## Decision tree — which reference do I read?

| If the user wants to...                                  | Read                  |
| -------------------------------------------------------- | --------------------- |
| <task 1>                                                 | `<topic1>.md`         |
| <task 2>                                                 | `<topic2>.md`         |
| ...                                                      | ...                   |

## Quick checklist

- [ ] <step>
- [ ] <step>
- ...

## Files in this skill

\`\`\`
<slug>/
├── SKILL.md               # this file (router)
└── references/
    ├── <topic1>.md        # <one-line topic>
    ├── <topic2>.md        # <one-line topic>
    └── <topic3>.md        # <one-line topic>
\`\`\`

Each reference is self-contained and readable in isolation. Load only what's relevant — don't pull all of them into context at once.
```

The four pieces this skill must preserve when editing later: (1) frontmatter with auto-invoke trigger phrases, (2) the always-apply rule list, (3) the decision-tree table, (4) the scope/when-to-apply section. These are the contract Claude Code relies on.

## `plugins/<slug>/skills/<slug>/references/<topic>.md`

Each reference file starts with the standard header (verbatim, with the slug filled in):

```markdown
# <Topic title>

> Reference loaded by the `<slug>` skill. For the rule list and decision
> tree see `../SKILL.md`.

<deep technical content for this topic — examples, code blocks, tables, checklists. 200–400 lines is typical. Self-contained: a reader who hasn't read SKILL.md should still be able to follow this file.>
```

If the topic naturally cross-references another sibling reference, link to it explicitly (e.g. "see `troubleshooting.md`") so the loader knows what else might be relevant.
