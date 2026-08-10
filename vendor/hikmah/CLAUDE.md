# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin marketplace** published by Hikmah Labs. There is no application code, no build, no test runner, and no package manager — every plugin is markdown distilled from a fully shipped integration. Work in this repo is almost always one of: authoring a new plugin, editing an existing skill's prose, or adjusting marketplace metadata.

## Layout

```
.claude-plugin/marketplace.json     # marketplace manifest — lists every plugin
plugins/<plugin-name>/
  .claude-plugin/plugin.json        # plugin manifest (name, version, author, license)
  README.md                         # human-facing plugin overview
  skills/<plugin-name>/
    SKILL.md                        # router skill — frontmatter + decision tree
    references/*.md                 # detail files, loaded on demand
```

The plugin name, the directory under `plugins/`, and the directory under `skills/` are all the **same string**. Renaming requires changing all three plus the `source` and `name` fields in `marketplace.json`.

## The router-skill convention (load-bearing)

Every `SKILL.md` is a **router**, not a manual. The pattern, repeated in both existing plugins:

1. **YAML frontmatter** with `name`, `description`, `version`, `license`. The `description` is what Claude Code matches against user prompts to auto-invoke the skill, so it must enumerate concrete trigger phrases ("translate this app", "set up Stripe webhook", error messages users will paste). Vague descriptions break discoverability.
2. **A short numbered list of always-apply rules** (the "8 rules" / "6 rules" sections). These exist so a Claude instance reading only `SKILL.md` already has the non-negotiables in context.
3. **A decision-tree table** mapping user intent → which `references/*.md` to load. The explicit instruction in both skills is *"Load only what's relevant — don't pull all references into context at once."* Preserve this property when adding references: each one should be self-contained and individually loadable.
4. **A scope/when-to-apply section** that tells Claude when *not* to use the skill (e.g. stripe-convex-webhook only applies when both `convex/` and `stripe` are present).

When editing or adding a skill, keep these four pieces — they are the contract Claude Code relies on.

## Adding a new plugin

1. Create `plugins/<name>/.claude-plugin/plugin.json` (mirror an existing one).
2. Create `plugins/<name>/skills/<name>/SKILL.md` with the frontmatter + router structure above.
3. Add references under `plugins/<name>/skills/<name>/references/`.
4. **Register it in `.claude-plugin/marketplace.json`** under `plugins[]` with matching `name` and `source: "./plugins/<name>"`. A plugin not listed here is invisible to `/plugin install`.
5. Optionally add a `plugins/<name>/README.md` and link it from the root `README.md`.

The two plugin descriptions (in `marketplace.json`, `plugin.json`, `SKILL.md` frontmatter, root `README.md`) currently duplicate prose. When changing one, audit the others for drift.

## Source provenance

Each plugin is described as "distilled from a fully shipped integration" with concrete numbers (locales, event types, file counts). This framing is intentional — the skills carry weight because they encode shipped patterns, not theoretical advice. Preserve specificity when editing; don't generalize the prose into something hypothetical.

## What this repo does not have

- No `package.json`, no lockfile, no build/lint/test commands. Don't fabricate them.
- No CI configuration.
- Markdown is the deliverable. Treat formatting and prose precision as you would code.
