#!/bin/sh
# Prepare the dedicated ledger clone, then hand over to the daemon.
# The token is passed via a git credential helper reading the env, never written to disk.
set -eu
: "${GH_TOKEN:?set GH_TOKEN}"
: "${TARGET_REPO:?set TARGET_REPO}"
BRANCH="${ICARUS_LEDGER_BRANCH:-main}"
git config --global credential.helper '!f() { echo username=x-access-token; echo "password=${GH_TOKEN}"; }; f'
if [ ! -d "$ICARUS_LEDGER_CLONE/.git" ]; then
  git clone --quiet --depth 50 --branch "$BRANCH" "https://github.com/${TARGET_REPO}.git" "$ICARUS_LEDGER_CLONE"
fi
export PYTHONPATH=/app
exec python3 -m icarus.primitives.daemon "$@"
