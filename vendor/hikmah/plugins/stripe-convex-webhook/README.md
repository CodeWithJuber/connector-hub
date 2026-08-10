# stripe-convex-webhook

Claude Code plugin for hosting Stripe webhooks on a [Convex](https://convex.dev) HTTP endpoint instead of a Next.js API route. Removes the need to run `stripe listen --forward-to localhost:3000/...` in a separate terminal during development — Stripe can reach the dev Convex deployment (`*.convex.site`) directly from the public internet.

## Install

```
/plugin marketplace add hikmahlabs/plugins
/plugin install stripe-convex-webhook
```

## What it covers

- **The `httpAction` pattern** — why Convex's V8 runtime + `stripe.webhooks.constructEventAsync()` is the right shape (sync `constructEvent` silently fails outside Node)
- **Migration from a Next.js API route** — mechanical substitutions for `convex.mutation` → `ctx.runMutation`, response shape, env-var move
- **Fresh setup** — same pattern, no Next.js route to delete
- **`internalMutation` conversion** — webhook-only Convex functions should not stay public after the Next.js route is deleted
- **Updating internal Convex callers** — reconciliation crons / admin helpers that called `api.foo.bar` need to switch to `internal.foo.bar`
- **`*.convex.site` URL discovery** — the right domain (HTTP routes), not `*.convex.cloud` (WebSocket queries)
- **Convex env-var audit** — `STRIPE_WEBHOOK_SECRET` and any `LOOPS_*` template IDs that previously lived only on the Next.js side
- **Stripe Dashboard setup** — endpoint creation, event subscription scoped to actual `switch` cases, signing-secret behavior on edit-vs-create
- **Common pitfalls** — sync vs async signature verify, wrong domain, public-mutation security, 200-on-error masking failures, `"use node"` on `httpAction`

## How it works

The skill is auto-discoverable. When you ask Claude something like:

- "Set up the Stripe webhook for this Convex project"
- "Why do I need `stripe listen` in dev?"
- "Move the Stripe webhook off the Next.js route"
- "I'm getting signature verification failures in Convex"

…Claude loads `SKILL.md` (the router with the critical rules + decision tree), then fetches the relevant reference file from `references/`:

| Reference            | Topic                                                                |
| -------------------- | -------------------------------------------------------------------- |
| `setup.md`           | Audit, create `convex/stripeWebhook.ts`, register the route, internal-mutation conversion, delete the old Next.js route |
| `dashboard.md`       | Convex env-var audit + Stripe Dashboard endpoint setup (dev + prod) |
| `troubleshooting.md` | Pitfalls + verification commands (lint, tsc, end-to-end test)        |

## Origin

Distilled from the Sakeenaty migration (May 2026): a Next.js API route at `src/app/api/stripe/webhook/route.ts` handling seven Stripe event types was ported verbatim into a Convex `httpAction` at `convex/stripeWebhook.ts`, with eight webhook-only mutations/queries tightened to `internalMutation` / `internalQuery`. After the migration, Stripe delivers events directly to the dev `*.convex.site` URL with no local tunnel.

## License

MIT
