"""Icarus memory and identity loader.

Core loads identity itself on every run, so a model cannot fail to receive it. No identity, no run.
Recall is a keyword scorer over learned.md, carried over in spirit from Recall v3.
"""
from __future__ import annotations

import math
import os
import re

from .kernel import norm_path

STOP = set(
    "this that with from have been were will would should could there their what when where which about into "
    "your only also than then them they does done make made must need needs more most some such very each both "
    "over under after before again task rule rules read file files state states".split()
)


class IdentityMissing(RuntimeError):
    pass


class MemoryRejected(ValueError):
    pass


def _tokens(s):
    return {t for t in re.findall(r"[a-z0-9_\-]{4,}", s.lower()) if t not in STOP}


class Memory:
    def __init__(self, root, memory_dir="icarus/memory"):
        self.root = os.path.abspath(root)
        self.dir = memory_dir

    def _p(self, name):
        return os.path.join(self.root, self.dir, name)

    def _read(self, name):
        p = self._p(name)
        if not os.path.isfile(p):
            return ""
        with open(p, "r", encoding="utf-8") as f:
            return f.read()

    def identity_text(self):
        ident = self._read("identity.md").strip()
        if not ident:
            raise IdentityMissing("icarus/memory/identity.md is missing or empty; Core refuses to run without identity")
        parts = [ident]
        for name in ("inherited.md", "current-state.md"):
            body = self._read(name).strip()
            if body:
                parts.append(f"## {name}\n{body[:6000]}")
        return "\n\n".join(parts)

    def recall(self, query, k=5, maxchars=6000):
        paras = [p.strip() for p in re.split(r"\n\s*\n", self._read("learned.md")) if p.strip()]
        q = _tokens(query)
        if not paras or not q:
            return ""
        toks = [_tokens(p) for p in paras]
        df = {t: sum(1 for ts in toks if t in ts) for t in q}
        scored = []
        for p, ts in zip(paras, toks):
            s = sum(1.0 / (1 + math.log(df[t])) for t in q & ts if df.get(t))
            if s > 0:
                scored.append((s, p))
        scored.sort(key=lambda x: -x[0])
        out, size = [], 0
        for _, p in scored[:k]:
            if size + len(p) > maxchars:
                break
            out.append(p)
            size += len(p)
        return "\n\n".join(out)

    def write_back(self, entry):
        """Append a lesson only if it carries an `Evidence:` line naming a file that exists (not memory itself)."""
        m = re.search(r"^Evidence:\s*(\S+)", entry, re.MULTILINE)
        if not m:
            raise MemoryRejected("no Evidence line")
        n = norm_path(m.group(1))
        if n is None:
            raise MemoryRejected("Evidence path invalid")
        if n.startswith(self.dir.rstrip("/") + "/"):
            raise MemoryRejected("memory cannot be evidence for itself")
        if not os.path.isfile(os.path.join(self.root, n)):
            raise MemoryRejected(f"Evidence file does not exist: {n}")
        p = self._p("learned.md")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n\n" + entry.strip() + "\n")
