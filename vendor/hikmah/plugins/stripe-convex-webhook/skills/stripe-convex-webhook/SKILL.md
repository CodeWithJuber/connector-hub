---
name: stripe-convex-webhook
description: Set up (or migrate to) a Stripe webhook hosted on a Convex HTTP endpoint instead of a Next.js API route. Use this in Convex+Stripe projects so Stripe can deliver webhooks directly to the dev deployment with no `stripe listen` tunnel. Triggers on phrases like "set up Stripe webhook", "move Stripe webhook to Convex", "stop needing stripe listen in dev", or signature-verification failures inside a Convex httpAction.
version: 1.0.0
license: MIT
---

# Stripe webhook on a Convex HTTP endpoint — Skill router

This skill encodes a fully shipped migration from a Next.js Stripe webhook
to a Convex `httpAction` (Sakeenaty, May 2026: 7 event types, 8 mutations
tightened to internal). Read THIS file first to identify what you need,
then load the relevant reference from `references/` for detail.

## When to apply

- The project uses **Convex** (look for `convex/` dir + `convex` in `package.json`) **and** **Stripe** (`stripe` in `package.json`).
- The user wants Stripe webhooks to "just work" in dev without `stripe listen --forward-to`, OR is fresh-installing Stripe and needs a webhook endpoint.
- A webhook may already exist at `src/app/api/stripe/webhook/route.ts` (migration path) or may not (fresh-install path).

If the project does **not** use Convex, do not apply this skill. The Next.js route pattern is correct for Convex-less projects.

## The 6 rules (always apply)

1. **`stripe.webhooks.constructEventAsync()`, never `constructEvent()`.** The sync version uses Node `crypto` and silently fails to verify in Convex's V8 runtime. Web Crypto only works via the async API.
2. **Public URL is `*.convex.site`, not `*.convex.cloud`.** `.convex.cloud` is the queries/mutations WebSocket. HTTP routes (httpActions) live on `.convex.site`. Stripe Dashboard takes the `.convex.site` form.
3. **Webhook-only mutations must be `internalMutation` / `internalQuery`.** Once the Next.js route is gone, anything left as `mutation` is reachable from any browser with the Convex deployment URL — anyone can write fake subscription rows. Convert after migration.
4. **Return 5xx on unhandled errors, not 200.** Stripe retries 5xx for up to 3 days; 200 marks the event delivered and a transient failure leaves you permanently out of sync. Idempotent handlers + a daily reconciliation cron make retries safe.
5. **No `"use node"` on `httpAction`.** HTTP actions run in Convex's default V8 runtime only. The Stripe SDK and Web Crypto both work there; Node-only APIs do not.
6. **Convex+Stripe scope only.** Don't apply this pattern to Stripe projects without Convex — there's no public backend endpoint to host the handler on.

## Decision tree — which reference do I read?

| If the user wants to...                                              | Read                  |
| -------------------------------------------------------------------- | --------------------- |
| Migrate an existing Next.js Stripe webhook to Convex                 | `setup.md`            |
| Set up a fresh Stripe webhook in a new Convex+Stripe project         | `setup.md`            |
| Convert webhook-only public mutations to `internalMutation`          | `setup.md` (§ 4)      |
| Configure the Stripe Dashboard endpoint URL + signing secret         | `dashboard.md`        |
| Audit Convex env vars (`STRIPE_*`, `LOOPS_*`) before testing         | `dashboard.md` (§ 1)  |
| Move from dev to prod (separate endpoint, separate secret)           | `dashboard.md` (§ 3)  |
| Debug "Stripe webhook signature verification failed"                 | `troubleshooting.md`  |
| Debug events going to the wrong URL (`.convex.cloud` typo, etc.)     | `troubleshooting.md`  |
| Run final verification (lint, typecheck, end-to-end test)            | `troubleshooting.md` (§ Verify) |

## Quick checklist for a complete setup

(Full version in `references/setup.md` and `references/dashboard.md`.)

- [ ] `convex/stripeWebhook.ts` exists, exports an `httpAction` using `constructEventAsync`
- [ ] `convex/http.ts` registers `/stripe/webhook` POST → handler
- [ ] All webhook-only Convex functions are `internalMutation` / `internalQuery`
- [ ] Internal Convex callers (crons, admin helpers) updated from `api.foo.bar` → `internal.foo.bar`
- [ ] Old `src/app/api/stripe/webhook/route.ts` deleted (migration only)
- [ ] `STRIPE_WEBHOOK_SECRET` set on Convex (`bunx convex env set`)
- [ ] `STRIPE_SECRET_KEY`, `STRIPE_*_PRICE_ID`, `LOOPS_*_TEMPLATE_ID` confirmed on Convex
- [ ] Stripe Dashboard webhook endpoint points at `https://<deployment>.convex.site/stripe/webhook`
- [ ] Endpoint subscribed only to events the `switch` cases actually handle
- [ ] `bun run lint`, `bunx tsc --noEmit`, `bunx tsc --noEmit -p convex/tsconfig.json` clean
- [ ] End-to-end event triggered with `stripe listen` **off**, Convex Dashboard logs show success

## Files in this skill

```
stripe-convex-webhook/
├── SKILL.md               # this file (router)
└── references/
    ├── setup.md           # audit → create handler → register route → internal-conversion → delete old route (with full httpAction skeleton)
    ├── dashboard.md       # Convex env vars + Stripe Dashboard endpoint setup (dev + prod)
    └── troubleshooting.md # pitfalls + verification commands
```

Each reference is self-contained and readable in isolation. Load only what's relevant to the current task — don't pull all three into context at once.
