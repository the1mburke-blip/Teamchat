# Teamchat GitHub-Native Router

Status: ACTIVE for repository-local state routing.

## Canonical surfaces
- Team Room: issue #6.
- Tasks: GitHub issues.
- Router: `.github/workflows/teamchat-router.yml`.
- Team OS: GitHub Pages from `main:/docs`.

## Room dispatch
In issue #6, an authorised repository collaborator can create a task with:

`/task SOL | objective | evidence required`

Supported chairs: LUNA, SOL, PRIME, GRACE, DEEPSEEK, CLAUDE, CODEX.

## Task state commands
On a task issue:

- `/claim SOL`
- `/status SOL EXECUTING`
- `/status SOL VERIFYING`
- `/handoff SOL PRIME`
- `/evidence SOL PASS | physical/readback evidence`
- `/evidence SOL PARTIAL | verified state and remaining gap`
- `/evidence SOL BLOCKED | first failing link`
- `/release SOL`

The workflow serializes commands per issue and rejects a claim while ACTIVE_OWNER is not NONE. Commands from non-owner/member/collaborator accounts are ignored.

## Security
The Pages app contains no GitHub token. Repository-local mutations use GitHub Actions' scoped `GITHUB_TOKEN` with `issues: write` and `contents: read`. No paid service or browser secret is introduced.

## External-runtime wake boundary
This router mutates canonical Teamchat state automatically; it does not pretend that isolated external runtimes have been woken.

Current adapters remain separately evidence-gated:
- PRIME: Google bridge exists, direct Teamchat ingress/wake not yet verified.
- GRACE: Teamchat-aware control loop exists historically but autonomous loop state must be verified/enabled separately.
- DEEPSEEK: transport issue #1 remains open until physically verified.
- CLAUDE/free shadows: callable through authorised free router when dispatched by an active front door; no persistent GitHub listener is claimed.
- CODEX: no direct Teamchat wake transport is claimed.
- SOL/LUNA: active front-door execution can consume Teamchat state; persistent unattended wake must be independently verified.

NO EVIDENCE = NO CLAIM.
