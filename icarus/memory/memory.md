# ICARUS shared memory

Owner: Michael. Repository: the1mburke-blip/Teamchat. This is the concise source-controlled cross-session memory summary. current-state.md contains the full dated operational handoff; learned.md contains reusable lessons; root TRAINING_MATRIX.md contains indexed preflight experience.

## 2026-11-21 — Current operational truth

- Main is at 1035d604a8703152cbba722d3a1ae92a99869e23; PR #266 merged the recovery that makes Issue #99 the canonical scheduled mailbox and wake/availability write target. Issue #6 and PR #8 are read-only legacy sources.
- The autonomous duty loop is not yet verified end-to-end. 03:09 schedule monitoring succeeded but dispatched 0. 03:53 and 13:21 schedule runs skipped cadence. The 12:31 scheduled run failed HTTP 403 posting to legacy Issue #8. A 12:32 manual branch run wrote wake comments for four existing tasks but had no worker receipts and skipped inference/reasoning. The 14:28 merge push's harness was cancelled; no genuine post-merge schedule result existed at the 15:19Z review cutoff.
- Michael's executor fallback request remains pending: selected executor first, then any available eligible executor; explicit blocked result if none. See Issue #99 comment 7062908689.
- Snapshot ingress rows 61 and 62 verify the 09:11 and 12:11 snapshot runs. Both payloads were Form-appended and physically read back in the Sheet. Both workflow logs show BUFFER_API_KEY_MISSING, so Buffer was not refreshed. The snapshot generator still reads Issue #6 comments and needs a separately authorised correction to Issue #99.
- The LIVE Google Doc carried an October 30 marker at review time. NotebookLM ingestion was not independently verified.
- Documentation persistence does not prove Icarus runtime uptake, scheduled execution, worker receipts, or model-weight training.

**Non-negotiable reporting rule:** separate monitoring, cadence skip, dispatch, wake, worker receipt, inference, external ingress, notebook ingestion and independent verification. Never promote an intermediate stage to PASS.

See [HV-EXP-176](../../TRAINING_MATRIX.md), [current-state.md](current-state.md), and [learned.md](learned.md).

## 2026-11-21 — Icarus autonomous duty recovery and daily evidence

- **Proposed by:** Michael. **Recorded by:** ChatGPT GPT-6 through authenticated Teamchat GitHub. **Execution scope:** documentation and evidence reconciliation only; no Sol execution or Icarus runtime action is claimed. **External monetary spend:** €0; connector/model tokens unmetered.
- **Main repository state:** main is at 1035d604a8703152cbba722d3a1ae92a99869e23. PR #266 merged the Issue #99 recovery. Issue #99 is the canonical scheduled mailbox and wake/availability write target. Issue #6 and PR #8 are read-only legacy sources; historical Issue #6 directives were migrated to task-local threads without replaying old directives. Main is protected with harness and completion-integrity required and admin enforcement enabled.
- **Duty-run evidence:**
  - 03:09Z run 44859659024: SUCCESS, 106 issues inspected, 103 eligible directives, 2 duplicates ignored, 2 authorization rejections, 0 new tasks dispatched.
  - 03:53Z run 44863352182: SKIPPED_CADENCE, 0 issues inspected, 0 dispatches.
  - 12:28Z manual run 44904076741 on a6b9967: 4 task packets dispatched (WORK canary, SOL #15/#28, CODEX #191), then HTTP 403 posting to Issue #8; task states waited for worker receipts.
  - 12:31Z genuine scheduled run 44904378014 on a6b9967: HTTP 403 posting to Issue #8, 0 new dispatches, no inference/reasoning.
  - 12:32Z manual branch run 44904398524: runner step succeeded, 0 new dispatches; wake comments were written for the existing four tasks, all still waiting for worker receipts; inference reservation/reasoning skipped.
  - 13:21Z genuine scheduled run 44908461473: SKIPPED_CADENCE, 0 issues inspected, 0 dispatches.
  - PR #265's draft branch had 259 passing harness tests in run 44909939755 after earlier failing attempts; PR #265 was closed and its branch deleted after PR #266 merged. This is not proof of the merged scheduled loop.
  - The PR #266 merge push run 44914144364 had completion-integrity success; harness was cancelled at 14:30:13Z. The subsequent issue-comment run 44914394825 was skipped. No full harness or genuine post-merge scheduled run was verified by the 15:19Z cutoff.
- **Snapshot evidence:**
  - Run 44888385278 (workflow_dispatch) at 09:11Z: 12,727-character payload, FORM_APPEND_OK; row 61 in HumanVibe Prime Snapshot Ingress / Form Responses 1 independently read back with run ID and exact marker.
  - Run 44902633014 (schedule) at 12:11Z: 12,718-character payload, FORM_APPEND_OK; row 62 independently read back with run ID and exact marker.
  - Both runs logged BUFFER_API_KEY_MISSING; Buffer was not refreshed. icarus/core/snapshot.py still reads Issue #6 comments, not canonical Issue #99, so generated snapshot commentary can be stale even when its marker is fresh.
  - The existing LIVE Google Doc was stale at review time: marker 2026-10-30, Drive modification 2026-11-16. This task's later append-only source refresh is recorded separately in the snapshot receipt; NotebookLM ingestion remains unverified unless a matching interactive readback exists.
- **Outstanding work:** (1) observe a genuine post-merge scheduled duty run and matching worker receipt; (2) implement and independently test Michael's selected-executor-first / any-available-eligible-executor fallback from Issue #99 comment 7062908689; (3) correct the snapshot generator's stale Issue #6 comment source in a separately authorised change; (4) retain Buffer refresh as blocked by missing BUFFER_API_KEY; (5) verify NotebookLM ingestion independently.
- **Do not infer:** the PR merge, a successful monitoring run, a manual dispatch, a wake comment, a Form append, a Sheet row, or a documentation update proves autonomous task execution or runtime learning uptake.
- **Sources:** [Issue #99 fallback request](https://github.com/the1mburke-blip/Teamchat/issues/99#issuecomment-7062908689), [403 evidence](https://github.com/the1mburke-blip/Teamchat/issues/99#issuecomment-7063163756), [recovery merge report](https://github.com/the1mburke-blip/Teamchat/issues/99#issuecomment-7064155372), [PR #266](https://github.com/the1mburke-blip/Teamchat/pull/266), [main commit](https://github.com/the1mburke-blip/Teamchat/commit/1035d604a8703152cbba722d3a1ae92a99869e23), [snapshot run 44888385278](https://github.com/the1mburke-blip/Teamchat/actions/runs/44888385278), [snapshot run 44902633014](https://github.com/the1mburke-blip/Teamchat/actions/runs/44902633014), [scheduled failure 44904378014](https://github.com/the1mburke-blip/Teamchat/actions/runs/44904378014), [merge push 44914144364](https://github.com/the1mburke-blip/Teamchat/actions/runs/44914144364).

**Integrity-gate finding (15:26Z):** The first PR check correctly rejected the current-state.md write because no receipt accompanied it. The read-only gate requires a receipt under .icarus/receipts/ tied to workflow ID 408772344 and path .github/workflows/icarus-harness-gate.yml. GitHub reports that workflow as DELETED; the active Pulse workflow is ID 410687420 at .github/workflows/icarus-pulse.yml and is not accepted by the verifier. No receipt was fabricated and the verifier was not changed. To stay within the requested target and the existing gate, current-state.md is restored byte-for-byte to main; the full 21 November operational record is retained in the requested memory.md, learned.md and TRAINING_MATRIX.md.

## 2026-11-21 — Final PR harness outcome

**Post-commit harness result (15:33:50Z):** PR #267 run 44919458401 / job 136892203506 completed with 19 failed and 239 passed in 194.82 seconds (exit code 1). All 19 failures were in tests/test_icarus_duty_runner.py. The PR's final diff changes only TRAINING_MATRIX.md, learned.md, memory.md and the memory README; it changes no runtime code. Therefore the failure is outside the documentation diff, but a separate main-branch baseline run was not performed, so it is not asserted to be pre-existing. completion-integrity passed. The required harness check is red, so branch protection prevents merge. Do not bypass it or claim PASS.

Harness run: https://github.com/the1mburke-blip/Teamchat/actions/runs/44919458401
Job log: https://github.com/the1mburke-blip/Teamchat/actions/runs/44919458401/job/136892203506
