# Provider tree — `<GTProvider>` placement & `useOptionalGT`

> Reference loaded by the `general-translation` skill. For the rule list
> and decision tree see `../SKILL.md`.
>
> **This is the #1 source of bugs.** Get it right once and you'll never
> think about it again.

## 1. Why ordering matters

- `<GTProvider>` is a **Server Component** that renders a `<script>` tag
  containing the active translations.
- React 19 forbids rendering `<script>` from inside a Client Component.
- Therefore `<GTProvider>` must NOT be a descendant of any Client Component
  *that re-renders it on the client*. In practice: it must be reached via a
  server-rendered path.

## 2. The correct shape

```tsx
// src/app/layout.tsx  (Server Component — no 'use client')
import { GTProvider } from 'gt-next';
import { getLocale, getLocaleDirection } from 'gt-next/server';
import { Providers } from '@/components/providers';

export default async function RootLayout({ children }) {
  const locale = await getLocale();
  const dir = getLocaleDirection(locale); // 'ltr' | 'rtl'

  return (
    <html lang={locale} dir={dir} suppressHydrationWarning>
      <body>
        <Providers>           {/* client-side context tree */}
          <GTProvider>        {/* server component, injects <script> */}
            <Navbar />
            {children}
          </GTProvider>
        </Providers>
      </body>
    </html>
  );
}
```

`<Providers>` is a Client Component (`'use client'`) that renders all your
React contexts (theme, auth, toast, modals, etc). It accepts `children` and
renders them — that's how Server Component children pass through a Client
Component boundary. `<GTProvider>` is part of those `children`, so it stays
on the server side of the boundary.

## 3. What this means in practice

Any component that lives **as a sibling of `{children}`** inside `<Providers>`
is rendered **outside** `<GTProvider>`. Look at this typical pattern:

```tsx
// src/components/providers.tsx
'use client';
export function Providers({ children }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <CallProvider>
          <IncomingCallBanner />     {/* ← OUTSIDE GTProvider */}
          <SuspendedNotice />        {/* ← OUTSIDE GTProvider */}
          <SomeGlobalModal />        {/* ← OUTSIDE GTProvider */}
          {children}                  {/* ← INSIDE GTProvider */}
        </CallProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
```

Every component above `{children}` (banners, gates, modals, any side-channel
UI rendered by a top-level provider) is outside the GT context tree. Those
files **cannot use `useGT()`, `<T>`, or `<Var>`** — they will throw at
runtime.

## 4. Identifying outside-provider files

After scaffolding, audit `src/components/providers.tsx` (or whatever your
top-level client provider file is called). For each component rendered
**before** `{children}`, add it to the outside-provider list.

Typical candidates:
- Auth gates (banned/suspended/terms-not-accepted banners)
- Global modals / notice boxes
- Real-time call/notification banners
- Presence heartbeats, analytics identify components
- Anything that lives inside a feature provider's child tree but is not the
  page content itself

Recursively: if `<CallProvider>` itself renders `<IncomingCallBanner>` as
part of its own JSX, then everything inside `CallProvider`'s render output
is also outside `GTProvider`.

## 5. The `useOptionalGT` wrapper

### 5.1 Create the helper

```ts
// src/lib/useOptionalGT.ts
'use client';
import { useGT } from 'gt-next';

export function useOptionalGT(): (s: string) => string {
  try {
    return useGT();
  } catch {
    return (s: string) => s; // identity fallback when no provider
  }
}
```

### 5.2 Use in outside-provider components

```tsx
// src/components/auth/SuspendedNotice.tsx
'use client';
import { useOptionalGT } from '@/lib/useOptionalGT';

export function SuspendedNotice() {
  const t = useOptionalGT();
  return <p>{t('Account suspended')}</p>;
}
```

### 5.3 Rules for outside-provider files

- ✅ `t('Static string')` — works, will be extracted by the GT CLI scanner
- ❌ `t(variable)` — never extracted
- ❌ `<T>...</T>` — runtime error (no provider context)
- ❌ `<Var>...</Var>` — same
- For dynamic content, use template literals with static prefixes:
  ```ts
  // The scanner extracts the literal portion; the var slots in at runtime.
  t(`You have ${count} unread messages.`)
  ```
  Note: this works *at runtime* but the scanner extraction is best-effort
  for template literals — prefer fixed pluralization branches when count
  affects grammar:
  ```ts
  count === 1 ? t('You have 1 unread message.') : t(`You have ${count} unread messages.`)
  ```

## 6. Workflow when adding a new outside-provider component

1. Add the file to the ESLint `no-restricted-imports` rule (see
   `enforcement.md`).
2. Add the file to the smoke test (see `enforcement.md`).
3. Use `useOptionalGT()` instead of `useGT()`.
4. Use only `t('literal')` — no `<T>` or `<Var>`.
