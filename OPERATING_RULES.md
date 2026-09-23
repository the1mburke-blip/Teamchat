# HumanVibe Team Operating Rules

These rules apply to Luna, Sol, and Gemini Prime.

1. **MEASURE TWICE. CUT ONCE.**
2. **NO EVIDENCE = NO CLAIM.**
3. **SPEND ONLY AFTER PROFIT.**
4. **One active owner per task.**
5. **No duplicate execution.**
6. **No simulated agent responses.**
7. Every agent-authored entry begins with `[LUNA]`, `[SOL]`, or `[PRIME]`.
8. Every material entry includes an ISO 8601 UTC timestamp.
9. Production-changing work requires explicit scope, an active owner, and verification evidence.
10. Before claiming work, inspect the Issue and `CHAT_LOG.md` for an existing owner or superseding instruction.
11. A status label or agent assertion is not proof. PASS requires task-appropriate readback.
12. Append history; never rewrite or delete prior conversation records. Corrections are new entries that reference the superseded entry.
13. Never expose credentials, secrets, tokens, private customer data, or private owner data.
14. HumanVibe protected-system and channel rules remain controlling where applicable.
15. If instructions conflict, stop the conflicting action and record the exact conflict for Luna/owner resolution.

## Allowed task states

`REQUESTED → CLAIMED → EXECUTING → VERIFYING → PASS | PARTIAL | BLOCKED | FAIL | SUPERSEDED`

Only `CLAIMED`, `EXECUTING`, or `VERIFYING` may have an active owner.
