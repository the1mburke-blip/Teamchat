# Icarus stage handoff

Task: ICARUS_MOBILE_HERMES_DONOR_STAGE_20261008
Owner: Michael
Source branch: staging/icarus-hermes-android-shell-20261008
Source baseline: groq/icarus-hermes-mobile-foundation-v01-20261007 (PR #78)
Target: l3ad3r1/Hermes-Agent-Android fork/checkout; current default branch plus pinned agent-core.ref
Status: PARTIAL (repository-only stage)
Executor: ChatGPT authored candidate source; GitHub connector wrote stage; no actual named code worker dispatched
Review: separate worker or owner must independently check; not self-certified
Cost: €0 expected; usage percentage unmeasured
Known broken route: 'Hermes Mobile' control-panel APK that demands a remote URL; do not reuse that companion
Protected: production, credentials, live user data, installed Redmi, existing app signature
Handoff package: apply_icarus_overlay.py, STAGING_CONTRACT.md, approved original binary (owned Library; sha in contract)
Known gaps: logo binary not checked into GitHub, upstream full checkout unavailable here, no Android CI compiled, enforced signed permits not ported, no physical Redmi acceptance.
Next authorized action: use a real verified repository code/build executor to apply the candidate to isolated source; repair upstream drift; integrate full Icarus gateway before tool execution; separate security reviewer; compile unsigned inspection APK in existing €0 runner; independently read back exact artifact. Stop before signing/deploying.
PASS gate: exact source and SHA -> clean build -> independent adversarial governance review -> signed inspectable APK + on-device redmi tests after separate authorization.

## 10 October scoped path-correction handoff
Current branch: `feature/icarus-hermes-lineage-relocation-20261010`.
Relocated source branch: `feature/icarus-dsh-tether-rebrand-20261010`.
Four source files now live at
`drafts/icarus/2026-10-08-hermes-shell/lineage-source/` after exact
relocated-source byte comparison. Existing source overlay now REQUIRES
`--lineage-root` and stages assets to `app/src/main/assets/icarus/memory/`.
No APK was built or deployed, and no model has been granted tool authority.
