#!/usr/bin/env python3
"""Icarus off-laptop runtime v0.

Host: GitHub Actions (EUR 0 within free minutes). Model: Gemini Flash-class via GEMINI_API_KEY
(free tier). Memory: read-only from icarus/memory/. Output: append-only receipt in icarus/runs/.

Constitutional rules enforced here:
- The model never self-awards PASS. Verdict is binary and comes only from deterministic gates
  (VERIFY_FILE / VERIFY_URL lines in the task). No gate supplied => FAIL (unverified).
- No blind retries: each model attempt uses a different candidate model; max 3 calls per run.
- No secrets are printed. Memory is never rewritten, only a new receipt file is added.
"""
import os, re, json, pathlib, datetime, urllib.request, urllib.error

KEY = os.environ.get("GEMINI_API_KEY", "")
BASE = "https://generativelanguage.googleapis.com/v1beta"
RAW = os.environ.get("COMMENT_BODY", "")
CID = os.environ.get("COMMENT_ID", "0")
ACTOR = os.environ.get("COMMENT_ACTOR", "unknown")
NOW = datetime.datetime.now(datetime.timezone.utc)
MAX_CALLS = 4
CALL_TIMEOUT = 75
FAILOVER_CODES = (0, 404, 408, 429, 500, 502, 503, 504)  # 0 = network/timeout


def redact(s):
    return s.replace(KEY, "[REDACTED]") if KEY else s


def read(path, head=0, tail=0):
    p = pathlib.Path(path)
    if not p.is_file():
        return ""
    t = p.read_text(encoding="utf-8", errors="replace")
    if head + tail and len(t) > head + tail:
        return t[:head] + "\n[...trimmed...]\n" + t[-tail:]
    return t


def http(method, url, body=None, timeout=60):
    headers = {}
    if url.startswith(BASE):
        headers = {"x-goog-api-key": KEY, "content-type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # network/timeout
        return 0, str(e)


def candidates():
    code, txt = http("GET", f"{BASE}/models?pageSize=200")
    if code != 200:
        return [], f"model list HTTP {code}"
    out = []
    for m in json.loads(txt).get("models", []):
        n = m["name"].split("/")[-1]
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        if "flash" not in n or any(x in n for x in ("image", "tts", "live", "audio", "robotics", "computer", "embedding", "native")):
            continue
        ver = [-int(x) for x in re.findall(r"\d+", n.split("flash")[0])]
        # explicit stable models first; -latest aliases last; lite (spare capacity) first, newest first within class
        out.append((n.endswith("-latest"), ("preview" in n or "exp" in n), ("lite" not in n), ver, n))
    out.sort()
    return [x[4] for x in out], ""


def gate(line):
    kind, _, val = line.partition(":")
    kind, val = kind.strip(), val.strip()
    if kind == "VERIFY_FILE":
        ok = (".." not in val) and (not val.startswith("/")) and pathlib.Path(val).is_file()
        return ok, f"VERIFY_FILE {val}: exists={ok}"
    if kind == "VERIFY_URL":
        if not val.startswith("https://"):
            return False, f"VERIFY_URL {val}: rejected (https only)"
        c, _ = http("GET", val, timeout=20)
        return c == 200, f"VERIFY_URL {val}: HTTP {c}"
    return False, f"unknown gate {kind}"


def main():
    lines = RAW.splitlines()
    first = lines[0] if lines else ""
    rest = [first[len("ICARUS_RUN"):].strip()] + lines[1:] if first.startswith("ICARUS_RUN") else lines
    gates = [l for l in rest if l.split(":")[0].strip() in ("VERIFY_FILE", "VERIFY_URL")]
    model_override = next((l.split(":", 1)[1].strip() for l in rest if l.startswith("MODEL:")), "")
    task = "\n".join(l for l in rest if l not in gates and not l.startswith("MODEL:")).strip()

    system = (
        "You are Icarus, a persistent autonomous fixer. Memory belongs to Icarus, not the model.\n\n"
        + read("icarus/memory/identity.md") + "\n\n"
        + read("icarus/memory/inherited.md") + "\n\n"
        + read("icarus/memory/current-state.md", 1500, 2500) + "\n\n"
        + "RECENT LEARNED (tail):\n" + read("icarus/memory/learned.md", 0, 3000) + "\n\n"
        "RUNTIME RULES: You run headless on GitHub Actions with NO tools and NO internet. You cannot "
        "execute, send, publish or verify anything. Never claim you did. Never claim PASS; adjudication is "
        "done by the runtime. Answer concisely. Reply ONLY as JSON: "
        '{"answer": string, "unverified_claims": [string], "needs_owner": boolean, "owner_reason": string}.'
    )

    log, answer, used, err = [], None, "none", ""
    if not KEY:
        err = "GEMINI_API_KEY missing"
    elif not task:
        err = "empty task"
    else:
        cands, e = candidates()
        if model_override:
            cands = [model_override]
        if not cands:
            err = e or "no flash-class candidate"
        for n in cands[:MAX_CALLS]:
            body = {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": task}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1500, "responseMimeType": "application/json"},
            }
            code, txt = http("POST", f"{BASE}/models/{n}:generateContent", body, timeout=CALL_TIMEOUT)
            log.append(f"{n}: HTTP {code}" + ("" if code == 200 else f" ({redact(txt)[:90]})"))
            if code == 200:
                try:
                    part = json.loads(txt)["candidates"][0]["content"]["parts"][0]["text"]
                    try:
                        answer = json.loads(part)
                    except Exception:
                        answer = {"answer": part, "unverified_claims": [], "needs_owner": False, "owner_reason": ""}
                    used = n
                    break
                except Exception as ex:
                    err = f"parse error on {n}: {ex}"
            elif code not in FAILOVER_CODES:
                err = f"{n}: HTTP {code} {redact(txt)[:200]}"
                break
        if answer is None and not err:
            err = "all candidate attempts failed: " + "; ".join(log)

    gate_results = [gate(g) for g in gates]
    passed = bool(gate_results) and all(ok for ok, _ in gate_results) and answer is not None
    if not gates:
        reason = "no evidence gate supplied (add VERIFY_FILE:/VERIFY_URL: lines); output is UNVERIFIED"
    elif answer is None:
        reason = "no model output"
    else:
        reason = "all gates passed" if passed else "a gate failed"
    verdict = "PASS" if passed else "FAIL"

    ans = answer if isinstance(answer, dict) else {}
    lines_out = [
        f"# Icarus run {NOW:%Y-%m-%dT%H:%M:%SZ}",
        f"- Proposed by: {ACTOR} (comment {CID})",
        f"- Executed by: Icarus runtime v0 on GitHub Actions; model: {used}",
        f"- Cost: EUR 0 (free-tier model, free Actions minutes)",
        f"- Memory read: icarus/memory/{{identity,inherited,current-state,learned}}.md (read-only)",
        f"- Model attempts: {'; '.join(log) or 'none'}",
        f"- VERDICT: {verdict} - {reason}",
        "",
        "## Task", task or "(empty)", "",
        "## Gates", *(f"- {'ok' if ok else 'FAIL'}: {d}" for ok, d in gate_results), *([] if gate_results else ["- none"]), "",
        "## Model output (UNVERIFIED)", redact(str(ans.get("answer", "")) or f"(none) {err}"), "",
        "## Unverified claims", *(f"- {c}" for c in ans.get("unverified_claims", [])), "",
        f"## Owner needed: {ans.get('needs_owner', False)} {ans.get('owner_reason', '')}",
    ]
    if err:
        lines_out += ["", f"## Error\n{redact(err)}"]
    out = redact("\n".join(lines_out))
    d = pathlib.Path("icarus/runs")
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{NOW:%Y%m%dT%H%M%SZ}-{CID}.md").write_text(out + "\n", encoding="utf-8")
    pathlib.Path("/tmp/icarus-reply.md").write_text(out[:6000], encoding="utf-8")
    print(out[:2000])


if __name__ == "__main__":
    main()
