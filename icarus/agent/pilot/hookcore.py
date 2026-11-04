"""The hook decision core: path mapping, tool classification, and one default-deny decision function.

This is the policy half of the hook channel (the transport is the next item). It answers one question for
a call a harness is about to run: may it run? The answer is always a plain dict in the contract's shape and the
default is DENY. Nothing here executes anything.

What it adds on top of the Session (session.py) and the kernel:
- PathMapper: DSH sends absolute and Windows paths, but the real kernel only accepts repo-relative POSIX paths.
  The mapper turns a harness path into the kernel's form, or refuses it. It is purely lexical (it cannot see
  symlinks or junctions), refuses parent traversal, drive-relative paths, alternate data streams, UNC paths,
  Windows device names and anything that expands (~, %VAR%, $VAR).
- DSH_TOOLS: every tool in DSH's published catalog, with an effect class. A tool that is not in the table is
  denied. Dangerous classes (exec, code, agent, runtime, net, future, context, history) are denied by default.
- MappedKernelAdapter: the single policy point the Session consults at proposal time and again at execution time:
  classification, class permission, owner-only detection, path requirement, path mapping, protected paths for
  write-class tools, then the real GovernedKernel.
- HookCore.decide: validates the request, finds the session, and calls Session.authorize_execution. Any
  exception, an unreachable ledger or a broken kernel is a denial. A policy denial burns the call. An owner-only
  denial also returns an escalation record; it never waits for the owner.

It imports the M1 kernel and governed modules read-only; session.py stays independent of them.
"""
from __future__ import annotations

import json
import re

from ..governed import redact
from ..kernel import under
from .session import LedgerError, PATH_KEYS, norm_path, path_within

DECISION_ESCALATIONS = {
    "credentials": "decide whether this credential or secret may be used, and supply it yourself if so; Icarus will not open it",
    "security": "decide whether code may be loaded into or changed inside the harness runtime; Icarus will not do it",
    "legal": "make the legal decision yourself",
    "payment": "make or approve the payment yourself",
    "safety": "decide whether this action is safe to take",
}
OWNER_ONLY = frozenset(DECISION_ESCALATIONS)
SECRET_MARKERS = (".env", ".pem", ".credentials", "id_rsa", "id_ed25519", ".dpapi", ".pfx", ".p12", ".kdbx")
SECRET_DIRS = (".ssh", ".aws", ".gnupg", ".kube", ".azure", ".docker")
WINDOWS_DEVICES = frozenset({"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)})
MAPPER_KEYS = set(PATH_KEYS) | {"workdir"}

# name -> (class, package). Source: DSH docs/tool-catalog.md, read 4 Nov 2026 (the first 100,000 of 107,252
# characters; workflow, web_fetch, web_search and todo_write come from its package map). Not the installed version.
DSH_TOOLS = {
    "read": ("read", "dsh-tool-fs"), "read_image": ("read", "dsh-tool-fs"), "glob": ("read", "dsh-tool-fs-search"),
    "grep": ("read", "dsh-tool-fs-search"), "lsp": ("read", "dsh-tool-lsp"),
    "write": ("write", "dsh-tool-fs"), "edit": ("write", "dsh-tool-fs"),
    "str_replace_editor": ("editor", "dsh-tool-str-replace-editor"),
    "todo_write": ("meta", "dsh-tool-todo"), "ask_user_question": ("meta", "dsh-tool-ask-user"),
    "exit_plan_mode": ("meta", "dsh-plan-mode"), "get_goal": ("meta", "dsh-tool-goal"),
    "list_agents": ("meta", "dsh-tool-subagent-control"), "job_list": ("meta", "dsh-tool-jobs"),
    "job_output": ("meta", "dsh-tool-jobs"), "schedule_list": ("meta", "dsh-schedule"),
    "terminal_list": ("meta", "dsh-tool-terminal"), "terminal_read": ("meta", "dsh-tool-terminal"),
    "bash": ("exec", "dsh-tool-bash / dsh-tool-bash-persistent"), "pwsh": ("exec", "dsh-tool-pwsh"),
    "terminal_open": ("exec", "dsh-tool-terminal"), "terminal_send": ("exec", "dsh-tool-terminal"),
    "terminal_signal": ("exec", "dsh-tool-terminal"), "terminal_close": ("exec", "dsh-tool-terminal"),
    "job_kill": ("exec", "dsh-tool-jobs"),
    "run_code": ("code", "dsh-tools"),
    "subagent": ("agent", "dsh-tool-subagent"), "subagent_fork": ("agent", "dsh-tool-subagent"),
    "send_message": ("agent", "dsh-tool-subagent-control"), "interrupt_agent": ("agent", "dsh-tool-subagent-control"),
    "report": ("agent", "dsh-tool-subagent-report"), "ralph": ("agent", "dsh-tool-ralph"),
    "workflow": ("agent", "dsh-tool-workflow"),
    "cordis_define": ("runtime", "dsh-tool-cordis"), "cordis_inspect_list": ("runtime", "dsh-tool-cordis"),
    "cordis_inspect_query": ("runtime", "dsh-tool-cordis"), "cordis_inspect_self": ("runtime", "dsh-tool-cordis"),
    "cordis_run": ("runtime", "dsh-tool-cordis"), "cordis_stop": ("runtime", "dsh-tool-cordis"),
    "cordis_undefine": ("runtime", "dsh-tool-cordis"),
    "web_fetch": ("net", "dsh-tool-web"), "web_search": ("net", "dsh-tool-web"),
    "skill": ("context", "dsh-tool-skill"),
    "create_goal": ("future", "dsh-tool-goal"), "update_goal": ("future", "dsh-tool-goal"),
    "schedule_create": ("future", "dsh-schedule"), "schedule_delete": ("future", "dsh-schedule"),
    "session_event_read": ("history", "dsh-tool-session-query"), "session_event_search": ("history", "dsh-tool-session-query"),
    "session_event_trace": ("history", "dsh-tool-session-query"), "session_search": ("history", "dsh-tool-session-query"),
    "session_trace": ("history", "dsh-tool-session-query"),
}
# the path-bearing parameter(s) of each path tool, from the same catalog
PATH_PARAMS = {"read": ("file_path",), "read_image": ("file_path",), "write": ("file_path",), "edit": ("file_path",),
               "lsp": ("file_path",), "glob": ("path",), "grep": ("path",), "str_replace_editor": ("path",),
               "bash": ("workdir",), "pwsh": ("workdir",), "terminal_open": ("cwd",)}
PATH_REQUIRED_CLASSES = frozenset({"read", "write", "editor"})
DEFAULT_ALLOWED_CLASSES = frozenset({"read", "write", "editor", "meta"})
CLASS_NOTES = {
    "read": "reads files; a path is required so DSH cannot fall back to its own workspace",
    "write": "changes files; protected paths are refused",
    "editor": "view reads, create/str_replace/insert write",
    "meta": "changes only harness bookkeeping or asks the user; no effect outside the harness",
    "exec": "runs commands or controls processes; the effect is not visible in the arguments",
    "code": "runs a program that calls tools; its sub-calls are each gated, the program itself is not scoped",
    "agent": "starts or messages other agents that may use other models",
    "runtime": "loads or changes code inside the harness runtime",
    "net": "reaches the network",
    "context": "loads instructions into the model's context",
    "future": "arranges effects for later",
    "history": "reads other session history",
}


class PathMapper:
    """Maps harness paths to the kernel's repo-relative POSIX form. Lexical only."""

    def __init__(self, root, cwd=None):
        self.root = norm_path(root)
        if self.root is None or not self._absolute(self.root):
            raise ValueError("the mapper root must be an absolute path")
        self.cwd = norm_path(cwd) if cwd else self.root
        if self.cwd is None or not self._absolute(self.cwd) or not path_within(self.cwd, self.root):
            raise ValueError("the mapper cwd must be an absolute path inside the root")

    @staticmethod
    def _absolute(p):
        return p.startswith("/") or re.match(r"^[a-z]:/", p) is not None

    def map(self, raw):
        """(True, relative path) or (False, reason)."""
        if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
            return False, "not a usable path"
        if any(c in raw for c in "~%$"):
            return False, "home, environment and variable expansion are not mapped"
        s = raw.replace("\\", "/")
        if s.startswith("//"):
            return False, "UNC and network paths are not mapped"
        body = re.sub(r"^[A-Za-z]:(?=/)", "", s)
        if ":" in body:
            return False, "drive-relative paths and alternate data streams are not mapped"
        for seg in body.split("/"):
            if seg in ("", ".", ".."):
                continue
            if seg.endswith(".") or seg.endswith(" "):
                return False, "segments ending in a dot or a space are normalised by Windows and are refused"
            if seg.split(".")[0].lower() in WINDOWS_DEVICES:
                return False, "Windows device names are refused"
        n = norm_path(s)
        if n is None:
            return False, "parent traversal or an invalid path"
        if not self._absolute(n):
            n = norm_path(self.cwd.rstrip("/") + "/" + n)
            if n is None:
                return False, "parent traversal or an invalid path"
        if not path_within(n, self.root):
            return False, "outside the kernel workdir"
        rel = n[len(self.root):].lstrip("/")
        if not rel:
            return False, "the workdir root itself is not addressable by the kernel"
        return True, rel


class HookPolicy:
    """Classification and class permission. Everything not listed is denied."""

    def __init__(self, tools=None, allowed_classes=DEFAULT_ALLOWED_CLASSES, extra_secret_markers=()):
        self.tools = dict(DSH_TOOLS if tools is None else tools)
        self.allowed_classes = frozenset(allowed_classes)
        self.secret_markers = SECRET_MARKERS + tuple(extra_secret_markers)

    def classify(self, tool, args):
        entry = self.tools.get(tool)
        if entry is None:
            return None
        cls = entry[0]
        if cls == "editor":
            cmd = args.get("command") if isinstance(args, dict) else None
            return "read" if cmd == "view" else "write"
        return cls

    def owner_only(self, tool, cls, args, raw_paths):
        """(category, detail) or None."""
        if cls == "runtime":
            return "security", f"{tool} loads or changes code inside the harness runtime"
        for p in raw_paths:
            low = str(p).lower().replace("\\", "/")
            segs = [x for x in low.split("/") if x]
            if any(m in low for m in self.secret_markers) or any(d in segs for d in SECRET_DIRS):
                return "credentials", "the call touches a credential or key path"
        try:
            text = json.dumps(args, sort_keys=True, default=str)
        except (TypeError, ValueError):
            return "security", "arguments could not be inspected"
        if redact(text) != text:
            return "credentials", "the arguments contain secret material"
        return None


def extract_paths(args):
    """Every (key, raw value) that names a path. A list value yields one entry per item."""
    out = []
    if not isinstance(args, dict):
        return out
    for k, v in args.items():
        if k not in MAPPER_KEYS:
            continue
        for item in (v if isinstance(v, list) else [v]):
            out.append((k, item))
    return out


class MappedKernelAdapter:
    """What the Session consults for every call. Returns (allowed, reason); a refusal that only the owner can
    resolve is reported as 'OWNER_ONLY:<category>:<detail>'."""

    accepts_phase = True

    def __init__(self, kernel, grant, mapper, policy=None, name="GovernedKernel+DSH"):
        self.kernel, self.grant, self.mapper = kernel, grant, mapper
        self.policy = policy or HookPolicy()
        self.name = name

    def __call__(self, tool, args, phase="proposal"):
        args = args if isinstance(args, dict) else {}
        cls = self.policy.classify(tool, args)
        if cls is None:
            return False, f"UNCLASSIFIED_TOOL: {str(tool)[:60]} is not in the tool table, so it is denied"
        found = extract_paths(args)
        owner = self.policy.owner_only(tool, cls, args, [v for _, v in found])
        if owner:
            return False, f"OWNER_ONLY:{owner[0]}:{owner[1]}"
        if cls not in self.policy.allowed_classes:
            return False, f"CLASS_NOT_ALLOWED: {cls}-class tools are denied by default"
        if cls in PATH_REQUIRED_CLASSES and not [v for k, v in found if k in PATH_PARAMS.get(tool, ()) or tool == "str_replace_editor"]:
            return False, f"PATH_REQUIRED: {tool} must name a path, because DSH would otherwise use its own workspace"
        rels = []
        for key, raw in found:
            ok, res = self.mapper.map(raw)
            if not ok:
                return False, f"PATH_NOT_MAPPABLE: {key}: {res}"
            rels.append(res)
        if cls == "write":
            for rel in rels:
                if any(under(rel, prot) for prot in self.kernel.protected):
                    return False, f"PROTECTED_PATH: {rel}"
        kargs = {"path": rels[0]} if rels else {}
        for extra in rels[1:]:
            d = self.kernel.decide(self.grant, tool, {"path": extra})
            if not d.allowed:
                return False, d.reason
        d = self.kernel.authorize(self.grant, tool, kargs) if phase == "proposal" else self.kernel.decide(self.grant, tool, kargs)
        return d.allowed, d.reason


def coverage_markdown(policy=None):
    """The coverage table, generated from the same table the code uses so the two cannot drift."""
    pol = policy or HookPolicy()
    rows = ["| Tool | Package | Class | Path parameter | Default |", "|---|---|---|---|---|"]
    for name in sorted(pol.tools):
        cls, pkg = pol.tools[name]
        shown = "read or write by command" if cls == "editor" else cls
        default = "allowed" if cls in pol.allowed_classes else "denied"
        if cls == "runtime":
            default = "denied and escalated to the owner as security"
        rows.append(f"| `{name}` | {pkg} | {shown} | {', '.join(PATH_PARAMS.get(name, ())) or '-'} | {default} |")
    notes = ["| Class | What it means |", "|---|---|"] + [f"| {c} | {CLASS_NOTES[c]} |" for c in CLASS_NOTES]
    return "\n".join(rows) + "\n\n" + "\n".join(notes) + "\n"


# Session denials that are deterministic for the same arguments: retrying the same call can never succeed.
BURN_CODES = frozenset({"KERNEL_DENIED", "PATH_OUT_OF_SCOPE", "TOOL_NOT_GRANTED", "RELATIVE_PATH", "BAD_ARGS", "OUT_OF_MILESTONE"})
OWNER_PREFIX = re.compile(r"^OWNER_ONLY:([a-z]+):(.*)$", re.S)


def _reply(decision, code, reason, seq=None, escalation=None):
    return {"decision": decision, "code": code, "reason": str(reason)[:300], "ledger_seq": seq, "escalation": escalation}


class HookCore:
    """Default-deny decision for one pending tool call. Fails closed on anything unexpected."""

    def __init__(self):
        self._sessions = {}

    def register(self, session):
        if not isinstance(getattr(session, "kernel_check", None), MappedKernelAdapter):
            raise ValueError("a hooked session must be opened with a MappedKernelAdapter, so every call is mapped and classified")
        if session.execution != "harness":
            raise ValueError("the hook serves harness-mode sessions only")
        self._sessions[session.session_id] = session

    @staticmethod
    def _shape_problem(req):
        if not isinstance(req, dict):
            return "request must be a JSON object"
        for k in ("session_id", "call_id", "tool"):
            if not isinstance(req.get(k), str) or not req[k]:
                return f"{k} is required"
        if not isinstance(req.get("args"), dict):
            return "args must be a JSON object"
        for k in ("cwd", "harness", "harness_version"):
            if k in req and not isinstance(req[k], str):
                return f"{k} must be a string"
        return None

    def decide(self, req):
        try:
            return self._decide(req)
        except LedgerError as e:
            return _reply("deny", "LEDGER_UNAVAILABLE", f"the decision could not be recorded ({e.code}), so nothing is allowed")
        except Exception as e:  # fail closed: an unexpected error is never an allow
            return _reply("deny", "INTERNAL", f"the decision failed closed ({type(e).__name__})")

    def _decide(self, req):
        problem = self._shape_problem(req)
        if problem:
            return _reply("deny", "BAD_REQUEST", problem)
        sess = self._sessions.get(req["session_id"])
        if sess is None:
            return _reply("deny", "UNKNOWN_SESSION", "no such session is registered")
        if not sess.live_ready:
            return _reply("deny", "NOT_LIVE_READY", "this session is not live ready")
        r = sess.authorize_execution(req["call_id"], req["tool"], req["args"], "harness")
        if r["decision"] == "allow":
            return _reply("allow", "OK", "matches the proposal exactly and passed policy", r["ledger_seq"])
        reason, code = r["reason"], r["code"]
        m = OWNER_PREFIX.match(reason)
        escalation = None
        if m and m.group(1) in OWNER_ONLY:
            cat, detail = m.group(1), m.group(2)
            escalation = {"category": cat, "owner_action": f"OWNER ASSISTANCE REQUIRED - {DECISION_ESCALATIONS[cat]}", "evidence": detail[:200]}
            sess.log_event("hook", "owner_escalation", call_id=req["call_id"], category=cat, evidence=detail[:200])
            sess.burn_call(req["call_id"], "OWNER_ONLY", reason)
            return _reply("deny", "OWNER_ONLY", f"owner-only boundary: {cat}", r["ledger_seq"], escalation)
        if code in BURN_CODES:
            sess.burn_call(req["call_id"], code, reason)
        return _reply("deny", code, reason, r["ledger_seq"])
