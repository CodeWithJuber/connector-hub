# Enforcement — ESLint + smoke tests

> Reference loaded by the `general-translation` skill. For the rule list
> and decision tree see `../SKILL.md`.
>
> Two layers of defense against the most common bug: someone adds a
> component to the outside-provider tree and forgets to use
> `useOptionalGT()`. ESLint catches the import; smoke tests catch the
> runtime crash.

## 1. ESLint — block forbidden imports

Add to `eslint.config.mjs`:

```js
{
  files: [
    // ↓ EVERY outside-GTProvider file goes here
    'src/components/call/**/*.{ts,tsx}',
    'src/components/auth/SuspendedNotice.tsx',
    'src/components/auth/BannedGate.tsx',
    'src/components/auth/EnforcementNoticeModal.tsx',
    'src/components/auth/TermsWarningModal.tsx',
    'src/components/profile/ProfileCompletionGate.tsx',
    'src/components/presence/**/*.{ts,tsx}',
    'src/components/analytics/**/*.{ts,tsx}',
    // ...etc
  ],
  rules: {
    'no-restricted-imports': ['error', {
      paths: [{
        name: 'gt-next',
        importNames: ['useGT', 'T', 'Var'],
        message:
          "This file renders outside <GTProvider>. Use useOptionalGT() from " +
          "'@/lib/useOptionalGT' instead of useGT(), and t() instead of <T>/<Var>.",
      }],
    }],
  },
}
```

**Maintain this list as you add new outside-provider components.** Whenever
you add a new banner/modal/gate that renders inside the top-level provider
tree, add its path to this rule.

## 2. Husky pre-commit hook

```json
// .lintstagedrc.json
{
  "*.{ts,tsx}": ["eslint --no-warn-ignored"],
  "src/**/*.{ts,tsx}": ["vitest related --run"]
}
```

```bash
# .husky/pre-commit
bunx lint-staged   # or pnpm/npm equivalent
```

## 3. Smoke tests — second line of defense

Mock `useGT` to throw by default. Any outside-provider component that
accidentally calls `useGT()` instead of `useOptionalGT()` will crash the
test, exactly mimicking real-world behavior.

```ts
// src/__tests__/setup.ts
import { vi } from 'vitest';

vi.mock('gt-next', () => ({
  useGT: vi.fn(() => {
    throw new Error(
      'useGT(): No context provided. Use useOptionalGT() outside <GTProvider>.'
    );
  }),
  GTProvider: ({ children }: { children: React.ReactNode }) => children,
  T: ({ children }: { children: React.ReactNode }) => children,
  Var: ({ children }: { children: React.ReactNode }) => children,
}));
```

```tsx
// src/__tests__/smoke/providers.smoke.test.tsx
import { render } from '@testing-library/react';
import { SuspendedNotice } from '@/components/auth/SuspendedNotice';
import { IncomingCallBanner } from '@/components/call/IncomingCallBanner';
// ...import every outside-provider component

describe('outside-GTProvider components do not crash', () => {
  it('SuspendedNotice', () => render(<SuspendedNotice />));
  it('IncomingCallBanner', () => render(<IncomingCallBanner />));
  // ...one assertion per component
});
```

Run in CI on every push: `bun run test:smoke` (or your equivalent).

## 4. CI workflow

In `.github/workflows/ci.yml`:

```yaml
- run: bun run lint
- run: bun run test:smoke
- run: bun run build
```

Both lint + smoke tests must pass for a PR to merge.

## 5. The maintenance rule

Whenever you add a new component that renders inside the top-level client
provider tree (i.e. as a sibling or ancestor of `{children}` inside
`<Providers>`), do all three of these in the same PR:

1. Refactor the file to use `useOptionalGT()` instead of `useGT()`.
2. Add its path to the ESLint `no-restricted-imports` files list.
3. Add a smoke-test case in `providers.smoke.test.tsx`.

If any of the three is missing, expect a runtime crash on the page that
renders the component.
