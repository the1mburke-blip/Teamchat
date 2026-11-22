# Icarus component status — 2026-11-17 17:10Z

- Proposed by: Michael (owner). Executed by: Claude (Opus 5.5), cloud chat session. Verification: self-checked only → PARTIAL until independently verified.
- Sources read: Teamchat main + all 110 branches, last 30 Actions runs, live broker /health, GitHub repo list, icarus/memory/{learned,current-state,android-harness}.md.

| Component | Status | Evidence |
|---|---|---|
| Cloudflare broker `icarus-mobile-broker` | LIVE (readback 17 Nov) | /health: ok, v0.13.3, stage deterministic-read-gateway, Shopify OAUTH_MCP CONNECTED, read routes CANARY/GMAIL/CALENDAR/SHOPIFY_ORDERS. `cloudflare-broker-deployment.md` still describes the 2 Oct v0.1.0 scaffold (stale). |
| `icarus-pulse.yml` | RUNNING | Scheduled run 2026-11-17T14:16Z success; last failures were PR runs 16 Nov. Prime Snapshot Sync success 12:49Z. |
| `icarus-harness-gate.yml` | NOT ON MAIN | Deliberately removed in 56ea8e4 (9 Nov, "prune redundant workflows to eliminate trigger fanout"). Exists only on audit/chore branches. Not restored: reversing that prune needs an explicit owner decision. |
| `scripts/verify_icarus_pulse.py` | NOT ON MAIN / NOT MERGEABLE AS-IS | Only on codex/verify-pulse-writeback-20261110. It verifies `harness-mailbox-log-*` artifacts and an issue #6 writeback comment; current main `icarus-pulse.yml` emits only `harness-run-log-*`, so the script would always fail. Needs the writeback step first. |
| `icarus_pilot.py` | NOT ON MAIN | Only on claude/end-to-end-autonomous-loop-teamchat (loop-v3/). Main uses icarus/core/pilot_state.py. |
| `icarus_daemon.py` | NOT FOUND | Absent on every branch; container daemon (#159) was consolidated by #175. |
| Docker container layer | PARTIAL | Dockerfile on main (ENTRYPOINT proxy_monitor.py). Docker Sign In error: owner-reported, no repo record; needs laptop check. |
| DSH / Cordis kernel | SOURCE ONLY | dsh/cordis/kernel.py on main; laptop install recorded UNKNOWN. |
| Android client | NOT DELIVERED | current-state.md: FAIL/NOT DELIVERED; builds #65–#67 failed; icarus-android-build last push 2026-10-17. Recorded package com.icarus.agent; `com.aistudio.icarus.primex` appears in one file only — identity unconfirmed. |
| Firebase boundary | HISTORICAL PASS ONLY | "previously passed"; no current readback. |
| Composio MCP (in-app) | HISTORICAL PASS ONLY | Early-Oct pass; later owner-reported invalid/unavailable tool output. |
| Hermes donor / esaradev/icarus-plugin | ASSESSED, NOT ADOPTED | "not newly verified"; latest standalone Android directive excludes Hermes. |
| Pydroid 3, Qamar HTML Editor, harnesstest.html | NO REPO RECORD | Not in any branch; device-only. |
| Termux | REJECTED ROUTE | Gated behind owner fingerprint/passcode by Hermes; logged as do-not-retry. |

Overall: PARTIAL. Only broker and Pulse are verified live.
