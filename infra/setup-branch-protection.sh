#!/usr/bin/env bash
# infra/setup-branch-protection.sh
# ─────────────────────────────────────────────────────────────────────────────
# Enforces branch protection on main: CI must pass, PRs required, no force-push.
# Run this once from your local machine (gh CLI must be authed as a repo admin).
#
# Usage:
#   bash infra/setup-branch-protection.sh
#
# To verify the result:
#   gh api repos/SamakshMathur/LETA-TEC-INFRA/branches/main/protection
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO="SamakshMathur/LETA-TEC-INFRA"
BRANCH="main"

# The CI check context must match EXACTLY what GitHub shows in the PR checks UI.
# For a workflow named "CI" with job display-name "Compile · Import · Lint · Test",
# GitHub Actions reports the check as that display name.
# Verify by opening any PR and inspecting the check name in the "Checks" tab.
CI_CHECK="Compile · Import · Lint · Test"

echo "→ Applying branch protection to $REPO/$BRANCH"

gh api \
  "repos/$REPO/branches/$BRANCH/protection" \
  --method PUT \
  --header "Accept: application/vnd.github+json" \
  --field "required_status_checks[strict]=true" \
  --field "required_status_checks[contexts][]=$CI_CHECK" \
  --field "enforce_admins=true" \
  --field "required_pull_request_reviews[required_approving_review_count]=1" \
  --field "required_pull_request_reviews[dismiss_stale_reviews]=true" \
  --field "restrictions=null" \
  --field "allow_force_pushes=false" \
  --field "allow_deletions=false"

echo ""
echo "✓ Branch protection applied."
echo "  • CI ('$CI_CHECK') must pass before merge"
echo "  • 1 approving review required"
echo "  • Stale reviews dismissed on new push"
echo "  • Force-push to main: disabled"
echo "  • Branch deletion: disabled"
echo "  • Enforced on admins too"
echo ""
echo "To verify:"
echo "  gh api repos/$REPO/branches/$BRANCH/protection | python3 -m json.tool"
