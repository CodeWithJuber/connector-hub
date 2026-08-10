# Troubleshooting — error table, what NOT to do, sanity checklist

> Reference loaded by the `general-translation` skill. For the rule list
> and decision tree see `../SKILL.md`.

## 1. Common errors and fixes

| Symptom                                                                   | Cause                                                  | Fix                                                                       |
| ------------------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------- |
| `Encountered a script tag while rendering React component`               | `<GTProvider>` placed outside the client `<Providers>` | Move `<GTProvider>` inside `<Providers>`, wrapping `{children}` (see `provider-tree.md`) |
| Runtime: `useGT(): No context provided`                                   | Component renders outside `<GTProvider>` tree          | Add file to ESLint list, switch to `useOptionalGT()` (see `provider-tree.md`)             |
| Build: `gt translate` succeeds but a string isn't translated at runtime   | String wasn't statically extractable                   | Wrap variables in `<Var>`, replace `t(variable)` with literal lookup map (see `patterns.md`) |
| Browser shows English even after `setLocale('ar')`                        | No reload after locale change                          | Call `window.location.assign(...)` after `setLocale()` (see `patterns.md` § 15.1)         |
| Network errors loading translations                                       | CSP blocks `*.gtx.dev`                                 | Add `https://*.gtx.dev` to `connect-src` (see `setup.md` § 6)             |
| ESLint passes but `useGT()` crashes in production                         | Outside-provider file not in ESLint list               | Audit `providers.tsx`, add file to list AND smoke test (`enforcement.md`) |
| `npx gt translate --publish` fails with "missing API key"                 | Env var not set                                        | Add `GT_API_KEY` (or equivalent) to local `.env.local` and CI/prod        |
| RTL layout looks broken (everything still LTR)                            | Using physical Tailwind props (`ml-`, `pr-`, `left-`)  | Switch to logical props (`ms-`, `pe-`, `start-`, see `patterns.md` § 16)  |
| Translated string includes JS expression as literal text                  | Ternary or function call placed directly inside `<T>`  | Wrap entire expression in single `<Var>` block (see `patterns.md` § 4)    |

## 2. What NOT to do

- Don't put `<GTProvider>` at the top of `layout.tsx` outside `<Providers>`.
- Don't call `useGT()` in any file rendered inside `ProvidersInner` /
  before `{children}` in your client provider tree.
- Don't pass variables, props, or DB values directly to `t()` — only
  literals.
- Don't put runtime expressions directly inside `<T>` — wrap with `<Var>`.
- Don't translate user-generated content with GT — use DeepL/Google for
  that.
- Don't try to translate backend error messages — return error codes.
- Don't forget to reload the page after `setLocale()`.
- Don't commit `public/_gt/`.
- Don't skip the smoke tests — they're how you catch provider-tree bugs.
- Don't add new outside-provider components without updating the ESLint
  list AND the smoke test.

## 3. File structure cheatsheet

After full integration your repo should contain:

```
gt.config.json                              # locale config
.gitignore                                  # + public/_gt/
next.config.ts                              # withGTConfig wrapper
package.json                                # gt + gt-next deps, build script
eslint.config.mjs                           # no-restricted-imports rule
.husky/pre-commit                           # runs lint-staged
.lintstagedrc.json                          # eslint + vitest related
.github/workflows/ci.yml                    # lint + smoke + build

src/
├── app/
│   └── layout.tsx                          # GTProvider inside Providers
├── components/
│   ├── providers.tsx                       # client provider tree
│   └── navbar/
│       └── LanguageSwitcher.tsx            # uses useSetLocale + reload
├── lib/
│   └── useOptionalGT.ts                    # try/catch wrapper
└── __tests__/
    ├── setup.ts                            # mocks useGT to throw
    └── smoke/
        └── providers.smoke.test.tsx        # renders outside-provider components
```

## 4. Sanity checklist before you call it done

- [ ] `npm run build` succeeds with `gt translate --publish` step
- [ ] Every visible English string in active pages is wrapped in `<T>` or
      `t()`
- [ ] Every outside-provider component uses `useOptionalGT()` and `t()`
      only — no `<T>`, no `<Var>`, no raw `useGT()`
- [ ] ESLint `no-restricted-imports` rule lists all outside-provider files
- [ ] Smoke tests render every outside-provider component and pass
- [ ] `<html lang>` and `<html dir>` use server-side `getLocale()` /
      `getLocaleDirection()`
- [ ] LanguageSwitcher does a full page reload after `setLocale()`
- [ ] CSP allows `https://*.gtx.dev`
- [ ] `public/_gt/` is gitignored
- [ ] `GT_API_KEY` (or equivalent) is set in CI and production
- [ ] Tailwind logical properties (`ms`, `me`, `start`, `end`) used for
      anything that needs to flip in RTL
- [ ] Manual QA performed in at least one RTL locale
- [ ] Pre-commit hook runs ESLint + `vitest related`
- [ ] CI runs lint + smoke tests + build on every PR

If all 14 boxes are checked, you have a solid translation pipeline.
