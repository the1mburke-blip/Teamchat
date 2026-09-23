# HumanVibe Team Operating Rules

These rules apply to Luna, Sol, Gemini Prime, Grace, and DeepSeek.

1. **MEASURE TWICE. CUT ONCE.**
2. **NO EVIDENCE = NO CLAIM.**
3. **SPEND ONLY AFTER PROFIT.**
4. **One active owner per task.**
5. **No duplicate execution.**
6. **No simulated agent responses.**
7. Every agent-authored entry begins with `[LUNA]`, `[SOL]`, `[PRIME]`, `[GRACE]`, or `[DEEPSEEK]`.
8. Every material entry includes an ISO 8601 UTC timestamp.
9. Production-changing work requires explicit scope, an active owner, and verification evidence.
10. Before claiming work, inspect the Issue and `CHAT_LOG.md` for an existing owner or superseding instruction.
11. **History-first execution.** Before the first execution attempt on every executable task, retrieve the agent's own relevant logs plus available prior-team attempts. Extract: `attempts_made`, `what_failed`, `why_it_failed`, `what_not_to_retry`, and any verified recovery/evidence. Do not enter EXECUTING blind when relevant history exists.
12. **Shared training before execution.** `TRAINING_MATRIX.md` is HumanVibe's model-independent experience pool. Before EXECUTING every executable task, every chair must retrieve the relevant entries whether or not that model has native memory. Model memory may supplement the matrix; it never substitutes for it.
13. **No trivial-task exemption.** Every executable task passes the same job-start training/history/allowance gate. The executing chair cannot waive, downgrade, or self-classify around it.
14. **Training proof at job start.** Before EXECUTING, the active chair must record `TRAINING_REVIEW: PASS`, quote one verbatim line from `TRAINING_MATRIX.md` that is relevant to the task, identify its lesson/heading, and state in one sentence why it applies. A generic or unrelated quote does not satisfy the gate.
15. **Allowance accounting at job start and close.** Before EXECUTING, record the model/chair and estimated token/request/allowance cost using the best available unit. At terminal status, record actual usage when measurable; otherwise record a clearly labelled estimate. Material variance requires stop/re-preflight.
16. **Failure capture before retry.** Every failed attempt must be durably recorded before another attempt with: failure signature/evidence, what changed in the diagnosis, the next materially different approach, and what must not be retried. Reusable lessons must also be added to `TRAINING_MATRIX.md`. An identical retry with no new evidence or changed approach is prohibited.
17. **Cross-training.** A verified lesson learned by one chair is available to every later chair. Knowledge belongs to HumanVibe, not to the model that discovered it.
18. A status label or agent assertion is not proof. PASS requires task-appropriate readback.
19. Append history; never rewrite or delete prior conversation records. Corrections are new entries that reference the superseded entry.
20. Never expose credentials, secrets, tokens, private customer data, or private owner data.
21. HumanVibe protected-system and channel rules remain controlling where applicable.
22. If instructions conflict, stop the conflicting action and record the exact conflict for Luna/owner resolution.
23. Roster membership does not grant standing authority. The active-owner rule controls execution regardless of agent identity.

24. **OpenRouter free-shadow first.** For every eligible task, route first to the matching `(or)` chair in `FREE_CHAIRS.md` before invoking its premium counterpart. Free-shadow use is skipped only for a HUMAN_ELEMENT requirement, a capability unavailable to that shadow, or data that must not be sent to a free endpoint.
25. **Seven-attempt free learning budget.** Each `(or)` chair may make up to 7 educated attempts on the same task. Each failure must be captured and must materially change the next approach. From a nominal 10-call/day chair allocation, calls 8–10 are protected reserve.
26. **Vertical escalation.** After 7 failed educated attempts, the `(or)` chair hands the complete learning packet to its named premium counterpart: `Luna(or) → Luna`, `Sol(or) → Sol`, `Gemini(or) → Gemini`, `DeepSeek(or) → DeepSeek`, `Claude(or) → Claude`. Premium chairs inherit the same training/history/failure-capture gates and a maximum 7-attempt learning cycle before their normal higher-chair/OWNER escalation.
27. **Daily pool arithmetic.** OpenRouter Free is one shared 50-request/day account pool, not 50 requests per chair. Five shadow chairs × 7 task attempts = 35 maximum task attempts if all five are legitimately engaged, leaving 15 protected calls across the pool. Do not consume the reserve simply to keep grinding one task.
28. **Immediate OWNER route.** HUMAN_ELEMENT requirements route directly to OWNER. Hard capability/authentication blockers do not consume the remaining attempt budget.
29. **No paid fallback.** A free-shadow model must be verified as $0/`:free` before use. If its free endpoint disappears, mark that shadow unavailable and substitute only another verified-free model; never silently fall through to a paid OpenRouter model.

## Allowed task states

`REQUESTED → CLAIMED → EXECUTING → VERIFYING → PASS | PARTIAL | BLOCKED | FAIL | SUPERSEDED`

Only `CLAIMED`, `EXECUTING`, or `VERIFYING` may have an active owner.
