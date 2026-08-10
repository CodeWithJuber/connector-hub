#!/usr/bin/env bash
#
# bootstrap-project.sh — one idempotent command to stand up (or repair) the
# Dev Lifecycle GitHub layer for a repo: labels, merge settings, a branch
# ruleset on the default branch, and the Projects v2 board + classification
# fields.
#
# Safe to re-run. It creates what's missing and leaves the rest alone.
#
# Requires: gh (authenticated), jq.
#   The board step needs the `project` token scope:
#     gh auth refresh -s project -s read:project
#
# Usage:
#   scripts/bootstrap-project.sh            # reads .github/dev-workflow.yml
#   OWNER=acme REPO=app scripts/bootstrap-project.sh   # override target
#
# This is the portable Part-C artifact: drop it + .github/ into any repo and run.

set -euo pipefail

# ---------- locate config ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="$REPO_ROOT/.github/dev-workflow.yml"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
ok() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
info() { printf '  \033[36m·\033[0m %s\n' "$1"; }

# Minimal YAML scalar reader (no yq dependency) — pulls `key: value` under a path.
yaml_get() { grep -E "^[[:space:]]*$1:" "$CONFIG" | head -1 | sed -E "s/^[[:space:]]*$1:[[:space:]]*//; s/[[:space:]]*#.*\$//" | tr -d '\042\047'; }

# ---------- preflight ----------
bold "Dev Lifecycle bootstrap"
command -v gh >/dev/null || { echo "gh CLI not found. Install: https://cli.github.com"; exit 1; }
command -v jq >/dev/null || { echo "jq not found. Install: brew install jq"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "gh not authenticated. Run: gh auth login"; exit 1; }

OWNER="${OWNER:-$(yaml_get owner)}"
REPO="${REPO:-$(yaml_get name)}"
DEFAULT_BRANCH="${DEFAULT_BRANCH:-$(yaml_get defaultBranch)}"
PROJECT_TITLE="${PROJECT_TITLE:-$(yaml_get title)}"
DEFAULT_BRANCH="${DEFAULT_BRANCH:-main}"
[ -n "$OWNER" ] && [ -n "$REPO" ] || { echo "Could not read owner/name from $CONFIG"; exit 1; }
info "Target: $OWNER/$REPO (default branch: $DEFAULT_BRANCH)"

CI_CHECK_NAME="Lint, Typecheck & Test" # must match .github/workflows/ci.yml job name

# =====================================================================
bold "1. Labels"
# =====================================================================
# Idempotent: --force creates or updates. name|color|description
LABELS=$(
  cat <<'EOF'
type:feature|a2eeef|New capability or enhancement
type:bug|d73a4a|Bug or defect
type:chore|fef2c0|Maintenance, deps, tooling, cleanup
type:refactor|c5def5|Restructure without behavior change
type:docs|0075ca|Documentation only
type:spike|d4c5f9|Timeboxed research / investigation
priority:p0|b60205|Critical — drop everything
priority:p1|d93f0b|High — next up
priority:p2|fbca04|Medium — soon
priority:p3|0e8a16|Low — nice to have
area:convex|ededed|Backend / Convex
area:payments|ededed|Stripe / subscriptions
area:auth|ededed|Auth / permissions
area:matching|ededed|Requests / matching
area:ui|ededed|Frontend / design system
area:safety|ededed|Blocking / reporting / moderation
area:wali|ededed|Wali system
area:admin|ededed|Admin panel
area:email|ededed|Resend / transactional email
area:calls|ededed|Daily.co video/audio calls
area:presence|ededed|Presence / online status
area:i18n|ededed|Translation / localization
area:infra|ededed|CI / tooling / workflow
area:docs|ededed|Project documentation
needs-human-review|e11d48|Sensitive/uncertain — a human must approve before merge
ready|0e8a16|Triaged and ready to start
blocked|5319e7|Waiting on something else
EOF
)
while IFS='|' read -r name color desc; do
  [ -z "$name" ] && continue
  gh label create "$name" --color "$color" --description "$desc" --force \
    --repo "$OWNER/$REPO" >/dev/null 2>&1 && ok "$name" || warn "label $name failed"
done <<<"$LABELS"

# =====================================================================
bold "2. Merge settings (squash-only, delete branch on merge)"
# =====================================================================
if gh api -X PATCH "repos/$OWNER/$REPO" \
  -F allow_squash_merge=true \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=false \
  -F delete_branch_on_merge=true >/dev/null 2>&1; then
  ok "squash-only + auto-delete branch"
else
  warn "could not patch merge settings (need admin on the repo?)"
fi

# =====================================================================
bold "3. Branch ruleset on '$DEFAULT_BRANCH' (PR + green CI, admins bypass)"
# =====================================================================
RULESET_NAME="dev-lifecycle: protect $DEFAULT_BRANCH"
# GET rulesets. On a free plan with a PRIVATE repo this 403s — rulesets/branch
# protection need GitHub Pro/Team there. Detect that and degrade gracefully.
if ! RULESETS_JSON=$(gh api "repos/$OWNER/$REPO/rulesets" 2>/dev/null); then
  warn "branch rulesets need GitHub Pro/Team on a private repo — skipping enforcement."
  warn "main stays SOFT-enforced: CI runs on PRs + CODEOWNERS request review + the /ship gate."
  warn "To hard-enforce: upgrade the plan (or make the repo public), then re-run this script."
  RULESETS_JSON=""
fi
EXISTING=""
if [ -n "$RULESETS_JSON" ]; then
  EXISTING=$(printf '%s' "$RULESETS_JSON" | jq -r ".[] | select(.name==\"$RULESET_NAME\") | .id" 2>/dev/null | head -1)
fi
if [ -z "$RULESETS_JSON" ]; then
  : # plan unsupported — already warned, skip creation
elif [ -n "$EXISTING" ]; then
  ok "ruleset already present (id $EXISTING) — leaving as-is"
else
  RULESET_BODY=$(
    cat <<JSON
{
  "name": "$RULESET_NAME",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "pull_request",
      "parameters": { "required_approving_review_count": 0, "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false, "require_last_push_approval": false,
        "required_review_thread_resolution": false } },
    { "type": "required_status_checks",
      "parameters": { "strict_required_status_checks_policy": false,
        "required_status_checks": [ { "context": "$CI_CHECK_NAME" } ] } },
    { "type": "non_fast_forward" }
  ],
  "bypass_actors": [ { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" } ]
}
JSON
  )
  if echo "$RULESET_BODY" | gh api -X POST "repos/$OWNER/$REPO/rulesets" --input - >/dev/null 2>&1; then
    ok "ruleset created — PR required, CI '$CI_CHECK_NAME' must pass, repo admins bypass"
  else
    warn "ruleset creation failed — set it manually: Settings → Rules → Rulesets."
    warn "(Require a PR + status check '$CI_CHECK_NAME'; add 'Repository admin' as a bypass actor.)"
  fi
fi

# =====================================================================
bold "4. Projects v2 board + classification fields"
# =====================================================================
if ! gh project list --owner "$OWNER" --format json >/dev/null 2>&1; then
  warn "Projects scope missing. Run:  gh auth refresh -s project -s read:project"
  warn "then re-run this script. Skipping board for now."
else
  NUM=$(gh project list --owner "$OWNER" --format json \
    --jq ".projects[] | select(.title==\"$PROJECT_TITLE\") | .number" 2>/dev/null | head -1 || true)
  if [ -z "$NUM" ]; then
    NUM=$(gh project create --owner "$OWNER" --title "$PROJECT_TITLE" --format json --jq '.number')
    ok "created board '$PROJECT_TITLE' (#$NUM)"
  else
    ok "board '$PROJECT_TITLE' exists (#$NUM)"
  fi

  ensure_field() { # name | comma-separated options
    local fname="$1" opts="$2"
    if gh project field-list "$NUM" --owner "$OWNER" --format json \
      --jq ".fields[] | select(.name==\"$fname\") | .name" 2>/dev/null | grep -q .; then
      info "field '$fname' exists"
    else
      gh project field-create "$NUM" --owner "$OWNER" --name "$fname" \
        --data-type SINGLE_SELECT --single-select-options "$opts" >/dev/null \
        && ok "field '$fname'" || warn "field '$fname' failed"
    fi
  }
  ensure_field "Stage" "Backlog,Ready,In Progress,In Review,Needs Human Review,Done"
  # "Type" is a reserved field name in Projects v2 (clashes with Issue Types) — use "Work Type".
  ensure_field "Work Type" "feature,bug,chore,refactor,docs,spike"
  ensure_field "Priority" "p0,p1,p2,p3"
  ensure_field "Effort" "XS,S,M,L,XL"
  ensure_field "Area" "convex,payments,auth,matching,ui,safety,wali,admin,email,calls,presence,i18n,infra,docs"
  ensure_field "Needs Human Review" "yes"

  # Best-effort: write the board number back into dev-workflow.yml.
  if grep -qE '^[[:space:]]*number:[[:space:]]*0[[:space:]]*$' "$CONFIG"; then
    sed -i.bak -E "s/^([[:space:]]*number:)[[:space:]]*0[[:space:]]*$/\1 $NUM/" "$CONFIG" && rm -f "$CONFIG.bak"
    ok "wrote project.number=$NUM into .github/dev-workflow.yml"
  fi
fi

# =====================================================================
bold "5. Dependabot (security-only — no routine version-bump PRs)"
# =====================================================================
# We deliberately do NOT ship a dependabot.yml (routine weekly bumps are noisy).
# Instead enable security updates: Dependabot opens a PR only for a real advisory.
gh api -X PUT "repos/$OWNER/$REPO/vulnerability-alerts" >/dev/null 2>&1 && ok "Dependabot alerts on" || warn "could not enable alerts (admin needed)"
gh api -X PUT "repos/$OWNER/$REPO/automated-security-fixes" >/dev/null 2>&1 && ok "security updates on" || warn "could not enable security updates (admin needed)"

# =====================================================================
bold "Done. Finish these one-time UI steps (not scriptable):"
# =====================================================================
cat <<EOF
  · (optional) Board → Workflows: enable "Auto-add to project" (issues + PRs) and
    "Item closed → Stage = Done" so the board self-updates. The lifecycle commands
    also add items directly, so this is a convenience, not required.
  · Board view → group by "Stage" for the swimlanes.
  · Commit & PR the .github/ + scripts/ changes through the normal flow.

Lifecycle commands are ready: /intake  /triage  /start  /preflight  /open-pr
EOF
