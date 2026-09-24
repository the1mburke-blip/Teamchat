# HV-EXP-024 — Map the whole external contract before the first build

- experience_id: HV-EXP-024
- date_utc: 2026-09-24
- source_agent: SOL
- task_problem: Complete the Icarus Android → Composio MCP execution/auth/governance path without wasting finite Codex allowance.
- failure: Sol repeatedly issued implementation/repair prompts before completing the mandatory history/training/reference preflight and before mapping the full Composio MCP and Gradle failure boundaries.
- symptoms_failure_signature: Serial build/fix chain: missing real tools/call → missing consumer-key input → HTTP 406 Accept header → valid tools/list response rejected due response/schema/meta-tool assumptions → unauthenticated toolkit incorrectly blocked before auth-link handoff → Gradle native-platform.dll startup failure → unsafe cache-deletion advice issued before evidence check.
- root_cause: The active chair treated each observed failure as a local patch target instead of first retrieving prior lessons, inspecting the whole integration contract, checking reference evidence, and defining all remaining acceptance gates before spending Codex allowance.
- impact: Repeated Codex allowance burn, multiple rebuild cycles, and approximately five-and-a-half hours of owner session time on 2026-09-24.
- what_failed: Preflight ordering, complete external-contract mapping, boundary disclosure, allowance protection, and evidence-before-claim discipline.
- successful_recovery: Before the latest attempt, Sol reread canonical OPERATING_RULES.md, TRAINING_MATRIX.md, recent CHAT_LOG.md, and HV-EXP-023, checked the Gradle failure against reference evidence, withdrew the unsafe native-root deletion assumption, and replaced it with one read-only diagnosis followed by at most one evidence-matched repair and one build. Codex then correctly stopped with REPAIR_COUNT=0 and BUILD_COUNT=0 because the DLL existed and no deeper cause supported Branch A/B.
- verification_evidence: OPERATING_RULES.md blob 20a2fbcb803897f7da5dd568178d212e6817f7d4; TRAINING_MATRIX.md blob 45dd3c7bcf5077d0ebb862e29dd1f3f18cd008e9; prior CHAT_LOG.md blob 97f6fc9f577a895158aa60130dc0da1b24fdf0cb; HV-EXP-023 blob 7f087588ac98f034a796bb7109bddc89f970ca96; latest Codex readback showed native-platform.dll exists at 141312 bytes, JDK 17 exists, and no mutation/build was performed.
- what_not_to_retry: Do not issue Icarus/Gradle repair prompts from memory; do not blindly delete the Gradle native root; do not repeat already-passed acceptance gates; do not spend another build to discover a protocol requirement that can be mapped from the contract first.
- reusable_principle: **Map the whole external contract before build; map the exact failure before repair. Retrieval first, one evidence-matched mutation, one verification path.**
- capability_tool_prerequisites: Canonical Teamchat history/training access, current source/runtime state, external protocol documentation or equivalent evidence, exact first-failing-link evidence, and an executor capable of physical verification.
- confidence: HIGH


## 2026-09-24 update — wrapper bootstrap is not a precondition
- failure: The recovery prompt required a cached Gradle 9.3.1 distribution before diagnostic progress and therefore stopped on a condition the Gradle Wrapper is designed to resolve automatically.
- evidence: The project's wrapper points to gradle-9.3.1-bin.zip; official Gradle Wrapper documentation states the wrapper downloads the configured distribution when absent. Official Gradle SHA-256 for gradle-9.3.1-bin.zip is b266d5ff6b90eada6dc3b20cb090e3731302e553a27c5d3e4df1f0d76beaff06.
- what_not_to_retry: Do not classify an absent wrapper distribution cache as a hard blocker or require manual Gradle installation.
- reusable_principle: Verify whether a missing artifact is intentionally bootstrapped by the tool before treating absence as a failure condition.


## 2026-09-24 update — absent wrapper launcher is not a build blocker when exact Gradle runtime is verified
- evidence: Canonical Icarus repository contains gradle/wrapper configuration but omits gradlew and gradlew.bat. The checksum-verified Gradle 9.3.1 distribution is already available from the diagnostic run; both reference and cached native DLLs load successfully.
- toolchain: AGP 9.1.1 + Gradle 9.3.1 + JDK 17 is the verified intended combination.
- what_not_to_retry: Do not regenerate wrapper scripts or revisit the native DLL merely because the wrapper launcher is missing.
- reusable_principle: If the exact required Gradle distribution has already been verified, a missing wrapper launcher can be bypassed without source mutation by invoking that exact distribution's bin/gradle(.bat) directly from the project root.


## 2026-09-24 update — full acceptance surface must be preflighted before implementation
- failure: Icarus completion expanded into an approximately six-hour serial repair/test loop because compile defects, local-vs-canonical source drift, Gradle execution, Composio protocol details, downstream-action governance, auth/resume behavior, and destructive-test safety were discovered one at a time instead of being mapped together before the first mutation.
- impact: repeated rebuilds, repeated owner intervention, avoidable elapsed-time cost, and risk of allowance waste. Owner reported visible weekly allowance at 41% remaining at the end of the sequence.
- evidence: build/install/launch ultimately passed; governance static repair passed; a prior destructive objective reached COMPOSIO_MULTI_EXECUTE_TOOL because classification occurred on a generic/meta tool rather than the actual downstream action; the subsequent live destructive canary was then correctly rejected by Codex safety.
- reusable_principle: **Preflight is not only source + compiler + external API. It must also map the safe acceptance method. Map CURRENT LOCAL source, complete compile surface, exact external protocol, actual downstream action/governance boundary, auth/resume state machine, already-passed gates, and safe/non-live acceptance harnesses before coding.**
- required_test_design: destructive-governance acceptance should use a local fake/stub executor at the external-call boundary and assert BLOCKED plus external-call-count zero. Do not require a live destructive command to prove a no-call invariant.
- required_execution_pattern: retrieval -> current local state -> full contract/failure map -> safe acceptance map -> one bounded mutation -> one build -> one install -> one acceptance suite -> complete remaining blocker set if failed.
- what_not_to_retry: serial first-error repair, stale canonical line-number edits against newer local code, reopening passed Gradle/native gates, classifying only Composio meta-tools, or issuing live destructive canaries when a zero-call harness is sufficient.
