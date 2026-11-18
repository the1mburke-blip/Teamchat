"""Minimal environment for anything a job author controls (plan commands, harness commands).

Allowlist, not denylist: the daemon's own environment holds GH_TOKEN, GEMINI_API_KEY and
similar, and job code must never receive them. SYSTEMROOT/WINDIR let Python start on Windows.

This removes credentials from the job's environment. It is NOT a sandbox: job code runs as
the daemon's uid and can still read files (e.g. /proc/<pid>/environ) and start processes.
"""
from __future__ import annotations

import os
from pathlib import Path

PASS_THROUGH = ("PATH", "LANG", "LC_ALL", "TZ", "SYSTEMROOT", "WINDIR")


def job_env(job_dir: Path) -> dict:
    env = {k: os.environ[k] for k in PASS_THROUGH if k in os.environ}
    d = str(Path(job_dir).resolve())
    env.update({"HOME": d, "USERPROFILE": d, "TMPDIR": d, "TEMP": d, "TMP": d,
                "PYTHONNOUSERSITE": "1"})
    return env
