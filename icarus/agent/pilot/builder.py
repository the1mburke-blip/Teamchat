"""ToolBuilder: Icarus writes and runs his own tools, fully inside the existing kernel's grant.

Not a new authority and not a sandbox escape. The write tool is named "write_file" on purpose: the kernel's
WRITE_TOOLS set (kernel.py, unedited) keys its protected-path check on that exact tool name, so this hand's
writes get the SAME protected-path denial as every other hand's, with no change to the kernel. run_tool will
only ever run a file THIS hand wrote in THIS process (tracked in self.written, never restored from disk), with
one of a small fixed set of interpreters invoked as an explicit argv (never a shell string), a timeout and an
output cap. It cannot run an arbitrary pre-existing file or command.

This gives Icarus the "build the missing tool" rung from the owner's own history (writing a script when a
plugin route was blocked by design) without any capability to defeat a harness's sandbox or permission checks.
"""
from __future__ import annotations

import os
import subprocess

from ..kernel import norm_path

ALLOWED_INTERPRETERS = {"python3": ["-I"], "node": []}  # -I: isolated mode, ignores PYTHONPATH/site customizations


class ToolBuilder:
    name = "icarus-tool-builder"

    def __init__(self, workdir, timeout=20, max_out=12000):
        self.workdir = os.path.abspath(workdir)
        self.timeout = timeout
        self.max_out = max_out
        self.written = set()  # repo-relative paths THIS hand has written in THIS run
        self.executed = []

    def tools(self):
        return {
            "write_file": "args: path, content. Writes a tool file. The kernel's own grant and protected-path rules still apply.",
            "run_tool": "args: path (must be a file this hand wrote), interpreter ('python3'|'node'), argv (optional list of extra string args). Returns stdout/stderr/returncode.",
        }

    def probe(self):
        return {"surfaces": ["process"], "name": self.name}

    def stop(self):
        pass

    def _full(self, p):
        n = norm_path(p)
        if n is None:
            return None, None
        return n, os.path.join(self.workdir, n)

    def execute(self, tool, args):
        self.executed.append((tool, dict(args)))
        if tool == "write_file":
            return self._write(args)
        if tool == "run_tool":
            return self._run(args)
        return {"ok": False, "error": "unknown tool", "origin": "rule"}

    def _write(self, args):
        n, full = self._full(args.get("path"))
        if n is None:
            return {"ok": False, "error": "invalid path", "origin": "rule"}
        content = args.get("content")
        if not isinstance(content, str):
            return {"ok": False, "error": "content must be a string", "origin": "rule"}
        os.makedirs(os.path.dirname(full) or self.workdir, exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        self.written.add(n)
        return {"ok": True, "path": n}

    def _run(self, args):
        n, full = self._full(args.get("path"))
        if n is None:
            return {"ok": False, "error": "invalid path", "origin": "rule"}
        if n not in self.written:
            return {"ok": False, "error": "run_tool only runs a file this hand wrote in this run", "origin": "rule"}
        interp = args.get("interpreter")
        if interp not in ALLOWED_INTERPRETERS:
            return {"ok": False, "error": f"interpreter not allowed: {interp!r}", "origin": "rule"}
        extra = args.get("argv", [])
        if not isinstance(extra, list) or not all(isinstance(a, str) for a in extra):
            return {"ok": False, "error": "argv must be a list of strings", "origin": "rule"}
        argv = [interp] + ALLOWED_INTERPRETERS[interp] + [full] + extra
        env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if k in os.environ}
        try:
            p = subprocess.run(argv, cwd=self.workdir, env=env, capture_output=True, text=True, timeout=self.timeout, shell=False)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout"}
        except OSError as e:
            return {"ok": False, "error": type(e).__name__}
        out = {"ok": p.returncode == 0, "returncode": p.returncode,
               "stdout": p.stdout[: self.max_out], "stderr": p.stderr[: self.max_out]}
        if p.returncode != 0:
            lines = [ln for ln in p.stderr.strip().splitlines() if ln.strip()]
            out["error"] = lines[-1][:200] if lines else f"exit {p.returncode}"
        return out
