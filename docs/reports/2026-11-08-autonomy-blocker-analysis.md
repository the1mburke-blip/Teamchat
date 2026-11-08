# Icarus autonomy blockers · 8 November 2026 UTC

Task OPS-AUTONOMY-LOOP-20261108-01. Michael proposed the change. ChatGPT Work prepared the implementation and evidence on feature/closed-loop-autonomy. Sol or Gemini Prime is the independent auditor.

## Selector

The existing Pulse inspected open issues but delegated only explicit TASK_INCOMING packets. The new scheduled selector ranks authorized, explicitly ready, unassigned issues by priority and issue number. It excludes blocked, occupied, and terminal issues, respects existing chair routes, and records claims on source issues. Manual directives retain precedence and Issue #6 remains the dispatch mailbox. A persisted source claim survives an interrupted dispatch. A dispatched backlog issue stays in flight while its source issue is open.

The branch can prove selection, claim, dispatch, and recovery with fixtures. Live selection requires the reviewed workflow on the default branch and an eligible issue. The worker wake is a separate boundary. The dispatch outbox has no verified unattended consumer for Work or Sol. General backlog evidence also needs task-specific adjudication rules before the runner can verify and release arbitrary completed tasks autonomously.

## Egress

The fixed edit URL selected one response to replace. The new sender opens the fresh responder form and submits to its standard formResponse action, omitting edit tokens. Existing configuration can supply PRIME_SNAPSHOT_FORM_URL or the existing edit URL as a form identifier. The workflow carries the originating Pulse run ID, event and SHA into the snapshot and gives separate pulses separate concurrency groups. Pulse-linked and branch verification runs avoid Buffer writes. Standalone main snapshots retain the existing Buffer refresh.

A Form POST has no verified idempotency key. Reruns cannot replay the POST, and an ambiguous transport error requires sheet readback before a recovery dispatch. The sheet remains the final acceptance evidence. A successful sync job does not by itself prove sheet persistence.

## Canary adjudicator

The physical owner intake, Icarus dispatch, Work claim and Work receipt are all on Issue #6. Work's ECHO_COMPLETE receipt was posted at 09:53:32 UTC after an owner intervention. The runner verifies the matching IDs, chair, exact echo, comment order, and GitHub identities before posting an adjudication. GitHub comments persist the state across stateless wakes. The JSON artifact records WAITING_FOR_RECEIPT, ADJUDICATED, and IDLE_SELECT. The owner and Work currently use the same GitHub identity. Their separate roles are recorded in the comments.

- Owner intake [6715421000](https://github.com/the1mburke-blip/Teamchat/issues/6#issuecomment-6715421000)
- Icarus dispatch [6715423547](https://github.com/the1mburke-blip/Teamchat/issues/6#issuecomment-6715423547)
- Work claim [6720040376](https://github.com/the1mburke-blip/Teamchat/issues/6#issuecomment-6720040376)
- Work completion [6720043721](https://github.com/the1mburke-blip/Teamchat/issues/6#issuecomment-6720043721)

**Blocking prerequisite for the requested cron receipt.** GitHub schedules run the workflow on the repository's default branch. The task authorizes only a branch and PR. After independent review and authorized deployment, wait for a scheduled Pulse and verify its run ID and bot-authored adjudication referencing receipt 6720043721. Confirm the subsequent snapshot row correlates to that Pulse ID. A separate cron canary with a verified unattended worker and independent receipt is required to establish the complete owner-free loop. This historical receipt establishes a manually initiated worker leg.

[GitHub schedule semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
