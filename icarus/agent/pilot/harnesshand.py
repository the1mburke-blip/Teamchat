"""HarnessHand: wires the prober and the tool-builder into one hand GovernedCore can drive.

Every tool still goes through the same unedited kernel.authorize() (protected paths, allowed_paths, budget).
This file adds no authority of its own: it only routes tool names to the piece that handles them.
probe_harness is read-only (see probe.py: no secret file opened, no value stored). write_file/run_tool are
ToolBuilder's (see builder.py: run_tool only runs a file this hand wrote, fixed interpreters, no shell).
"""
from __future__ import annotations

from ..hands import LocalFilesHand
from .builder import ToolBuilder
from .probe import probe as probe_harness


def _evidence_dict(ev):
    return {"kind": ev.kind, "where": ev.where, "detail": ev.detail}


class HarnessHand:
    name = "icarus-harness-hand"

    def __init__(self, workdir, env=None, which=None, guide=None, command=None):
        self.workdir = workdir
        self.files = LocalFilesHand(workdir)
        self.builder = ToolBuilder(workdir)
        self._probe_kwargs = {"env": env, "guide": guide, "command": command}
        if which is not None:
            self._probe_kwargs["which"] = which
        self.executed = []
        self.last_probe = None

    def tools(self):
        return {
            "read_file": self.files.tools()["read_file"],
            "list_dir": self.files.tools()["list_dir"],
            **self.builder.tools(),
            "probe_harness": "args: none. Read-only scan for harness control surfaces (model_slot, approval_channel, "
                             "tool_registry) with evidence; never opens a secrets-named file, never returns a value.",
        }

    def probe(self):
        return {"surfaces": ["read", "write", "process"], "name": self.name}

    def stop(self):
        pass

    def execute(self, tool, args):
        self.executed.append((tool, dict(args) if isinstance(args, dict) else args))
        if tool == "probe_harness":
            r = probe_harness(self.workdir, **{k: v for k, v in self._probe_kwargs.items() if v is not None})
            self.last_probe = r
            return {"ok": True, "harness": r.harness, "status": r.status,
                    "surfaces": {k: [_evidence_dict(e) for e in v] for k, v in r.surfaces.items()},
                    "checked_count": len(r.checked), "skipped_secret_files_count": len(r.skipped_secret_files)}
        if tool in ("read_file", "list_dir"):
            return self.files.execute(tool, args)
        if tool in ("write_file", "run_tool"):
            return self.builder.execute(tool, args)
        return {"ok": False, "error": "unknown tool", "origin": "rule"}
