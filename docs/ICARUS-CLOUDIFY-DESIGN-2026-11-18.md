# Icarus Cloudification — Zero-Cost Design

**Task:** ICARUS-CLOUDIFY-20261118  
**Authority:** Michael, 2026-11-18 08:28 Europe/Dublin  
**Proposed by:** Michael  
**Prepared by:** Claude (task packet only; no execution attributed to Claude)  
**Executor:** [SOL] Sol chair, GPT-6 runtime  
**Retrieved:** 2026-11-18 UTC  
**Status:** DESIGN COMPLETE / SELF-STATUS PARTIAL — independent adjudication and owner-only gates remain open.

## 1. Decision

**Preferred route: reuse the existing GitHub Actions workflow as an ephemeral, one-job cloud worker.** Do not provision an always-on VM. Reuse the existing operational schedule in .github/workflows/icarus-pulse.yml and its existing workflow_dispatch entry point. Add a dedicated ledger-runner job to that workflow only after the security and billing gates below pass. Run the existing daemon with --once, so a hosted runner starts, claims at most one job, verifies it, commits the receipt, and exits.

This is the only route found with an already-active account and a successful scheduled runner readback. It avoids a new cloud account, trial, card, paid service, or persistent host. It is **conditionally €0**, not yet proven €0: the GitHub account plan, remaining included minutes, other Actions usage, and paid-overage setting were not read. If those cannot be confirmed as within existing included usage with paid overage disabled, do not run the worker; leave jobs queued.

**Fallback:** Google Cloud Run Jobs, but only if Michael already has a billing-enabled project, the applicable compute and scheduler quotas are unused, outbound egress is confirmed free, and no new account, trial, credit, card, or paid service is needed. None of those account-specific conditions is currently verified. It is not authorised for setup.

There is no verified always-on, persistent, guaranteed €0 VM route in the evidence reviewed. The VM free tiers have material eligibility, reclaim, region, or billing risks.

## 2. Authority and boundaries

This packet authorises research and design only. This branch contains documentation only.

Not performed: deployment, container build/start/restart, account creation, trial activation, payment method entry, billing changes, secret access, secret-value handling, trigger/scheduler/workflow creation or enablement, edits to existing files, merge, or changes to main.

R1–R5 are assessed below. Where evidence does not prove a requirement, the gap is explicit rather than assumed satisfied.

## 3. Repository evidence and current architecture

All source refs below were read directly through the connected GitHub repository.

| Ref | Exact commit |
|---|---|
| main (design base) | a784eedd026bd1129d83c3d63e78162a5bf17b76 |
| agent/icarus-primitives (daemon source) | 0405949603c8d8ed54346b3cb8ea932aa300244a |
| icarus-ledger (queue/state) | ca388dff531e5a8dd045b9aa817ed1d89fb87531 |

### Active daemon and ledger

- The active daemon imports GitLedger from icarus/primitives/gitledger.py, not the older icarus/primitives/ledger.py. daemon.py imports GitLedger at lines 34–38. Do not use the SQLite ledger implementation as the cloud worker's source of truth.
- GitLedger documents the queue, state and hash-chained run log layout at lines 1–16. The actual implementation writes state/<job_id>.json, not claims/<job_id>.json.
- A missing state file is treated as queued with zero attempts and the job's max_attempts at git ledger lines 107–113. There is no unclaimed-job TTL or expiry.
- claim() synchronises the dedicated clone, skips final jobs and unexpired claims, writes claimed_by and lease_expires, then commits and pushes the state and run-log update. A rejected push raises ClaimLost after resync. See git ledger lines 87–97 and 141–162.
- settle() requires a verifier receipt, checks the current claimed_by runner ID, increments attempts, and sets DONE, queued, or BLOCKER_DISCOVERED. See lines 164–190. Offline time does not increment attempts because no worker has claimed or settled the job.
- The run log is hash-chained; chain_ok() validates previous hashes and record hashes at lines 40–68.
- daemon.py supports --once at lines 87–90 and 125–127. Without --once it polls every 60 seconds. Its default lease is 21,600 seconds (six hours), default runner ID is the shared string daemon, and the poll interval is 60 seconds; see lines 97–127.
- identity.py fetches memory from main, including icarus/memory/identity.md, inherited.md, current-state.md, learned.md and TRAINING_MATRIX.md; see identity.py lines 17–52. The ledger clone therefore needs a fetch of main as well as the ledger branch.

### Current queue readback

On icarus-ledger, queue/canary-005.json exists. The state directory contains state records for earlier canaries but no canary-005.json. The run_log.jsonl currently has eight records; the hash-chain check passed for all eight, and none refers to canary-005. The matching issue #237 comment records the enqueue, not a completed daemon verdict.

**Supported conclusion:** canary-005 is queued and has not been claimed or recorded in the ledger run log at the time of readback. This does not prove the laptop daemon is running or stopped. No live laptop/container readback was available.

### Material source/prompt discrepancies

1. The task packet's file list calls out ledger.py, but daemon.py imports gitledger.py. The latter is the active Git-backed ledger.
2. The Docker entrypoint defaults ICARUS_LEDGER_BRANCH to main (primitives-entrypoint.sh line 7), and setup-primitives.ps1 writes ICARUS_LEDGER_BRANCH=main. The active queue is on icarus-ledger. A cloud worker must set the branch explicitly to icarus-ledger.
3. approved-routes.json exists on icarus-ledger. The daemon loads it from the ledger clone at daemon.py lines 97–102.
4. The current main-branch Athena.gs source (blob 3bd4686ded06e2a8998a5af08d43b50457a9a51c) describes ICARUS_RUN comment polling and hourly checks, but contains no ICARUS_QUEUE marker, no icarus/ledger/queue path and no workflow_dispatch call. The deployed “cloud-4.4” queue-relay claim in the task packet is therefore not proven by current repository source. Treat deployed Apps Script provenance as UNVERIFIED; do not add an Athena dispatch dependency on this evidence.
5. The current .github/workflows/icarus-pulse.yml has three cron entries, including two alternating two-hour schedules and a day-31 heartbeat, plus workflow_dispatch. Taken together, its scheduled workflow runs hourly; the operational-duty cron is every two hours. This is not the “roughly every 3–4 hours” described in the packet.
6. The current workflow's icarus-pulse job has contents:read, issues:write and actions:write. It cannot push ledger state with its current contents permission. A dedicated worker job would need its own explicit contents:write permission.
7. The current Athena.gs source and the queue files may represent different deployed versions. The actual Apps Script deployment version was not read.
8. The task/handoff material describes an older container build, but no live container image digest or running-host readback was available. Do not assume the laptop container is built from the current source SHA.

### Existing Actions evidence

Workflow source: .github/workflows/icarus-pulse.yml, blob 125c7b57b2ac2d734f2e3b9fb31d5d6dbf6fd202. It already has schedule and workflow_dispatch events (lines 3–12). The operational schedule is exposed as ICARUS_PULSE_DUTY_SCHEDULE at line 23. The existing runner job has contents:read at lines 18–27.

Run 44257371439 started and completed successfully on 2026-11-18. Its job log shows IDLE_SELECT, zero tasks dispatched, and the inference step skipped. This proves that a scheduled Actions runner started for that workflow. It does **not** prove that the ledger daemon ran, that the workflow can push to icarus-ledger, or that the run incurred zero billable usage.

Issue #149 remains an historical billing/spending-admission record. The later successful run means the old blocker is not a universal barrier to all Actions jobs; account billing and included-minute availability remain UNVERIFIED.

## 4. Runtime, resources, network and secrets

### Runtime profile

- Image base: python:3.12-slim. Dockerfile.primitives installs git and ca-certificates, copies the primitives and harness packages, and runs as user app (lines 18–35).
- The process needs Git fetch/push to the Teamchat repository, the approved model endpoint, and local temporary job work directories.
- The ledger itself is durable in the Git branch. A hosted one-shot runner can use an ephemeral clone and ephemeral work directory; a persistent VM volume is not required for queue durability.
- No listening service or inbound port is defined in the daemon path. The required network path is outbound HTTPS to GitHub and the approved inference endpoints.
- Source endpoints: github.com for Git transport; generativelanguage.googleapis.com/v1beta/openai for Gemini; openrouter.ai/api/v1 for OpenRouter.
- No CPU, RAM, disk, or image-size benchmark is recorded. A small Python/Git workload is visible, but minimum RAM and CPU are **UNVERIFIED**. Do not represent a 1-vCPU/1-GB allocation as measured capacity.

### Credentials

The source names these credential locations only; no values were read or requested:
- GitHub PAT or GITHUB_TOKEN in the existing Apps Script properties and the laptop primitives.env file.
- GEMINI_API_KEY in Apps Script properties, the laptop primitives.env file, and the existing Actions workflow secret reference.
- Optional OPENROUTER_API_KEY in those same configuration paths.
- For GitHub Actions, prefer the job-scoped ephemeral GITHUB_TOKEN over a long-lived personal token. The existing workflow references GEMINI_API_KEY but its configured presence was not checked.

### Security blocker — isolate the executor

runner.py executes model-produced argv with subprocess.run and does not supply a sanitised env argument (lines 55–88). The child therefore inherits the daemon process environment. The daemon process holds GitHub and model credentials. The allowlist checks argv[0]; if sh is permitted, a shell can invoke other commands. The verifier scans known secret patterns in outputs (verify.py lines 43–59), but output scanning cannot prevent a process from reading an inherited credential and sending it over the container's default network.

Dockerfile.primitives drops Linux capabilities and enables no-new-privileges, but the entrypoint configures a Git credential helper and the daemon and command executor share the same container environment. That is not a sufficient secret boundary for cloud execution.

**Required before cloud execution:** separate the privileged orchestrator from the model-command sandbox. The orchestrator may hold the short-lived GitHub token and inference key. The command sandbox receives only the task files and plan, a minimal environment, a single writable job directory, no Docker socket, no host mounts, no credentials, and no network access. Keep the root filesystem read-only where practical. The verifier remains outside the sandbox and reads only the produced job directory and execution record. Do not deploy until this boundary is tested.

## 5. Queue holding and single-claim safety

### R2 — hold while no worker exists

The Git queue is durable. If no daemon is running, an unclaimed job remains in queue/; missing state defaults to queued, and no TTL is applied. When a cloud worker next starts, it can claim the queued job. This meets the basic hold-until-worker-available behaviour at the ledger layer. It does not require the laptop to return.

A claimed job is different: it remains claimed until settled or its lease expires. The daemon's default lease is six hours. Offline holding must not convert queued work into a failed attempt, and no queue cleanup or expiry should be introduced.

### R5 — one executor per job

The Git commit/push claim is a useful compare-and-swap lock: simultaneous workers starting from the same branch cannot both successfully push the same claim. A losing push resynchronises and raises ClaimLost.

The current implementation does not fully prove R5 under all failure cases:
- runner_id defaults to daemon; the laptop setup uses a fixed laptop-daemon value. Cloud workers must use a unique ID per invocation, such as gha-<run_id>-<run_attempt>.
- The claim has no unique fencing token or generation. settle() checks claimed_by, not a claim nonce.
- There is no lease heartbeat. The model switcher defaults max_pool_breaks to zero, meaning rate-limit pool exhaustion can loop indefinitely (switcher.py lines 60–106). A six-hour lease can expire while a worker is still waiting or executing; another worker could then claim the same job.
- No explicit host-affinity/capability field exists in the queue schema. The current ledger cannot distinguish laptop-only work from cloud-safe work.

**Required before dual-host execution:** add a unique claim generation/token, require it in settle, use a unique runner ID for each process, enforce a hard maximum job runtime shorter than the lease, and add lease renewal if longer tasks are permitted. The sandbox must have no external network so stale execution cannot duplicate external side effects. Add an explicit execution target/capability field (for example any-host or laptop-only); cloud workers must claim only jobs marked cloud-safe. Until this exists and is tested, R5 is PARTIAL, not PASS.

## 6. Hosting options — current public limits

Limits below were checked against provider documentation on 2026-11-18. Account-specific usage, existing projects, payment methods and quota consumption were not inspected. Free tier is not a guarantee against charges if limits are exceeded.

| Route | Public free allowance / fit | Main risks | Assessment |
|---|---|---|---|
| GitHub Actions hosted runner | GitHub Free lists 2,000 Actions minutes/month for private repositories. The existing workflow already has an operational schedule and workflow_dispatch. The daemon supports --once. Docker is available on Ubuntu runners. | Account plan and remaining minutes unknown; current workflow has contents:read, so it cannot write ledger state; job must be bounded; no persistent process. | **Preferred, conditional.** Reuse the existing workflow only; no new schedule or workflow. Stop if included minutes or zero-overage conditions cannot be verified. |
| Google Cloud Run Jobs + Cloud Scheduler | Cloud Run Jobs free tier: 240,000 vCPU-seconds and 450,000 GiB-seconds/month. Cloud Scheduler gives 3 jobs/month free per billing account. Docker and one-shot jobs fit. A 1-vCPU job running 10 minutes every 2 hours would use 60 vCPU-hours/month, below the 66.7-hour compute allowance. | Requires an active billing account; overages are billable. Cloud Scheduler free jobs are account-level, not project-level. Internet egress outside the North America free allowance can cost money. No current GCP account/quota/egress readback. | **Fallback only**, owner-gated. Do not create a project, trial, card, or billing account. |
| Google Compute Engine e2-micro | Free tier includes one non-preemptible e2-micro instance-month in specified US regions, 30 GB standard persistent disk and 1 GB outbound data transfer from North America. Docker can run on a VM. | US-only free region, small shared-core/1-GB class, outbound quota, active billing account and overage risk. Region/data-location trade-off for an Ireland-based owner. | Not preferred. Capacity is marginal and account billing is unverified. |
| Oracle Cloud Always Free A1 VM | Always Free allowance includes up to 2 OCPU and 12 GB RAM equivalent from the Ampere A1 pool, plus free block storage within the published limits. Docker can run persistently. | Oracle documents reclaim of idle Always Free compute after seven days when utilisation thresholds are met. A low-CPU, low-network daemon is exposed to that risk. Home-region capacity and account verification apply; signup requires payment-card verification. | Not reliable enough for the primary daemon; no account or card action authorised. |
| Cloudflare Workers Free | 100,000 requests/day, 10 ms CPU per request, 128 MB memory, limited Cron Triggers and a 15-minute wall-time ceiling. | It is not a Docker host and cannot run this Python/Git daemon as-is. | Not a host. Could only be a thin event relay, which adds no value while GitHub Actions already exists. |
| BigQuery | Google documents a free monthly allowance for query processing and storage. | It is a data warehouse, not a persistent Python/Docker execution host. Git already supplies the durable queue and hash-chained log. | Do not add it; redundant complexity and billing surface. |

Provider documentation:
- GitHub Actions billing and included usage: https://github.com/pricing and https://docs.github.com/en/billing/concepts/product-billing/github-actions
- GitHub workflow schedule and usage limits: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
- Google Cloud Free Tier: https://cloud.google.com/free
- Cloud Run pricing and free tier: https://cloud.google.com/run/pricing
- Cloud Scheduler pricing: https://cloud.google.com/scheduler/pricing
- Oracle Always Free resources: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- Oracle Free Tier signup and verification: https://docs.oracle.com/en-us/iaas/Content/GSG/Tasks/signingup_topic-Sign_Up_for_Free_Oracle_Cloud_Promotion.htm
- Cloudflare Workers limits: https://developers.cloudflare.com/workers/platform/limits/

## 7. Inference budget and provider policy

Hosting cost and model-inference cost are separate. A free compute host does not make a paid model call free.

- The checked approved-routes.json blob is 878a64cf5d0331bb132d1a330b5b3ec4d65e9daa on icarus-ledger. Its note says the Google model rate limits were read on 2026-10-13. Those RPD values are stale for a current decision and are **UNVERIFIED** until checked in the relevant AI Studio project.
- The switcher uses Google Gemini and optional OpenRouter :free routes. It rejects non-free OpenRouter model names, but does not enforce a per-day request budget in this code path. Its unlimited pool-break default can wait forever.
- Google documents a free tier for selected Gemini API models, but quotas are project/model-specific. Google also states that content submitted on the free tier may be used to improve its products. Do not send private repository content through that tier unless Michael accepts that data policy. Current model-specific RPD is UNVERIFIED.
- OpenRouter's current free-tier documentation lists 50 requests/day and 20 requests/minute for free-model use. Buying credits to raise the limit is prohibited by this task. Free-model availability and upstream provider data handling can change; routes marked compatibilityVerified=false in the repository have not been proven for this daemon.
- No paid API, top-up, trial credit, or fallback to a paid model is permitted. If free routes are exhausted, leave the job held or return a bounded blocker; do not loop indefinitely or silently switch to a paid route.

Sources:
- Gemini API pricing and free-tier data handling: https://ai.google.dev/gemini-api/docs/pricing
- Gemini API rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- OpenRouter limits: https://openrouter.ai/docs/limits

## 8. Recommended architecture

1. Queue remains authoritative on icarus-ledger. No new database is required.
2. Reuse the existing operational schedule in icarus-pulse.yml (every two hours) and the existing workflow_dispatch event. Do not add a new workflow or cron. The scheduled worker picks up queued jobs while the laptop is offline; workflow_dispatch is an existing manual recovery path.
3. Add a dedicated job to the existing workflow, conditioned on the operational-duty schedule or workflow_dispatch. Checkout the Icarus code at the pinned source SHA 0405949603c8d8ed54346b3cb8ea932aa300244a. Clone the ledger branch explicitly as icarus-ledger. Do not rely on the setup script's main default.
4. Run python -m icarus.primitives.daemon --once. Claim at most one job per worker. Use a unique run ID for ICARUS_RUNNER_ID.
5. Grant the job short-lived repository permissions appropriate to an agent: contents:write for repository branch changes, issues:write for issue comments, and pull-requests:write where PR creation is required. Keep workflow/secrets/admin permissions out of scope. The current workflow's contents:read permission is insufficient. Preserve main branch protection and require review for changes to main.
6. Keep the privileged GitHub token and inference keys in the orchestrator only. The command sandbox receives no secrets and no network.
7. Add claim fencing and explicit host capability before allowing laptop and cloud workers to run concurrently. Cloud workers claim only jobs marked cloud-safe.
8. Enforce a finite model retry/deadline budget. Use a worker hard timeout shorter than the claim lease; for example, a 10-minute worker timeout and a 20-minute lease, subject to tests. If the worker is terminated, the queue item remains durable and can be reclaimed after expiry. Do not increment attempts merely because no worker was available.
9. Record the runner ID, source SHA, ledger head at claim, verifier receipt, final ledger state, model route trace and measured execution time. Never log token values or environment dumps.

This gives Icarus a cloud execution chair with repository read/write capability while keeping the model-command sandbox separate from credentials. It does not depend on the owner's laptop waking.

## 9. Rollout, verification and rollback

No rollout was performed. The following is the required future plan.

| Step | Action (future owner-authorised implementation) | PASS evidence |
|---|---|---|
| 0. Account gate | Read GitHub plan, included Actions minutes, current usage and paid-overage setting. | Screenshot/readback shows included quota available and no paid overage can occur. |
| 1. Source pin | Pin code SHA and ledger branch; verify route file, identity fetch and Docker build inputs. | Readback of both refs and image build source SHA; no mutable branch ambiguity. |
| 2. Security hardening | Separate orchestrator credentials from executor sandbox; disable sandbox network; add claim nonce/fencing and bounded retries. | Sentinel secret is not visible in sandbox env/output; sandbox cannot make outbound requests; stale claim cannot settle. |
| 3. No-work dry run | Invoke existing workflow_dispatch with an empty queue. | Worker exits idle; no claim, model call, state file or run-log mutation. |
| 4. Queue hold test | Leave a synthetic job unclaimed while no worker runs, then start one worker. | Queue file remains byte-identical while idle; later one worker claims it; attempts remain unchanged until settle. |
| 5. Concurrency test | Start two workers simultaneously against the same synthetic job. | Exactly one claim commit; other returns ClaimLost/idle; one receipt only. Repeat with lease expiry and stale runner. |
| 6. Canary | Run one owner-authorised, harmless synthetic job. | One unique runner ID, one verifier receipt, one final state, hash-chain valid, no secret leakage, measured cost within included quota. |
| 7. Cutover | Only after independent PASS, stop relying on laptop daemon. | Cloud worker executes a later scheduled job while laptop is offline; later readback proves the workflow remains enabled and queue is healthy. |

**Rollback:** disable only the ledger-runner job condition in the existing workflow. Do not delete queue files, reset icarus-ledger, clear state, or rewrite the run log. Queued jobs remain held. Restore laptop execution only after its current image/source and branch configuration are verified. No rollback action is authorised in this task.

## 10. Owner actions (none required to preserve the current queue)

1. **GitHub cost gate:** open GitHub Settings → Billing & licensing → Usage → Actions. Confirm the plan, included minutes, current monthly usage and any paid-overage setting. Do not upgrade or enable paid usage. If €0 cannot be guaranteed, do not enable the worker.
2. **Credential-name gate:** confirm only that the existing Actions secret named GEMINI_API_KEY is present; do not paste or disclose its value. Confirm whether it is on the free API tier and check the current model quota in Google AI Studio.
3. **Data-policy gate:** decide whether private Teamchat task content may be sent to the Google free API tier. Its free-tier data-use terms differ from paid API terms.
4. **Security gate:** approve a code change that removes credentials from the command sandbox environment and disables sandbox network access. This is mandatory before cloud execution.
5. **Permissions gate:** approve a dedicated job with contents:write and, if needed, issues:write and pull-requests:write. Keep main protected. Do not grant secrets, administration, or workflow-edit permissions.
6. **Source gate:** when the laptop is available, read back the actual running container image digest and confirm its source SHA and ledger branch. The setup script currently writes main as the ledger branch; do not assume it is correctly configured.
7. **Fallback gate:** only if GitHub Actions cannot meet the zero-cost condition, check whether an existing Google Cloud billing account already exists and whether Cloud Run compute, Cloud Scheduler jobs and outbound egress are within free quotas. No new project, trial, credit, payment method or card is authorised.

## 11. R1–R5 disposition

- **R1 €0:** conditional on existing GitHub included minutes and paid overage disabled. Account usage not read; therefore not yet proven.
- **R2 hold queued work:** supported by GitLedger's durable queue and default queued state with no TTL. A cloud worker is required for automatic pickup.
- **R3 vendor-neutral:** GitHub, Google Cloud, Oracle Cloud and Cloudflare were evaluated; BigQuery and the inference providers were considered separately.
- **R4 secrets:** no secret values were accessed or written. Current executor isolation is insufficient; mandatory hardening specified.
- **R5 one executor:** atomic Git claim protects the normal simultaneous-claim race, but expired leases, shared runner IDs and missing fencing mean full proof is incomplete. Mandatory hardening and tests specified.

**Recommendation remains conditional.** If GitHub's existing included quota and zero-overage condition cannot be read back, the correct €0 behaviour is to leave jobs queued, not to create a cloud account or incur spend.
