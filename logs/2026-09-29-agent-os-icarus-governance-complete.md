# 2026-09-29 — Agent OS / Icarus / governance session

## Durable outcomes

1. Phone agent-OS research compared OpenClaw, Open WebUI, Letta, AnythingLLM, LibreChat, Dify, Agent Zero and related options under the €0/current-plan constraint.
2. The governing lesson is PRIOR ART FIRST: define the endpoint, search broadly for existing solutions, compare the strongest candidates against current constraints, and build only the residual gap.
3. The first application to Icarus was wrong because the research anchored on OpenClaw instead of searching for an already-developed Icarus.
4. Corrected Icarus prior-art search surfaced Hermes Agent + Hermes Studio + Hermes Android as the closest complete analogue, with Open Jarvis and AIOPE as additional strong matches; idem was noted as a paid commercial analogue.
5. Conclusion: ground-up Icarus agent-OS development is not justified without a verified residual gap. A retained option is to keep Icarus as branding/control surface over proven infrastructure.
6. Icarus immutable-rule audit: 12 rules applied, 7 were followed, 5 were missed.
7. Missed rules: PRIOR ART FIRST; PREFLIGHT FIRST; correct routing; allowance discipline; material change requires re-preflight.
8. Training entry HV-EXP-057 records the 7/12 audit.
9. The first interpretation of "weigh the rules" as CRITICAL/HIGH/MEDIUM/LOW scoring was incorrect.
10. Controlling correction: review and apply all 12 rules to the task before execution, maintain them during execution, audit actual compliance at completion, and then create a separate compliance-tracker task.
11. HV-EXP-059 is the controlling training entry for that correction. HV-EXP-058 remains historical evidence of the misunderstanding.
12. A separate compliance tracker for the governance correction exists as Issue #28.

## Evidence already created
- Icarus retained architecture option: commit bc3d777b53e029d1c1b71eaef11a1845b576fe0f
- HV-EXP-057: commit 82946b4adab3e34f568dbfea768eb587778f0f7f
- OPERATING_RULES contextual compliance correction: commit 16532819354e5730ff2a0a5a697017a53211e5d2
- HANDOFF_PROTOCOL contextual compliance correction: commit 97645d3b70e4f9e29d3dc0e912c183c5cd52d600
- HV-EXP-059: commit 21743930ed32de2c88f5ac8e63b25e70f684a4d6
- Separate compliance tracker: GitHub Issue #28

## Controlling workflow
Before: read history/training/rules; define endpoint and evidence; review all 12 rules against the exact task; run PRIOR ART FIRST; map the shortest valid route; verify that mapped route complies.

During: keep all applicable rules active; re-check them on failures, retries, escalations, route/tool/executor/cost/scope changes or new blockers; material change means stop and re-preflight.

Completion: physically verify the endpoint; audit the completed run against all 12 rules; log reusable learning; create and close a separate compliance-tracker task.

Icarus is the canonical proof case for why these controls exist.
