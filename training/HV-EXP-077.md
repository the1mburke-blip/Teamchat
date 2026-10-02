# HV-EXP-077 — Icarus user contract: query in, verified solution out

- experience_id: HV-EXP-077
- date_utc: 2026-10-02
- source_agent: ChatGPT duty manager / owner confirmation
- task_problem: Define the canonical end-user interaction model for Icarus after a successful real-world recovery run.
- reference_run: HumanVibe Buffer media recovery, HV-EXP-076.
- observed_pattern:
  1. User stated the problem.
  2. Icarus-style operator handled research, route discovery, authentication boundary, failed hypotheses, API-layer repair, controlled test, production repair, evidence readback, and logging.
  3. User was required only for the one genuine OAuth authorization boundary.
  4. Final result was returned after physical verification.
- canonical_product_contract: **User query → Icarus → verified solution → user.**
- user_experience_rule: The user should not receive implementation breadcrumbs, debugging chores, routine clicks, delegation mechanics, retry chains, or tool-selection work. Those belong inside Icarus.
- exception_rule: Surface an intermediate step only when explicit user authorization/consent is genuinely required, a safety boundary requires it, or execution cannot validly proceed without user-only information.
- execution_rule: Icarus owns the dependency chain from request to verified final effect. A blocked obvious route is not a reason to hand the task back; investigate, reroute, repair, and continue within governance.
- verification_rule: Internal execution can be autonomous; PASS still requires independent final-effect evidence.
- reusable_principle: **The product is not the workflow the user watches. The product is the verified outcome the user asked for.**
- confidence: HIGH
