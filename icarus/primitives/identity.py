"""Icarus identity for the daemon: the same memory the pulse (Athena.gs) loads.

Every model the switcher picks gets this as the start of its system prompt, so
whichever model is running, it is Icarus thinking (memory belongs to Icarus,
not the model). Read fresh from the ledger clone each job, so edits to his
memory files take effect on the next job without rebuilding the container.

Mirrors Athena.gs runAthena_ system prompt: identity.md, inherited.md,
current-state.md (head 1500 / tail 2500), learned.md tail 3000,
TRAINING_MATRIX.md tail 3000. Missing files are skipped, never invented.
"""
from __future__ import annotations

from pathlib import Path

OPENING = "You are Icarus, a persistent autonomous fixer. Memory belongs to Icarus, not the model."


def _read(root: Path, rel: str, head: int = 0, tail: int = 0) -> str:
    p = root / rel
    if not p.is_file():
        return ""
    t = p.read_text(encoding="utf-8", errors="replace")
    if (head or tail) and len(t) > head + tail:
        return t[:head] + "\n[...trimmed...]\n" + (t[-tail:] if tail else "")
    return t


def load_identity(root: str | Path) -> str:
    root = Path(root)
    parts = [
        OPENING,
        _read(root, "icarus/memory/identity.md"),
        _read(root, "icarus/memory/inherited.md"),
        _read(root, "icarus/memory/current-state.md", 1500, 2500),
        "RECENT LEARNED (tail):\n" + _read(root, "icarus/memory/learned.md", 0, 3000),
        "RECENT TRAINING (tail of TRAINING_MATRIX.md):\n" + _read(root, "TRAINING_MATRIX.md", 0, 3000),
    ]
    return "\n\n".join(p for p in parts if p.strip())
