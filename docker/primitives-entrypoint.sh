#!/bin/sh
# Prepare the dedicated ledger clone, then hand over to the daemon.
# The token is passed via a git credential helper reading the env, never written to disk.
#
# Runs as root with only SETUID/SETGID/CHOWN/DAC_OVERRIDE/FOWNER (see Dockerfile.primitives) so
# the daemon can run each job command as the unprivileged user jobrunner (ICARUS_JOB_UID).
# Jobs then cannot read this process's /proc/<pid>/environ (GH_TOKEN) or the ledger clone.
set -eu
: "${GH_TOKEN:?set GH_TOKEN}"
: "${TARGET_REPO:?set TARGET_REPO}"
BRANCH="${ICARUS_LEDGER_BRANCH:-main}"
git config --global credential.helper '!f() { echo username=x-access-token; echo "password=${GH_TOKEN}"; }; f'
# The ledger volume may still be owned by the old daemon uid (app); root git must accept it.
git config --global --add safe.directory "$ICARUS_LEDGER_CLONE"
if [ ! -d "$ICARUS_LEDGER_CLONE/.git" ]; then
  git clone --quiet --depth 50 --branch "$BRANCH" "https://github.com/${TARGET_REPO}.git" "$ICARUS_LEDGER_CLONE"
fi
# Job user may enter its own job dir but may not read the ledger clone or list other jobs.
chown root:root "$ICARUS_LEDGER_CLONE" "$ICARUS_WORK_DIR"
chmod 700 "$ICARUS_LEDGER_CLONE"
chmod 711 "$ICARUS_WORK_DIR"
export PYTHONPATH=/app
exec python3 -m icarus.primitives.daemon "$@"
