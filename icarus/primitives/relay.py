"""Early verdict notice: the daemon tells the job's source issue as soon as the verifier settles.

Athena's ledger relay (pulse, every 10 minutes) stays the canonical verdict. This only removes
the wait: the notice is posted seconds after settle instead of up to ~20 minutes later.

- Prefix "[ICARUS via runtime]" is in Athena's OWN_OUTPUT pattern, so the notice can never
  trigger Athena; the text avoids "Ledger job" so nobody mistakes it for the canonical relay.
- It relays the verifier's receipt verdict; the daemon never grades anything itself.
- Runs in the daemon process with GH_TOKEN; job processes never see the token.
- Any failure is returned as False and logged by the caller; it never stops the daemon.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

PREFIX = "[ICARUS via runtime] [laptop-daemon early notice]"
API = "https://api.github.com"


def notice_body(job_id: str, status: str, receipt: dict, attempts: int, utc: str) -> str:
    verdict = receipt.get("verdict", "?")
    reasons = (receipt.get("gate_1_technical", {}).get("reasons", [])
               + receipt.get("gate_2_policy", {}).get("reasons", []))
    lines = [f"{PREFIX} Job `{job_id}` settled at {utc}: verifier verdict **{verdict}**, "
             f"ledger status `{status}` (attempt {attempts}).",
             f"Verifier: {receipt.get('verifier', '?')} (not self-awarded)."]
    if reasons:
        lines.append("Reasons: " + "; ".join(str(r) for r in reasons)[:600])
    lines.append("Athena's ledger relay follows at her next poll and is the canonical verdict.")
    return "\n".join(lines)


def post_notice(repo: str, token: str, issue: int, body: str, opener=urllib.request.urlopen) -> bool:
    if not (repo and token and isinstance(issue, int) and issue > 0):
        return False
    req = urllib.request.Request(
        f"{API}/repos/{repo}/issues/{issue}/comments", method="POST",
        data=json.dumps({"body": body}).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "User-Agent": "icarus-daemon", "Content-Type": "application/json"})
    try:
        with opener(req, timeout=20) as r:
            return r.status == 201
    except (urllib.error.URLError, OSError, ValueError):
        return False
