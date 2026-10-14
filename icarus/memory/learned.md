
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
