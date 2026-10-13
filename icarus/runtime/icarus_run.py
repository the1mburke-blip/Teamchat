#!/usr/bin/env python3
"""Icarus off-laptop runtime v0.

Host: GitHub Actions (EUR 0 within free minutes). Model: Gemini Flash-class via GEMINI_API_KEY
(free tier). Memory: read-only from icarus/memory/. Output: append-only receipt in icarus/runs/.

Constitutional rules enforced here:
- The model never self-awards PASS. Verdict is binary and comes only from deterministic gates
  (VERIFY_FILE / VERIFY_URL lines in the task). No gate supplied => FAIL (unverified).
- No blind retries: each model attempt uses a different candidate model; approved routes only (icarus/runtime/approved-routes.json); one 90s cooldown retry on 429/503 for every model; pool exhausted => 180s break then reset the pool (max 3 rounds).
- No secrets are printed. Memory is never rewritten, only a new receipt file is added.
"""
import os, re, json, time, pathlib, datetime, urllib.request, urllib.error, urllib.parse

KEY = os.environ.get("GEMINI_API_KEY", "")
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OR_BASE = "https://openrouter.ai/api/v1"
PROVIDER = {}  # model id -> provider, filled by approved()
SKIPPED = []
BASE = "https://generativelanguage.googleapis.com/v1beta"
RAW = os.environ.get("COMMENT_BODY", "")
CID = os.environ.get("COMMENT_ID", "0")
ACTOR = os.environ.get("COMMENT_ACTOR", "unknown")
NOW = datetime.datetime.now(datetime.timezone.utc)
MAX_CALLS = 9
COOLDOWN = 90  # seconds; per-minute peak window reset: one cooldown retry on 429/503 for EVERY model in EVERY round
POOL_BREAK = 180  # seconds; when the whole pool is exhausted: take a break, then reset the pool and go again
MAX_ROUNDS = 3  # initial pass + 2 pool resets (bounded so the job cannot run forever on free Actions minutes)
CALL_TIMEOUT = 60
FAILOVER_CODES = (0, 404, 408, 429, 500, 502, 503, 504)  # 0 = network/timeout


def redact(s):
    for k in (KEY, OR_KEY):
        if k:
            s = s.replace(k, "[REDACTED]")
    return s


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
    elif url.startswith(OR_BASE):
        headers = {"Authorization": "Bearer " + OR_KEY, "content-type": "application/json"}
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
        prov = r.get("provider")
        ok = prov in ("google", "openrouter") and r.get("model") and r.get("approved") is True and r.get("costPolicy") == "verified-zero-cost"
        if ok and prov == "openrouter" and not str(r["model"]).endswith(":free"):
            ok = False  # OpenRouter: free (:free) variants only
        if not ok or r["model"] in seen:
            return [], f"invalid route entry: {r}"
        seen.add(r["model"])
        if prov == "openrouter" and not OR_KEY:
            SKIPPED.append(r["model"])
            continue
        PROVIDER[r["model"]] = prov
        out.append(r["model"])
    return out, ("" if out else "no approved routes")


START = time.time()
STATE = {"calls": 0}
DEFAULT_CFG = {
    "dailyRunCap": 30,
    "maxApiCallsPerRun": 24,
    "maxRuntimeSeconds": 3000,
    "verifyUrlHosts": ["github.com", "raw.githubusercontent.com", "api.github.com"],
    "riskyActionPattern": r"\b(publish|post to|send (?:an? )?(?:email|message|dm)|delete|purchase|buy|pay|transfer|deploy|force.push|wipe)\b",
}


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        cfg.update(json.loads(pathlib.Path("icarus/runtime/enforcement.json").read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


CFG = load_cfg()


def over_budget(extra=0):
    if STATE["calls"] >= CFG["maxApiCallsPerRun"]:
        return f"call budget exhausted ({STATE['calls']}/{CFG['maxApiCallsPerRun']})"
    if time.time() - START + extra > CFG["maxRuntimeSeconds"]:
        return f"runtime budget would be exceeded ({int(time.time() - START)}s + {extra}s > {CFG['maxRuntimeSeconds']}s)"
    return ""


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
        host = urllib.parse.urlparse(val).hostname or ""
        if host not in CFG["verifyUrlHosts"]:
            return False, f"VERIFY_URL {val}: host '{host}' not on the allowlist (icarus/runtime/enforcement.json)"
        c, _ = http("GET", val, timeout=20)
        return c == 200, f"VERIFY_URL {val}: HTTP {c}"
    return False, f"unknown gate {kind}"


def main():
    lines = RAW.splitlines()
    first = lines[0] if lines else ""
    rest = [first[len("ICARUS_RUN"):].strip()] + lines[1:] if first.startswith("ICARUS_RUN") else lines
    gates = [l for l in rest if l.split(":")[0].strip() in ("VERIFY_FILE", "VERIFY_URL")]
    model_override = next((l.split(":", 1)[1].strip() for l in rest if l.startswith("MODEL:")), "")
    try:
        inject = int(next((l.split(":", 1)[1].strip() for l in rest if l.startswith("TEST_EXHAUST_ROUNDS:")), "0") or 0)
    except Exception:
        inject = 0
    try:
        test_cap = int(next((l.split(":", 1)[1].strip() for l in rest if l.startswith("TEST_MAX_CANDIDATES:")), "0") or 0)
    except Exception:
        test_cap = 0
    list_q = next((l.split(":", 1)[1].strip().lower() for l in rest if l.startswith("LIST_MODELS:")), "")
    task = "\n".join(l for l in rest if l not in gates and not l.startswith("MODEL:") and not l.startswith("LIST_MODELS:") and not l.startswith("TEST_EXHAUST_ROUNDS:") and not l.startswith(("TEST_MAX_CANDIDATES:", "TEST_CAP_RUNS:", "TEST_CAP_CALLS:", "TEST_DEADLINE:", "OWNER_APPROVED:"))).strip()

    def hook(name):
        v = next((l.split(":", 1)[1].strip() for l in rest if l.startswith(name + ":")), "")
        return int(v) if v.isdigit() else None

    test_notes = []
    for hk, key in (("TEST_CAP_RUNS", "dailyRunCap"), ("TEST_CAP_CALLS", "maxApiCallsPerRun"), ("TEST_DEADLINE", "maxRuntimeSeconds")):
        hv = hook(hk)
        if hv is not None:
            CFG[key] = hv
            test_notes.append(f"{hk}={hv}")
    if inject:
        test_notes.append(f"TEST_EXHAUST_ROUNDS={inject}")
    if test_cap:
        test_notes.append(f"TEST_MAX_CANDIDATES={test_cap}")
    approved_line = next((l.split(":", 1)[1].strip() for l in rest if l.startswith("OWNER_APPROVED:")), "")
    risky = re.search(CFG["riskyActionPattern"], task, re.I)
    today = list(pathlib.Path("icarus/runs").glob(f"{NOW:%Y%m%d}T*.md")) if pathlib.Path("icarus/runs").is_dir() else []
    daily = len(today)
    stop_pre = ""
    if daily >= CFG["dailyRunCap"]:
        stop_pre = f"HARD STOP: daily run cap reached ({daily}/{CFG['dailyRunCap']})"
    elif risky and not approved_line:
        stop_pre = f"HARD STOP: owner approval required for action '{risky.group(0)}' (add an OWNER_APPROVED: <what you approve> line)"

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
    if stop_pre:
        err = stop_pre
    elif not KEY:
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
        hard = False
        if SKIPPED:
            log.append("openrouter routes skipped (OPENROUTER_API_KEY not set): " + ", ".join(SKIPPED))
        for rnd in range(1, MAX_ROUNDS + 1):
            if rnd > 1:
                why = over_budget(POOL_BREAK)
                if why:
                    err = "HARD STOP: " + why
                    hard = True
                    break
                log.append(f"pool exhausted -> {POOL_BREAK}s break, then pool reset (round {rnd}/{MAX_ROUNDS})")
                time.sleep(POOL_BREAK)
                err = ""
            for idx, n in enumerate(cands[:(test_cap or MAX_CALLS)]):
                is_or = PROVIDER.get(n) == "openrouter"
                if is_or:
                    body = {"model": n, "temperature": 0.2, "max_tokens": 1500,
                            "messages": [{"role": "system", "content": system}, {"role": "user", "content": task}]}
                elif n.startswith("gemma"):
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
                    why = over_budget(0)
                    if why:
                        err = "HARD STOP: " + why
                        hard = True
                        break
                    STATE["calls"] += 1
                    injected = rnd <= inject
                    if injected:
                        code, txt = 503, "injected test failure (no API call; TEST_EXHAUST_ROUNDS)"
                    else:
                        url = f"{OR_BASE}/chat/completions" if is_or else f"{BASE}/models/{n}:generateContent"
                        code, txt = http("POST", url, body, timeout=CALL_TIMEOUT)
                    log.append(f"{n}#{tryno}: HTTP {code}" + ("" if code == 200 else f" ({redact(txt)[:90]})"))
                    if code in (429, 503) and tryno == 1:
                        why = over_budget(COOLDOWN)
                        if why:
                            err = "HARD STOP: " + why
                            hard = True
                            break
                        time.sleep(COOLDOWN)
                        continue
                    break
                if hard:
                    break
                if code == 200:
                    try:
                        if is_or:
                            part = json.loads(txt)["choices"][0]["message"].get("content") or ""
                            if not part.strip():
                                raise ValueError("empty OpenRouter content")
                        else:
                            parts = json.loads(txt)["candidates"][0]["content"]["parts"]
                            part = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                        answer = parse_json(part) or {"answer": part, "unverified_claims": [], "needs_owner": False, "owner_reason": ""}
                        used = n
                        break
                    except Exception as ex:
                        err = f"parse error on {n}: {ex}"
                elif code not in FAILOVER_CODES and not is_or:
                    err = f"{n}: HTTP {code} {redact(txt)[:200]}"
                    hard = True
                    break
            if answer is not None or hard:
                break
        if answer is None and not err:
            err = f"pool exhausted after {MAX_ROUNDS} rounds: " + "; ".join(log)

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
        f"- Enforcement: API calls {STATE['calls']}/{CFG['maxApiCallsPerRun']}; runtime {int(time.time() - START)}s/{CFG['maxRuntimeSeconds']}s; runs today {daily}/{CFG['dailyRunCap']}; tools: none (allowlist empty)",
        *([f"- TEST HOOKS ACTIVE (owner-set): {', '.join(test_notes)}"] if test_notes else []),
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
