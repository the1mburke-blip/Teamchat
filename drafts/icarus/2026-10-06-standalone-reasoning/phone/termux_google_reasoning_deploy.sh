#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SCRIPT_ID="14k-ImKDntPPXhhFC7Wzj-2nMEbRIxNxNBDFRtRt03Q-5E5132k7r-wGL"
DEPLOYMENT_ID="AKfycbw7k-w7MVQt81U8vB3tJfLNsa3vvglvl1ANR2eIzsx2YJMJeifn5DrbnVWVy7rxocwJXw"
CANDIDATE_COMMIT="172ad32f65d39fc129ff02c52e2472f7a1ff3bcb"
BASE_CODE="31254738eeb5f4537a0efffb16dd2adaa10bdf529bd4797038fc833203c94af1"
BASE_RUNTIME="d9049f33ed869329572acc2b713ccc8d32c42fab06a4af560f33e14e09a53f90"
BASE_PROVIDER="eea6bd55163d1f6b5fd35d524f1c2a1810d1d73e72ed3098ecfb361ce17c09b3"
ROOT="$HOME/icarus-google-reasoning-only"
LIVE="$ROOT/live"
CAND="$ROOT/candidate"
VERSION_READBACK="$ROOT/version-readback"
RAW_BASE="https://raw.githubusercontent.com/the1mburke-blip/Teamchat/$CANDIDATE_COMMIT/drafts/icarus/2026-10-06-standalone-reasoning/candidate"

die(){ printf 'BLOCKED: %s\n' "$*" >&2; exit 1; }
hash(){ sha256sum "$1" | awk '{print $1}'; }

printf '%s\n' "ICARUS Google-reasoning-only phone deploy"
printf '%s\n' "€0 route; same script; same deployment; no Android/Composio mutation."

command -v pkg >/dev/null 2>&1 || die "TERMUX_REQUIRED"
pkg install -y nodejs-lts git curl coreutils >/dev/null
if ! command -v clasp >/dev/null 2>&1; then
  npm install -g @google/clasp >/dev/null
fi
printf 'clasp=%s node=%s\n' "$(clasp --version)" "$(node --version)"

if ! clasp show-authorized-user >/dev/null 2>&1; then
  printf '%s\n' "OWNER_AUTH_REQUIRED: Google OAuth will use a localhost listener on this Redmi."
  printf '%s\n' "Approve the Google screen. Keep this Termux process running until it says login succeeded."
  clasp login --redirect-port 8888
fi
clasp show-authorized-user

rm -rf "$LIVE" "$CAND" "$VERSION_READBACK"
mkdir -p "$LIVE" "$CAND" "$VERSION_READBACK"
printf '{"scriptId":"%s","rootDir":"."}\n' "$SCRIPT_ID" > "$LIVE/.clasp.json"

cd "$LIVE"
clasp pull >/dev/null
test -f Code.gs && test -f Runtime.gs && test -f Provider.gs || die "LIVE_PULL_INCOMPLETE"

[ "$(hash Code.gs)" = "$BASE_CODE" ] || die "BASELINE_CODE_HASH_MISMATCH"
[ "$(hash Runtime.gs)" = "$BASE_RUNTIME" ] || die "BASELINE_RUNTIME_HASH_MISMATCH"
[ "$(hash Provider.gs)" = "$BASE_PROVIDER" ] || die "BASELINE_PROVIDER_HASH_MISMATCH"

clasp list-deployments > "$ROOT/deployments.before.txt"
grep -F "$DEPLOYMENT_ID" "$ROOT/deployments.before.txt" >/dev/null || die "TARGET_DEPLOYMENT_NOT_FOUND"
OLD_VERSION="$(grep -F "$DEPLOYMENT_ID" "$ROOT/deployments.before.txt" | sed -n 's/.*@\([0-9][0-9]*\).*/\1/p' | head -n1)"
[ -n "$OLD_VERSION" ] || die "OLD_DEPLOYMENT_VERSION_UNPARSEABLE"

for f in Code.gs Runtime.gs Provider.gs; do
  curl -fsSL "$RAW_BASE/$f" -o "$CAND/$f"
  cp "$CAND/$f" "$ROOT/check.js"
  node --check "$ROOT/check.js" >/dev/null || die "SYNTAX_FAIL_$f"
done
rm -f "$ROOT/check.js"

grep -F "scheduleTaskAdvance_();" "$CAND/Code.gs" >/dev/null || die "ASYNC_CONTINUATION_MISSING"
! grep -F "executeComposioTask_(" "$CAND/Runtime.gs" >/dev/null || die "COMPOSIO_CALL_PRESENT"
grep -F "route=GEMINI_DIRECT_REASONING_ONLY" "$CAND/Runtime.gs" >/dev/null || die "REASONING_ONLY_ROUTE_MISSING"
grep -F "const mode = 'GEMINI_DIRECT'" "$CAND/Provider.gs" >/dev/null || die "GEMINI_PRIMARY_NOT_PINNED"

CAND_CODE="$(hash "$CAND/Code.gs")"
CAND_RUNTIME="$(hash "$CAND/Runtime.gs")"
CAND_PROVIDER="$(hash "$CAND/Provider.gs")"
tar -czf "$ROOT/live-baseline.tgz" -C "$LIVE" .

cp "$CAND/Code.gs" "$LIVE/Code.gs"
cp "$CAND/Runtime.gs" "$LIVE/Runtime.gs"
cp "$CAND/Provider.gs" "$LIVE/Provider.gs"

cd "$LIVE"
clasp push >/dev/null

rm -rf "$ROOT/head-readback"
mkdir -p "$ROOT/head-readback"
printf '{"scriptId":"%s","rootDir":"."}\n' "$SCRIPT_ID" > "$ROOT/head-readback/.clasp.json"
cd "$ROOT/head-readback"
clasp pull >/dev/null
[ "$(hash Code.gs)" = "$CAND_CODE" ] || die "HEAD_READBACK_CODE_MISMATCH"
[ "$(hash Runtime.gs)" = "$CAND_RUNTIME" ] || die "HEAD_READBACK_RUNTIME_MISMATCH"
[ "$(hash Provider.gs)" = "$CAND_PROVIDER" ] || die "HEAD_READBACK_PROVIDER_MISMATCH"

cd "$LIVE"
if ! clasp create-deployment --deploymentId "$DEPLOYMENT_ID" --description "Icarus Google reasoning-only recovery" > "$ROOT/deploy.out" 2>&1; then
  cat "$ROOT/deploy.out" >&2
  die "SAME_DEPLOYMENT_UPDATE_FAILED_ACTIVE_VERSION_UNCHANGED"
fi

clasp list-deployments > "$ROOT/deployments.after.txt"
grep -F "$DEPLOYMENT_ID" "$ROOT/deployments.after.txt" >/dev/null || die "TARGET_DEPLOYMENT_MISSING_AFTER_UPDATE"
NEW_VERSION="$(grep -F "$DEPLOYMENT_ID" "$ROOT/deployments.after.txt" | sed -n 's/.*@\([0-9][0-9]*\).*/\1/p' | head -n1)"
[ -n "$NEW_VERSION" ] || die "NEW_DEPLOYMENT_VERSION_UNPARSEABLE"
[ "$NEW_VERSION" != "$OLD_VERSION" ] || die "DEPLOYMENT_VERSION_DID_NOT_ADVANCE"

printf '{"scriptId":"%s","rootDir":"."}\n' "$SCRIPT_ID" > "$VERSION_READBACK/.clasp.json"
cd "$VERSION_READBACK"
if ! clasp pull --versionNumber "$NEW_VERSION" >/dev/null; then
  cd "$LIVE"
  clasp create-deployment --deploymentId "$DEPLOYMENT_ID" --versionNumber "$OLD_VERSION" --description "Automatic rollback after version readback failure" >/dev/null 2>&1 || true
  die "DEPLOYED_VERSION_READBACK_FAILED_ROLLBACK_REQUESTED"
fi

if [ "$(hash Code.gs)" != "$CAND_CODE" ] || [ "$(hash Runtime.gs)" != "$CAND_RUNTIME" ] || [ "$(hash Provider.gs)" != "$CAND_PROVIDER" ]; then
  cd "$LIVE"
  clasp create-deployment --deploymentId "$DEPLOYMENT_ID" --versionNumber "$OLD_VERSION" --description "Automatic rollback after hash mismatch" >/dev/null 2>&1 || true
  die "DEPLOYED_VERSION_HASH_MISMATCH_ROLLBACK_REQUESTED"
fi

printf '%s\n' "VERIFYING: SAME_PROJECT_AND_DEPLOYMENT_UPDATED"
printf 'SCRIPT_ID=%s\nDEPLOYMENT_ID=%s\nOLD_VERSION=%s\nNEW_VERSION=%s\n' "$SCRIPT_ID" "$DEPLOYMENT_ID" "$OLD_VERSION" "$NEW_VERSION"
printf 'CODE_SHA256=%s\nRUNTIME_SHA256=%s\nPROVIDER_SHA256=%s\n' "$CAND_CODE" "$CAND_RUNTIME" "$CAND_PROVIDER"
printf '%s\n' "NEXT_GATE: independent cloud readback, then provider.reason enable, then one fresh Redmi reasoning canary."
