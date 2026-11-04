"""Shared authority for the pilot surfaces (model slot, hook channel, supervisor).

One Session per task. Every surface asks the Session and writes to the Session's ledger.

Authority model (owner directive for checkpoint 3):
- The owner signs a Charter: Icarus's objectives and boundaries, plus the registry of principals.
- Icarus (role adjudicator) issues sessions to executing agents without owner approval for routine work,
  but only inside the charter (attenuation: a session can never exceed the charter).
- An agent can never grant itself anything and can never approve its own work. Issuance and review decisions
  are Ed25519 signatures checked against keys in the owner-signed charter. Names inside a record are never authority.
- Icarus can review delegated work. His own work (a session where he is the executor) needs an owner or
  independent verifier decision.
- A checkpoint plan, when present, makes review gates mandatory (PAUSED_FOR_REVIEW until a signed decision).
- No code path here writes PASS. Only an independent adjudicator outside this module can.
- Spend defaults to EUR 0 and can never exceed the charter.

Self-contained on purpose: standard library only, plus an optional Ed25519 verifier from `cryptography`.
It imports nothing from the M1 modules (kernel, core, memory, hands, reasoners, governed).
If no vetted Ed25519 verifier is available, anything that needs a signature fails closed (BLOCKED_NO_VERIFIER).

Ordering rule: a transition that grants something (authorize, record, resume) is persisted to the ledger BEFORE
state changes, so a failed write can never leave an authorized or completed call. A transition that restricts
(burn a call, pause for review, close) changes state first, so a failed write can only make the session stricter.
A ledger that fails a write is marked broken and refuses every later write (LEDGER_BROKEN). A kernel decision is
required for every call: Session.open refuses to start without one unless the caller says so explicitly, and a
session started that way is never live_ready.

Known limits (CP3): a ledger is new per session (no resume from disk; scheduled for checkpoint 8); nonces are per process; path scoping
only covers arguments under the known path keys, so shell-like tools must not be granted; key custody is an
operational matter this module cannot prove.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone

ROLES = ("owner", "adjudicator", "verifier")
ISSUER_ROLES = ("owner", "adjudicator")
DECISIONS = ("resume", "rework", "stop")
EXEC_KINDS = ("proposal", "execution_authorized", "tool_result", "milestone_reached")
PATH_KEYS = {"path", "file", "filepath", "file_path", "dir", "directory", "cwd", "target", "dest",
             "destination", "source", "src"}
STATES = ("ACTIVE", "PAUSED_FOR_REVIEW", "CLOSED_COMPLETE", "CLOSED_STOPPED")  # deliberately no PASS
GENESIS = "0" * 64
DEFAULT_SPEND_EUR = 0
SIDE_FILE_CAP = 65536


class AuthorityError(Exception):
    def __init__(self, code, message=""):
        self.code = code
        super().__init__(f"{code}: {message}" if message else code)


class LedgerError(AuthorityError):
    pass


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(public_key_b64):
    return "sha256:" + sha256_hex(base64.b64decode(public_key_b64, validate=True))


def _utc_now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value):
    if not isinstance(value, str):
        raise AuthorityError("BAD_TIMESTAMP", "timestamp must be a string")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        raise AuthorityError("BAD_TIMESTAMP", value)


# ---------------------------------------------------------------- signatures

class Ed25519Verifier:
    """Verifies Ed25519 signatures against public keys only. Never holds a private key."""

    def __init__(self):
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            self._key_cls = Ed25519PublicKey
            self._invalid = InvalidSignature
            self.available = True
        except Exception:
            self.available = False

    def verify(self, public_key_b64, message, signature_b64):
        if not self.available:
            raise AuthorityError("BLOCKED_NO_VERIFIER", "no vetted Ed25519 verifier is available; there is no weaker fallback")
        try:
            raw = base64.b64decode(public_key_b64, validate=True)
            sig = base64.b64decode(signature_b64, validate=True)
        except Exception:
            return False
        if len(raw) != 32 or len(sig) != 64:
            return False
        try:
            self._key_cls.from_public_bytes(raw).verify(sig, message)
            return True
        except self._invalid:
            return False
        except Exception:
            return False


def _need_verifier(verifier):
    if verifier is None or not getattr(verifier, "available", False):
        raise AuthorityError("BLOCKED_NO_VERIFIER", "no vetted Ed25519 verifier is available; there is no weaker fallback")


def _unsigned(record):
    return {k: v for k, v in record.items() if k != "signature"}


# ---------------------------------------------------------------- paths and grants

def norm_path(p):
    """Normalised path, or None. Parent traversal is never normalised away: it is refused."""
    if not isinstance(p, str) or not p or "\x00" in p:
        return None
    s = p.replace("\\", "/")
    drive = ""
    m = re.match(r"^([A-Za-z]):(/|$)", s)
    if m:
        drive = m.group(1).lower() + ":"
        s = s[2:]
    absolute = s.startswith("/")
    parts = []
    for seg in s.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            return None
        parts.append(seg)
    out = drive + ("/" if absolute else "") + "/".join(parts)
    return out.lower() if drive else out


def path_within(child, parent):
    c, p = norm_path(child), norm_path(parent)
    if c is None or p is None:
        return False
    p = p.rstrip("/")
    return c == p or c.startswith(p + "/")


def _check_grants_shape(g, where):
    if not isinstance(g, dict):
        raise AuthorityError("BAD_GRANTS", where)
    if not isinstance(g.get("tools", []), list) or not all(isinstance(t, str) and t for t in g.get("tools", [])):
        raise AuthorityError("BAD_GRANTS", f"{where}: tools")
    scopes = g.get("path_scopes", [])
    if not isinstance(scopes, list) or not all(norm_path(s) is not None for s in scopes):
        raise AuthorityError("BAD_GRANTS", f"{where}: path_scopes")
    for k in ("max_calls",):
        if k in g and (not isinstance(g[k], int) or isinstance(g[k], bool) or g[k] < 0):
            raise AuthorityError("BAD_GRANTS", f"{where}: {k}")
    if "spend_eur" in g and (isinstance(g["spend_eur"], bool) or not isinstance(g["spend_eur"], (int, float)) or g["spend_eur"] < 0):
        raise AuthorityError("BAD_GRANTS", f"{where}: spend_eur")
    if "expires_at" in g:
        _parse_ts(g["expires_at"])


def _subset(child, parent, where, limits=True):
    """Attenuation: child grants must fit inside parent grants. Missing numbers mean the strictest value (0).
    limits=False checks tools and path scopes only (milestones inherit calls, spend and expiry from the session)."""
    for t in child.get("tools", []):
        if t not in parent.get("tools", []):
            raise AuthorityError("ATTENUATION_VIOLATION", f"{where}: tool {t!r} not in parent")
    for s in child.get("path_scopes", []):
        if not any(path_within(s, ps) for ps in parent.get("path_scopes", [])):
            raise AuthorityError("ATTENUATION_VIOLATION", f"{where}: path scope {s!r} not inside parent")
    if not limits:
        return
    if child.get("max_calls", 0) > parent.get("max_calls", 0):
        raise AuthorityError("ATTENUATION_VIOLATION", f"{where}: max_calls")
    if child.get("spend_eur", DEFAULT_SPEND_EUR) > parent.get("spend_eur", DEFAULT_SPEND_EUR):
        raise AuthorityError("ATTENUATION_VIOLATION", f"{where}: spend_eur")
    if "expires_at" in child and "expires_at" in parent and _parse_ts(child["expires_at"]) > _parse_ts(parent["expires_at"]):
        raise AuthorityError("ATTENUATION_VIOLATION", f"{where}: expires_at")
    if "expires_at" in parent and "expires_at" not in child:
        raise AuthorityError("ATTENUATION_VIOLATION", f"{where}: expires_at required")


# ---------------------------------------------------------------- ledger

class Ledger:
    """Append-only, hash-chained JSONL. If it cannot be written, callers must fail closed."""

    def __init__(self, path, clock=_utc_now):
        self.path = path
        self._clock = clock
        self.seq = 0
        self.head = GENESIS
        self.broken = False
        self._lock = threading.Lock()
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            open(path, "x").close()
        except FileExistsError:
            raise LedgerError("LEDGER_EXISTS", "append-only: a session gets a new ledger")
        except OSError as e:
            raise LedgerError("LEDGER_UNWRITABLE", str(e))

    def append(self, surface, kind, session_id, task_id, **fields):
        with self._lock:
            if self.broken:
                raise LedgerError("LEDGER_BROKEN", "an earlier write failed; the tail of the file is unknown, so nothing more is written")
            entry = {"seq": self.seq + 1, "ts": _iso(self._clock()), "session_id": session_id, "task_id": task_id,
                     "surface": surface, "kind": kind}
            entry.update(fields)
            entry["prev_hash"] = self.head
            entry["hash"] = sha256_hex(canonical({k: v for k, v in entry.items() if k != "hash"}))
            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, sort_keys=True) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            except OSError as e:
                self.broken = True
                raise LedgerError("LEDGER_UNWRITABLE", str(e))
            self.seq += 1
            self.head = entry["hash"]
            return entry

    @staticmethod
    def verify(path):
        prev, seq = GENESIS, 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    e = json.loads(line)
                    seq += 1
                    if e.get("seq") != seq or e.get("prev_hash") != prev:
                        return False, f"chain broken at seq {seq}"
                    if e.get("hash") != sha256_hex(canonical({k: v for k, v in e.items() if k != "hash"})):
                        return False, f"hash mismatch at seq {seq}"
                    prev = e["hash"]
        except (OSError, ValueError) as e:
            return False, str(e)
        return True, f"{seq} entries"

    @staticmethod
    def read(path):
        with open(path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f]


# ---------------------------------------------------------------- charter

class Charter:
    """Owner-signed objectives, boundaries and principal registry. The trust anchor is pinned by the caller."""

    def __init__(self, record, principals):
        self.record = record
        self.principals = principals  # id -> principal dict
        self.boundaries = record["boundaries"]
        self.self_work = record.get("self_work")
        self.objectives = record["objectives"]

    @classmethod
    def load(cls, record, verifier, trusted_owner_fingerprint, clock=_utc_now):
        _need_verifier(verifier)
        if not isinstance(record, dict):
            raise AuthorityError("BAD_CHARTER", "not an object")
        for k in ("charter_id", "owner_id", "objectives", "boundaries", "principals", "signer_id", "signature"):
            if k not in record:
                raise AuthorityError("BAD_CHARTER", f"missing {k}")
        principals = {}
        for p in record["principals"]:
            if not isinstance(p, dict) or p.get("role") not in ROLES or not p.get("id") or p["id"] in principals:
                raise AuthorityError("BAD_CHARTER", "principal")
            try:
                fp = fingerprint(p["public_key"])
            except Exception:
                raise AuthorityError("BAD_CHARTER", "public_key")
            if p.get("public_key_fingerprint") != fp:
                raise AuthorityError("BAD_CHARTER", f"fingerprint mismatch for {p['id']}")
            principals[p["id"]] = p
        signer = principals.get(record["signer_id"])
        if signer is None or signer["role"] != "owner":
            raise AuthorityError("BAD_CHARTER", "charter must be signed by an owner principal")
        if signer["public_key_fingerprint"] != trusted_owner_fingerprint:
            raise AuthorityError("UNTRUSTED_CHARTER", "signer is not the pinned owner key")
        if not verifier.verify(signer["public_key"], canonical(_unsigned(record)), record["signature"]):
            raise AuthorityError("BAD_SIGNATURE", "charter signature")
        b = record["boundaries"]
        _check_grants_shape(b, "boundaries")
        if "expires_at" not in b:
            raise AuthorityError("BAD_CHARTER", "boundaries need expires_at")
        if _parse_ts(b["expires_at"]) <= clock():
            raise AuthorityError("CHARTER_EXPIRED")
        if record.get("self_work") is not None:
            _check_grants_shape(record["self_work"], "self_work")
            _subset(record["self_work"], b, "self_work")
        return cls(record, principals)

    def spend_ceiling(self):
        return self.boundaries.get("spend_eur", DEFAULT_SPEND_EUR)


# ---------------------------------------------------------------- session

class Session:
    """The one authority record all three surfaces share."""

    def __init__(self):
        raise TypeError("use Session.open(...)")

    @classmethod
    def open(cls, record, signature, charter, ledger_path, verifier, clock=_utc_now, kernel_check=None,
             allow_unenforced_kernel=False):
        _need_verifier(verifier)
        if kernel_check is not None and not callable(kernel_check):
            raise AuthorityError("KERNEL_REQUIRED", "kernel_check must be callable")
        if kernel_check is None and not allow_unenforced_kernel:
            raise AuthorityError("KERNEL_REQUIRED", "a kernel decision is required for every call; pass the kernel, or "
                                 "allow_unenforced_kernel=True for a session that is never live_ready")
        if not isinstance(record, dict):
            raise AuthorityError("BAD_SESSION", "not an object")
        for k in ("session_id", "task_id", "issued_by", "signer_id", "executor_id", "execution", "grants"):
            if not record.get(k):
                raise AuthorityError("BAD_SESSION", f"missing {k}")
        if record["execution"] not in ("core", "harness"):
            raise AuthorityError("BAD_SESSION", "execution must be core or harness")
        signer = charter.principals.get(record["signer_id"])
        if signer is None:
            raise AuthorityError("UNKNOWN_SIGNER", record["signer_id"])
        if signer["role"] not in ISSUER_ROLES:
            raise AuthorityError("ROLE_NOT_ALLOWED", f"{signer['role']} cannot issue sessions")
        if not isinstance(signature, str) or not verifier.verify(signer["public_key"], canonical(record), signature):
            raise AuthorityError("BAD_SIGNATURE", "session record")
        issued_by, executor = record["issued_by"], record["executor_id"]
        grants = record["grants"]
        _check_grants_shape(grants, "grants")
        if "expires_at" not in grants:
            raise AuthorityError("BAD_GRANTS", "session grants need expires_at")
        if _parse_ts(grants["expires_at"]) <= clock():
            raise AuthorityError("SESSION_EXPIRED")
        if issued_by == "owner":
            if signer["role"] != "owner":
                raise AuthorityError("ISSUER_MISMATCH", "issued_by owner needs an owner signature")
            ceiling = charter.boundaries
        elif issued_by == "icarus":
            if signer["role"] != "adjudicator":
                raise AuthorityError("ISSUER_MISMATCH", "issued_by icarus needs an adjudicator signature")
            ceiling = charter.boundaries
        elif issued_by == "charter":
            if signer["role"] != "adjudicator":
                raise AuthorityError("ISSUER_MISMATCH", "self-work is for the adjudicator only")
            if charter.self_work is None:
                raise AuthorityError("NO_SELF_WORK_AUTHORITY", "the charter grants no self-work")
            ceiling = charter.self_work
        else:
            raise AuthorityError("ISSUER_MISMATCH", f"unknown issued_by {issued_by!r}")
        self_work = issued_by == "charter"
        if executor == record["signer_id"] and not self_work:
            raise AuthorityError("SELF_GRANT", "an agent cannot issue a session to itself")
        if self_work and executor != record["signer_id"]:
            raise AuthorityError("ISSUER_MISMATCH", "charter self-work must be executed by its signer")
        _subset(grants, ceiling, "grants")
        # reviewers must be exactly principals the owner put in the charter
        reviewers = {}
        for r in record.get("reviewers", []):
            p = charter.principals.get(r.get("id")) if isinstance(r, dict) else None
            if p is None or r.get("role") != p["role"] or r.get("public_key") != p["public_key"]:
                raise AuthorityError("REGISTRY_FORGED", "reviewer is not a charter principal")
            if p["role"] not in ROLES:
                raise AuthorityError("REGISTRY_FORGED", "role")
            reviewers[p["id"]] = p
        independent = executor in charter.principals and charter.principals[executor]["role"] == "adjudicator"
        plan = record.get("checkpoint_plan")
        milestones = []
        if plan is not None:
            if not isinstance(plan, dict) or not isinstance(plan.get("milestones"), list) or not plan["milestones"]:
                raise AuthorityError("PLAN_INVALID", "plan needs milestones")
            if plan.get("plan_sha256") != sha256_hex(canonical(plan["milestones"])):
                raise AuthorityError("PLAN_INVALID", "plan_sha256 does not match milestones")
            if plan.get("approved_by") != record["signer_id"]:
                raise AuthorityError("PLAN_INVALID", "the plan must be approved by the session signer")
            seen = set()
            for m in plan["milestones"]:
                if not isinstance(m, dict) or not m.get("id") or m["id"] in seen:
                    raise AuthorityError("PLAN_INVALID", "milestone id")
                seen.add(m["id"])
                ev = m.get("evidence_required")
                if not isinstance(ev, list) or not ev or not all(isinstance(x, str) and x for x in ev):
                    raise AuthorityError("PLAN_INVALID", f"milestone {m['id']} needs evidence_required")
                _check_grants_shape(m.get("grants", {}), f"milestone {m['id']}")
                _subset(m.get("grants", {}), grants, f"milestone {m['id']}", limits=False)
                milestones.append(m)
            eligible = [r for r in reviewers.values() if r["id"] != executor
                        and (r["role"] in ("owner", "verifier") if independent else True)]
            if not eligible:
                raise AuthorityError("NO_ELIGIBLE_REVIEWER", "a plan needs at least one reviewer who can approve this work")
        self = object.__new__(cls)
        self.record = record
        self.session_id, self.task_id = record["session_id"], record["task_id"]
        self.executor_id, self.execution = executor, record["execution"]
        self.signer_id, self.issued_by = record["signer_id"], issued_by
        self.grants = grants
        self.cwd = record.get("cwd")
        self.reviewers = reviewers
        self.independent_required = independent
        self.milestones = milestones
        self.plan = plan
        self.verifier = verifier
        self.clock = clock
        self.kernel_check = kernel_check
        self.kernel_enforced = kernel_check is not None
        self.kernel_name = (getattr(kernel_check, "name", None) or getattr(kernel_check, "__name__", None) or "unnamed") if kernel_check is not None else None
        self.state = "ACTIVE"
        self.milestone_index = 0
        self.gate = None
        self.blocked_reason = None
        self.calls = {}
        self.calls_authorized = 0
        self.spent_eur = 0.0
        self._nonces = set()
        self._evidence = {}
        self._actors = set()
        self._lock = threading.RLock()
        self.ledger = Ledger(ledger_path, clock)
        self.ledger.append("session", "session_opened", self.session_id, self.task_id, issued_by=issued_by,
                           signer_id=self.signer_id, executor_id=executor, execution=self.execution,
                           independent_verification_required=independent,
                           kernel_enforced=self.kernel_enforced, kernel_name=self.kernel_name,
                           record_sha256=sha256_hex(canonical(record)))
        if plan is None:
            self.ledger.append("session", "no_plan", self.session_id, self.task_id)
        else:
            self.ledger.append("session", "plan_loaded", self.session_id, self.task_id, plan_sha256=plan["plan_sha256"],
                               approved_by=plan["approved_by"], milestones=[m["id"] for m in milestones])
        return self

    # ------------------------------------------------------------ helpers
    @property
    def actors(self):
        return set(self._actors)

    def active_milestone(self):
        return self.milestones[self.milestone_index] if self.milestones else None

    def active_grants(self):
        m = self.active_milestone()
        return m.get("grants", {}) if m else self.grants

    def _log(self, surface, kind, **fields):
        if kind in EXEC_KINDS and fields.get("actor"):
            self._actors.add(fields["actor"])
        return self.ledger.append(surface, kind, self.session_id, self.task_id, **fields)

    def _deny(self, surface, kind, code, reason, **fields):
        e = self._log(surface, kind, decision="deny", code=code, reason=reason, **fields)
        return {"decision": "deny", "code": code, "reason": reason, "ledger_seq": e["seq"]}

    def _live(self):
        """None if the session may act, else (code, reason)."""
        if self.state == "PAUSED_FOR_REVIEW":
            return "PAUSED", "a review gate is open"
        if self.state != "ACTIVE":
            return "SESSION_CLOSED", self.state
        if self.clock() >= _parse_ts(self.grants["expires_at"]):
            return "SESSION_EXPIRED", "session expired"
        return None

    def _args_problem(self, tool, args):
        if not isinstance(args, dict):
            return "BAD_ARGS", "arguments must be a JSON object"
        g = self.active_grants()
        scopes = g.get("path_scopes", [])
        for key, val in args.items():
            if key not in PATH_KEYS:
                continue
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                if not isinstance(v, str):
                    return "PATH_OUT_OF_SCOPE", f"{key} is not a path string"
                n = norm_path(v)
                if n is None:
                    return "PATH_OUT_OF_SCOPE", f"{key} is not an acceptable path"
                if not (n.startswith("/") or re.match(r"^[a-z]:/", n)):
                    if not self.cwd or norm_path(self.cwd) is None:
                        return "RELATIVE_PATH", f"{key} is relative and the session has no cwd"
                    n = norm_path(self.cwd).rstrip("/") + "/" + n
                if not any(path_within(n, s) for s in scopes):
                    return "PATH_OUT_OF_SCOPE", f"{key} is outside the active scope"
        return None

    def _tool_problem(self, tool):
        if tool in self.active_grants().get("tools", []):
            return None
        if self.milestones and tool in self.grants.get("tools", []):
            return "OUT_OF_MILESTONE", f"{tool} is not granted in milestone {self.active_milestone()['id']}"
        return "TOOL_NOT_GRANTED", f"{tool} is not in the grant"

    @property
    def live_ready(self):
        """True only when a kernel decides every call, signatures can be verified and the ledger is writable."""
        return bool(self.kernel_enforced and getattr(self.verifier, "available", False) and not self.ledger.broken)

    def _kernel_decision(self, tool, args):
        """(ok, code, reason). A kernel that raises or answers badly is a denial, never an allow."""
        if self.kernel_check is None:
            return True, "OK", "kernel not enforced (session opened with allow_unenforced_kernel)"
        try:
            out = self.kernel_check(tool, args)
            ok, why = out
        except Exception as e:
            return False, "KERNEL_ERROR", f"kernel raised {type(e).__name__}"
        if not isinstance(ok, bool):
            return False, "KERNEL_ERROR", "kernel answered with a non-boolean decision"
        return (True, "OK", str(why)[:200]) if ok else (False, "KERNEL_DENIED", str(why)[:200])

    # ------------------------------------------------------------ calls
    def propose(self, tool, args, actor, cost_eur=0):
        """Slot-time check. Mints the call_id and fixes tool + exact arguments for it."""
        with self._lock:
            live = self._live()
            if live:
                return self._deny("slot", "proposal_denied", live[0], live[1], actor=actor, tool=tool)
            if isinstance(cost_eur, bool) or not isinstance(cost_eur, (int, float)) or cost_eur < 0:
                return self._deny("slot", "proposal_denied", "BAD_COST", "cost must be a non-negative number", actor=actor, tool=tool)
            if not isinstance(tool, str) or not tool:
                return self._deny("slot", "proposal_denied", "BAD_TOOL", "tool name required", actor=actor)
            prob = self._tool_problem(tool) or self._args_problem(tool, args)
            if prob:
                return self._deny("slot", "proposal_denied", prob[0], prob[1], actor=actor, tool=tool)
            if self.calls_authorized >= self.grants.get("max_calls", 0):
                return self._deny("slot", "proposal_denied", "MAX_CALLS", "call budget used", actor=actor, tool=tool)
            if self.spent_eur + cost_eur > self.grants.get("spend_eur", DEFAULT_SPEND_EUR):
                return self._deny("slot", "proposal_denied", "SPEND_EXCEEDED", "spend would exceed the grant", actor=actor, tool=tool)
            ok, kcode, kwhy = self._kernel_decision(tool, args)
            if not ok:
                return self._deny("slot", "proposal_denied", kcode, kwhy, actor=actor, tool=tool, kernel=self.kernel_name)
            canon = canonical(args)
            call_id = f"call_{self.session_id}_{self.ledger.seq + 1:04d}"
            sha = sha256_hex(canon)
            side = None
            if len(canon) <= SIDE_FILE_CAP:
                side_dir = self.ledger.path + ".calls"
                side_path = os.path.join(side_dir, call_id + ".json")
                try:
                    os.makedirs(side_dir, exist_ok=True)
                    with open(side_path, "wb") as f:
                        f.write(canon)
                        f.flush()
                        os.fsync(f.fileno())
                    side = side_path
                except OSError as e:
                    return self._deny("slot", "proposal_denied", "SIDE_FILE_FAILED",
                                      f"could not save the call arguments ({type(e).__name__}); nothing authorized", actor=actor, tool=tool)
            try:
                e = self._log("slot", "proposal", call_id=call_id, decision="allow", reason="in grant, scope and budget", actor=actor,
                              tool=tool, args_sha256=sha, args_bytes=len(canon), args_saved=side is not None, call_state="AUTHORIZED",
                              kernel=self.kernel_name, kernel_reason=kwhy)
            except Exception:
                if side:
                    try:
                        os.remove(side)
                    except OSError:
                        pass
                raise
            self.calls_authorized += 1
            self.spent_eur += cost_eur
            self.calls[call_id] = {"tool": tool, "args_sha256": sha, "state": "AUTHORIZED", "by": None,
                                   "milestone": self.active_milestone()["id"] if self.milestones else None, "result": None}
            return {"decision": "allow", "code": "OK", "call_id": call_id, "args_sha256": sha, "ledger_seq": e["seq"]}

    def authorize_execution(self, call_id, tool, args, by, actor=None):
        """Hook-time check. The harness's own hash is never trusted: arguments are recomputed here."""
        actor = actor or self.executor_id
        with self._lock:
            live = self._live()
            if live:
                return self._deny("hook", "execution_denied", live[0], live[1], call_id=call_id, actor=actor)
            call = self.calls.get(call_id)
            if call is None:
                return self._deny("hook", "execution_denied", "UNPROPOSED_CALL", "call_id was not minted by this session", call_id=call_id, actor=actor)
            if call["state"] == "BURNED":
                return self._deny("hook", "execution_denied", "CALL_BURNED", "call_id is burned", call_id=call_id, actor=actor)
            if call["state"] in ("EXECUTED", "RESULT_RECORDED"):
                return self._deny("hook", "execution_denied", "DUPLICATE_EXECUTION", "call already executed", call_id=call_id, actor=actor)
            if by != self.execution:
                return self._deny("hook", "execution_denied", "WRONG_EXECUTOR", f"this session executes in {self.execution} mode", call_id=call_id, actor=actor)
            if tool != call["tool"]:
                call["state"] = "BURNED"
                return self._deny("hook", "execution_denied", "TOOL_MISMATCH", "tool differs from the proposal", call_id=call_id, actor=actor,
                                  proposed_tool=call["tool"], received_tool=str(tool)[:80])
            if not isinstance(args, dict):
                call["state"] = "BURNED"
                return self._deny("hook", "execution_denied", "ARGS_MISMATCH", "arguments must be a JSON object", call_id=call_id, actor=actor)
            got = sha256_hex(canonical(args))
            if got != call["args_sha256"]:
                call["state"] = "BURNED"
                return self._deny("hook", "execution_denied", "ARGS_MISMATCH", "arguments differ from the proposal", call_id=call_id, actor=actor,
                                  proposed_args_sha256=call["args_sha256"], received_args_sha256=got)
            if call["milestone"] != (self.active_milestone()["id"] if self.milestones else None):
                return self._deny("hook", "execution_denied", "OUT_OF_MILESTONE", "call belongs to another milestone", call_id=call_id, actor=actor)
            prob = self._tool_problem(tool) or self._args_problem(tool, args)
            if prob:
                return self._deny("hook", "execution_denied", prob[0], prob[1], call_id=call_id, actor=actor)
            ok, kcode, kwhy = self._kernel_decision(tool, args)
            if not ok:
                return self._deny("hook", "execution_denied", kcode, kwhy, call_id=call_id, actor=actor, kernel=self.kernel_name)
            e = self._log("hook", "execution_authorized", call_id=call_id, decision="allow", reason="matches the proposal exactly", actor=actor,
                          tool=tool, args_sha256=got, executed_by=by, call_state="EXECUTED", kernel=self.kernel_name, kernel_reason=kwhy)
            call["state"], call["by"] = "EXECUTED", by  # persisted first: a failed write leaves the call AUTHORIZED, never EXECUTED
            return {"decision": "allow", "code": "OK", "call_id": call_id, "ledger_seq": e["seq"]}

    def record_result(self, call_id, content, source=None, actor=None):
        """Records a tool result. Harness-reported results are evidence of what the harness says, not independent."""
        actor = actor or self.executor_id
        with self._lock:
            call = self.calls.get(call_id)
            data = content if isinstance(content, bytes) else str(content).encode("utf-8")
            src = source or ("harness_reported" if self.execution == "harness" else "core_reported")
            if call is None:
                e = self._log("slot", "unmatched_tool_result", call_id=str(call_id)[:80], decision="deny", code="UNMATCHED_RESULT",
                              reason="no such call", actor=actor, content_sha256=sha256_hex(data), source=src)
                return {"decision": "deny", "code": "UNMATCHED_RESULT", "ledger_seq": e["seq"]}
            if call["state"] != "EXECUTED":
                return self._deny("slot", "tool_result_denied", "RESULT_NOT_EXPECTED", f"call state is {call['state']}", call_id=call_id, actor=actor)
            sha = sha256_hex(data)
            e = self._log("slot", "tool_result", call_id=call_id, decision="allow", reason="recorded", actor=actor,
                          content_sha256=sha, args_sha256=call["args_sha256"], source=src, call_state="RESULT_RECORDED")
            call["state"], call["result"] = "RESULT_RECORDED", sha  # persisted first
            return {"decision": "allow", "code": "OK", "ledger_seq": e["seq"]}

    # ------------------------------------------------------------ milestones and gates
    def declare_milestone(self, milestone_id, evidence, actor=None):
        actor = actor or self.executor_id
        with self._lock:
            if not self.milestones:
                return self._deny("session", "milestone_denied", "NO_PLAN", "this session has no checkpoint plan", actor=actor)
            live = self._live()
            if live:
                return self._deny("session", "milestone_denied", live[0], live[1], actor=actor)
            m = self.active_milestone()
            if milestone_id != m["id"]:
                return self._deny("session", "milestone_denied", "NOT_ACTIVE_MILESTONE", f"active milestone is {m['id']}", actor=actor)
            kinds = {e.get("kind") for e in evidence if isinstance(e, dict) and isinstance(e.get("ref"), str) and e["ref"]} if isinstance(evidence, list) else set()
            missing = [k for k in m["evidence_required"] if k not in kinds]
            if missing:
                e = self._log("session", "milestone_incomplete", milestone_id=milestone_id, decision="deny", code="MILESTONE_INCOMPLETE",
                              reason="missing evidence kinds", missing=missing, actor=actor)
                return {"decision": "deny", "code": "MILESTONE_INCOMPLETE", "missing": missing, "ledger_seq": e["seq"]}
            self._log("session", "milestone_reached", milestone_id=milestone_id, decision="allow", reason="required evidence kinds present",
                      evidence=evidence, actor=actor)
            gate_id = f"g-{milestone_id}"
            # restrictive transition: pause first. If the next write fails the session stays paused with no gate to
            # decide on (blocked), which is stricter, never more permissive.
            self.state = "PAUSED_FOR_REVIEW"
            self.gate = None
            self.blocked_reason = "gate could not be opened because the ledger write failed"
            opened = self._log("session", "gate_opened", milestone_id=milestone_id, gate_id=gate_id)
            self.gate = {"gate_id": gate_id, "milestone_id": milestone_id, "ledger_head_hash": opened["hash"]}
            self.blocked_reason = None
            return {"decision": "allow", "code": "GATE_OPEN", "gate_id": gate_id, "milestone_id": milestone_id,
                    "ledger_head_hash": opened["hash"], "state": self.state}

    def apply_decision(self, d):
        """Apply a signed review decision. Names in the record are lookup keys; only the signature is authority."""
        with self._lock:
            def reject(code, why):
                self._log("session", "decision_rejected", decision="deny", code=code, reason=why,
                          reviewer_id=str(d.get("reviewer_id"))[:80] if isinstance(d, dict) else None)
                raise AuthorityError(code, why)

            if self.state != "PAUSED_FOR_REVIEW" or self.gate is None:
                reject("NOT_PAUSED", "no gate is open")
            if not getattr(self.verifier, "available", False):
                self.blocked_reason = "no vetted Ed25519 verifier"
                self._log("session", "gate_blocked", reason=self.blocked_reason)
                raise AuthorityError("BLOCKED_NO_VERIFIER", "gate stays closed")
            if not isinstance(d, dict):
                reject("BAD_DECISION", "not an object")
            for k in ("session_id", "gate_id", "milestone_id", "ledger_head_hash", "decision", "nonce", "expires_at", "reviewer_id", "signature"):
                if not isinstance(d.get(k), str) or not d[k]:
                    reject("BAD_DECISION", f"missing {k}")
            if d["session_id"] != self.session_id or d["gate_id"] != self.gate["gate_id"] or d["milestone_id"] != self.gate["milestone_id"]:
                reject("WRONG_GATE", "decision is for another session, gate or milestone")
            if d["ledger_head_hash"] != self.gate["ledger_head_hash"]:
                reject("STALE_LEDGER_HEAD", "decision does not cover the evidence state under review")
            if d["decision"] not in DECISIONS:
                reject("BAD_DECISION", "decision must be resume, rework or stop")
            reviewer = self.reviewers.get(d["reviewer_id"])
            if reviewer is None:
                reject("UNKNOWN_REVIEWER", "reviewer is not in the session registry")
            try:
                expired = self.clock() >= _parse_ts(d["expires_at"])
            except AuthorityError:
                reject("BAD_DECISION", "expires_at")
            if expired:
                reject("DECISION_EXPIRED", "decision expired")
            if d["nonce"] in self._nonces:
                reject("NONCE_REPLAY", "nonce already used")
            if reviewer["id"] == self.executor_id or reviewer["id"] in self._actors:
                reject("SELF_APPROVAL", "the executor, or anyone who acted in this session, cannot approve it")
            if self.independent_required and reviewer["role"] not in ("owner", "verifier"):
                reject("INDEPENDENCE_REQUIRED", "work done by the adjudicator needs an owner or independent verifier")
            if not self.verifier.verify(reviewer["public_key"], canonical(_unsigned(d)), d["signature"]):
                reject("BAD_SIGNATURE", "signature does not verify against the registered key")
            self._log("session", "decision_accepted", decision="allow", reason=d["decision"], reviewer_id=reviewer["id"],
                      reviewer_role=reviewer["role"], gate_id=d["gate_id"], milestone_id=d["milestone_id"], nonce=d["nonce"])
            self._nonces.add(d["nonce"])  # persisted first: a failed write leaves the gate closed and the nonce unused
            self.gate = None
            if d["decision"] == "stop":
                self.state = "CLOSED_STOPPED"
            elif d["decision"] == "rework":
                self.state = "ACTIVE"
            else:
                if self.milestone_index + 1 >= len(self.milestones):
                    self.state = "CLOSED_COMPLETE"
                else:
                    self.milestone_index += 1
                    self.state = "ACTIVE"
            if self.state.startswith("CLOSED"):
                self._log("session", "session_closed", reason=self.state)
            return {"state": self.state, "milestone": (self.active_milestone() or {}).get("id")}
