# Icarus cloud worker (ICARUS-CLOUDIFY-20261118, route 1)

Implements route 1 of `docs/ICARUS-CLOUDIFY-DESIGN-2026-11-18.md` (Sol design): an ephemeral
GitHub Actions runner drains the ledger, so queued jobs no longer wait for the laptop.
Prepared by Claude (chat), 2026-11-18. Self-status: PARTIAL until independent verification.

## Cost
€0. GitHub: "Actions usage is free for standard GitHub-hosted runners in public repositories"
(docs.github.com, About billing for GitHub Actions). Teamchat is public; `ubuntu-latest` is a standard runner.

## Design-doc gates closed in code (tests: `tests/test_primitives_cloud_worker.py`)
| Gate (design §4–5) | Fix |
|---|---|
| Model commands inherit daemon secrets | `runner.execute` passes a minimal env (PATH, HOME=job dir, LANG) |
| No secret boundary / network egress | `ICARUS_SANDBOX=docker`: each command runs in `docker run --network none --read-only --cap-drop ALL --security-opt no-new-privileges`, job dir is the only mount. Tested for real: no token visible, outbound TCP blocked |
| Harness gate inherits daemon secrets | `verify.harness_gate` passes a minimal env |
| Shared runner id | workflow sets `ICARUS_RUNNER_ID=gha-<run_id>-<attempt>`; settle checks it |
| Unbounded rate-limit wait vs lease | `ICARUS_MAX_POOL_BREAKS=2`, job `timeout-minutes: 25` < `ICARUS_LEASE_SECONDS=1800` |
| No host/capability field | queue key `execution_target: "laptop-only"` is skipped when `ICARUS_HOST=cloud`; default stays any-host (laptop behaviour unchanged) |

## Activation (owner yes required — production change)
Add `icarus-ledger-worker.yml` (this folder's `cloud-worker.workflow.yml`, with `__CODE_SHA__` set to
this branch's commit) at `.github/workflows/` on the **icarus-ledger** branch. It runs on every queue push
from the pulse. Its own pushes use `GITHUB_TOKEN`, which by GitHub design starts no new run, so no loop.
Uses existing secret `GEMINI_API_KEY`; if absent, the run fails visibly with `OWNER ASSISTANCE REQUIRED`.
Kill switch: disable the workflow in the Actions tab or delete the file from icarus-ledger.
The laptop daemon can keep running; claims are git compare-and-swap, so one job never runs twice.
