# Icarus donor-source & reinstall forensics — DSH / Hermes
Date: 2026-11-04 UTC
Owner: Michael | Proposed by: Michael | Research compiled by: ChatGPT
Status: PARTIAL — repository and upstream-source research only; no owner-laptop inspection, uninstall, reinstall, runtime probe, donor-code extraction, build, or Icarus adjudication.
Spend: EUR 0 external; allowance not directly measurable.
Scope: provenance and candidates. This is **not** a working integration or a verified diagnosis of the owner's machine.

## 1. Reinstall persistence: observed source behavior vs unverified cause

### DeepSeek Harness (DSH)
Official source states the Windows Desktop uninstaller **never removes the Harness home** (`~/.dsh` or `DSH_HOME`). Profiles, plugins, sessions, credentials, settings and user composition survive an application uninstall. Profile composition loads shipped bundles, then `$DSH_HOME/profiles/<name>/cordis.patch.yml`, then global `$DSH_HOME/cordis.patch.yml`, then CLI `--patch` overlays. Windows also supports a Desktop-provided `dsh` command and other PATH commands; higher-priority commands may shadow it. An update or `/KEEP_APP_DATA` installation retains separate app data. Thus old patches/plugins/home config **can** make a new executable behave like the previous customized harness; this is **not proof that it happened on Michael's laptop**.

Sources:
- https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/desktop/README.md
- https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md
- https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/cli/reference/README.md
- Local historical evidence: https://github.com/the1mburke-blip/Teamchat/issues/150 (25 Oct preset `cordis`, stale workspace AGENTS.md and local AGENTS.local.md, not a proven cause).
- Historical staged source-root caveat: https://github.com/the1mburke-blip/Teamchat/issues/93

### Hermes
Official Hermes Windows docs distinguish code, PATH launchers, managed tools, versioned installs, config/credentials, profiles, sessions, and logs under `%LOCALAPPDATA%\hermes`. Normal `hermes uninstall` for a managed source install **keeps user data** unless `--full` is intentionally chosen. Named profiles may be preserved. A desktop-only uninstall leaves the agent installed. Hermes Desktop connects to a gateway process that can continue running after the GUI closes. Separate native, WSL, store/MSIX and source installations can coexist. Thus code replacement without removing or isolating old profile/home/gateway state **can** preserve behavior; the actual uninstall command, distribution mode and live machine state have not been read.

Sources:
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/windows-native.md
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/getting-started/updating.md
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/desktop.md
- https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/uninstall.py

### Evidence still needed for an actual cause
Read-only evidence from the laptop: installation type/version and command resolution for both executables; relevant user/system PATH and DSH_HOME/HERMES_HOME **names and locations, never secret values**; owner-homed profile/plugin manifests and non-secret patches; active processes/parent-child paths and start times; Hermes gateway/service/task state; Windows uninstall entries and installer/uninstall logs; actual commands/scripts used for uninstall/reinstall; hashes of current executable and changed source/config compared to clean matching release. No deletion or change before a separately approved removal preflight.

**Important:** DSH `--dump-config` is not a pure inspection operation on a previously missing profile: the official CLI reference says it initializes missing profile files. Do not run it blindly for the read-only audit.

## 2. Reusable upstream source catalogue (candidate pointers, no code transplanted)

Pin a specific upstream commit before copying any source. The `master`/`main` links below are moving references. Candidate status means the upstream source path and role were inspected through official source/docs, **not** tested inside Icarus.

| Priority | Donor | Source file(s) | Existing mechanism | Icarus integration seam / caution |
|---|---|---|---|---|
| P0 | DSH TypeScript | `packages/interaction/user-approval/src/index.ts`, `types.ts`, `invariant.ts` | `ctx.approval`, `ApprovalService.request`, `approval/request`, allow-once/deny + session audit | Candidate hook adapter. Preserve Icarus as decision authority; verify every real tool execution is covered. |
| P0 | DSH TypeScript | `packages/interaction/permission-presets/src/index.ts`, `types.ts` | `ctx.permissionPresets`, `PermissionPresetService.set(session,name)` toggles sandbox and approval policies | Candidate to map owner-approved grants to native full/limited presets; a preset by itself is not Icarus enforcement. |
| P0 | DSH TypeScript | `packages/goal/goal/src/index.ts`, `fold.ts`, `domain.ts`, `types.ts` | Durable goal state, CAS/replay validation, pause/resume | Reuse goal state concept rather than duplicate it. Goal state alone does not enforce checkpoint approval. |
| P1 | DSH TypeScript | `packages/sdk/server/src/server.ts`, `index.ts` | `HarnessSdkJsonRpcServer` over stdio; session events and optional `initialize.approvalRequests` | Candidate out-of-process execution/approval bridge; independent validation against installed version required. |
| P1 | DSH TypeScript | `apps/cli/src/args.ts`, `bin.ts` | CLI profile selection and boot | Establish process ownership and exact launch command; no speculative patching of packaged runtime. |
| P1 | Hermes Python | `agent/conversation_loop.py`, `agent/turn_*.py`, `run_agent.py` | Existing agent loop / turn handling | Borrow ideas/interfaces only until Icarus has a single controlling loop; do not run a second competing mind. |
| P1 | Hermes Python | `tools/registry.py`, `model_tools.py` | Tool discovery, schema and dispatch | Candidate adapter for Icarus's governed hand/registry; dispatch must not bypass Icarus grants. |
| P1 | Hermes Python | `agent/plugins.py`, `agent/callbacks.py` | Plugin hooks, callback/approval paths | Probe supported real interception before claiming enforcement. |
| P2 | Hermes Python | `cron/scheduler.py`, `cron/jobs.py` | Persistent scheduled agent tasks | Reuse scheduling patterns only, preserving owner/Icarus control. |
| P2 | Hermes Python | `agent/skills_config.py`, `agent/skills_hub.py` | Skills enablement/discovery | Reuse skill catalog/progressive disclosure; imported skills are untrusted proposals until reviewed. |
| P2 | Hermes Python | `agent/runtime_provider.py`, `agent/model_switch.py` | Provider selection and model switching | Integrate adapter, not second identity or policy source. |
| P2 | Hermes TS/JS/React | `apps/desktop/` (directory; exact files not yet isolated) | Desktop chat/UI, streaming tool activity and profile controls | UI candidate only; requires separate file-level investigation. Hermes core above is mainly **Python**, not JavaScript. |

Original source locations:
- DSH approval: https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/interaction/user-approval/src/index.ts
- DSH permissions: https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/interaction/permission-presets/src/index.ts
- DSH goal: https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/goal/goal/src/index.ts
- DSH SDK bridge: https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/sdk/server/src/server.ts
- Hermes loop: https://github.com/NousResearch/hermes-agent/blob/main/agent/conversation_loop.py
- Hermes registry: https://github.com/NousResearch/hermes-agent/blob/main/tools/registry.py
- Hermes scheduler: https://github.com/NousResearch/hermes-agent/blob/main/cron/scheduler.py
- Hermes architecture map: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/architecture.md

Licensing: both upstream repositories state MIT; verify exact source revision, third-party notices and attribution before reuse. 
- https://github.com/deepseek-ai/deepseek-harness/blob/master/LICENSE
- https://github.com/NousResearch/hermes-agent/blob/main/LICENSE

## 3. Prior donor intake — don't duplicate

Teamchat issue #87 already reports a bounded donor harvest, with historical upstream commits:
- DSH `5badb15009ae1756c3afe0ae0cef1faafc290ccc` — reported 55 source candidates.
- Hermes `99a45ecc17cc51c0488ec3b8ccf7eaf483f7203d` — reported 35 source candidates.
- Workflow run `37769962437`, artifacts `11546744274` (DSH) and `11546534359` (Hermes).
- Report was PARTIAL, and artifacts had short retention; not re-downloaded or independently hash-verified today.
Source: https://github.com/the1mburke-blip/Teamchat/issues/87

## 4. Next checkpoint / acceptance

1. From an authorised laptop session, inspect both installed harnesses and compare to exact clean releases without modification. Identify the **specific** residue or altered install route, or report cause unresolved.
2. Pin upstream source revisions and inventory the exact code bytes/function signatures/dependency & licence graph before harvesting snippets. Do not blindly copy into Icarus.
3. Integrate via Icarus-owned control paths, and validate against the real harness. Source mapping, fixtures and documentation never equal live governance.

No uninstall, reinstall, API spend, agent dispatch or change to Icarus implementation is evidenced by this record.