#!/usr/bin/env python3
import datetime as dt
import json
import os
import pathlib
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "the1mburke-blip/Teamchat")
TOKEN = os.environ["GITHUB_TOKEN"]
WEBHOOK_SECRET = os.environ["SNAPSHOT_WEBHOOK_SECRET"]
ROOT = pathlib.Path(__file__).resolve().parents[1]
PAYLOAD_PATH = pathlib.Path(os.environ.get("SNAPSHOT_PAYLOAD_PATH", "prime_snapshot_payload.json"))

def read_text(path, max_chars=None):
    p = ROOT / path
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8", errors="replace")
    return text if max_chars is None else text[-max_chars:]

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

def issue_summary(issue):
    return "\n".join([
        f"## #{issue['number']} — {issue.get('title','')}",
        f"State: {issue.get('state','')} | Updated: {issue.get('updated_at','')}",
        (issue.get("body") or "")[:7000],
        "",
    ])

def recent_comments(issue_number, limit=8):
    comments = gh_get(f"/issues/{issue_number}/comments?per_page=100")
    lines = []
    for c in comments[-limit:]:
        author = (c.get("user") or {}).get("login", "unknown")
        created = c.get("created_at", "")
        body = (c.get("body") or "")[:5000]
        lines.append(f"[{created}] {author}\n{body}\n")
    return "\n".join(lines)

now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
marker = f"SNAPSHOT_GENERATED_UTC: {now}"
issues = [x for x in gh_get("/issues?state=open&per_page=100") if "pull_request" not in x]
issues.sort(key=lambda x: x.get("updated_at",""), reverse=True)

sections = [
    "# HumanVibe Prime Snapshot — LIVE",
    "",
    marker,
    f"SOURCE_REPOSITORY: {REPO}",
    f"TRIGGER: {os.environ.get('GITHUB_EVENT_NAME','unknown')}",
    f"RUN_ID: {os.environ.get('GITHUB_RUN_ID','unknown')}",
    "",
    "## Purpose",
    "Machine-maintained context bridge from canonical HumanVibe Teamchat to Gemini Prime. The Google Doc ID is intentionally stable; content is refreshed in place.",
    "",
    "## Canonical roster / operating definition",
    read_text("README.md", 12000),
    "",
    "## Operating rules",
    read_text("OPERATING_RULES.md", 24000),
    "",
    "## Handoff protocol",
    read_text("HANDOFF_PROTOCOL.md", 18000),
    "",
    "## Content pipeline",
    read_text("CONTENT_PIPELINE.md", 16000),
    "",
    "## Current repository status",
    read_text("STATUS.md", 12000),
    "",
    "## Recent canonical chat log",
    read_text("CHAT_LOG.md", 30000),
    "",
    "## Recent shared training",
    read_text("TRAINING_MATRIX.md", 30000),
    "",
    "## Team Room — recent comments",
    recent_comments(6, 30),
    "",
    "## Open Teamchat work",
]
for issue in issues[:30]:
    sections.append(issue_summary(issue))
    if issue["number"] != 6:
        comments = recent_comments(issue["number"], 6)
        if comments:
            sections.extend(["### Recent comments", comments])

snapshot = "\n".join(sections).strip() + "\n"
if len(snapshot) > 450000:
    snapshot = snapshot[:450000] + "\n\n[SNAPSHOT_TRUNCATED_AT_450000_CHARS]\n"

payload = {
    "secret": WEBHOOK_SECRET,
    "marker": marker,
    "snapshot": snapshot,
    "repository": REPO,
    "runId": os.environ.get("GITHUB_RUN_ID", "unknown"),
}
PAYLOAD_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
print(f"SNAPSHOT_PAYLOAD_READY path={PAYLOAD_PATH} chars={len(snapshot)} marker={marker}")
