# CHILD_POOL_V01.md  

## Scope  
Define the **Child Pool** for Teamchat Issue #75. The pool is a leaf‑only ghost/sub‑agent collection governed by the repository‑stage leaf ghost/sub‑agent pool. No live provider dispatcher is installed; all execution is performed by agents, with Icarus acting as the judge.

## Architecture  

| Component | Description |
|-----------|-------------|
| **Governance ID** | `<parentTaskId>:child:<childId>` – resolves to the parent task for original objective/Skills binding via the GovernanceKernel’s two strict lookup changes. |
| **Child Spec** | Binds: <br>• Ghost identity <br>• `parentTaskId` <br>• `childId` <br>• Sub‑objective hash <br>• `depth=1` <br>• Exact non‑empty subset of `analysis.read`, `research.read`, `code.draft`, `review.read` <br>• Route from `GROQ_FREE`, `OPENROUTER_FREE`, `GEMINI_FREE`, `CEREBRAS_FREE` <br>• `budgetEUR=0` <br>• `write=false` <br>• Binding hash <br>• Evidence contract |
| **State Sheets** | `CHILD_BINDINGS` – holds bindings; `CHILD_RESULTS` – stores durable results/evidence. No changes to `TASK_QUEUE` schema. |
| **Dispatcher Callback** | Trusted‑host rail only; no arbitrary JavaScript sandbox. |
| **Executor Identity** | Cannot self‑PASS; the existing verifier seam remains authoritative. |
| **Replay Protection** | Duplicate effects denied by the permit lifecycle combined with durable binding/result rules. |

## v0.1 Hard Denials  

The version 0.1 policy explicitly forbids:  

- Nested delegation or further child creation.  
- User clarification loops.  
- Shared‑memory writes or any mutation of external state.  
- Scheduling, cron, or background jobs.  
- Verifier authority overrides.  
- Execution of Google/Composio tools, any capability/route/cost widening.  
- Dynamic MCP, live ghost‑provider execution, or credential‑based actions.  

All such requests must be rejected with a deterministic “DENIED” response.

## Acceptance Evidence  

- **Deterministic Test Suite**: `node --test runtime/google-plugin/google-bundle/governance/skills/childpool` → **25 passed, 0 failed**.  
- **Individual ChildPool A‑H Tests**: **8/8 passed**.  
- No production deployment, no credential usage, and zero EUR cost incurred.  
- Results and evidence are durably stored in `CHILD_RESULTS` and read back before the governance run returns, satisfying the evidence contract.

## Boundaries & Provenance  

- **Repository Stage**: Leaf ghost/sub‑agent pool only; no live provider dispatcher.  
- **Base Commit**: PR #74 head `22fce7af2138e275ded488c5150dad99e41adddb`.  
- **Source Author**: Groq GPT‑OSS‑120B (proposed by Michael).  
- **Status**: **VERIFYING** – pending independent reviewer and CI/build read‑back. No claim of PASS is made.

---  

SOURCE_AUTHOR: GROQ_GPT_OSS_120B  
SELF_PASS: DENIED