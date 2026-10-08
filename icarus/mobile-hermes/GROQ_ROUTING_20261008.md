# Groq execution route amendment — 8 October 2026

**Owner directive:** "Use groq." This supersedes the earlier CODEX executor request for this Icarus Mobile Hermes-donor build stage.

- **Requested executor:** GROQ model `openai/gpt-oss-120b` (prior Icarus worker-pool stage #75/#76 reports actual Groq-authored source).
- **Actual present status:** `ROUTED_ONLY / GROQ NOT ACCEPTED`. No model request, authenticated claim, or source/compile evidence from Groq for THIS Android build.
- **Task ticket:** https://github.com/the1mburke-blip/Teamchat/issues/90 updated from CODEX to GROQ.
- **Stage PR:** https://github.com/the1mburke-blip/Teamchat/pull/89 (this is only the contract staging source).
- **Authentication finding:** Read-only 2026-10-08 Composio discovery returned GroqCloud `GROQCLOUD_GROQ_CREATE_CHAT_COMPLETION` as an available action but `groqcloud.has_active_connection=false` in this chat. Therefore this connector cannot legitimately invoke Groq now. No connection or paid service was created.
- **Alternative existing execution route:** inspect the actual previously-authorized Groq worker invocation responsible for #76 before using it. A GH Issue does not invoke a worker. Verify a fresh invocation identity/response and strict €0 pricing/call count BEFORE model work. Do NOT substitute GPT/Codex/ChatGPT.
- **Preflight monetary limit:** €0 additional; no paid fallbacks. **Allowance:** current ChatGPT meter unknown; Groq call budget target initial 1–2 bounded calls, then re-evaluate. No Groq calls spent by this amendment.
- **Owner involvement:** zero routine work. A new GroqCloud connection would require owner authorization, not implicit consent.
- **Protected:** main, donor upstream, installed Hermes phone APK, signed devices, production systems, keys and Google/Apps Script/Composio production.
- **References physically read:** Immutable Rules and Michael Operations Kernel skill bodies, Teamchat OPERATING_RULES.md, TRAINING_MATRIX.md, FREE_CHAIRS.md, issue #75, PR #76, issue #90, donor source, Icarus constitutional identity files, stage spec.
- **Mandatory seed training quote** (TRAINING_MATRIX.md, HV-EXP-001): "A strong model without the required read/write/verification capability is the wrong execution chair. Capability-gate the entire route before spending execution attempts." This prevents fabricating an executor handoff and wasting allowance.
- **Executor acceptance gate:** Groq must produce an authenticated job/task response with exact requested Icarus Android spec, and bounded reproducible code change; independent runner should test and reread artifact before reporting PASS at the permitted scope. No worker self-PASS.
- **Implementation directive once invocation verified:** Preserve Hermes Android as one standalone body, replace user-facing branding with Icarus and EXACT approved preproduction 2026-10-07 logo (if asset bytes available), read canonical inherited memory/identity and enforce Icarus constitution above model/tool pathways. Stage source only in isolated branch, never ship bypassable prompt-only governance. Use the full BUILD_STAGE.md acceptance contract.
