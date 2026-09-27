#!/usr/bin/env python3
import datetime as dt
import json
import os
import pathlib
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "the1mburke-blip/Teamchat")
TOKEN = os.environ["GITHUB_TOKEN"]
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = pathlib.Path("prime_snapshot_payload.json")
MAX_CHARS = 40000  # stay below Google Sheets' 50,000-character cell limit

def read_text(path, max_chars=None, tail=False):
    p = ROOT / path
    if not p.exists():
        return ""
    value = p.read_text(encoding="utf-8", errors="replace")
    if max_chars is None or len(value) <= max_chars:
        return value
    return value[-max_chars:] if tail else value[:max_chars]

def gh_get(path):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}{path}",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "humanvibe-prime-snapshot",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
marker = f"SNAPSHOT_GENERATED_UTC: {now}"
issues = [x for x in gh_get("/issues?state=open&per_page=100") if "pull_request" not in x]
issues.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

issue_lines = []
for issue in issues[:20]:
    issue_lines.extend([
        f"### #{issue['number']} — {issue.get('title','')}",
        f"State: {issue.get('state','')} | Updated: {issue.get('updated_at','')}",
        (issue.get("body") or "")[:1200],
        "",
    ])

sections = [
    "# HumanVibe Prime Snapshot — LIVE",
    marker,
    f"SOURCE_REPOSITORY: {REPO}",
    f"TRIGGER: {os.environ.get('GITHUB_EVENT_NAME','unknown')}",
    f"RUN_ID: {os.environ.get('GITHUB_RUN_ID','unknown')}",
    "",
    "## Canonical roster / operating definition",
    read_text("README.md", 5000),
    "",
    "## Operating rules — core",
    read_text("OPERATING_RULES.md", 8000),
    "",
    "## Current status",
    read_text("STATUS.md", 4000),
    "",
    "## Content pipeline",
    read_text("CONTENT_PIPELINE.md", 3500),
    "",
    "## Recent canonical chat log",
    read_text("CHAT_LOG.md", 7000, tail=True),
    "",
    "## Recent shared training",
    read_text("TRAINING_MATRIX.md", 6000, tail=True),
    "",
    "## Open Teamchat work",
    "\n".join(issue_lines),
]

snapshot = "\n".join(sections).strip() + "\n"
if len(snapshot) > MAX_CHARS:
    snapshot = snapshot[:MAX_CHARS - 60] + "\n[SNAPSHOT_TRUNCATED_TO_SAFE_CELL_LIMIT]\n"

payload = {
    "run_id": os.environ.get("GITHUB_RUN_ID", "unknown"),
    "marker": marker,
    "sequence": "1",
    "total": "1",
    "snapshot": snapshot,
}
OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
print(f"SNAPSHOT_PAYLOAD_READY chars={len(snapshot)} marker={marker}")
