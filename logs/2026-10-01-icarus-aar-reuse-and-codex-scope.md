# Icarus AAR reuse decision — 2026-10-01

Status: RESEARCH COMPLETE / IMPLEMENTATION NOT YET STARTED

## Objective

Determine how much of the Agent Attestation Record (AAR) layer already exists publicly and can be reused immediately for Icarus, then bound the next Codex implementation scope to a maximum 5% allowance target.

## Governance / provenance

- Proposed by: Michael (OWNER)
- Research executed by: Saul / GPT-5.6 Sol
- Date: 2026-10-01
- Monetary spend: €0
- Production mutation during research: NONE
- Training review: PASS
- Training quote: "Knowledge belongs to HumanVibe, not to the model occupying the chair."
- Training source: TRAINING_MATRIX.md — Purpose
- Relevance: the AAR prior-art findings must be durable and reusable by the next executor rather than rediscovered with premium allowance.

## Current Icarus architectural boundary

Icarus remains the independent adjudicator: agents execute; Icarus judges. An executor does not self-certify PASS. Work enters VERIFYING, evidence is checked independently against the required endpoint, and only the adjudicator issues PASS / FAIL / UNCLEAR.

The 2026-09-29 prior-art decision remains valid. This entry sharpens it rather than superseding it: commodity attestation/proof infrastructure should be reused; Icarus should retain the independent judgment layer and framework-neutral adjudication API.

## Closest current AAR prior art

### 1. Frontier Infra — Agent Control Plane / AAR

Repository: `frontier-infra/agentcontrolplane`

Verified facts from live GitHub source:
- Public repository.
- MIT licensed.
- AAR spec version 0.02.
- Zero-dependency Node reference signer/verifier: `tools/aar.mjs`.
- Official conformance ladder:
  - L0: signed record.
  - L1: ground-truth + evidence commitment.
  - L2: structurally independent verifier (`verifier.id != subject`).
  - L3: tamper-evident history via prior chain and/or transparency-log commitment.
- Ed25519 signatures.
- did:web identity.
- Evidence commitments via SHA-256 over the canonical preimage.
- Signed valid and invalid fixtures plus tests.

Important limitation: the specification explicitly states that signatures prove provenance and inspectability; they do not make a dishonest verifier's verdict magically true.

### 2. TechMages Warlock — Python/FastAPI AAR implementation

Repository: `techmages-org/warlock`

Verified facts:
- Public repository.
- MIT licensed.
- Python >=3.11.
- FastAPI backend.
- Existing AAR package under `src/warlock/aar/`.
- Relevant reusable modules inspected:
  - `builder.py`
  - `signer.py`
  - `did.py`
  - `preimage.py`
  - `producer.py`
  - `store.py`
  - `api/aar.py`
  - `tests/test_aar.py`
- Uses the `rfc8785` library for canonical JSON.
- Uses Ed25519 through Python cryptography.
- Stores evidence preimages separately from portable records.
- Implements per-subject prior-hash chaining.
- Provides FastAPI endpoints to list/fetch AAR records, fetch DID JSON, and retrieve authorized evidence preimages.
- Tests tamper failure, evidence-hash recomputation, DID shape, prior chaining, and interoperability against the official AAR oracle.

Important adaptation requirement: at least one Warlock path records the verifier as the same subject / same-principal attestation. Icarus must preserve the stronger independent verifier boundary and target AAR L2, not copy that self-attestation behavior.

### 3. Frontier SDK audit package

Repository: `frontier-infra/frontier-sdk`
Package: `@frontier-infra/audit`

Verified facts:
- MIT licensed.
- Binds an external evidence packet to an AAR.
- Recomputes the evidence SHA-256 before verification.
- Stamps the exact verifier package version and policy/snapshot SHA-256.
- Requires `verifier.id != subject` for its L2 receipt path.
- Immediately verifies signed receipts after creation.
- Bundles the AAR reference verifier for offline verification.

This is useful prior art for binding Icarus's adjudication evidence packet to a signed receipt.

## Reuse estimate

Engineering estimate from inspected source, before comparing against the current local Icarus tree:

- Approximately 80–90% of the AAR proof/receipt layer already exists publicly and can be reused or adapted under MIT licenses.
- This percentage is an engineering estimate, not a physically verified integration measurement.

### Reuse immediately

- AAR record/schema: ~100%
- Ed25519 signing: ~100%
- signature verification: ~100%
- did:web/public-key document shape: ~100%
- RFC8785 canonicalization: ~100%
- SHA-256 evidence commitments: ~100%
- evidence-preimage custody pattern: ~100%
- record persistence pattern: ~100%
- prior hash-chain pattern: ~100%
- official fixtures and conformance tests: ~100%
- FastAPI AAR API surface: ~90% adaptable
- detached evidence receipt pattern: ~90% adaptable

### Keep as Icarus-owned logic

- What evidence is required for a specific task.
- How evidence is collected from GitHub, Shopify, files, APIs, or other endpoints.
- Whether the observed endpoint satisfies the task contract.
- PASS / FAIL / UNCLEAR adjudication.
- Policy / immutable-rule evaluation.
- Framework-neutral verifier API and connector adapters.

## L3 decision

Do not spend the first implementation pass on an external transparency log.

Reason:
- AAR v0.02 still lists transparency-log binding details among open questions.
- The `prior` hash chain provides an immediate tamper-evident history path.
- External transparency logging can be added later after the core L2 adjudication path is physically proven.

## 5% Codex execution boundary

Target allowance: maximum 5% Codex allowance.

Expected achievable endpoint with strict reuse-first scope:
- integrate/adapt the AAR components into the existing Icarus backend;
- Ed25519 key generation/signing/verification;
- RFC8785 canonicalization;
- AAR schema/record creation;
- evidence hashing and preimage storage;
- enforce `verifier.id != subject`;
- emit signed PASS / FAIL / UNCLEAR receipts;
- expose minimal FastAPI AAR endpoints;
- run official AAR fixture/conformance checks;
- tamper test must fail;
- add prior-hash chain;
- wire receipt emission to the existing Icarus `VERIFYING -> PASS|FAIL|UNCLEAR` state boundary.

### Exact PASS endpoint for that Codex run

Given one controlled test task and evidence:
1. executor submits a completion claim;
2. Icarus independently evaluates the supplied/collected evidence;
3. Icarus enters VERIFYING and issues PASS, FAIL, or UNCLEAR;
4. Icarus emits a signed AAR v0.02 receipt;
5. the official Frontier AAR reference verifier validates the receipt at L2;
6. modification of a signed field causes verification to fail;
7. the receipt is durably stored and linked into the prior-record hash chain.

### Explicitly out of scope for the 5% run

- L3 external transparency-log service.
- every external connector.
- UI polish.
- Android work.
- broad deployment infrastructure.
- rebuilding crypto or AAR mechanisms already available under MIT.
- sophisticated qualitative judging beyond the minimum controlled adjudication test.

## Execution guardrail

If Codex begins redesigning or rebuilding the AAR machinery instead of adapting the inspected MIT implementations, stop and re-preflight. The 5% budget is for integration and verification, not rediscovery.

## Sources physically inspected during this research

- `frontier-infra/agentcontrolplane`
  - `LICENSE`
  - `README.md`
  - `CONFORMANCE.md`
  - `CHANGELOG.md`
  - `specs/aar-agent-attestation-record.md`
  - `specs/fixtures/`
  - `tools/aar.mjs`
  - `test/aar.test.mjs`
- `frontier-infra/frontier-sdk`
  - `packages/typescript/audit/README.md`
  - `packages/typescript/audit/src/index.mjs`
  - `packages/typescript/audit/src/cli.mjs`
  - `packages/typescript/audit/package.json`
- `techmages-org/warlock`
  - `LICENSE`
  - `pyproject.toml`
  - `src/warlock/aar/builder.py`
  - `src/warlock/aar/signer.py`
  - `src/warlock/aar/did.py`
  - `src/warlock/aar/preimage.py`
  - `src/warlock/aar/producer.py`
  - `src/warlock/aar/store.py`
  - `src/warlock/api/aar.py`
  - `tests/test_aar.py`

## Status

RESEARCH: PASS
IMPLEMENTATION: NOT STARTED
NEXT EXECUTOR: Codex only after its own mandatory preflight/history/training/current-tree inspection.
