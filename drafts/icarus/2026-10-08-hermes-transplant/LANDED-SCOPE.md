ICARUS owns native Hermes execution through a durable permit kernel, mandatory profile hooks and final dispatch checks. The isolated candidate was implemented and landed; overall status is PARTIAL.

Related to Teamchat Issue #85. Current owner instruction supersedes that issue's older standalone-launcher scope. This draft does not close the issue or claim full acceptance.

The attached `hermes-runtime.patch` applies to Hermes commit `99a45ecc17cc51c0488ec3b8ccf7eaf483f7203d`. It changes native lifecycle, registry/inline/bridge/RPC/backend admission, immutable Docker configuration, trusted target readback, profile governance and focused tests. It includes only repository-derived canonical lineage; installed private profile history, skills, credentials and databases are excluded. The public patch's minimal lineage manifest intentionally differs from the local deployment's additional protected continuity snapshot.

Reproduction: apply the patch to an isolated checkout of the pinned Hermes commit with its existing dependencies. For an isolated profile, copy `icarus_profile_template/governance` and `icarus_profile_template/config.yaml`; keep the installed profile protected. Use the native Hermes entrypoint, `python -m hermes_cli.main`, with HERMES_HOME set to that isolated profile. A real conversation still requires an approved model/provider; the template deliberately configures none. Do not rewrite existing credentials or select a paid route under the €0 constraint.

Focused validation used Hermes's supported per-file runner (`scripts/run_tests_parallel.py`) for `test_icarus_authority.py`, `test_icarus_native_runtime.py` and `test_icarus_transplant_hooks.py`, with one worker, zero retries, temporary profiles and cleared credential variables. 19 checks passed in staging and again after landing. Native CLI help also exited zero after relocation. Runtime conversation responses were deterministic local HTTP/SSE fixtures, not autonomous model inference.

Independent Codex review closed the startup/evidence findings and the later missing-post-hook and hardcoded-path findings. The reviewer recomputed the actual native todo readback hash and confirmed identity/task/todo reconstruction across fixture models. No reviewed finding blocked isolated promotion. Fresh OS-process identity/task and governed memory continuity was separately checked by the executor; it is not independently certified.

Remaining: Docker image pull/contained execution (Docker is unavailable locally), live-model operation, full approved tool/plugin/integration/fallback coverage, and the full repository suite. The current capability catalogue is intentionally restricted; full capability preservation is incomplete. Read/add observation memory is enabled; automatic background learning and unreviewed providers/plugins are disabled. Outcomes remain awaiting independent verification; model prose never awards PASS.

No separate supervisor or wrapper application was introduced. Native Hermes licensing is preserved (MIT, copyright Nous Research); the upstream LICENSE remains in the landed source. No merge, default-branch change or installed-app switch is authorized by this draft.

