#!/usr/bin/env python3
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import urllib.parse
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "the1mburke-blip/Teamchat")
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path("prime_snapshot_payload.json")
MAX_CHARS = 14000
TRUNCATION_NOTICE = "\n[SNAPSHOT_TRUNCATED_TO_SAFE_CELL_LIMIT]\n"


def read_text(path, max_chars, tail=False):
    p = ROOT / path
    if not p.exists():
        return ""
    value = p.read_text(encoding="utf-8", errors="replace")
    return value[-max_chars:] if tail else value[:max_chars]


def gh_get(path, *, with_links=False):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}{path}",
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "humanvibe-prime-snapshot",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if with_links:
            return data, resp.headers.get("Link", "")
        return data


def linked_page(links, relation):
    match = re.search(r'<([^>]+)>;\s*rel="' + relation + r'"', links)
    if match:
        return int(urllib.parse.parse_qs(urllib.parse.urlsplit(match[1]).query)["page"][0])
    return None


def latest_team_comments():
    path = "/issues/6/comments?per_page=5"
    comments, links = gh_get(path, with_links=True)
    page = linked_page(links, "last") or 1
    if page > 1:
        comments, links = gh_get(f"{path}&page={page}", with_links=True)
    # A concurrent append can turn the previously last page into an earlier page.
    while next_page := linked_page(links, "next"):
        page = next_page
        comments, links = gh_get(f"{path}&page={page}", with_links=True)
    if page > 1 and len(comments) < 5:
        comments = gh_get(f"{path}&page={page - 1}") + comments
    return comments[-5:][::-1]


def latest_pulse_status():
    runs = gh_get("/actions/workflows/icarus-pulse.yml/runs?branch=main&status=completed&per_page=1")["workflow_runs"]
    if not runs:
        return "unavailable (no completed main run)"
    run = runs[0]
    jobs = gh_get(f"/actions/runs/{run['id']}/jobs")["jobs"]
    runner = next((step for job in jobs for step in job.get("steps", [])
                   if step["name"] == "Execute ICARUS On-Duty Runner"), {})
    return (f"run={run['id']} event={run['event']} workflow={run['conclusion']} "
            f"runner={runner.get('conclusion') or 'unavailable'}")


def main():
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    marker = f"SNAPSHOT_GENERATED_UTC: {now}"
    # The workflow checks out the triggering main SHA with five commits of history.
    commits = subprocess.check_output(
        ["git", "log", "-5", "--oneline"], cwd=ROOT, text=True,
    ).splitlines()
    comments = latest_team_comments()
    pulse_status = latest_pulse_status()
    issues = [x for x in gh_get("/issues?state=open&sort=updated&direction=desc&per_page=100")
              if "pull_request" not in x]

    sections = [
        "# HumanVibe Prime Snapshot — LIVE",
        marker,
        f"SOURCE_REPOSITORY: {REPO}",
        f"TRIGGER: {os.environ.get('GITHUB_EVENT_NAME', 'unknown')}",
        f"RUN_ID: {os.environ.get('GITHUB_RUN_ID', 'unknown')}",
    ]
    if pulse_id := os.environ.get("PULSE_RUN_ID"):
        sections.extend([
            f"PULSE_RUN_ID: {pulse_id}",
            f"PULSE_TRIGGER: {os.environ['PULSE_EVENT']}",
            f"PULSE_CHECKOUT_SHA: {os.environ['PULSE_SHA']}",
        ])
    sections.extend(["", "## Latest main commits", *(commit[:240] for commit in commits),
                     "", "## Latest Pulse runner exit status", pulse_status,
                     "", "## Recent Team Room comments — newest first"])
    for comment in comments:
        login = (comment.get("user") or {}).get("login", "unknown")
        sections.extend([
            f"### Comment {comment['id']} — @{login} | {comment.get('created_at', '')}",
            (comment.get("body") or "").strip()[:700],
            "",
        ])

    issue_lines = []
    for issue in issues[:20]:
        issue_lines.extend([
            f"### #{issue['number']} — {issue.get('title', '')[:200]}",
            f"State: {issue.get('state', '')} | Updated: {issue.get('updated_at', '')}",
            (issue.get("body") or "")[:360],
            "",
        ])
    sections.extend([
        "", "## Open Teamchat work", "\n".join(issue_lines)[:4000],
        "", "## Blog queue state — operational priority", read_text("BLOG_QUEUE_STATE.md", 1000),
        "", "## Current status", read_text("STATUS.md", 900),
        "", "## Operating rules — core", read_text("OPERATING_RULES.md", 850),
        "", "## Content pipeline", read_text("CONTENT_PIPELINE.md", 450),
        "", "## Recent shared training", read_text("TRAINING_MATRIX.md", 600, tail=True),
        "", "## Canonical roster / operating definition", read_text("README.md", 450),
    ])

    snapshot = "\n".join(sections).strip() + "\n"
    # Count UTF-16 units conservatively for Forms, including astral characters.
    encoded = snapshot.encode("utf-16-le")
    if len(encoded) // 2 >= MAX_CHARS:
        budget = MAX_CHARS - len(TRUNCATION_NOTICE) - 1
        snapshot = encoded[:2 * budget].decode("utf-16-le", errors="ignore") + TRUNCATION_NOTICE

    payload = {
        "run_id": os.environ.get("GITHUB_RUN_ID", "unknown"),
        "marker": marker,
        "sequence": "1",
        "total": "1",
        "snapshot": snapshot,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"SNAPSHOT_PAYLOAD_READY chars={len(snapshot)} "
          f"form_units={len(snapshot.encode('utf-16-le')) // 2} marker={marker}")
    # Readback records identifiers only, keeping issue and commit text out of the job log.
    commit_ids = ",".join(line.split()[0] for line in commits)
    comment_ids = ",".join(str(comment["id"]) for comment in comments)
    print(f"SNAPSHOT_TOP_READY commits={commit_ids} issue6_comments={comment_ids} pulse_{pulse_status}")


if __name__ == "__main__":
    main()
