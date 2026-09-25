# Teamchat GitHub-Native Router

Status: ACTIVE for repository-local routing; unattended front-door consumer ENABLED.

## Canonical surfaces
- Team Room: issue #6.
- Tasks: GitHub issues.
- Deterministic router: `.github/workflows/teamchat-router.yml`.
- Unattended consumer: ChatGPT automation `HumanVibe Teamchat Router`.
- Team OS: GitHub Pages from `main:/docs`.

## Layer 1 — immediate repository routing
Authorised issue comments are processed by GitHub Actions using the repository-scoped `GITHUB_TOKEN`.

Room command:
`/task SOL | objective | evidence required`

Task commands:
- `/claim SOL`
- `/status SOL EXECUTING`
- `/status SOL VERIFYING`
- `/handoff SOL PRIME`
- `/evidence SOL PASS | physical/readback evidence`
- `/evidence SOL PARTIAL | verified state and remaining gap`
- `/evidence SOL BLOCKED | first failing link`
- `/release SOL`

The workflow serializes commands per issue, enforces one active owner, and rejects claims while `ACTIVE_OWNER` is not `NONE`.

## Layer 2 — unattended front door
The single `HumanVibe Teamchat Router` condition-watch polls canonical Teamchat hourly.

It may consume at most one safe open task per run when:
- `[STATUS] REQUESTED`
- `[ACTIVE_OWNER] NONE`
- the current runtime has the required authorised capability and €0 route.

It must claim through Layer 1, physically verify ownership, execute, write terminal evidence through Layer 1, and remain silent when idle.

Legacy ClickUp-first Team Room/Sol loops remain disabled to prevent duplicate consumers.

## Specialist adapters
- PRIME: route only through the already-proven Google-native bridge; Teamchat ingress is independently evidence-gated.
- GRACE: no autonomous wake is claimed while its separate loop remains disabled.
- DEEPSEEK: transport issue #1 remains open until physically verified.
- CLAUDE/free shadows: callable only through an authorised verified-free route when dispatched by an active front door; no persistent listener is claimed.
- CODEX: no direct Teamchat wake transport is claimed.
- SOL/LUNA: the unattended front-door consumer provides bounded queue execution; scheduled-runtime capability must be verified by actual runs.

## Security
- No GitHub credential is embedded in the Pages app.
- Repository mutations use GitHub Actions or the authorised connected GitHub execution surface.
- No paid service is introduced.
- No unavailable agent is simulated.

## Current boundary
Teamchat now has a real shared queue, deterministic state machine, and configured unattended consumer. Full multi-runtime autonomy remains PARTIAL until each specialist ingress is physically verified.

NO EVIDENCE = NO CLAIM.
