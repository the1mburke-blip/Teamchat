"""Minimal environment for anything a job author controls (plan commands, harness commands).

Allowlist, not denylist: the daemon's own environment holds GH_TOKEN, GEMINI_API_KEY and
similar, and job code must never receive them. SYSTEMROOT/WINDIR let Python start on Windows.

Second layer (container only): when ICARUS_JOB_UID is set, job and harness commands run as
that unprivileged uid via setpriv, so they cannot read the daemon's /proc/<pid>/environ
(which holds GH_TOKEN) or the ledger clone. This needs the daemon to run as root with
CAP_SETUID/CAP_SETGID; if ICARUS_JOB_UID is set and the switch is impossible, jobs are
refused (fail closed) rather than run as the daemon. Still not a full sandbox: no network
or filesystem namespace of its own.
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


class JobUidError(RuntimeError):
    pass


def job_uid() -> int | None:
    """The uid jobs must run as, or None when no separate job user is configured."""
    v = os.environ.get("ICARUS_JOB_UID", "").strip()
    if not v:
        return None
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise JobUidError("ICARUS_JOB_UID is set but the daemon is not root; refusing to run "
                          "job code as the daemon user")
    return int(v)


def job_argv(argv: list[str]) -> list[str]:
    uid = job_uid()
    if uid is None:
        return list(argv)
    return ["setpriv", f"--reuid={uid}", f"--regid={uid}", "--clear-groups", "--", *argv]


def hand_over(path: Path) -> None:
    """Give a job dir tree (or one file) to the job uid so the job can use it."""
    uid = job_uid()
    if uid is None:
        return
    path = Path(path)
    for p in [path, *(path.rglob("*") if path.is_dir() else [])]:
        os.chown(p, uid, uid)
