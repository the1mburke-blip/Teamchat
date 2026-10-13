#!/usr/bin/env python3
"""Icarus off-laptop runtime v0.

Host: GitHub Actions (EUR 0 within free minutes). Model: Gemini Flash-class via GEMINI_API_KEY
(free tier). Memory: read-only from icarus/memory/. Output: append-only receipt in icarus/runs/.

Constitutional rules enforced here:
- The model never self-awards PASS. Verdict is binary and comes only from deterministic gates
  (VERIFY_FILE / VERIFY_URL lines in the task). No gate supplied => FAIL (unverified).
- No blind retries: each model attempt uses a different candidate model; approved routes only (icarus/runtime/approved-routes.json); one 60s cooldown retry on 429/503.
- No secrets are printed. Memory is never rewritten, only a new receipt file is added.
"""
import os, re, json, time, pathlib, datetime, urllib.request, urllib.error

KEY = os.environ.get("GEMINI_API_KEY", "")
BASE = "https://generativelanguage.googleapis.com/v1beta"
RAW = os.environ.get("COMMENT_BODY", "")
CID = os.environ.get("COMMENT_ID", "0")
ACTOR = os.environ.get("COMMENT_ACTOR", "unknown")
NOW = datetime.datetime.now(datetime.timezone.utc)
MAX_CALLS = 6
COOLDOWN = 60  # seconds; one cooldown retry on 429/503, first candidate only (keeps the run inside the Actions timeout)
CALL_TIMEOUT = 60
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


def approved():
    """Only routes listed in icarus/runtime/approved-routes.json (owner-edited). No model discovery."""
    try:
        cfg = json.loads(pathlib.Path("icarus/runtime/approved-routes.json").read_text(encoding="utf-8"))
    except Exception as ex:
        return [], f"approved-routes.json unreadable: {ex}"
    out, seen = [], set()
    for r in cfg.get("routes", []):
        ok = r.get("provider") == "google" and r.get("model") and r.get("approved") is True and r.get("costPolicy") == "verified-zero-cost"
        if not ok or r["model"] in seen:
            return [], f"invalid route entry: {r}"
        seen.add(r["model"])
        out.append(r["model"])
    return out, ("" if out else "no approved routes")


def parse_json(s):
    s = (s or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


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
    list_q = next((l.split(":", 1)[1].strip().lower() for l in rest if l.startswith("LIST_MODELS:")), "")
    task = "\n".join(l for l in rest if l not in gates and not l.startswith("MODEL:") and not l.startswith("LIST_MODELS:")).strip()

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
        cands, e = approved()
        if model_override:
            cands = [model_override] if model_override in cands else []
            e = e or f"MODEL override {model_override} is not an approved route"
        if not cands:
            err = e or "no approved route"
        for idx, n in enumerate(cands[:MAX_CALLS]):
            if n.startswith("gemma"):
                # Gemma on the Gemini API: no systemInstruction / JSON mime mode; fold the system text into the prompt.
                body = {
                    "contents": [{"role": "user", "parts": [{"text": system + "\n\nTASK:\n" + task}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1500},
                }
            else:
                body = {
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": task}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1500, "responseMimeType": "application/json"},
                }
            for tryno in (1, 2):
                code, txt = http("POST", f"{BASE}/models/{n}:generateContent", body, timeout=CALL_TIMEOUT)
                log.append(f"{n}#{tryno}: HTTP {code}" + ("" if code == 200 else f" ({redact(txt)[:90]})"))
                if code in (429, 503) and tryno == 1 and idx == 0:
                    time.sleep(COOLDOWN)
                    continue
                break
            if code == 200:
                try:
                    parts = json.loads(txt)["candidates"][0]["content"]["parts"]
                    part = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                    answer = parse_json(part) or {"answer": part, "unverified_claims": [], "needs_owner": False, "owner_reason": ""}
                    used = n
                    break
                except Exception as ex:
                    err = f"parse error on {n}: {ex}"
            elif code not in FAILOVER_CODES:
                err = f"{n}: HTTP {code} {redact(txt)[:200]}"
                break
        if answer is None and not err:
            err = "all candidate attempts failed: " + "; ".join(log)

    diag = []
    if list_q and KEY:
        c, t = http("GET", f"{BASE}/models?pageSize=200")
        if c == 200:
            for m in json.loads(t).get("models", []):
                nm = m["name"].split("/")[-1]
                if list_q in nm.lower():
                    diag.append(f"- {nm}: {','.join(m.get('supportedGenerationMethods', []))}")
            diag = diag or [f"- no model names contain '{list_q}'"]
        else:
            diag = [f"- model list HTTP {c}"]

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
        *(["## Diagnostics (LIST_MODELS, read-only)", *diag, ""] if diag else []),
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
