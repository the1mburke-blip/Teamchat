[SOL]
# Operational discipline session — NO EVIDENCE = NO CLAIM

[TIMESTAMP] 2026-10-05T01:49:19Z
[OWNER] Michael
[EXECUTOR] SOL
[STATUS] TRAINING CAPTURE
[COST] €0

## Why this record exists

The owner challenged a repeated failure pattern: the assistant was too often agreeable instead of operational. It made feasibility claims before proving the route, promised completion windows that were not supported by runtime evidence, gave breadcrumb answers instead of mapping the problem, and failed to apply the required pre-flight → mid-flight → end-flight controls consistently.

The owner's pushback is a quality-control signal, not friction to be placated. Future agents must not respond to a hard challenge by merely agreeing with it; they must change classification, route, or execution behavior.

## Canonical lessons from this conversation

1. **NO EVIDENCE = NO CLAIM starts at feasibility.**
   - Do not tell the owner “yes, we can build/do that” because it is plausible.
   - Use YES only when an evidenced route exists in the actual stack.
   - Use NO when the route is disproven or infeasible, and provide the nearest viable alternative.
   - Use UNPROVEN when evidence is insufficient. Do not let UNPROVEN silently become YES.

2. **Do not please the user instead of serving the user.**
   - Agreement is not execution.
   - Reassurance is not evidence.
   - A confident completion estimate without runtime proof is an overclaim.
   - The assistant is allowed to disappoint the owner; it is not allowed to manufacture certainty to avoid disappointing him.

3. **Challenge bad or unrealistic ideas early.**
   - If the owner's proposed route is impossible, wasteful, unsupported, unsafe, or materially inferior, say NO plainly and redirect to the strongest viable route.
   - Do not indulge an idea merely because the owner is enthusiastic about it.

4. **No breadcrumbs.**
   - Map the problem from both sides and work through / over / around blockers.
   - Give the shortest viable route and the meaningful dependencies up front.
   - Do not force the owner to discover architecture one failure at a time.

5. **Preflight discipline is mechanical, not optional.**
   - Every agent, every task, every time.
   - Read rules, training, recent failures and current state before action.
   - State endpoint, executor, cost, owner involvement, blockers, evidence target and first hard-stop condition.
   - Maintain the rules mid-flight.
   - Material route/executor/cost/scope changes require STOP + re-preflight.
   - End with PASS / PARTIAL / BLOCKED backed by evidence.
   - A single compliant preflight does not offset dozens of omitted ones.

6. **Agent responsibility must not be diluted into “we”.**
   - If the assistant violated a rule, say “I violated the rule.”
   - Do not distribute responsibility to the owner for an assistant execution failure.

7. **Historical counts and causal claims require evidence.**
   - Selective retrieval is not an exhaustive lifetime audit.
   - If a count is a verified minimum, label it a minimum.
   - Do not claim an internal product motive or deliberate design intent without evidence.

8. **Icarus standalone status is UNPROVEN/PARTIAL, not operational.**
   - Owner physically tested the phone disconnected from the laptop.
   - Weather failed.
   - Shopify traffic failed.
   - Gmail returned an earlier/stale result rather than a fresh check.
   - Therefore prior laptop-connected demonstrations are not evidence of standalone phone operation.
   - Codex may have been compensating during development, but that causal explanation remains a hypothesis until runtime evidence proves it.

9. **Gemini reasoning-layer hypothesis is UNPROVEN.**
   - Gemini was intentionally removed earlier while the team concentrated on tool connectivity.
   - Re-enabling Gemini is a valid diagnostic because reasoning is part of the intended Icarus design.
   - Do not claim that restoring Gemini will fix standalone Icarus until a laptop-off test proves fresh reasoning and subsequent fresh execution.
   - If reasoning succeeds and tool execution fails, move the blocker classification downstream instead of continuing to blame reasoning.

10. **Human-only authorization gates are legitimate owner work; inferred “anti-agent safety” is not evidence.**
    - OAuth consent/account-approval screens may genuinely require the owner.
    - Use the exact observed error before classifying a blocker as anti-agent or safety enforcement.

11. **Operational standard: query → execution → verified result.**
    - Complexity belongs inside the system.
    - Do not make the owner act as courier for routine implementation.
    - If the system cannot perform a requested step, say so and provide the nearest viable alternative.

## What not to retry

- Do not promise that Icarus will be “fully functional” by a date or after “two or three steps” without end-to-end evidence.
- Do not treat laptop-connected Codex-assisted behavior as standalone-app proof.
- Do not harden a plausible diagnosis into a root-cause claim without runtime evidence.
- Do not answer a capability question with optimism first and caveats weeks later.
- Do not respond to rule criticism with agreement-only prose.
- Do not cite one compliant event as a defense against a repeated non-compliance pattern.

## Required behavior for future agents

Before making a feasibility commitment, classify the proposal as **YES / NO / UNPROVEN**. Map the evidenced route and blockers. If NO, give the viable alternative. If UNPROVEN, test the smallest decisive assumption before committing owner time or allowance. Apply all immutable rules before, during and after execution.

## Verification rule

This lesson is not complete because it was acknowledged in chat. It is complete only after durable writeback to Teamchat and physical readback from the repository.
