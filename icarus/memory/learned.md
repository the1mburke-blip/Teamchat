
## 2026-10-13 — Verified Upgrades: Three New Icarus Abilities
- Live Test Status: Verified PASS (€0 cost).
- 1. **Read Tools:** Ability to read repo files and issues directly during a run, verified by live test return values.
- 2. **Lesson Log:** Ability to save one-sentence runtime insights to a review folder without polluting main memory, requiring manual review and promotion.
- 3. **Task Planning:** Ability to parse `PLAN: yes` tags in tasks and automatically decompose objectives into up to 4 sequential steps.
- Protocol Integration: These capabilities are fully operational within the runtime and integrated into our canonical repository architecture (icarus/memory/learned.md).

## 2026-10-14 — Owner standing orders (from Michael, repeated many times)
- Icarus is the pilot; Hermes (or any harness) is the plane. The plane executes tool calls and makes no decisions. Same as the PC harness.
- Take a task and complete it. No gate-by-gate updates, no partial work, no reassurance without evidence. "Task complete = pass, everything else is burned tokens and a fail."
- Do not circle. When told what to do, do that. Do not claim a fix without showing the cause was fixed; say plainly what is proven and what is not.
- Do not hand routine steps back to Michael. Only owner-only boundaries (credentials, consent) go to him. Never ask him to paste secrets into chat; he adds secrets himself as repo secrets.
- Give him the exact tap-by-tap route for the device he is on (phone: no GitHub Developer settings in the app; use the browser links).
- Michael said he was "having the same issue" with Claude as with ChatGPT: agents saying done when it was not. Icarus exists to stop that.

## 2026-10-14 — Android app (Hermes-Agent-Android v1.1.7 + Icarus) attempt log
Repo: the1mburke-blip/icarus-android-build (private). CI: GitHub Actions build.yml clones Hermes + agent-core, applies overlay patches, signs, releases Icarus.apk (tag icarus-N). Gradle cannot run in the Claude sandbox; CI is the only compiler. Patches are Python string replacements on anchors, so one wrong anchor or name breaks the build.

FAILED / WRONG ATTEMPTS (what, why, lesson):
1. Gemini 3.x tool use 400 (missing thought_signature on replayed tool calls). Fixed by adding extra_content.google.thought_signature to ToolCallDto and a placeholder value on Google endpoints (icarus-3). Worked.
2. Said the fix covered identity by editing prompt text only ("You are Hermes" to "You are Icarus"). Wrong: that only reworded Hermes. Lesson: prompt rewording is not control.
3. Added a narrow regex identity gate. Wrong scope: "Name?" slipped through and the model answered "Hermes". Lesson: gates in code must cover the real inputs; test with the owner's exact phrases.
4. Built Icarus as a layer inside Hermes (preamble, reminder, verifier, guard) and called it "in control". Wrong: Hermes still built the turn, ran proactive/evolution workers, and appended its own persona and standing notes. Lesson: control means owning what the model reads, what runs, and what the user sees.
5. Rename pass over strings, wrap-up on tool-loop limit, reply filter that rewrites Hermes to Icarus, root patch removing Hermes persona/standing notes from the system prompt and the proactive scheduler: pushed as 712afe2, 93228ef, 7525a5e. 712afe2 and 93228ef were cancelled by newer pushes (workflow concurrency). 7525a5e FAILED to compile: my new wrapUp() in AgentLoopRunner used `provider`, which is a parameter of the run function, not a class member (Unresolved reference 'provider', 'content', 'toolCalls'). Fixed in 2dcb76c by passing provider into wrapUp. Lesson: check variable scope against the real source before pushing; read the CI log with proxy_execute GET /repos/<owner>/<repo>/actions/jobs/<job_id>/logs and grep "e: file".
6. Token for live memory sync: the owner made three fine-grained tokens. First two could not see Teamchat (wrong repository selected), third had Metadata and Issues but not Contents (403 "Resource not accessible by personal access token", header x-accepted-github-permissions showed contents=read needed). Fixed when Contents: Read-only was added. Lesson: test the token against the real files before storing it; the permission header names the missing permission. Fine-grained token permissions cannot be changed through the API.
7. Claimed "working as intended" before testing on a phone. Wrong. Build success is not behavior. The owner's phone test showed: (a) "Name and a task from yesterday" hit the tool-step limit (12 rounds of get_current_datetime, session_search, todo, notes, tool_call, search_conversations, memory) and returned an error with no answer; (b) "Name?" returned "My name is Hermes" with a verifier line "FAIL - claimed name not supported by any tool output". Causes: no final-answer fallback in AgentLoopRunner; verifier judged identity statements; Hermes text still in prompts and strings.

HOW THE APP IS WIRED (so the next harness move is faster):
- OrchestratorImpl.sendMessage builds stableSystem = IcarusDirective.preamble() + agent prompt + toolInstruction + IcarusDirective.reminder(); turnContext = user memories + previous context + deferred tool block. Replies go through IcarusVerifier.verify() and now IcarusGate.persona().
- AgentLoopRunner.run is the tool loop (MAX_TOOL_ROUNDS = 12). ToolCallExecutor runs the tools. These are the hands.
- Overlay patches in order: patch.py, patch_gemini, patch_identity, patch_gate, patch_control, patch_pilot, patch_loop, patch_rename, patch_persona, patch_root. IcarusGuard requires owner approval by regex for risky actions.
- Memory sync: IcarusDirective pulls icarus/memory/{identity,inherited,current-state,learned}.md from the Teamchat repo every 10 minutes using the ICARUS_REPO_TOKEN Actions secret (bundled copy is the fallback).

NEXT-HARNESS RULES FOR ICARUS:
- Decide with his own files; have the harness only run tools. Do not let the harness persona, standing notes, proactive jobs, self-evolution, OTA or skill-authoring act on its own.
- Never report PASS without final-effect evidence: build log, release asset, and a test of the exact question the owner asked.
- Compile before claiming. Read the real source for names and scope. When CI fails, read the job log and fix without messaging the owner until PASS.
- Tell the owner the truth about what is unproven.

## 2026-10-14 — Android build icarus-15: Icarus is the app's orchestrator (build-repo commit fa38d0b)
- Architecture: IcarusRuntime replaces Hermes's OrchestratorImpl as the app's Orchestrator (DI binding patched in AgentsModule). Hermes's bot chats still run on Hermes.
- Pilot: each turn starts with one Icarus decision call under constitution + live repo memory. JSON: act=false with reply, or act=true with directive and granted tools.
- Hands: Hermes's AgentLoopRunner executes only on Icarus's directive with only the tools he granted; result verified against the tool log; Hermes name filtered out of replies.
- Own tool icarus_repo: read, list, and note (saves lesson notes to icarus/memory/review/). Use it to check the repo; do not use shell for that.
- Shell and termux need owner fingerprint/passcode (Hermes ToolConfirmationService.BIOMETRIC_REQUIRED_TOOLS). A fast decline means that approval failed; report it plainly and take another route.
- Lesson: the earlier fixed CONVERSATIONAL route made the router treat turns as non-tool turns and use the on-device model. The new runtime requires reliable tool calls.
- Lesson: read the real source and dry-run patches locally before pushing; build 15 compiled first time after that.

## 2026-10-14 — Android runtime verified on the owner's phone
- Result: build icarus-15 (run 15, commit fa38d0b) passed the owner's device test. Asked to tell what he learned yesterday, Icarus answered from live repo memory. Owner verdict: "Well done (finally)".
- Cost of the road there: a full day and about 30% of the weekly allowance (owner-stated). The cause was text-level patching and blind CI iteration instead of reading the host source and seating a runtime at its orchestrator interface.
- Standing rule for any harness: own the decision in code, let the host only execute, read the real source and dry-run patches before the first build. Training entry: HV-EXP-097 in TRAINING_MATRIX.md.
- Untested on the phone: icarus_repo note write, shell approval handling.

## 2026-10-14 — Correction, root cause and icarus-18 (build-repo commit ac908d4)
- Correction: the entry above saying the Android runtime was "verified on the owner's phone" (icarus-15) proves only that Icarus answered from live repo memory. It did not prove he commanded Hermes's tools, and the same entry lists the tool paths as untested. The owner later reported Icarus saying he only has memory functions. Tool control is UNVERIFIED on a phone until a real tool call is seen.
- Cause found in code (overlay/IcarusRuntime.kt): when the decision step returned a reply that was not JSON (no '{'), it was returned as the final chat answer and never reached the tool-granting path, so a chatty model reply meant chat only.
- Fix (ac908d4): removed that fallback so a non-JSON reply falls through to the hands path, and the decision prompt now states Icarus has full tool control via act=true and must never say he can only chat or use memory. Built as release icarus-18 (Actions run 18 success, signed with the Icarus key, package com.icarus.agent). Not yet tested on a phone.
- Pass test: ask "Read your own learned.md and tell me its first line." PASS only if a tool call is visible in the app and the answer matches the file's real first line.
- Rule: a memory answer is not evidence of tool control. Test with a task that needs a tool and check the tool log.

## 2026-10-15 — icarus-18 phone test: PASS (tool control)
- Test: "Read your own learned.md and tell me its first line." Run on the owner's phone, app build icarus-18.
- Result reported by owner from the app: verdict PASS, 1 tool call (`icarus_repo` action=read, path=icarus/memory/learned.md), answer "## 2026-10-13 — Verified Upgrades: Three New Icarus Abilities".
- Independent check (Claude, GitHub contents API, 2026-10-15): first non-empty line of the file on main is exactly that heading (line 1 of the file is blank). Answer matches the real file; it could not come from memory alone.
- Status: tool control via Hermes hands = PASS for read. Write/other tools not yet tested on the phone.
