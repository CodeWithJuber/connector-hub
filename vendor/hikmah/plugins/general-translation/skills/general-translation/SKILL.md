---
name: general-translation
description: Set up or extend General Translation (gt-next) i18n in a Next.js App Router app — wrapping strings with <T>/<Var>, configuring GTProvider placement, useOptionalGT for outside-provider components, ESLint + smoke-test enforcement, locale switching, RTL, backend error codes, and migration workflow. Use when adding translations to a project, fixing "script tag while rendering" errors, debugging "useGT(): No context provided" runtime errors, or planning a full app i18n migration.
version: 1.0.0
license: MIT
---

# General Translation (gt-next) — Skill router

This skill encodes a fully shipped `gt-next` integration (Next.js 16 App
Router, 5 locales, ~960 `<T>` blocks, ESLint + smoke-test enforcement).
Read THIS file first to identify what you need, then load the relevant
reference file from `references/` for detail.

## The 8 rules (always apply)

1. **`<GTProvider>` goes INSIDE the client `<Providers>` wrapper, wrapping
   only `{children}`.** Never above. It injects a `<script>` tag and React
   throws if you place it outside a client boundary.
2. **Anything rendered as a sibling of `{children}` inside the client
   provider tree is OUTSIDE `<GTProvider>`.** Those files cannot use
   `useGT()`, `<T>`, or `<Var>`. Use `useOptionalGT()` instead.
3. **`<T>` children must be statically analyzable.** Wrap any runtime
   expression (variables, ternaries, function calls) in `<Var>`. The GT
   CLI scans source code at build time — it cannot evaluate JS.
4. **`t()` only accepts string literals.** `t('Hello')` ✅, `t(varName)`
   ❌. For dynamic labels, build a lookup map of `t('Literal')` calls.
5. **`<GTProvider>` is a Server Component, `<Providers>` is a Client
   Component.** This ordering matters and is the single most common bug.
6. **Locale changes require a full page reload** —
   `window.location.assign(...)` after `setLocale()`.
7. **Backend strings are not translated by GT.** Return error codes/keys
   from your server functions; translate them on the frontend.
8. **Add `https://*.gtx.dev` to your CSP `connect-src`** or runtime
   translation requests will be blocked.

## Decision tree — which reference do I read?

| If the user wants to...                                    | Read                          |
| ---------------------------------------------------------- | ----------------------------- |
| Add gt-next to a fresh project                             | `setup.md` → `provider-tree.md` |
| Fix "Encountered a script tag while rendering"             | `provider-tree.md`            |
| Fix "useGT(): No context provided"                         | `provider-tree.md`            |
| Wrap strings in `<T>` / write `t()` calls                  | `patterns.md`                 |
| Handle plurals, dates, currency, forms                     | `patterns.md` (§ Forms, Dates) |
| Add a language switcher / RTL support                      | `patterns.md` (§ Locale, RTL) |
| Translate backend errors / user-generated content          | `backend.md`                  |
| Add ESLint + smoke-test enforcement                        | `enforcement.md`              |
| Plan a full migration of an existing app                   | `workflow.md`                 |
| Debug a specific failure mode                              | `troubleshooting.md`          |

## Quick checklist for a fresh integration

(Full version in `references/workflow.md` and `references/troubleshooting.md`.)

- [ ] `gt-next` + `gt` installed; `build` script runs `npx gt translate
      --publish && next build`
- [ ] `gt.config.json` at repo root with `defaultLocale` + `locales`
- [ ] `next.config.ts` wraps with `withGTConfig(...)`
- [ ] `<GTProvider>` placed inside `<Providers>` in `layout.tsx`
- [ ] `src/lib/useOptionalGT.ts` exists
- [ ] CSP allows `https://*.gtx.dev`
- [ ] `public/_gt/` is gitignored
- [ ] `GT_API_KEY` set in env (local + CI + prod)
- [ ] Outside-provider files audited and added to ESLint rule + smoke test
- [ ] Strings wrapped tier-by-tier (auth → nav → core → secondary)
- [ ] Manual QA in at least one RTL locale

## Files in this skill

```
general-translation/
├── SKILL.md                    # this file (router)
└── references/
    ├── setup.md                # install, config, env, CSP
    ├── provider-tree.md        # GTProvider placement + useOptionalGT
    ├── enforcement.md          # ESLint + smoke tests
    ├── patterns.md             # <T>, <Var>, t(), forms, dates, RTL
    ├── backend.md              # error codes, UGC, DeepL split
    ├── workflow.md             # 5-phase migration plan
    └── troubleshooting.md      # error table, what NOT to do, checklist
```

Each reference is self-contained and readable in isolation. Load only
what's relevant to the current task — don't pull all 7 into context at
once.
