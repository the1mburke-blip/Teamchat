# Compulsory completion audit: implementation and deployment boundary

Proposed by Michael; implemented by Codex on 2026-11-06. External spend EUR 0;
tokens unmetered. This document describes a CI admission check, not a universal
interceptor or an activated repository protection rule.

## Verified deployment blockers

The branch-protection and ruleset GET endpoints both returned HTTP 403 with:
`Upgrade to GitHub Pro or make this repository public to enable this feature.`
The authorized branch-protection PUT also returned HTTP 403. No plan, visibility,
credential or permission changes were made. Teamchat remains private. Required
checks therefore have NOT been enabled by this change. A passing workflow alone
does not block an API write to main.

The connected owner credential has admin rights. Workers retaining owner/admin
credentials can alter protections or verifier code. Worker credentials must lose
administration, workflow-edit, status-forging and issue-closing capabilities;
only a separate trusted coordinator may close operational issues. Branch checks
cannot transactionally veto issue-close requests. An issues event that reopens
an issue afterward is not a substitute for removing the write capability.

## Code and configuration

`python harness-runner.py --audit-state-writes` compares the candidate against
the merge base with origin/main (or the immutable CI event base/head revisions).
It enforces append-only CHAT_LOG history and requires evidence for added terminal
claims there and for changes to recognized state/status/ledger/goal registers.
The concrete filename and claim selectors are in `dsh/state_write_gate.py`.
Unknown registers or arbitrary prose elsewhere are not magically recognized.

The workflow has two distinct job contexts: `harness` and
`completion-integrity`. Both must be required, with GitHub Actions app ID 15368.
CODEOWNERS review is part of the proposed protection configuration because an
editable workflow or validator could otherwise remove the check. Code owners
are ineffective without an enabled review/protection rule and separate identities.

After eligible repository protection becomes available, apply and read back:

```bash
gh api --method PUT repos/the1mburke-blip/Teamchat/branches/main/protection \
  --input .github/branch-protection.main.json
gh api repos/the1mburke-blip/Teamchat/branches/main/protection
```

This is a concrete configuration, not evidence that the above PUT succeeded.
Do not change visibility or purchase a plan as an implicit recovery step.

## Receipt and replay prevention

The successful harness job produces `COMPLETION_MANIFEST.json` using physical
state-file readback after the containerized tests. It uploads that manifest
with RUN_LOG.jsonl. A completion claim initially fails admission without a
receipt, but the independent harness job can still produce its evidence.

After that run finishes, a client with a full checkout and an Actions-read token
can generate the receipt, then commit ONLY the receipt:

```bash
python harness-runner.py --receipt-from-run RUN_ID .icarus/receipts/RUN_ID.json
git add .icarus/receipts/RUN_ID.json
git commit -m "evidence: attach authenticated harness proof"
```

RUN_ID is the actual numeric producer run, not a fabricated value. The generated
receipt has exactly these fields: version, task_id, harness_run_id, run_attempt,
artifact_id, artifact_sha256, source_commit and artifacts (path-to-SHA256 map).

Admission independently queries GitHub for the run, current attempt, expected
workflow ID/path, repository identity, successful harness job, artifact identity,
expiry and digest. It downloads the ZIP without forwarding bearer credentials
to blob storage, hashes the bytes, parses the bounded JSON manifest without
extracting arbitrary files, and compares every covered state hash to Git blobs.
The source commit must be an ancestor of the candidate, and only receipts may
change after it. Producer workflow, runner, Dockerfile and verifier must match
the trusted base. A locally forged JSON PASS cannot replace this readback.

An overall run with conclusion failure is usable only when its harness job
succeeded and every other failed job is the completion-integrity admission job.
This resolves the receipt-generation cycle; it does not accept failed tests.
Cancelled, stale-attempt, expired, other-workflow and altered-artifact evidence
fails closed. Digests establish integrity against authenticated GitHub metadata;
they are not standalone signatures and do not establish the semantic truth of
every sentence an agent might write.

## Verification and limitations

Local adversarial tests cover actual Git diffs and mocked remote-proof inputs;
mock responses are unit fixtures, not claims of remote execution. CI also runs
the existing complete offline suite. A separate draft canary PR appends an
unverified `[STATUS] PASS` to CHAT_LOG.md: completion-integrity must fail with
FRAUDULENT_OR_UNVERIFIED_COMPLETION_CLAIM. That canary must never merge.

After server-side protection and worker credential separation are active, test
direct push and merge denial on an isolated protected canary branch with the
same rules. Do not probe a currently unprotected main with a write: the probe
could succeed and would itself be an unverified production modification.
Read back both required contexts and admin enforcement, verify removal of
bypass permissions, then test an unauthorized issue close with a worker token.
These server/permission denial tests remain BLOCKED until those prerequisites
exist. Client-side Git hooks, conversational statements and self-signed receipts
are not evidence of these denials.

References: GitHub Docs, [protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
and [Actions artifact API](https://docs.github.com/en/rest/actions/artifacts).
