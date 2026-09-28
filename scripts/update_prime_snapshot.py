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
MAX_CHARS = 14000  # measured-safe margin: 15k passed Google Forms edit transport

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

team_room_comments = gh_get("/issues/6/comments?per_page=20")
team_room_lines = []
for comment in team_room_comments[-5:]:
    body = (comment.get("body") or "").strip()
    if body:
        team_room_lines.extend([
            f"### Comment {comment.get('id','')} — @{comment.get('user',{}).get('login','unknown')}",
            body[:700],
            "",
        ])

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
    "## Recent Team Room comments — highest priority",
    "\n".join(team_room_lines),
    "",
    "## Recent canonical chat log — highest priority",
    read_text("CHAT_LOG.md", 6500, tail=True),
    "",
    "## Open Teamchat work",
    "\n".join(issue_lines),
    "",
    "## Current status",
    read_text("STATUS.md", 2200),
    "",
    "## Recent shared training",
    read_text("TRAINING_MATRIX.md", 2200, tail=True),
    "",
    "## Canonical roster / operating definition",
    read_text("README.md", 1600),
    "",
    "## Operating rules — core",
    read_text("OPERATING_RULES.md", 2200),
    "",
    "## Content pipeline",
    read_text("CONTENT_PIPELINE.md", 1400),
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
