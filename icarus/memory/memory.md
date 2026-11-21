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
