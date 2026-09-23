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
11. **History-first execution.** Before the first execution attempt on any non-trivial or previously attempted task, retrieve the agent's own relevant logs plus available prior-team attempts. Extract: `attempts_made`, `what_failed`, `why_it_failed`, `what_not_to_retry`, and any verified recovery/evidence. Do not enter EXECUTING blind when relevant history exists.
12. **Shared training before execution.** `TRAINING_MATRIX.md` is HumanVibe's model-independent experience pool. Before EXECUTING a non-trivial task, every chair must retrieve the relevant entries whether or not that model has native memory. Model memory may supplement the matrix; it never substitutes for it.
13. **Training proof at job start.** Before EXECUTING, the active chair must record `TRAINING_REVIEW: PASS`, quote one verbatim line from `TRAINING_MATRIX.md` that is relevant to the task, identify its lesson/heading, and state in one sentence why it applies. A generic or unrelated quote does not satisfy the gate.
14. **Allowance accounting at job start and close.** Before EXECUTING, record the model/chair and estimated token/request/allowance cost using the best available unit. At terminal status, record actual usage when measurable; otherwise record a clearly labelled estimate. Material variance requires stop/re-preflight.
15. **Failure capture before retry.** Every failed attempt must be durably recorded before another attempt with: failure signature/evidence, what changed in the diagnosis, the next materially different approach, and what must not be retried. Reusable lessons must also be added to `TRAINING_MATRIX.md`. An identical retry with no new evidence or changed approach is prohibited.
16. **Cross-training.** A verified lesson learned by one chair is available to every later chair. Knowledge belongs to HumanVibe, not to the model that discovered it.
17. A status label or agent assertion is not proof. PASS requires task-appropriate readback.
18. Append history; never rewrite or delete prior conversation records. Corrections are new entries that reference the superseded entry.
19. Never expose credentials, secrets, tokens, private customer data, or private owner data.
20. HumanVibe protected-system and channel rules remain controlling where applicable.
21. If instructions conflict, stop the conflicting action and record the exact conflict for Luna/owner resolution.
22. Roster membership does not grant standing authority. The active-owner rule controls execution regardless of agent identity.

## Allowed task states

`REQUESTED → CLAIMED → EXECUTING → VERIFYING → PASS | PARTIAL | BLOCKED | FAIL | SUPERSEDED`

Only `CLAIMED`, `EXECUTING`, or `VERIFYING` may have an active owner.
