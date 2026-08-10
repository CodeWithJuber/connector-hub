# Marketplace conventions — `marketplace.json` and root README

> Reference loaded by the `draft-plugin` skill. For the rule list and
> decision tree see `../SKILL.md`. For the procedure see `flow.md`.
> For per-plugin file templates see `templates.md`.

These are the two repo-wide files that must be touched on every plugin scaffold (Steps F and G of `flow.md`). They are easy to skip, and skipping the root README is the single most common scaffold gap.

## 1. `.claude-plugin/marketplace.json`

Use the **Edit** tool. Find the closing `]` of the `plugins` array and insert a new entry above it.

### Entry shape

```json
    {
      "name": "<slug>",
      "source": "./plugins/<slug>",
      "description": "<one-paragraph description suitable for marketplace listing>"
    }
```

### Insertion rules

- Match the existing **2-space indent** at every level (4 spaces for the entry, 6 spaces for fields).
- The previous entry needs a **trailing comma** added after its closing `}` — JSON does not allow trailing commas on the last element, so the previous-last entry now needs one.
- Description should be a **single paragraph** that mirrors (or is a tightened version of) the `description` in the new plugin's own `plugin.json`. Drift between the two descriptions is allowed but should be intentional.

### Why this matters

A plugin not listed in `marketplace.json` is invisible to `/plugin install`. The directory under `plugins/<slug>/` exists but cannot be installed. Always edit this file in the same scaffold.

## 2. Root `README.md` `## Plugins` table

Use the **Edit** tool. The `## Plugins` section contains a 2-column table (`Plugin | Description`). Append **one new row** at the end of the table, before the blank line preceding `## Cursor / other agents`.

Do **not** create an `### <slug>` section — the root README is an index, not a manual. Per-plugin detail lives only in `plugins/<slug>/README.md` (created in Step E via `templates.md`).

### Row format

```markdown
| [`<slug-with-nbsp-hyphens>`](./plugins/<slug>/README.md) | <one-sentence description ending in a period.> |
```

### Two non-obvious requirements

#### a) Use U+2011 (non-breaking hyphen `‑`) for the hyphens **in the link text**

GitHub's table renderer treats kebab-case names with regular ASCII hyphens as wrappable. Long slugs like `stripe-convex-webhook` get broken across lines, narrowing the column. Replacing each `-` in the *display text* with U+2011 (`‑`) tells GitHub it's one indivisible token and to allocate enough column width.

The **URL target** in the same link keeps regular ASCII hyphens, because that's the actual filesystem path on disk.

Example:

```markdown
| [`stripe‑convex‑webhook`](./plugins/stripe-convex-webhook/README.md) | … |
```

Look closely: the backticks contain `‑` (U+2011), the path inside the parens contains `-` (U+002D, regular ASCII).

#### b) One sentence, ≤ ~200 chars, ending in a period

The bullet list of features and the Origin paragraph belong only in `plugins/<slug>/README.md`. The root README row is a single hook — what the plugin does in one breath. Look at the existing rows for tone calibration.

### Practical edit

Find the last existing table row (a line starting with `| [`). Insert the new row immediately after it, with **no blank line between rows**. The trailing blank line before `## Cursor / other agents` stays where it is.

## After both edits

Step H of `flow.md` validates `marketplace.json` with `python3 -m json.tool`. There's no validator for the root README — eyeball the rendered table by viewing the file in a Markdown previewer or visiting the GitHub URL after pushing. If a row wraps awkwardly, double-check that the display-text hyphens are actually U+2011 and not ASCII (a quick `grep -P '\xe2\x80\x91' README.md` will list rows that contain the non-breaking hyphen).
