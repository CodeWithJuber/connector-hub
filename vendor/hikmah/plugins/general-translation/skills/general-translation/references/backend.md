# Backend strings & user-generated content

> Reference loaded by the `general-translation` skill. For the rule list
> and decision tree see `../SKILL.md`.
>
> If your app has a backend (Convex, tRPC, REST), strings thrown or
> returned from the server **cannot** be translated by GT — the CLI
> scanner only reads your frontend tree.

## 1. Pattern: error codes from backend, translation on frontend

The backend throws structured errors with a stable `code`. The frontend
owns all user-facing copy.

```ts
// ─── backend: convex/calls.ts ─────────────────────────────
import { ConvexError } from 'convex/values';

export const start = mutation({
  args: { conversationId: v.id('conversations') },
  handler: async (ctx, args) => {
    const conversation = await ctx.db.get(args.conversationId);
    if (!conversation) {
      throw new ConvexError({ code: 'CONVERSATION_NOT_FOUND' });
    }
    if (!conversation.waliApprovedAt) {
      throw new ConvexError({ code: 'WALI_NOT_APPROVED' });
    }
    if (conversation.activeCallId) {
      throw new ConvexError({
        code: 'CALL_ALREADY_ACTIVE',
        meta: { callId: conversation.activeCallId },
      });
    }
    // ...
  },
});
```

```ts
// ─── frontend: src/lib/errors.ts ──────────────────────────
import { ConvexError } from 'convex/values';

export type AppErrorCode =
  | 'CONVERSATION_NOT_FOUND'
  | 'WALI_NOT_APPROVED'
  | 'CALL_ALREADY_ACTIVE'
  | 'RATE_LIMITED'
  | 'PAYMENT_REQUIRED';

export function extractErrorCode(error: unknown): AppErrorCode | null {
  if (error instanceof ConvexError && typeof error.data === 'object') {
    return (error.data as { code?: AppErrorCode }).code ?? null;
  }
  return null;
}
```

```tsx
// ─── frontend: src/lib/useTranslatedError.ts ──────────────
'use client';
import { useGT } from 'gt-next';
import type { AppErrorCode } from './errors';

export function useTranslatedError() {
  const t = useGT();

  // Map of code → factory. Each factory returns a translated string.
  // Factories let us inject runtime values into translated templates.
  const messages: Record<AppErrorCode, (meta?: any) => string> = {
    CONVERSATION_NOT_FOUND: () => t('That conversation no longer exists.'),
    WALI_NOT_APPROVED:      () => t('Cannot start a call until the Wali approves the conversation.'),
    CALL_ALREADY_ACTIVE:    () => t('A call is already in progress for this conversation.'),
    RATE_LIMITED:           () => t('Too many requests. Try again in a minute.'),
    PAYMENT_REQUIRED:       () => t('Please complete your subscription to continue.'),
  };

  return (error: unknown, fallback?: string): string => {
    const code = extractErrorCode(error);
    if (code && messages[code]) return messages[code]();
    return fallback ?? t('Something went wrong. Please try again.');
  };
}
```

```tsx
// ─── usage ────────────────────────────────────────────────
'use client';
import { useTranslatedError } from '@/lib/useTranslatedError';

export function StartCallButton({ conversationId }) {
  const startCall = useMutation(api.calls.start);
  const translateError = useTranslatedError();

  const onPress = async () => {
    try {
      await startCall({ conversationId });
    } catch (err) {
      showErrorToast(translateError(err));
    }
  };
  return <Button onPress={onPress}><T>Start call</T></Button>;
}
```

## 2. When the error has dynamic parameters

Backend sends a code + structured `meta`; frontend interpolates with `<Var>`:

```ts
// backend
throw new ConvexError({
  code: 'FILE_TOO_LARGE',
  meta: { maxMB: 10, actualMB: 23 },
});
```

```tsx
// frontend message factory
FILE_TOO_LARGE: (meta: { maxMB: number; actualMB: number }) =>
  t(`File is ${meta.actualMB}MB, max is ${meta.maxMB}MB.`),

// or, if you want <Var>-based extraction with cleaner semantics, return
// a node instead of a string:
FILE_TOO_LARGE: (meta) => (
  <T>
    File is <Var>{meta.actualMB}</Var>MB, max is <Var>{meta.maxMB}</Var>MB.
  </T>
),
```

## 3. Server-rendered emails / notifications

Transactional emails (Loops, SendGrid, Resend) are sent from the backend,
so GT cannot translate them. Two options:

1. **Per-locale email templates** in your email service. Pass the user's
   locale to the send call; the service picks the right template.
2. **A translations table** in your DB keyed by `(locale, key)`. The
   backend looks up the row matching the recipient's stored locale.

Pick option (1) if your email provider supports localization (Loops does
via `locale` data variable). Pick option (2) only if (1) is unavailable.

## 4. Avoid: catch-all error toast with `error.message`

`error.message` is whatever the backend stack threw, often English, often
an internal stack trace. Never display it directly:

```tsx
// ❌ leaks raw backend strings, never translated
catch (err) { showErrorToast(err.message); }

// ✅ translated, code-driven
catch (err) { showErrorToast(translateError(err, t('Failed to send'))); }
```

## 5. User-generated content (UGC) — different system entirely

Don't translate user-typed bios, posts, messages, or profile fields with
GT. Use a runtime machine-translation API on demand:

| Content type    | Tool             | Where it runs              |
| --------------- | ---------------- | -------------------------- |
| UI / labels     | GT (`gt-next`)   | Build-time + runtime swap  |
| Profile bios    | DeepL / Google   | Server action, on demand   |
| Chat messages   | DeepL / Google   | Server action, on demand   |
| Email subjects  | Per-locale templates / DB lookup | Server, per recipient |

Example DeepL integration sketch:

```ts
// convex/translateProfile.ts
'use node';
import { internalAction } from './_generated/server';

export const translateField = internalAction({
  args: { text: v.string(), targetLang: v.string() },
  handler: async (_ctx, { text, targetLang }) => {
    const res = await fetch('https://api-free.deepl.com/v2/translate', {
      method: 'POST',
      headers: {
        Authorization: `DeepL-Auth-Key ${process.env.DEEPL_API_KEY}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({ text, target_lang: targetLang.toUpperCase() }),
    });
    const data = await res.json();
    return data.translations[0].text;
  },
});
```

Cache results in a `profileTranslations` table keyed by
`(profileId, sourceLang, targetLang, fieldName, sourceHash)` so repeated
views don't burn quota. Store `sourceHash` so you re-translate when the
user edits their bio.

## 6. Locale code mapping (GT codes vs DeepL codes)

GT, DeepL, Google, and `Intl` all use slightly different locale code
conventions. Build a normalizer once:

```ts
// shared/localeCodes.ts
export function gtToDeepL(gtCode: string): string {
  const map: Record<string, string> = {
    en: 'EN',
    'en-US': 'EN-US',
    'en-GB': 'EN-GB',
    ar: 'AR',
    fr: 'FR',
    es: 'ES',
    'zh-Hans': 'ZH-HANS',
    'zh-Hant': 'ZH-HANT',
    ms: 'MS',
    id: 'ID',
  };
  return map[gtCode] ?? gtCode.toUpperCase();
}
```
