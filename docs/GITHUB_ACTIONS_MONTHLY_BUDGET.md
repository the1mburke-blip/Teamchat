# GitHub Actions — Monthly Minutes Budget

OWNER: Michael
PREPARED_BY: Saul (ChatGPT)
CREATED_UTC: 2026-10-26
STATUS: OPERATING BUDGET RECORDED; ACCOUNT BILLING CAP NOT CONFIGURED
TARGET_MONTH: November 2026; reuse the policy each following calendar month
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

## Monthly budget (2,000 minutes total)

| Workstream/account-wide category | Monthly cap (Linux standard-runner minutes) | Guideline |
|---|---:|---|
| Teamchat operation, Prime/Notebook snapshot and HumanVibe operational relay | **1,000** | ~33 min/day; protect core business continuity first |
| ICARUS Android builds and necessary acceptance tests | **500** | Schedule approved batches; don't run speculative rebuild loops |
| Other experiments, diagnostics and bounded canaries | **200** | One evidence-backed attempt per defined hypothesis |
| Protected emergency/recovery reserve | **300** | Hold back until there is an actual priority failure |
| **TOTAL** | **2,000** | **€0 paid overage** |

The normal planned spend of minutes is **1,700**, with **300** protected for recovery; this is a minutes allocation, **not** money. Reassigning minutes between workstreams is allowed only when the account's 2,000-minute ceiling and protected reserve are preserved, and actual usage is reread.

### November operational pacing

For November's 30 days, keep **planned/nonemergency** usage at or below these cumulative checkpoints:

| End of period (UTC) | Cumulative normal-use maximum |
|---|---:|
| 7 Nov | 400 min |
| 14 Nov | 800 min |
| 21 Nov | 1,200 min |
| 28 Nov | 1,600 min |
| 30 Nov | 1,700 min |

Daily normal-use average: **56.7 min/day**. The 300-minute reserve is not another budget on top of 2,000; it is inside the total.

### Guardrails and decisions

1. **Before each nontrivial workflow run**: check cumulative account-wide GitHub Actions consumption and estimate the new job minutes (each partial job minute rounds up; concurrent jobs count separately). Reuse current data rather than repeatedly dispatching failed runs.
2. **At 1,000 minutes (50%)**: review pace and the top consuming repositories.
3. **At 1,400 minutes (70%)**: cut optional tests and speculative builds; prioritise existing production and the Notebook sync.
4. **At 1,700 minutes (85%)**: freeze new nonessential GitHub-hosted Actions runs; retain 300 emergency minutes. Owner must explicitly authorise reserve use.
5. **At 2,000 minutes**: stop requesting further private-repository hosted-runner work until reset. Do not add payment details, enable overages, or purchase extra minutes.
6. **At each monthly reset**: verify the live billing meter and a real successful workflow run before declaring Actions recovered. If reset does not restore execution, investigate a separate blocker.
7. Protect production: this budget is a planning document. It **does not** disable, pause, reschedule, or rewrite any existing workflow, and it does not constitute a native GitHub billing spending cap.
8. Keep all existing repositories private. Do not move code to public repositories simply to avoid minute charges.

### How to audit

Source of truth: connected GitHub Billing usage summary/report for personal account `the1mburke-blip`, filtered to the **current year/month** and GitHub Actions; split report by repository and runner SKU. Check the effective billed amount separately from gross minute totals. Where usage data is delayed, state the latest billed date instead of claiming the counter is realtime.

At every check record: `period_utc`, `observed_at_utc`, `last_billed_usage_date`, `minutes_by_repo`, `total_minutes`, `remaining_vs_2000`, `net_billed_usd`, `threshold_status`, `proposed_action`, and whether the action occurred. Budget stages reset by the calendar month, not by the date of this document.

### Enforcement limit — account billing

GitHub supports native **Budgets and alerts** for personal accounts. The GitHub connector exposed usage reads and repository writes, but **no supported personal-account native budget creation/configuration action** was available in this session. Therefore **no $0 hard spending cap and no native 90%/100% included-usage alerts were configured or verified**. An owner-side billing control is separate from this internal budget. Do not falsely report it as enabled.

References:
- Official allowance and reset: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Native included-usage alerts / budget controls: https://docs.github.com/en/billing/concepts/budgets-and-alerts
- October run: https://github.com/the1mburke-blip/Teamchat/actions/runs/40370746118

## Execution record

- PROPOSED_BY: Michael (request, 2026-10-26)
- EXECUTED_BY: Saul / ChatGPT, read-only billing audit and additive budget document
- EVIDENCE: connected GitHub authenticated user plan and October Actions billing summary/report; GitHub repository source and workflow readback
- CHANGES: create this single Markdown budget document. No billing-setting changes, no workflow changes, no spending.
- VALIDATION: new file contents must be reread from the default branch, with the committing SHA recorded.
