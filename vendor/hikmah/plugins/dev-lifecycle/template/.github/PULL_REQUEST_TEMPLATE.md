<!--
  Title MUST be a Conventional Commit, e.g.  feat: add wali OTP retry
  This becomes the squash-merge commit subject.
-->

## Summary

<!-- What changed and why, in 1–3 sentences. -->

Closes #<!-- issue number -->

## Change type

- [ ] feat — new capability
- [ ] fix — bug fix
- [ ] chore — maintenance / deps / tooling
- [ ] refactor — no behavior change
- [ ] docs

## Risk / sensitive areas

<!-- Tick any this PR touches. Any tick => this PR needs human review before merge. -->

- [ ] Auth / permissions (`convex/authz/**`, `convex/lib/auth*`)
- [ ] Payments / Stripe (`convex/subscriptions*`, `stripeWebhook.ts`)
- [ ] Convex schema or migrations (`convex/schema.ts`, `convex/migrations/**`)
- [ ] Destructive / data operations
- [ ] Security-critical code
- [ ] None of the above

## Post-merge steps

<!--
  Merging auto-deploys (Vercel deploys the frontend AND Convex). The only thing
  to do by hand is run one-off DATA migrations AFTER the deploy lands. Keep schema
  changes backward-compatible (widen → migrate → narrow). Delete this block if none.
-->

```bash
# bunx convex run migrations/<name>:run
```

## How I tested

<!-- tsc --noEmit / lint / test results, and manual verification steps. -->

## Reviewer notes

<!-- Open questions, areas of low confidence, or anything you want a closer look at. -->
