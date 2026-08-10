# Migration workflow — translating an existing app

> Reference loaded by the `general-translation` skill. For the rule list
> and decision tree see `../SKILL.md`.
>
> When asked to "translate this entire app", do it in this order. Don't
> try to do everything in one pass.

## Phase 1 — infrastructure (no string changes)

1. Install `gt-next` and `gt`, add to `package.json` scripts (see
   `setup.md`).
2. Create `gt.config.json` with `defaultLocale: "en"` and an empty
   `locales: []` array (you can add target locales later).
3. Wrap `next.config.ts` with `withGTConfig`.
4. Add `<GTProvider>` to `layout.tsx` per `provider-tree.md` § 2.
5. Create `src/lib/useOptionalGT.ts` per `provider-tree.md` § 5.1.
6. Add `https://*.gtx.dev` to your CSP.
7. Add `public/_gt/` to `.gitignore`.
8. Set `GT_API_KEY` (or equivalent) in env vars.
9. Verify `npm run build` (or `bun run build`) succeeds with zero
   translatable strings yet — this confirms the pipeline works.

## Phase 2 — provider audit (most error-prone, do BEFORE wrapping strings)

1. Read `src/components/providers.tsx` (or your equivalent).
2. List every component that renders **before** `{children}` in the
   provider chain. Recursively expand any of those components that render
   *their own* sibling UI (banners/modals).
3. Add every such file path to the ESLint `no-restricted-imports` rule
   (see `enforcement.md` § 1).
4. Add a smoke test for each one (see `enforcement.md` § 3).
5. Refactor those files to use `useOptionalGT()` only.

This phase is the most error-prone. Get it right before wrapping strings.

## Phase 3 — string wrapping (most of the work)

Wrap pages/components in dependency order, leaf-first:

1. **Tier 1 — auth flow:** login, signup, password reset, email verify.
2. **Tier 2 — core navigation:** navbar, footer, top-level pages.
3. **Tier 3 — primary features:** dashboard, settings, the main product.
4. **Tier 4 — secondary pages:** marketing, legal (terms/privacy),
   not-found, support.
5. **Skip / defer:** admin pages, internal tools, debug screens — these
   typically don't need translation.

For each file:
- `import { useGT } from 'gt-next';` (or remove if you only use `<T>`).
- Wrap visible text in `<T>...</T>` (see `patterns.md`).
- Wrap dynamic slots in `<Var>{...}</Var>`.
- Replace string-literal `placeholder`, `aria-label`, `title`, `alt`,
  `errorMessage` with `t('...')`.
- Run `bun run lint && bun run typecheck` after each batch.

## Phase 4 — locale activation

1. Add target locales to `gt.config.json`.
2. Run `npx gt translate --publish` once to populate `public/_gt/`.
3. Add a `<LanguageSwitcher>` component per `patterns.md` § 15.1.
4. Manually QA in each locale, especially RTL (`patterns.md` § 16).
5. Add target locales to your CI build env.

## Phase 5 — maintenance discipline

- Every PR that adds user-facing strings MUST wrap them in `<T>` / `t()`.
- Every new outside-provider component MUST be added to the ESLint list
  AND the smoke test.
- Run lint + smoke tests in pre-commit and CI.
