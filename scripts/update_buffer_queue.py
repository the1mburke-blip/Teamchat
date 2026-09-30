#!/usr/bin/env python3
import datetime as dt
import json
import os
import pathlib
import urllib.error
import urllib.request

API_URL = "https://api.buffer.com"
ORG_ID = "6a9c0a7f6f15c41f1586b30f"
CHANNELS = {
    "6a9c0c92065799be469311a5": ("Facebook", "facebook"),
    "6a9c0c16065799be46930ff2": ("Instagram", "instagram"),
    "6a9c1052065799be46931ec8": ("Threads", "threads"),
}
TARGET_PER_CHANNEL = 9
REFILL_THRESHOLD = 6
OUT_MD = pathlib.Path("BUFFER_QUEUE_STATE.md")
OUT_JSON = pathlib.Path("buffer_queue_state.json")

def gql_string(value):
    return json.dumps(value, ensure_ascii=False)

def fetch_page(token, after=None):
    channel_ids = ", ".join(gql_string(x) for x in CHANNELS)
    after_arg = "" if after is None else f", after: {gql_string(after)}"
    query = f"""
    query QueueSnapshot {{
      posts(
        first: 100{after_arg}
        input: {{
          organizationId: {gql_string(ORG_ID)}
          filter: {{
            status: [scheduled]
            channelIds: [{channel_ids}]
          }}
          sort: [{{ field: dueAt, direction: asc }}]
        }}
      ) {{
        edges {{
          node {{
            id
            status
            dueAt
            channelId
          }}
        }}
        pageInfo {{
          hasNextPage
          endCursor
        }}
      }}
    }}
    """
    request = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "HumanVibe-Buffer-Queue-Monitor/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise SystemExit(f"Buffer HTTP {exc.code}: {detail}") from exc
    if body.get("errors"):
        raise SystemExit("Buffer GraphQL error: " + json.dumps(body["errors"])[:2000])
    posts = body.get("data", {}).get("posts")
    if not isinstance(posts, dict):
        raise SystemExit("Buffer response missing data.posts")
    return posts

def main():
    token = os.environ.get("BUFFER_API_KEY", "").strip()
    if not token:
        raise SystemExit("BUFFER_API_KEY missing")

    edges = []
    after = None
    for _ in range(10):
        page = fetch_page(token, after)
        edges.extend(page.get("edges") or [])
        info = page.get("pageInfo") or {}
        if not info.get("hasNextPage"):
            break
        after = info.get("endCursor")
        if not after:
            raise SystemExit("Buffer pagination said hasNextPage without endCursor")
    else:
        raise SystemExit("Buffer pagination exceeded 10 pages; stop for review")

    posts = []
    for edge in edges:
        node = (edge or {}).get("node") or {}
        channel_id = str(node.get("channelId") or "")
        if channel_id not in CHANNELS:
            continue
        posts.append({
            "id": str(node.get("id") or ""),
            "status": str(node.get("status") or ""),
            "dueAt": node.get("dueAt"),
            "channelId": channel_id,
        })

    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    per_channel = {}
    needs_refill = False
    for channel_id, (name, service) in CHANNELS.items():
        scheduled = [p for p in posts if p["channelId"] == channel_id]
        scheduled.sort(key=lambda p: p.get("dueAt") or "")
        count = len(scheduled)
        state = "CRITICAL" if count < REFILL_THRESHOLD else ("LOW" if count < TARGET_PER_CHANNEL else "OK")
        if count < REFILL_THRESHOLD:
            needs_refill = True
        per_channel[channel_id] = {
            "name": name,
            "service": service,
            "scheduled_posts": count,
            "target": TARGET_PER_CHANNEL,
            "state": state,
            "next_due_utc": scheduled[0].get("dueAt") if scheduled else None,
        }

    payload = {
        "generated_utc": now,
        "source": "Buffer API live read",
        "organization_id": ORG_ID,
        "target_per_channel": TARGET_PER_CHANNEL,
        "refill_threshold": REFILL_THRESHOLD,
        "needs_refill": needs_refill,
        "channels": per_channel,
        "posts": posts,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# HumanVibe Buffer Queue State",
        "",
        f"SNAPSHOT_GENERATED_UTC: {now}",
        "SOURCE: Buffer API live read",
        "AUTO_REFRESH: ACTIVE",
        f"NEEDS_REFILL: {'YES' if needs_refill else 'NO'}",
        f"TARGET: {TARGET_PER_CHANNEL} scheduled posts per channel",
        f"REFILL_THRESHOLD: below {REFILL_THRESHOLD} scheduled posts on any channel",
        "",
        "| Channel | Scheduled | Target | State | Next due UTC |",
        "|---|---:|---:|---|---|",
    ]
    for channel_id, (name, _) in CHANNELS.items():
        item = per_channel[channel_id]
        lines.append(
            f"| {name} | {item['scheduled_posts']} | {TARGET_PER_CHANNEL} | "
            f"{item['state']} | {item['next_due_utc'] or 'NONE'} |"
        )
    lines += [
        "",
        "PRIME_ACTION_IF_NEEDS_REFILL: Before generating a refill handoff, perform the current daily HumanVibe research/status scan. Then route the refill task through the established Prime -> Grace handoff. This monitor is read-only and must not publish.",
        "",
        "## Scheduled posts",
    ]
    if posts:
        for post in sorted(posts, key=lambda p: (p.get("dueAt") or "", p.get("channelId") or "")):
            name = CHANNELS[post["channelId"]][0]
            lines.append(f"- {post['dueAt'] or 'NO_DUE_AT'} | {name} | {post['id']}")
    else:
        lines.append("- NONE")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"BUFFER_QUEUE_STATE_READY posts={len(posts)} needs_refill={needs_refill}")

if __name__ == "__main__":
    main()
