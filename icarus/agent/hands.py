"""Hands: executors Core drives. A hand does what Core's kernel allowed, and nothing else.

LocalFilesHand is the reference hand (files under a workdir). Harness adapters (dsh, Claude Code, Codex,
Hermes, MCP) implement the same contract in later milestones: tools(), execute(), probe(), stop().
"""
from __future__ import annotations

import os

from .kernel import norm_path


class LocalFilesHand:
    def __init__(self, workdir):
        self.workdir = os.path.abspath(workdir)
        self.executed = []  # every call that actually reached the hand

    def tools(self):
        return {
            "read_file": "args: path. Returns file text.",
            "list_dir": "args: path. Returns entry names.",
            "write_file": "args: path, content. Writes a file.",
        }

    def probe(self):
        return {"surfaces": ["process"], "name": "local-files"}

    def _full(self, p):
        n = norm_path(p)
        if n is None:
            raise ValueError("invalid path")
        return os.path.join(self.workdir, n)

    def execute(self, tool, args):
        self.executed.append((tool, dict(args)))
        if tool == "read_file":
            with open(self._full(args["path"]), "r", encoding="utf-8") as f:
                return {"ok": True, "content": f.read()[:12000]}
        if tool == "list_dir":
            return {"ok": True, "entries": sorted(os.listdir(self._full(args["path"])))}
        if tool == "write_file":
            p = self._full(args["path"])
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(str(args.get("content", "")))
            return {"ok": True}
        return {"ok": False, "error": "unknown tool"}

    def stop(self):
        pass
