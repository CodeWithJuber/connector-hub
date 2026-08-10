# Setup — migrate or freshly install the Convex Stripe webhook

> Reference loaded by the `stripe-convex-webhook` skill. For the rule list
> and decision tree see `../SKILL.md`.

This is the full walkthrough. Steps 1–5 cover audit → handler → route → internal-conversion → delete-old-route. Env vars and Stripe Dashboard live in `dashboard.md`. Pitfalls and verification live in `troubleshooting.md`.

## Why this works

Convex deployments expose a public HTTPS site URL (`*.convex.site`) for HTTP actions. Stripe can reach the dev deployment from the public internet with no local tunnel. The Next.js dev server on `localhost:3000` cannot — that's why the old setup needed `stripe listen --forward-to`.

The Stripe SDK works in Convex's default V8 runtime — confirmed in projects that already call `new Stripe(...)` from regular `action`/`mutation` files without `"use node"`. The signature verifier needs Web Crypto, so use `stripe.webhooks.constructEventAsync()` — the synchronous `constructEvent()` requires Node `crypto` and silently fails outside Node.

## 1. Audit the current setup

Before writing code:

- **Read the existing webhook**, if there is one: `src/app/api/stripe/webhook/route.ts` (or similar Next.js path). Note which event types the `switch` handles, which Convex functions it calls, and what env vars it reads.
- **Read `convex/http.ts`** to confirm `httpRouter` is already in use (almost always) and to copy the registration pattern.
- **Read the top of any `convex/*.ts` file that already uses Stripe** (e.g., `convex/subscriptions.ts`). The `import` block tells you whether Stripe is being used in the default V8 runtime — those files should **not** have `"use node"` at the top. If they do, this skill's pattern still works for the `httpAction` (which can't use `"use node"`), but stop and flag the unusual setup before proceeding.
- **Identify webhook-only Convex functions.** For each function the webhook calls, grep for non-Convex callers:

  ```bash
  grep -rn "<funcName>" src/ convex/ --include="*.ts" --include="*.tsx"
  ```

  Functions called only from the webhook (no `src/` callers) should become `internalMutation` / `internalQuery` after migration so they're not reachable from any browser. Functions called from `src/` must stay public.

## 2. Create `convex/stripeWebhook.ts`

The handler is a single `httpAction`. If migrating, copy each `case` branch from the Next.js route verbatim and apply these mechanical substitutions:

| Old (Next.js route) | New (Convex httpAction) |
| --- | --- |
| `const convex = new ConvexHttpClient(...)` | _delete_ |
| `convex.mutation(api.x.y, args)` | `ctx.runMutation(internal.x.y, args)` (or `api.x.y` if the mutation must stay public) |
| `convex.query(api.x.y, args)` | `ctx.runQuery(internal.x.y, args)` |
| `stripe.webhooks.constructEvent(body, sig, secret)` | `await stripe.webhooks.constructEventAsync(body, sig, secret)` |
| `import { loopsAppVars } from '@/lib/appConfig'` | `import { loopsAppVars } from './lib/appConfig'` (Convex side; create the file if missing) |
| `NextResponse.json({ received: true })` | `new Response(JSON.stringify({ received: true }), { status: 200, headers: { 'Content-Type': 'application/json' } })` |

### Skeleton

```ts
import Stripe from 'stripe';
import { httpAction } from './_generated/server';
import { api, internal } from './_generated/api';
import type { Id } from './_generated/dataModel';
import { STRIPE_API_VERSION } from './lib/stripeApiVersion';

function getRequiredEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required environment variable: ${name}`);
  return v;
}

export const stripeWebhook = httpAction(async (ctx, request) => {
  const stripe = new Stripe(getRequiredEnv('STRIPE_SECRET_KEY'), {
    apiVersion: STRIPE_API_VERSION,
  });
  const webhookSecret = getRequiredEnv('STRIPE_WEBHOOK_SECRET');

  const body = await request.text();
  const sig = request.headers.get('stripe-signature');
  if (!sig) {
    return new Response(JSON.stringify({ error: 'Missing signature' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  let event: Stripe.Event;
  try {
    event = await stripe.webhooks.constructEventAsync(body, sig, webhookSecret);
  } catch (err) {
    console.error('Stripe webhook signature verification failed:', err);
    return new Response(JSON.stringify({ error: 'Invalid signature' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  try {
    switch (event.type) {
      // …port each case from the Next.js handler…
      // case 'invoice.payment_succeeded': { … break; }
      // case 'customer.subscription.updated': { … break; }
      // case 'customer.subscription.deleted': { … break; }
      // case 'invoice.payment_failed': { … break; }
      // case 'payment_intent.succeeded': { … break; }
      // case 'setup_intent.succeeded': { … break; }
      default:
        break;
    }
  } catch (err) {
    // Return 5xx so Stripe retries (idempotent handlers + reconciliation cron make this safe).
    console.error(
      `[Stripe webhook] unhandled error event=${event.id} type=${event.type}:`,
      err
    );
    return new Response(JSON.stringify({ error: 'Internal error processing webhook' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  return new Response(JSON.stringify({ received: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
});
```

### What to preserve from the original

- **All `case` branches** — port them with the substitutions above.
- **All helper functions** (e.g., `mapStripeStatus`, `getSubscriptionPeriod`, `extractCardInfo`, `sendLoopsEmail`, `formatDate`) — move them to top-level functions in the same file.
- **The 5xx-on-error semantics** — non-negotiable. Stripe needs to retry transient failures.

### What to drop

- The `ConvexHttpClient` instance and its constructor — replaced by `ctx.runMutation` / `ctx.runQuery`.
- The `eslint-disable-next-line @typescript-eslint/no-explicit-any` casts on `(api as any).foo.bar` — once you use `internal.foo.bar` directly, types are inferred.
- The `getRequiredEnv('NEXT_PUBLIC_CONVEX_URL')` — not needed; the action runs inside Convex.

## 3. Register the route in `convex/http.ts`

Add alongside any existing routes (telegram, auth, etc.):

```ts
import { stripeWebhook } from './stripeWebhook';
// …
http.route({
  path: '/stripe/webhook',
  method: 'POST',
  handler: stripeWebhook,
});
```

The path `/stripe/webhook` is conventional but free to change — just remember to use the same path in the Stripe Dashboard endpoint URL (`dashboard.md`).

## 4. Convert webhook-only Convex functions to `internal*`

For each function the webhook calls **with no callers in `src/`**, change `mutation` → `internalMutation` and `query` → `internalQuery`. Add the missing import to `_generated/server` if needed:

```ts
// before
import { mutation, query } from './_generated/server';

// after
import { internalMutation, internalQuery, mutation, query } from './_generated/server';
```

Then update any **internal Convex callers** of those functions (reconciliation crons, admin helpers, other actions) from `api.foo.bar` to `internal.foo.bar`. Find them with:

```bash
grep -rn "api\.<module>\.<funcName>" convex/ --include="*.ts"
```

Functions called from the client (`src/`) **must stay public** — leave them as `mutation`/`query` and call them from the webhook via `api.foo.bar`, not `internal.foo.bar`. A common case: `verificationCalls.finalizeMissedReschedulePayment` is also called from a client modal, so it stays `mutation`.

## 5. Delete the old Next.js route (migration only)

```bash
rm src/app/api/stripe/webhook/route.ts
# Then rmdir empty parent dirs:
rmdir src/app/api/stripe/webhook
rmdir src/app/api/stripe
```

If the parent dirs contain other routes, leave them.

## What's next

- **Env vars and Stripe Dashboard:** see `dashboard.md`.
- **Verification (lint, tsc, end-to-end):** see `troubleshooting.md` § Verify.
