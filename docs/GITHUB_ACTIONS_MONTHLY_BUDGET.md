# GitHub Actions — Monthly Minutes Budget

OWNER: Michael
PREPARED_BY: Saul (ChatGPT)
CREATED_UTC: 2026-10-26
STATUS: OPERATING BUDGET RECORDED; ACCOUNT BILLING CAP NOT CONFIGURED
TARGET_MONTH: November 2026 (30 days; exact daily ledger below); recompute for following months
MONETARY_LIMIT: EUR 0 external spend; no paid runner minutes, subscriptions, trials, or overage authorisations

## Verified entitlement and October baseline

- Account: `the1mburke-blip`; GitHub plan: **Free** (authenticated user account readback).
- Shared account allowance for **private repository** GitHub Actions standard hosted runners: **2,000 minutes each calendar month**. This is **account-wide**, not a separate allowance per repository, per workflow, or per agent.
- Reset: start of each month; next **2026-11-01 00:00 UTC**. Minutes do not carry over.
- October 2026 billing usage report: **3,504 Linux runner minutes** (last reported usage date 2026-10-21), comprising:
  - `Teamchat`: 2,561 minutes
  - `icarus-android-build`: 909 minutes
  - `Icarus-AIStudio-Latest-2026-09-24`: 34 minutes
- October consumption is 175.2% of the 2,000-minute Free entitlement (1,504 above it). Recorded GitHub Actions Linux runner gross amount $21.024, discount amount $21.024, net amount $0. The billing report does **not** establish the reason for the discounts. No overage spend is authorised.
- GitHub Actions run #40370746118 on 2026-10-26 failed before executing any steps; the October account minute overrun is a plausible explanation, but no runner-level GitHub billing rejection message was retrieved. Do not call that root cause definitively proven.

## November 2026 — daily GitHub Actions budget

**True budget: 2,000 GitHub-billed runner minutes / 30 days = 66 minutes 40 seconds per day (66.67 min/day).** This is the new month's allowance, not an allocation based on the number of minutes used by different repositories in October.

**Daily ledger implementation:** GitHub measures billed minutes as whole-minute units per job, so allocate **67 minutes/day on Nov 1–20** and **66 minutes/day on Nov 21–30**. That totals exactly **2,000 minutes** by Nov 30. The 67/66 split is a planning convention to represent the monthly average, not a GitHub daily reset. Unused daily allocation remains available later within November; excess daily usage reduces remaining later-day capacity. The **entire account and all repositories share** this limit.

| Day (UTC) | Planned daily minutes | Cumulative month-to-date maximum |
|---|---:|---:|
| 2026-11-01 | 67 | 67 |
| 2026-11-02 | 67 | 134 |
| 2026-11-03 | 67 | 201 |
| 2026-11-04 | 67 | 268 |
| 2026-11-05 | 67 | 335 |
| 2026-11-06 | 67 | 402 |
| 2026-11-07 | 67 | 469 |
| 2026-11-08 | 67 | 536 |
| 2026-11-09 | 67 | 603 |
| 2026-11-10 | 67 | 670 |
| 2026-11-11 | 67 | 737 |
| 2026-11-12 | 67 | 804 |
| 2026-11-13 | 67 | 871 |
| 2026-11-14 | 67 | 938 |
| 2026-11-15 | 67 | 1,005 |
| 2026-11-16 | 67 | 1,072 |
| 2026-11-17 | 67 | 1,139 |
| 2026-11-18 | 67 | 1,206 |
| 2026-11-19 | 67 | 1,273 |
| 2026-11-20 | 67 | 1,340 |
| 2026-11-21 | 66 | 1,406 |
| 2026-11-22 | 66 | 1,472 |
| 2026-11-23 | 66 | 1,538 |
| 2026-11-24 | 66 | 1,604 |
| 2026-11-25 | 66 | 1,670 |
| 2026-11-26 | 66 | 1,736 |
| 2026-11-27 | 66 | 1,802 |
| 2026-11-28 | 66 | 1,868 |
| 2026-11-29 | 66 | 1,934 |
| 2026-11-30 | 66 | 2,000 |

**Usage control:** `remaining_minutes = 2,000 - actual_billed_actions_minutes_in_November`. Compare actual consumption to the current date's cumulative allowance before approving further optional jobs. Use the **billing API** for actuals; usage reporting may be delayed. If a build exhausts its daily envelope, defer other optional work until the running monthly allocation catches up. Prioritise business-critical Prime/Notebook and storefront operations, then essential repair/build activity, then experiments.

**October 2026 repository usage is historical analysis, not the November budget.** No repository is automatically entitled to repeat its October consumption.

### Guardrails and decisions

1. **Before each nontrivial workflow run**: check cumulative account-wide GitHub Actions consumption and estimate how many billed minutes the job will consume. Linux-hosted runner billing may differ from elapsed end-to-end workflow time; every started billed job minute counts.
2. **At 1,000 minutes (50%)**: review pace and the highest consuming repositories.
3. **At 1,400 minutes (70%)**: remove speculative retries, redundant builds, and nonessential tests.
4. **At 1,800 minutes (90%)**: reserve remaining capacity for essential work only; do not create additional experimental runs.
5. **At 2,000 minutes (100%)**: no more private-repository GitHub-hosted Actions runs until the monthly reset; no paid overages without new explicit owner authorization.
6. **At each calendar-month reset**: verify the live meter and a genuinely successful workflow run before claiming execution is recovered. Separate account/billing/platform failures require investigation.
7. **Protect production**: this is a planning ledger, not a native hard spending cap; no existing workflow, schedule, code, billing setting, or runner configuration is modified by the document.
8. Do not move private source to a public repository simply to bypass GitHub Actions allowance.
9. **Daily cap is operational, not platform-enforced**: GitHub provides one monthly allowance, not 2,000 divided into 30 provider-enforced daily buckets. The team must budget against the monthly balance.

### How to audit

Source of truth: connected GitHub Billing usage summary/report for personal account `the1mburke-blip`, filtered to the **current year/month** and GitHub Actions; split report by repository and runner SKU. Check the effective billed amount separately from gross minute totals. Where usage data is delayed, state the latest billed date instead of claiming the counter is realtime.

At every check record: `period_utc`, `observed_at_utc`, `last_billed_usage_date`, `minutes_by_repo`, `total_minutes`, `remaining_vs_2000`, `net_billed_usd`, `threshold_status`, `proposed_action`, and whether the action occurred. Budget stages reset by the calendar month, not by the date of this document.

### Enforcement limit — account billing

GitHub supports native **Budgets and alerts** for personal accounts. The GitHub connector exposed usage reads and repository writes, but **no supported personal-account native budget creation/configuration action** was available in this session. Therefore **no $0 hard spending cap and no native 90%/100% included-usage alerts were configured or verified**. An owner-side billing control is separate from this internal budget. Do not falsely report it as enabled.

References:
- Official allowance and reset: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Native included-usage alerts / budget controls: https://docs.github.com/en/billing/concepts/budgets-and-alerts
- October run: https://github.com/the1mburke-blip/Teamchat/actions/runs/40370746118

## Revision — 2026-10-26

- CORRECTION_REQUESTED_BY: Michael — the first allocation by workstream used October consumption patterns; he specifically requires `2,000 / days in November` as the budget basis.
- CORRECTION_EXECUTOR: Saul (ChatGPT)
- NOVEMBER_BUDGET: 2,000 minutes / 30 days = 66 minutes 40 seconds/day (daily ledger 20×67 + 10×66 = 2,000)
- ACCOUNT_BILLING_CAP_CHANGED: NO

## Execution record

- PROPOSED_BY: Michael (request, 2026-10-26)
- EXECUTED_BY: Saul / ChatGPT, read-only billing audit and additive budget document
- EVIDENCE: connected GitHub authenticated user plan and October Actions billing summary/report; GitHub repository source and workflow readback
- CHANGES: create this single Markdown budget document. No billing-setting changes, no workflow changes, no spending.
- VALIDATION: new file contents must be reread from the default branch, with the committing SHA recorded.
