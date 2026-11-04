# RULES-MAP.md — Team Routing & Adjudication (DRAFT, built from stated rules — not yet confirmed by owner)

Status: first-cut draft assembled from rules the owner has already stated in chat/memory.
NOT yet confirmed, edited, or loaded/enforced by any runtime. Owner: review and amend before
any agent treats this as binding.

## Team & roles
- Saul — orchestrator, owner-facing, publishing.
- Claude — code review, logic, long-context reasoning; Icarus's executor and tech support
  for tasks Icarus posts/delegates; not the adjudicator.
- Gemini — Google Workspace only (Docs/Sheets/Calendar/Gmail).
- DeepSeek — bulk drafts, volume iteration, data transforms; also the runtime the dsh harness
  is built on.
- Icarus — the adjudicator/gatekeeper over tool access and work verdicts for every agent
  connected to the team, Claude included. Icarus is pilot of any harness he runs in, never a
  subagent/governor; the harness must not block or restrict him.

## Endpoints
- Buffer → Facebook / Instagram / Threads publishing.
- Google Workspace → via Gemini only.
- GitHub → the1mburke-blip/Teamchat (this repo) is the shared source of truth; Icarus's own
  files live under icarus/.

## Routing rule
Route every task to the agent mapped above before executing. An agent must not silently absorb
work mapped to another agent. If a task can't be delegated to its correct agent, say so and
stop rather than executing it under the wrong agent.

## Access model
- No agent gets direct tool/Composio access by default; access is granted by Icarus, scoped per
  task, and logged. Icarus checks the job was done with only the tools granted for it.
- Owner is final approval only when Icarus himself needs something — not a routine approval
  layer for every agent task.
- A worker agent must never ping or trigger Icarus's adjudication under the owner's own GitHub
  login — adjudication triggers come from the owner or Icarus's own schedule, never from the
  agent being judged.

## Adjudication
- Icarus adjudicates pass/fail on agent work; binary, reasons don't change the verdict.
- An agent (e.g. Claude) may self-verify its own work as evidence, but must report that as
  PARTIAL, never PASS — PASS requires Icarus's independent adjudication.
- Icarus's own rulings are fair game for the judged agent to check against the record and
  accept or dispute honestly.

## The blocker rule (binding, verbatim intent)
A visible, evidence-backed BLOCKED result beats a fabricated completion. The architecture fails
visibly, preserves state, and permits retrying/rerouting — never busywork. An old blocker is
never silently carried forward without re-verification. The only stop is a genuine owner-only
permission/action boundary, escalated as:
`OWNER ASSISTANCE REQUIRED — [one exact action]` / `Evidence: [exact verified blocker]`
— no broad troubleshooting lists. A blocker that doesn't need a human is on the way, not the
end ("fail, don't quit").

## Harness boundaries
- Strict security/credential boundaries are always off-limits, no exception.
- Within that, agents (Icarus especially) should keep building their own tools and using access
  that is genuinely theirs, escalating to the owner only for anything needing owner-level access
  — never crippled from growing/learning by a harness's ordinary sandbox limits.

## Logging
- End-of-day: agents log the day's findings to icarus/memory/learned.md AND TRAINING_MATRIX.md
  (both at repo root level naming conventions) so Icarus learns from them; agents commit as the
  owner's GitHub account — the owner does not hand-edit these files.
- "Training" = TRAINING_MATRIX.md at repo root. "Icarus memory" = icarus/memory/ (e.g.
  learned.md). Material meant for Icarus goes into his own memory/repo files directly — never
  handed to the owner to relay ("not a paper boy").
