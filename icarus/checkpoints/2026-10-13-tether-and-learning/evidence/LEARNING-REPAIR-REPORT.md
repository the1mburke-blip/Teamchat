# ICARUS continuous-learning repair — 12 October 2026

Desktop patch installed; live model behaviour remains unverified. Executed by Codex with local deterministic tools. No paid model calls, account calls, purchases or app rebuilds: €0. Measured allowance usage is unknown. No independent reviewer has awarded PASS.

## Findings

The installed desktop profile enabled memory but set memory.nudge_interval and skills.creation_nudge_interval to zero, with auxiliary.background_review.enabled=false. Its native MEMORY.md held 1,938 characters against a 2,200-character allowance. These settings exposed a missing configured review loop; they do not prove that every prior chat failed to learn.

The actual installed Hermes file tool successfully read the original learned-memory file, generational index and inherited-experience skill during an isolated native test. No evidence established that primary ICARUS lacked file access. Worker restrictions were retained.

## Installed changes

- Native memory capacity increased from 2,200 to 6,000 characters. Original memory content was retained and one owner-authorized learning-procedure pointer was added through the native memory tool. Actual file write time: 12 October, 23:44 UK time.
- Added icarus-continuous-learning through the native skill-management tool, then checked native skill loading. Desktop now has 70 skill documents.
- Added a supported pre_llm_call shell hook that reminds primary ICARUS on each turn to retrieve relevant experience and retain useful new knowledge before answering. It appends to the current user message; it does not rewrite identity or past conversation context.
- Added supported post_tool_call and on_session_end hooks. A private local journal records successful native memory/skill write events and completed/incomplete turn metadata. Failed writes, staged approvals and read calls do not count as learning writes. Counts describe recording activity, not truth or independent verification.
- Created workspace/learning/INDEX.md, a local activity database and evidence-bearing lesson records. Detailed knowledge can grow outside the bounded prompt memory. Duplicate lessons retain their original record; contradictions require separate attributed records.
- Recorded three initial lessons: Michael's learning request, the observed configuration/capacity diagnosis, and the repair's verified scope and remaining limits. These are explicitly operator-recorded, not claimed autonomous discoveries by ICARUS.

The new procedure differentiates owner-stated, observed, verified and hypothetical knowledge. It encourages updating a matching skill when a tested procedure improves, rather than creating duplicate skills. No new lesson is required when a turn supplies nothing useful. Failed saves must be reported accurately.

## Preservation and scope

488 original protected files matched their pre-repair hashes: identity, governance, credentials, original skill content/resources and inherited records. Two native skill activity files changed as expected when Hermes created/loaded the new skill: .curator_ledger.jsonl and .usage.json. The only existing configuration changes were the memory allowance and the three learning-hook entries. Existing governance hooks, provider/model, permissions and disabled background model review were preserved.

Inherited Luna/Sol/Prime snapshots remain the 7 October source retrieval. They are historical evidence. New ICARUS knowledge grows in his own native memory, skills and lesson journal. This repair does not synchronize cloud sources or silently rewrite ancestor history.

Daily bookkeeping happens during active ICARUS chats/tasks. It does not start research, spend tokens on unattended background reviews, or manufacture activity on idle days. The hook keeps transcripts and raw tool output out of the activity journal; explicit lesson saves still require avoiding sensitive content. Its credential-pattern check is a bounded guard, not a guarantee that all possible secrets are detected.

The Android phone and DSH Tether mobile installation were not changed. The Python profile hooks in this patch target desktop Hermes and must not be presented as Android deployment. Matching phone-native learning integration and device verification remain outstanding.

## Evidence

- learning-behaviour-tests.txt: eight passing contracts covering per-turn reminders, preservation of private conversation text, worker/unknown-caller rejection, successful-write filtering, deduplication, fresh-process persistence, invalid/credential-bearing records and incomplete turns/records.
- learning-native-test-evidence.json: installed Hermes native memory write and fresh-store retrieval, native skill creation/loading, actual source file access, and the production shell-hook subprocess runner recording a real native memory tool result in an isolated profile.
- learning-install-evidence.json: live desktop file readback, native skill loading, memory retrieval and preserved-file hashes. The delivered hook source matches the installed source.

The first test attempt hit the Windows sandbox's temporary-folder permissions; tests were relocated into workspace scratch space. Installed-runtime checks required the runtime's own Python and normal host shell visibility. An initial preservation check included skill audit/usage metadata, which native creation legitimately updates; checks were corrected to preserve original content and report metadata separately. No automatic approval rejection occurred.

## Activation and exact remaining blockers

The installed desktop source registers profile hooks when it constructs a new Hermes agent. Start a new ICARUS chat for the patched configuration; an already cached agent has not been proven to reload it. No app or active session was forcibly restarted.

No live primary-model learning/retrieval turn was performed. Isolated native tests prove the plumbing and persistence; they do not prove that a live model will always follow the reminder. A verified zero-cost live inference route and an independent/owner check are still needed for that final acceptance. No additional provider call was made under an unverified cost assumption. The phone also needs its own native patch and physical-device test.

The next live acceptance should use a nonsensitive new fact: confirm its actual native save, start a fresh ICARUS session, confirm accurate retrieval, and inspect the daily journal. Check a tested reusable procedure separately for skill updates. A statement by ICARUS alone is insufficient evidence.
