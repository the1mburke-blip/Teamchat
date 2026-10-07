# ICARUS Snapshot — Hermes + Icarus Core GitHub Oversight

**Date:** 2026-10-07  
**Owner:** Michael  
**Status:** DELEGATED / REQUESTED — worker execution not yet verified  
**Cost:** €0  
**Owner action:** none

## Decision captured

Target architecture:

```text
GitHub task / issue
  -> Hermes runtime / orchestrator
  -> Icarus Core governance gate
     - signed ExecutionPermit
     - capability / route / target binding
     - replay protection
     - append-only evidence
     - executor cannot self-award PASS
  -> delegated executor/tool
  -> evidence
  -> independent adjudication
  -> GitHub status/comment
```

Hermes is being evaluated as the persistent execution/orchestration layer and future GitHub task overseer. Icarus Core remains the authority above Hermes; Hermes must not be able to bypass permits, capability gates, replay protection, evidence capture, or independent adjudication.

## Verified repository state at snapshot

- PR #63 is the current Icarus governance-kernel candidate.
- Hermes feasibility work exists as parent Issue #65 with bounded research chunks #66–#70.
- Teamchat Router on Team Room #6 was used for the implementation delegation.
- Router created Issue #71 at **2026-10-07T12:08:45Z** with:
  - `[TO] [CODEX]`
  - `[STATUS] REQUESTED`
  - `[ACTIVE_OWNER] NONE`
- Therefore the task is physically delegated in the repository, but no worker claim/start/completion is claimed at this snapshot.

## Delegated implementation target — Issue #71

Read #65–#70 and PR #63. If the evidence supports adoption, implement the **smallest reversible Hermes + Icarus Core integration canary** on an isolated branch/PR so Hermes can oversee GitHub tasks through the existing Teamchat task surface.

Required fixture flow:

```text
GitHub task
  -> Hermes sees/claims
  -> Icarus permit
  -> delegated execution fixture
  -> evidence
  -> VERIFYING / independent verdict path
  -> GitHub status/comment
```

Required denial evidence:

- unpermitted execution denied;
- replayed permit denied;
- route/target mutation denied;
- executor self-PASS denied.

## Protected boundaries

Do not:

- merge or deploy the canary;
- replace current Icarus Mobile or Google bundle;
- bypass PR #63 governance;
- mutate production systems;
- introduce paid services, credits, trials, or API spend.

## Acceptance evidence for the delegated worker

- isolated branch, commit and PR;
- exact files changed;
- deterministic/adversarial tests;
- fixture GitHub task trace;
- denial proofs above;
- no production deployment;
- €0;
- executor reports VERIFYING/PARTIAL/BLOCKED, never PASS;
- independent adjudication remains separate.

## Evidence links

- Parent Hermes feasibility audit: https://github.com/the1mburke-blip/Teamchat/issues/65
- Research chunks: #66, #67, #68, #69, #70
- Icarus governance kernel candidate: https://github.com/the1mburke-blip/Teamchat/pull/63
- Implementation delegation: https://github.com/the1mburke-blip/Teamchat/issues/71
- Router evidence: https://github.com/the1mburke-blip/Teamchat/issues/6#issuecomment-6037583332

## Attribution

Proposed by **Michael**.  
Delegation executed by **ChatGPT through the existing Teamchat Router**.  
Snapshot recorded in the repository on **7 October 2026**.  
