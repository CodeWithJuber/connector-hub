# Translation patterns — `<T>`, `<Var>`, `t()`, locale, RTL

> Reference loaded by the `general-translation` skill. For the rule list
> and decision tree see `../SKILL.md`.
>
> These rules apply to every file that is **not** on the outside-provider
> list. Outside-provider files use only `useOptionalGT()` and `t()` (see
> `provider-tree.md`).

## 1. Plain static text → `<T>`

```tsx
<T>Welcome back</T>
<h1><T>Pricing</T></h1>
<button><T>Sign in</T></button>
```

## 2. Static text + dynamic value → `<T>` + `<Var>`

```tsx
<T>Welcome, <Var>{user.name}</Var></T>
<T>You have <Var>{unread}</Var> unread messages</T>
```

`<Var>` tells the GT scanner "this slot is dynamic; don't try to translate
it". Anything between `<T>` tags that is not a string literal must be
inside `<Var>`.

## 3. Multiple slots

```tsx
<T>
  <Var>{currentIndex + 1}</Var> of <Var>{totalScreens}</Var>
</T>

<T>
  <Var>{value.length}</Var>/<Var>{maxLength}</Var> characters
</T>
```

## 4. Ternaries — wrap the ENTIRE ternary in one `<Var>`

```tsx
// ❌ WRONG — scanner sees control flow as translatable text
<T>Status: {isOnline ? 'Online' : 'Offline'}</T>

// ✅ CORRECT — single dynamic slot
<T>
  Status: <Var>{isOnline ? t('Online') : t('Offline')}</Var>
</T>

// or pre-compute:
const status = isOnline ? t('Online') : t('Offline');
<T>Status: <Var>{status}</Var></T>
```

If the ternary returns short labels you also want translated, call `t()`
on each branch as shown above.

## 5. Inline HTML / JSX is allowed

```tsx
<T>This is <strong>important</strong> news</T>
<T>See our <a href="/terms">terms</a> for details</T>
<T>Marriage is not a swipe. <span className="accent">It's a commitment.</span></T>
```

The scanner understands JSX structure and translates the surrounding text
while preserving the markup. Just keep it shallow and avoid nesting other
React components with their own translations inside.

### 5.1 Mixing JSX, links, and dynamic values together

```tsx
<T>
  By signing up you agree to our{' '}
  <a href="/terms" className="underline">terms</a> and{' '}
  <a href="/privacy" className="underline">privacy policy</a>.
</T>

<T>
  Need help? Email <a href={`mailto:support@${appConfig.nameLowercase}.com`}>
    support@<Var>{appConfig.nameLowercase}</Var>.com
  </a>
</T>

<T>
  <strong className="text-text-primary">Account information:</strong>{' '}
  name, email, date of birth, location
</T>

<T>
  Last updated: <Var>{lastUpdated}</Var>
</T>
```

The translation engine sees the full sentence with placeholders for the
JSX nodes — translators can rearrange them. For example, in Arabic the
word order may flip, but the link still wraps the right phrase.

## 6. Plurals (manual count branching)

This pattern does not use a `<Plural>` component. Handle plurals by
calling `t()` once per branch, choosing the right one at runtime:

```tsx
const t = useGT();

const messageCountText =
  count === 0 ? t('No new messages')
  : count === 1 ? t('1 new message')
  : `${count} ${t('new messages')}`;

// Or, when only quantity differs and you want the count visible inside:
<T>
  You have <Var>{count}</Var>{' '}
  <Var>{count === 1 ? t('new message') : t('new messages')}</Var>
</T>

// Real-world example:
const remainingText =
  hours === 1
    ? t(`Time remaining: ${hours} hour.`)
    : t(`Time remaining: ${hours} hours.`);
```

> **Why two `t()` calls instead of one with a ternary inside?** Because
> the GT scanner extracts each `t('literal')` call independently. A
> ternary inside `t()` returns one runtime value — the scanner can't see
> both branches as separate translation keys.

## 7. Dates, times, and formatted numbers

`<T>` wraps the text around a value; the value itself is computed by your
existing formatting library (`Intl`, `date-fns`, `@internationalized/date`).
Dates/numbers go inside `<Var>`:

```tsx
import { useLocale } from 'gt-next';

function MessageTimestamp({ sentAt }: { sentAt: Date }) {
  const locale = useLocale();
  const formatted = new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(sentAt);

  return <T>Sent at <Var>{formatted}</Var></T>;
}

function PriceTag({ amount }: { amount: number }) {
  const locale = useLocale();
  const formatted = new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: 'USD',
  }).format(amount);

  return <T>Price: <Var>{formatted}</Var></T>;
}

function RelativeDate({ date }: { date: Date }) {
  const locale = useLocale();
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
  const days = Math.round((date.getTime() - Date.now()) / 86_400_000);
  return <T>Expires <Var>{rtf.format(days, 'day')}</Var></T>;
}
```

Pull the active locale from `useLocale()` (or `await getLocale()` in a
server component) and feed it to `Intl.*` formatters. GT does not
auto-format numbers/dates — that's `Intl`'s job.

## 8. Form fields — placeholders, labels, errors, char counters

Forms are the most repetitive translation surface. Standardize:

```tsx
'use client';
import { useGT } from 'gt-next';
import { useForm } from 'react-hook-form';
import { Input, Textarea } from '@/components/ui/heroui';

export function BioField() {
  const t = useGT();
  const { register, formState: { errors }, watch } = useForm();
  const value = watch('bio') ?? '';
  const MAX = 500;

  return (
    <label className="block">
      <p className="mb-2 text-sm font-medium">
        <T>About you</T>
      </p>

      <Textarea
        {...register('bio', {
          required: t('Required'),
          maxLength: { value: MAX, message: t('Too long') },
        })}
        placeholder={t('A few sentences about yourself...')}
        aria-label={t('About you')}
      />

      <div className="flex justify-between mt-1">
        <span className="text-sm text-danger">
          {errors.bio?.message as string | undefined}
        </span>
        <span className="text-sm text-text-muted">
          <T><Var>{value.length}</Var>/<Var>{MAX}</Var> characters</T>
        </span>
      </div>
    </label>
  );
}
```

Validation messages MUST be `t('literal')` — never `t(zod.errors[0])`.
Build an explicit message map per field if you use Zod:

```ts
const bioSchema = z.string()
  .min(1, t('Required'))
  .max(500, t('Too long'));
```

## 9. Toasts and notifications

```tsx
import { showSuccessToast, showErrorToast } from '@/lib/toast';

const t = useGT();

showSuccessToast(t('Subscription resumed!'));
showErrorToast(t('Failed to send message'));

// With error code mapping:
showErrorToast(ERROR_MESSAGES[err.code]?.() ?? t('Something went wrong.'));
```

## 10. Tooltips, aria-labels, and dynamic identifiers

When the visible identifier is user-generated (`@username`, an email, an
ID), keep it raw and translate the surrounding scaffold:

```tsx
<Tooltip content={
  <T>
    <Var>{`@${username}`}</Var> has paused requests temporarily
  </T>
}>
  <Avatar />
</Tooltip>

// For purely user-generated tooltips, no <T> at all:
<Tooltip content={user.bio}> ... </Tooltip>
```

Never write `t(\`${username} is online\`)` — the username is dynamic and
the scanner can't see what's static. Use `<T>` + `<Var>` instead.

## 11. Buttons that switch labels by state

```tsx
const t = useGT();
const submitLabel = isSubmitting ? t('Saving...') : t('Save');
return <Button>{submitLabel}</Button>;

// Or inline with <T>:
return (
  <Button>
    {isSubmitting ? <T>Saving...</T> : <T>Save</T>}
  </Button>
);
```

Both are valid. Prefer the variable form when the button is reused or
the condition is complex; prefer inline `<T>` for simple two-state cases.

## 12. `useGT()` for attributes / non-children strings

`<T>` only works in children position. For `placeholder`, `aria-label`,
`title`, `alt`, etc., use the `t()` function from `useGT()`:

```tsx
'use client';
import { useGT } from 'gt-next';

export function SearchBar() {
  const t = useGT();
  return (
    <input
      placeholder={t('Search...')}
      aria-label={t('Search the catalog')}
    />
  );
}
```

## 13. `t()` accepts ONLY string literals

```ts
t('Hello')                  // ✅ extracted
t(`Hello`)                  // ✅ extracted (template literal with no vars)
t(variable)                 // ❌ never extracted — scanner skips
t('Hello ' + name)          // ❌ never extracted
t(`Hello ${name}`)          // ⚠️ runtime works, extraction is best-effort
```

**For dynamic labels, build a lookup map:**

```tsx
// ❌ WRONG
<button>{t(item.label)}</button>

// ✅ RIGHT
const labels: Record<string, string> = {
  Overview: t('Overview'),
  Requests: t('Requests'),
  Chats: t('Chats'),
};
return <button>{labels[item.label] ?? item.label}</button>;
```

Each call site is a literal that the scanner can find. The runtime lookup
selects the right pre-translated string.

## 14. Server vs Client components

- **Client components** (`'use client'`): use `useGT()` hook for `t()`,
  use `<T>`/`<Var>` in JSX.
- **Server components**: cannot use hooks. Use `<T>`/`<Var>` in JSX (they
  work in both). For non-children strings in a server component, use
  `getGT()` from `gt-next/server`:
  ```tsx
  import { getGT } from 'gt-next/server';
  export default async function Page() {
    const t = await getGT();
    return <input placeholder={t('Search')} />;
  }
  ```

## 15. Locale switching

GT uses a **cookie**, not URL prefixing. URLs stay `/dashboard` instead of
`/en/dashboard` or `/ar/dashboard`.

### 15.1 Language switcher component

```tsx
'use client';
import { useGT } from 'gt-next';
import { useSetLocale } from 'gt-next/client';

const SUPPORTED_LOCALES = [
  { code: 'en', label: 'English' },
  { code: 'ar', label: 'العربية' },
  { code: 'fr', label: 'Français' },
];

export function LanguageSwitcher() {
  const t = useGT();
  const setLocale = useSetLocale();

  const switchTo = (code: string) => {
    setLocale(code);
    // Persist to your DB if you store user preferences
    // updateUserLocale.mutate({ locale: code });

    // CRITICAL: full reload so server components re-render with new locale
    window.location.assign(window.location.pathname + window.location.search + window.location.hash);
  };

  return (
    <select onChange={(e) => switchTo(e.target.value)} aria-label={t('Language')}>
      {SUPPORTED_LOCALES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
    </select>
  );
}
```

Without `window.location.assign(...)`, the page keeps the old server-rendered
HTML and only some client-side strings update — confusing inconsistent UI.

### 15.2 Persisting locale to your backend (optional)

If users have accounts, store their preferred locale in the DB on switch
and read it on initial render via a cookie or initial-state hydration. The
cookie is the source of truth; the DB column is a recovery mechanism for
new devices.

## 16. RTL & locale direction

For Arabic, Hebrew, Persian, Urdu:

```tsx
const dir = getLocaleDirection(locale); // 'rtl' for ar/he/fa/ur
<html lang={locale} dir={dir}>
```

**Use Tailwind logical properties** so layout flips automatically:

| Don't use      | Use instead     |
| -------------- | --------------- |
| `ml-4`, `mr-4` | `ms-4`, `me-4`  |
| `pl-2`, `pr-2` | `ps-2`, `pe-2`  |
| `left-0`       | `start-0`       |
| `right-0`      | `end-0`         |
| `text-left`    | `text-start`    |
| `text-right`   | `text-end`      |
| `border-l`     | `border-s`      |
| `rounded-l-*`  | `rounded-s-*`   |

For Arabic typography you may want a dedicated font (e.g. Scheherazade New)
loaded via `next/font` and applied conditionally:

```tsx
const arabicFont = Scheherazade_New({ subsets: ['arabic'] });
<body className={dir === 'rtl' ? arabicFont.variable : ''}>...
```
