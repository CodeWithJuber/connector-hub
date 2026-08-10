# general-translation

Claude Code plugin for integrating [General Translation](https://generaltranslation.com) (`gt-next`) into a Next.js App Router app.

## Install

```
/plugin marketplace add hikmahlabs/plugins
/plugin install general-translation
```

## What it covers

- **`<GTProvider>` placement** — the #1 bug (script-tag-while-rendering crash) and how to avoid it
- **`<T>` / `<Var>` / `t()` patterns** — static text, dynamic values, ternaries, plurals, dates, currencies, forms, toasts, tooltips
- **`useOptionalGT()` wrapper** — for components rendered outside the provider tree (banners, modals, gates)
- **ESLint enforcement** — `no-restricted-imports` rule + Husky pre-commit hook
- **Smoke tests** — mock `useGT` to throw, catches violations in CI
- **Locale switching** — cookie-based routing, full-page reload requirement, DB persistence
- **RTL support** — Tailwind logical properties, `getLocaleDirection()`
- **Backend strings** — error code → frontend translation pattern, UGC via DeepL
- **5-phase migration workflow** — for translating an existing app

## How it works

The skill is auto-discoverable. When you ask Claude something like:

- "Translate this Next.js app with gt-next"
- "Why am I getting 'Encountered a script tag while rendering'?"
- "I'm seeing 'useGT(): No context provided' at runtime"
- "Add a language switcher with RTL support"

…Claude loads `SKILL.md` (the router with the 8 critical rules + decision tree), then fetches the relevant reference file from `references/`:

| Reference            | Topic                                            |
| -------------------- | ------------------------------------------------ |
| `setup.md`           | Install, config, env vars, CSP                   |
| `provider-tree.md`   | `<GTProvider>` placement + `useOptionalGT`       |
| `enforcement.md`     | ESLint + smoke tests                             |
| `patterns.md`        | `<T>`, `<Var>`, `t()`, forms, dates, locale, RTL |
| `backend.md`         | Error codes, UGC, DeepL                          |
| `workflow.md`        | 5-phase migration plan                           |
| `troubleshooting.md` | Error table, what NOT to do, sanity checklist    |

## Origin

Distilled from a fully shipped `gt-next` integration in [Sakeenaty](https://sakeenaty.com): Next.js 16, 5 target locales (English, Arabic, French, Spanish, Malay, Indonesian), ~960 `<T>` blocks, 17 outside-provider files, ESLint + smoke-test enforcement, RTL support.

## License

MIT
