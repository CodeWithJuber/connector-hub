# Dashboard — Convex env vars + Stripe webhook endpoint

> Reference loaded by the `stripe-convex-webhook` skill. For the rule list
> and decision tree see `../SKILL.md`.

After the handler exists (`setup.md`) you need to (1) make sure Convex has every env var the handler reads and (2) point Stripe at the new `*.convex.site` URL. Order matters: create the Stripe endpoint first so you can copy its signing secret into Convex.

## 1. Audit Convex env vars

```bash
bunx convex env list | grep -iE 'STRIPE|LOOPS'
```

What needs to be set on the **Convex** deployment (not Next.js anymore):

| Env var                           | Notes |
| --------------------------------- | ----- |
| `STRIPE_SECRET_KEY`               | Usually already set if any other Convex code calls Stripe. |
| `STRIPE_WEBHOOK_SECRET`           | **Often missing on Convex** — previously lived only in `.env.local` for the Next.js route. Set after step 2 below using the secret Stripe shows for the new endpoint. |
| `STRIPE_MONTHLY_PRICE_ID`, `STRIPE_YEARLY_PRICE_ID`, `STRIPE_LIFETIME_PRICE_ID` (or your equivalents) | Confirm anything the webhook reads via `process.env.STRIPE_*_PRICE_ID`. |
| `LOOPS_API_KEY` and any `LOOPS_*_TEMPLATE_ID` referenced by the handler | Move from `.env.local` to Convex if missing. |

Set with:

```bash
bunx convex env set <NAME> <VALUE>
```

**Do not run `bunx convex deploy`** — env-set propagates to dev automatically and prod deploys are user-managed.

After the migration, you can remove `STRIPE_WEBHOOK_SECRET` (and any `LOOPS_*_TEMPLATE_ID` no longer used by Next.js code) from `.env.local`. Leave `STRIPE_SECRET_KEY` and `NEXT_PUBLIC_*` alone — the Next.js side still uses the SDK on the client (Stripe Elements, etc.).

## 2. Configure the Stripe Dashboard

### 2a. Find the Convex site URL

```bash
grep CONVEX_DEPLOYMENT .env.local
# → e.g. CONVEX_DEPLOYMENT=dev:rosy-lemming-68
```

The deployment slug after `dev:` (or `prod:`) is the subdomain. The webhook URL is:

```
https://<slug>.convex.site/stripe/webhook
```

Note `.convex.site`, **not** `.convex.cloud`. The `.cloud` form is the queries/mutations WebSocket — Stripe POSTs to `.site`.

### 2b. Create or edit the Stripe endpoint

1. Open https://dashboard.stripe.com/test/webhooks (test mode for dev work).
2. Either **edit an existing endpoint's URL** to the new `.convex.site` form, or **add a new endpoint**.
3. Set the URL to `https://<slug>.convex.site/stripe/webhook`.
4. Subscribe to **only the events the handler's `switch` cases actually handle**. For a typical subscription product these are usually:
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `payment_intent.succeeded` (lifetime / one-time + verification reschedule)
   - `setup_intent.succeeded` (trial-claim backstop)

   Read the `switch (event.type)` block in `convex/stripeWebhook.ts` and subscribe to exactly those event types — no more, no less. Subscribing to events you don't handle wastes function invocations; subscribing to fewer than you handle silently breaks features.

5. Copy the endpoint's signing secret (`whsec_…`) and run:

   ```bash
   bunx convex env set STRIPE_WEBHOOK_SECRET <whsec_value>
   ```

### 2c. Edit-vs-create signing-secret behavior

- **Editing the URL of an existing endpoint** keeps the same signing secret. You only need to update `STRIPE_WEBHOOK_SECRET` on Convex if it was never set there (common when migrating from Next.js).
- **Creating a brand-new endpoint** generates a new signing secret. Always update `STRIPE_WEBHOOK_SECRET` on Convex.

If you migrated and an old Next.js-pointing endpoint is still configured, **delete it** in the Stripe Dashboard once the new one is verified — duplicate delivery means duplicate processing.

## 3. Production parity

For prod:

1. Repeat step 2 against https://dashboard.stripe.com/webhooks (live mode).
2. Use the prod Convex deployment slug — find it in the Convex Dashboard or in the prod environment's `CONVEX_DEPLOYMENT` value (often `prod:<slug>`).
3. Use the prod-mode endpoint's signing secret. Set it on the **prod** Convex deployment via the Convex Dashboard env panel (or `bunx convex env set --prod`).

Test-mode and live-mode endpoints are separate Stripe configurations with separate signing secrets. Mixing them up is a common debugging dead end — every test event will fail signature verification in prod and vice versa.

## What's next

- **Verify it end-to-end:** see `troubleshooting.md` § Verify.
- **If something breaks:** start with `troubleshooting.md` § Common pitfalls.
