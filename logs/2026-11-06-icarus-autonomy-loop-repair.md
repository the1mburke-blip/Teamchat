# ICARUS autonomous-loop repair — implementation evidence

Proposed by Michael. Executed by actual Codex, 6 November 2026 UTC. External
spend EUR0; model/connector tokens unmetered. Source branch:
`fix/icarus-autonomy-loop-repair`, original main
`72f70707aee1d32052f49cd2193f4adb8a5dc948`.

Preflight/source and training read receipt:
https://github.com/the1mburke-blip/Teamchat/issues/64#issuecomment-6686785119

## Failed attempts and corrections

- The first offline Athena regression run exited 1, reporting two failures.
  The new dispatcher success detector scanned document contents for generic
  words such as `failed` and `error`, misclassifying successful reads of
  failure logs as transport failures. The first end-to-end assertion showed
  `Execution integrity: TOOL_EXECUTION_FAILED` despite recorded real read
  calls. Correction: inspect anchored transport/status prefixes; never infer
  read failure from arbitrary returned content. The next run uses this
  changed detector. Do not restore broad content keyword matching.
- The runtime Python initially lacked pytest; installed the repository's
  pinned requirements into a temporary test dependency directory. No source
  dependency pins changed. Host Docker is unavailable; the requested Python
  test-suite entry point runs the same offline suite locally; actual Docker
  image build remains a CI acceptance requirement.
- Grace packet regression process exited 0: missing fields, invalid types,
  nonzero cost, malformed JSON/object coercion and task-ID mismatch reject
  before transport; valid structured packet survives POST plus GET readback.
  This is an offline fixture, not a deployed Grace canary.

## Source boundary still unresolved

The first full Python suite reported 172 passing and two failing tests in
75.08 seconds. Both failures came from the host's missing `pytest` executable
on PATH: the existing kernel intentionally selected its syntax-only fallback,
so behavioral-failure tests could not exercise pytest. Installed packages
were present under `/tmp/icarus-test-deps`, including `bin/pytest`. The
corrected test environment adds that bin directory to PATH and the package
directory to PYTHONPATH; no kernel behavior or test assertion is weakened.

The owner's follow-up explicitly adds zero owner intervention and containment
verification. Host `docker` and `gh` are absent. Existing GitHub CI will build
and execute the container; authenticated GitHub connector is the available
equivalent of CLI publication/merge. A genuinely unavailable final action
will be logged as BLOCKED with exit code 3, without an owner prompt.

Issue #64 and Team Room comment 6680133343 identify literal `[object Object]`
in Grace Proxy output. The repository's main tree contains only
`scripts/grace_drive_relay.gs`, not the live `GracePulse.gs` generator.
Repository search and the relay's three historical commits do not establish
that the relay produces those Proxy Chair messages. The relay validation
repair therefore does not establish repair or deployment of that generator.
Issue #64 must stay open pending actual generator wiring and live canary.

## Acceptance status

Corrected full local suite: `python harness-runner.py --test-suite`, with the
temporary dependency/PATH configuration above, exited 0: **174 passed in
22.22 seconds**. Athena assertions include acknowledgment after completion,
failed/timeout/receipt-write recovery, required hourly reads, zero-tool
narrative rejection, two-route failure and authentication boundaries.

Independent CLI subprocess negative readback:

```text
{"verdict": "FAIL", "reason": "ZERO_TOOL_EXECUTION_REJECTED"}
exit_code=1
```

This negative fixture supplied one model call, zero tool events, a claimed
verdict and claimed verified readback. No PASS text was emitted on stdout.

PR #157 was opened at source commit
`2c3787c87b6c49aabfda736a6498d0850220355f`. CI run
https://github.com/the1mburke-blip/Teamchat/actions/runs/42233535339
built the Docker image, ran 174 tests successfully in 12.17s and completed
the completion-integrity job successfully. Job 127945180414 recorded:

```json
{"container_preflight": "VERIFIED", "uid": 1000, "capabilities": 0, "no_new_privileges": true, "application_read_only": true, "default_route": false}
```

An additional review found that a supplied execution receipt was ignored if
both optional requirement flags were omitted. The ordinary packet already
contains a command. Correction: always validate a supplied receipt, infer a
tool requirement from the assigned command when the flag is absent, and test
that zero-tool receipts cannot pass even when a real command creates a valid
physical artifact. These changes require a new CI run; earlier CI does not
attest their bytes.

Live branch-protection read returned HTTP403, `Resource not accessible by
integration`. This is an administration-read permission boundary, not proof
that merge is unavailable. The PR reports mergeable=true and state=blocked
while checks/repository conditions are evaluated. No protection is changed
or bypassed.

Final publication/checks remain pending. No independent governance
adjudication, Apps Script deployment, live provider canary or runtime uptake
is claimed. A repository merge alone cannot establish the deployed loop.
