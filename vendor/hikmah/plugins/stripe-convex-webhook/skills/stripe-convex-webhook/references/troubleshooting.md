# Troubleshooting — pitfalls and verification

> Reference loaded by the `stripe-convex-webhook` skill. For the rule list
> and decision tree see `../SKILL.md`.

## Common pitfalls

### `constructEvent` instead of `constructEventAsync`

Symptom: every event returns 400 "Invalid signature" in the Convex logs, even though Stripe says the secret is correct.

Cause: the synchronous `stripe.webhooks.constructEvent(...)` uses Node's `crypto` module. Convex's V8 runtime doesn't have it — verification silently fails.

Fix: use the async variant.

```ts
event = await stripe.webhooks.constructEventAsync(body, sig, webhookSecret);
```

This is the single most common bug after migrating from a Next.js handler.

### Wrong domain — `.convex.cloud` instead of `.convex.site`

Symptom: Stripe Dashboard shows the endpoint returning 404 or DNS errors. No Convex logs.

Cause: `https://<slug>.convex.cloud` is the queries/mutations WebSocket URL — it doesn't serve HTTP routes. HTTP actions live on `<slug>.convex.site`.

Fix: edit the Stripe endpoint URL to use `.convex.site`. The signing secret stays the same.

### Leaving webhook mutations public

Symptom: nothing breaks immediately, but anyone with the Convex deployment URL can call `webhookUpsertSubscription` from a browser console and write fake subscription rows.

Cause: after deleting the Next.js route, the only legitimate caller is `ctx.runMutation` from inside Convex — the mutations don't need to be public anymore.

Fix: convert to `internalMutation` / `internalQuery` (see `setup.md` § 4). Functions that are also called from `src/` (e.g., a client modal) must stay public.

### Signature secret mismatch

Symptom: 400 "Invalid signature" on every event, but `constructEventAsync` is in use and the URL is correct.

Cause: Stripe webhook secrets are **per-endpoint**. If you created a new endpoint instead of editing an existing one's URL, the secret changed.

Fix: copy the new endpoint's `whsec_…` from the Stripe Dashboard and update Convex:

```bash
bunx convex env set STRIPE_WEBHOOK_SECRET <whsec_value>
```

### Returning 200 on errors

Symptom: subscription rows go stale, but the Stripe Dashboard says all events delivered successfully.

Cause: the handler caught an exception and still returned 200. Stripe marked the event delivered and won't retry — your DB is permanently out of sync until manual reconciliation.

Fix: return 5xx from the unhandled-error path. Stripe retries 5xx for up to 3 days with exponential backoff. Idempotent handlers + a daily reconciliation cron make retries safe.

```ts
} catch (err) {
  console.error(`[Stripe webhook] unhandled error event=${event.id}:`, err);
  return new Response(JSON.stringify({ error: 'Internal error' }), {
    status: 500,
    headers: { 'Content-Type': 'application/json' },
  });
}
```

### `"use node"` on `httpAction`

Symptom: codegen error or runtime error about Node APIs unavailable.

Cause: HTTP actions don't support the `"use node"` directive — they only run in Convex's default V8 runtime.

Fix: don't add `"use node"` at the top of the webhook file. The Stripe SDK works in V8 since v15+; Web Crypto handles signature verification. If you genuinely need a Node-only API for some sub-step, factor it out into a separate `internalAction` with `"use node"` and call it via `ctx.runAction(internal.foo.bar, ...)` from the httpAction.

### Subscribed to wrong event set

Symptom: some flows work, others silently don't (e.g., trial-claim never finalizes; cancellations don't downgrade users).

Cause: the Stripe Dashboard endpoint subscribes to fewer events than the handler's `switch` cases handle. Missing events never fire.

Fix: read the `switch (event.type)` block in `convex/stripeWebhook.ts` and subscribe to exactly those event types in the Dashboard.

### Old Next.js endpoint still configured

Symptom: each event triggers two handler runs — one on the Next.js route, one on Convex. Some flows double-fire (e.g., duplicate emails).

Cause: after migrating, the old Stripe Dashboard endpoint pointing at the Next.js URL is still active alongside the new `.convex.site` one.

Fix: delete the old endpoint in the Stripe Dashboard once the new one is verified.

## Verify

End-to-end checks after `setup.md` and `dashboard.md`:

### Static checks

```bash
bun run lint
bunx tsc --noEmit
[ -f convex/tsconfig.json ] && bunx tsc --noEmit -p convex/tsconfig.json
```

All three should be clean. Type errors here usually mean a bad `internal.foo.bar` path or a stale `api.foo.bar` reference inside Convex.

### Convex codegen

After saving `convex/stripeWebhook.ts` and registering the route in `convex/http.ts`, `bunx convex dev` (already running per the project convention) regenerates `convex/_generated/api.d.ts`. Confirm the new module shows up:

```bash
grep stripeWebhook convex/_generated/api.d.ts
# → import type * as stripeWebhook from "../stripeWebhook.js";
# → stripeWebhook: typeof stripeWebhook;
```

If it doesn't appear, codegen failed silently — check the `bunx convex dev` terminal for syntax errors.

### End-to-end

With `bunx convex dev` running, **stop any `stripe listen`** that's still running, then trigger a real Stripe event in the test mode dashboard or your app:

- For subscriptions: subscribe a test user with the `4242 4242 4242 4242` card.
- For lifetime: complete a one-time payment.
- For cancellations: cancel from the customer portal.

In the Convex Dashboard → Logs, you should see the `httpAction` invocation (`POST /stripe/webhook`) succeed with a 2xx response. If it doesn't appear, the Stripe Dashboard endpoint isn't pointing at the right URL — recheck step 2 of `dashboard.md`.

If the Convex log shows the invocation but it returns 400 with "Invalid signature," walk through the [signature pitfalls](#signature-secret-mismatch) above.
