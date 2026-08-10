# Hikmah Labs Plugins

Claude Code plugins and agent skills built and maintained by [Hikmah Labs](https://hikmahlabs.com).

## Claude Code

Add the marketplace:

```
/plugin marketplace add hikmahlabs/plugins
```

Install a plugin:

```
/plugin install general-translation
```

Once installed, the skill is auto-discoverable — Claude will invoke it when your prompts match its description (e.g. "translate this app", "fix script tag while rendering", "add gt-next").

## Plugins

| Plugin                                                               | Description                                                                                                                                                                 |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`general‑translation`](./plugins/general-translation/README.md)     | Set up `gt-next` i18n in a Next.js App Router app — `<GTProvider>` placement, `<T>`/`<Var>`/`t()` patterns, ESLint + smoke-test enforcement, locale switching, RTL.         |
| [`stripe‑convex‑webhook`](./plugins/stripe-convex-webhook/README.md) | Host a Stripe webhook on a Convex `httpAction` — no `stripe listen` tunnel needed in dev. Covers signature verification, internal-mutation conversion, and Dashboard setup. |
| [`draft‑plugin`](./plugins/draft-plugin/README.md)                   | Scaffold a new plugin into this marketplace from the current session — confirmation flow, file templates, and `marketplace.json` + root-README updates. Writes files only; never touches git.                    |
| [`dev‑lifecycle`](./plugins/dev-lifecycle/README.md)                 | Idea → classified GitHub issue → worktree → PR → squash-merge. `/adopt` scaffolds any repo (issue forms, PR template, labels, CI, board); then `/intake` `/triage` `/start` `/preflight` `/open-pr` drive features. Auto-flags sensitive diffs for human review. Self-contained. |

## Cursor / other agents

These skills are markdown-first, so they work with any agent that supports custom rules. For Cursor, add the GitHub repo as a remote rule. For other agents, copy the relevant `SKILL.md` and `references/*.md` files into your agent's instruction directory.

## Contributing

Issues and PRs welcome. Each plugin lives under `plugins/<name>/` with a self-contained `skills/<name>/SKILL.md` plus `references/`.

## License

MIT
