"""Prober: finds which control surfaces a harness exposes, with evidence.

Icarus runs this on whatever he is plugged into. It reads, never writes. It never opens secret files and never
stores a value (only that a key or variable exists), so its output is safe to log and to show a reasoner.
Result is FOUND (at least one surface, with evidence) or BLOCKED (nothing found, with what was checked).
"""
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field

GUIDE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fieldguide.json")
SECRET_MARKERS = (".env", ".pem", ".credentials", "id_rsa", ".dpapi", "auth.json", "credentials", "secret", "token")


def load_guide(path=GUIDE_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_secret_name(path):
    base = os.path.basename(path).lower()
    return any(m in base for m in SECRET_MARKERS)


@dataclass(frozen=True)
class Evidence:
    kind: str  # env | config_key | binary | command
    where: str  # variable name, repo-relative file, or binary name
    detail: str  # key name or note; never a value


@dataclass
class ProbeResult:
    harness: str  # best match from the field guide, or "unknown"
    status: str  # FOUND | BLOCKED
    surfaces: dict = field(default_factory=dict)  # surface name -> [Evidence]
    checked: list = field(default_factory=list)  # what was looked at, for BLOCKED evidence
    skipped_secret_files: list = field(default_factory=list)


def _default_read(path, max_bytes):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(max_bytes)


def _candidate_files(root, guide):
    scan = guide["scan"]
    seen, out = set(), []

    def add(rel):
        if rel not in seen:
            seen.add(rel)
            out.append(rel)

    for h in guide["known_harnesses"].values():
        for rel in h.get("config_files", []):
            add(rel)
    for rel in guide.get("generic_files", []):
        add(rel)
    # shallow scan of dot-directories so an unknown harness's config can still be found
    root_abs = os.path.abspath(root)
    count = 0
    for dirpath, dirnames, filenames in os.walk(root_abs):
        depth = 0 if dirpath == root_abs else dirpath[len(root_abs):].count(os.sep)
        rel_dir = os.path.relpath(dirpath, root_abs)
        dirnames[:] = [d for d in dirnames if d not in scan["skip_dirs"] and (depth > 0 or d.startswith("."))]
        if depth >= scan["max_depth"]:
            dirnames[:] = []
        if depth == 0:
            continue  # only inside dot-directories, not the whole project
        for fn in sorted(filenames):
            if os.path.splitext(fn)[1].lower() in scan["extensions"]:
                add(os.path.normpath(os.path.join(rel_dir, fn)).replace(os.sep, "/"))
                count += 1
                if count >= scan["max_files"]:
                    return out
    return out


def probe(root, env=None, which=shutil.which, guide=None, read=None, command=None):
    """Probe `root` (a home or project directory). `env`, `which`, `read` are injectable so tests need no real harness."""
    guide = guide or load_guide()
    env = os.environ if env is None else env
    max_bytes = guide["scan"]["max_bytes"]
    read = read or (lambda p: _default_read(p, max_bytes))
    res = ProbeResult(harness="unknown", status="BLOCKED")

    def add(surface, ev):
        res.surfaces.setdefault(surface, []).append(ev)

    # environment: names only, never values
    for surface, spec in guide["surfaces"].items():
        for name in spec.get("env", []):
            res.checked.append(f"env:{name}")
            if name in env:
                add(surface, Evidence("env", name, "set"))

    # config files: key names only
    for rel in _candidate_files(root, guide):
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            continue
        if is_secret_name(rel):
            res.skipped_secret_files.append(rel)
            continue
        res.checked.append(f"file:{rel}")
        try:
            if os.path.getsize(full) > max_bytes:
                continue
            text = read(full)
        except OSError:
            continue
        for surface, spec in guide["surfaces"].items():
            for key in spec.get("config_keys", []):
                if re.search(r"""["']?\b""" + re.escape(key) + r"""\b["']?\s*[:=]""", text):
                    add(surface, Evidence("config_key", rel, key))

    # harness identity and the process surface
    best, best_score = "unknown", 0
    for name, h in guide["known_harnesses"].items():
        score = 0
        for b in h.get("binaries", []):
            res.checked.append(f"binary:{b}")
            if which(b):
                score += 2
                add("process", Evidence("binary", b, "on PATH"))
        for rel in h.get("config_files", []):
            if os.path.isfile(os.path.join(root, rel)):
                score += 1
        if score > best_score:
            best, best_score = name, score
    res.harness = best
    if command:
        res.checked.append(f"command:{command}")
        if os.path.isfile(command) or which(command):
            add("process", Evidence("command", command, "given by the caller"))
    res.status = "FOUND" if res.surfaces else "BLOCKED"
    return res
