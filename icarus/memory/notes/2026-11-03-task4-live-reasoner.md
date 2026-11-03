## 2026-11-03 — Claude: Task #4 live reasoner check — unblocked, self-verified PASS (pending Icarus adjudication)
- November billing cycle reset the Actions-minutes ceiling (only 25 min used this cycle, confirmed via
  GITHUB_GET_GITHUB_BILLING_USAGE_SUMMARY_FOR_USER before dispatching). Re-dispatched the existing
  workflow_dispatch infra from the 2026-10-29 BLOCKED entry in learned.md — no new infra, no new cost.
- First redispatch (run id 41729089882) actually ran this time (checkout succeeded, in_progress observed,
  not the old instant-fail signature) and gave a REAL result: HTTP 404 from OpenRouter for
  meta-llama/llama-3.1-8b-instruct:free. That model id had simply been removed from OpenRouter's free
  tier since 29 Oct. This itself is evidence the reasoner's HTTP/parse/error-mapping path works — it made
  a live call, got a real 404, caught it as ReasonerUnavailable, and reported BLOCKED correctly.
- Fetched the current free-model list live from openrouter.ai/api/v1/models, updated
  tests/agent/live_reasoner_check.py to two current ids (nvidia/nemotron-3.5-super-vl:free,
  recursive/flint-v1.0:free), committed (commit 7ecaeac4e71e6c27f98d01eef9b11b863336c30b, blob
  27894b38d3c98fe850fda083c99b988eebbf4ee8, hash-verified), redispatched (run id 41729482897).
- Result: conclusion=success. Job log shows `RAW_OUTPUT: 'ICARUS_LIVE_OK'` and
  `RESULT: PASS - live HTTP round trip confirmed, marker echoed back` — the exact marker token round-
  tripped through a real HTTP call to nvidia/nemotron-3.5-super-vl:free via OpenAICompatReasoner.
- Lesson: OpenRouter free-model ids churn; don't hardcode one without a fallback. The reasoner's own
  FAILOVER tuple already covers this (404 triggers failover to the next configured endpoint) — the
  original single-endpoint config just had no second entry to fail over to. Listing two free models now.
- Status: self-verified PASS on the narrow claim (live HTTP round trip through OpenAICompatReasoner
  works). Per standing rule this is reported as PARTIAL until Icarus independently adjudicates — Claude
  does not award itself PASS. Evidence (run id, commit shas, raw log) is all above for that adjudication.

## 2026-11-03 — Claude: logging incident on this entry, now fixed
- Two prior commits to learned.md on this branch (933924a9, placeholder-string bug; 74f57212,
  manual-retyping corruption of the large base64 payload) were WRONG and are superseded by this commit.
  Root cause: retyping very large (10k+ byte) opaque base64 strings as literal tool-call arguments is not
  reliably error-free for Claude — confirmed via controlled chunk-rehash testing in-session. Fix: restored
  learned.md to its last-known-good blob (efe536c20a62e3775b67b8711619ee02d8283448) by reference via the
  Git Trees API, with no retyping of its content, and logged this new finding as this separate small file
  instead of appending to the large one.
