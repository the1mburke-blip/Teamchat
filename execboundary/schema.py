"""Fail-closed ingress validation for v3.0.0 task packets wrapped in an execution envelope.

Nothing is repaired or inferred. Any deviation raises Rejected with a machine-readable code.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath

ENVELOPE_VERSION = "execboundary/1"
ENVELOPE_KEYS = frozenset({"envelope_version", "packet", "execution"})
EXECUTION_REQUIRED = frozenset({"authorized_by", "commands", "required_outputs", "tests",
                                "forbidden_paths", "forbidden_patterns"})
EXECUTION_KEYS = EXECUTION_REQUIRED
STAGE_KEYS = frozenset({"stage_id", "name", "description", "attempt_limit", "timeout_seconds"})
ADJ_KEYS = frozenset({"verifier_tier", "gate_1_technical_completion", "gate_2_policy_compliance"})
ACC_KEYS = frozenset({"success_condition", "blocker_condition", "human_escalation_condition",
                      "verification_file"})
VERIFIER_TIERS = frozenset({"TIER_1_MACHINE", "TIER_2_INDEPENDENT_AI_CHAIR", "TIER_3_HUMAN_OWNER"})
MAX_ATTEMPTS = 3
MAX_TIMEOUT = 300
MAX_BYTES = 256 * 1024
# Paths no packet may write to, whatever it declares (protected Icarus route + this boundary).
PROTECTED_PATHS = (".github/workflows/icarus-pulse.yml", "icarus/core", "icarus/harness",
                   "icarus/runtime", "execboundary", "training/TASK_DELEGATION_TEMPLATE.json")

HERE = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE.parent / "training" / "TASK_DELEGATION_TEMPLATE.json"
DEFAULT_AUTHORITY = HERE / "authority.json"


class Rejected(ValueError):
    def __init__(self, code, detail):
        super().__init__(code + ": " + detail)
        self.code = code
        self.detail = detail


def _no_dupes(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise Rejected("DUPLICATE_KEY", k)
        out[k] = v
    return out


def _bad_const(v):
    raise Rejected("NON_FINITE_NUMBER", v)


def parse(raw: bytes):
    if len(raw) > MAX_BYTES:
        raise Rejected("TOO_LARGE", str(len(raw)))
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise Rejected("NOT_UTF8", str(e))
    try:
        return json.loads(text, object_pairs_hook=_no_dupes, parse_constant=_bad_const)
    except Rejected:
        raise
    except json.JSONDecodeError as e:
        raise Rejected("MALFORMED_JSON", str(e))


def _exact_keys(obj, keys, where):
    if not isinstance(obj, dict):
        raise Rejected("WRONG_TYPE", where + " must be an object")
    missing = sorted(keys - obj.keys())
    extra = sorted(obj.keys() - keys)
    if missing:
        raise Rejected("MISSING_FIELD", where + ": " + ",".join(missing))
    if extra:
        raise Rejected("UNKNOWN_FIELD", where + ": " + ",".join(extra))


def _text(v, where):
    if not isinstance(v, str) or not v.strip():
        raise Rejected("EMPTY_OR_NON_STRING", where)
    if "{{" in v or "}}" in v:
        raise Rejected("UNFILLED_PLACEHOLDER", where)


def _int(v, where, lo, hi):
    if type(v) is not int or not lo <= v <= hi:
        raise Rejected("CONSTRAINT_VIOLATION", "%s must be int in [%d,%d], got %r" % (where, lo, hi, v))


def _relpath(p, where):
    _text(p, where)
    pp = PurePosixPath(p)
    if pp.is_absolute() or ".." in pp.parts or "\\" in p or p.startswith("~"):
        raise Rejected("PATH_ESCAPE", where + ": " + p)
    return str(pp)


def _argv_list(v, where):
    if not isinstance(v, list) or not v:
        raise Rejected("WRONG_TYPE", where + " must be a non-empty list of argv lists")
    for i, argv in enumerate(v):
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
            raise Rejected("SHELL_OR_BAD_ARGV", "%s[%d] must be a non-empty list of strings (no shell)" % (where, i))


def _under(path, roots):
    p = PurePosixPath(path).parts
    return any(p[:len(PurePosixPath(r).parts)] == PurePosixPath(r).parts for r in roots)


def validate_packet(packet, template):
    _exact_keys(packet, frozenset(template.keys()), "packet")
    if packet["template_version"] != "v3.0.0":
        raise Rejected("WRONG_TEMPLATE_VERSION", repr(packet["template_version"]))
    if packet["title"] != template["title"]:
        raise Rejected("TEMPLATE_MISMATCH", "title")
    if packet["immutable_execution_rules"] != template["immutable_execution_rules"]:
        raise Rejected("IMMUTABLE_RULES_ALTERED", "immutable_execution_rules differ from canonical template")
    for f in ("authority_scope", "task_id", "objective"):
        _text(packet[f], f)
    stages = packet["stages_to_execute"]
    if not isinstance(stages, list) or not stages:
        raise Rejected("WRONG_TYPE", "stages_to_execute must be a non-empty list")
    seen = set()
    for i, s in enumerate(stages):
        _exact_keys(s, STAGE_KEYS, "stages_to_execute[%d]" % i)
        for f in ("stage_id", "name", "description"):
            _text(s[f], "stages_to_execute[%d].%s" % (i, f))
        if s["stage_id"] in seen:
            raise Rejected("DUPLICATE_STAGE", s["stage_id"])
        seen.add(s["stage_id"])
        _int(s["attempt_limit"], "stages_to_execute[%d].attempt_limit" % i, 1, MAX_ATTEMPTS)
        _int(s["timeout_seconds"], "stages_to_execute[%d].timeout_seconds" % i, 1, MAX_TIMEOUT)
    adj = packet["adjudication"]
    _exact_keys(adj, ADJ_KEYS, "adjudication")
    if adj["verifier_tier"] not in VERIFIER_TIERS:
        raise Rejected("CONSTRAINT_VIOLATION", "adjudication.verifier_tier")
    if adj["gate_1_technical_completion"] != template["adjudication"]["gate_1_technical_completion"] or \
       adj["gate_2_policy_compliance"] != template["adjudication"]["gate_2_policy_compliance"]:
        raise Rejected("IMMUTABLE_RULES_ALTERED", "adjudication gates differ from canonical template")
    acc = packet["acceptance_criteria"]
    _exact_keys(acc, ACC_KEYS, "acceptance_criteria")
    for f in ACC_KEYS:
        _text(acc[f], "acceptance_criteria." + f)


def validate_execution(ex, authority):
    _exact_keys(ex, EXECUTION_KEYS, "execution")
    _text(ex["authorized_by"], "execution.authorized_by")
    if ex["authorized_by"] not in authority["authorized_principals"]:
        raise Rejected("UNAUTHORIZED", ex["authorized_by"])
    _argv_list(ex["commands"], "execution.commands")
    _argv_list(ex["tests"], "execution.tests")
    if not isinstance(ex["required_outputs"], list) or not ex["required_outputs"]:
        raise Rejected("WRONG_TYPE", "execution.required_outputs must be a non-empty list")
    outs = [_relpath(p, "execution.required_outputs") for p in ex["required_outputs"]]
    if not isinstance(ex["forbidden_paths"], list):
        raise Rejected("WRONG_TYPE", "execution.forbidden_paths")
    forb = [_relpath(p, "execution.forbidden_paths") for p in ex["forbidden_paths"]]
    if not isinstance(ex["forbidden_patterns"], list) or not all(isinstance(x, str) and x for x in ex["forbidden_patterns"]):
        raise Rejected("WRONG_TYPE", "execution.forbidden_patterns")
    all_forbidden = list(PROTECTED_PATHS) + forb
    for o in outs:
        if _under(o, all_forbidden):
            raise Rejected("CONSTRAINT_VIOLATION", "required output inside forbidden path: " + o)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_envelope(raw: bytes, template_path=DEFAULT_TEMPLATE, authority_path=DEFAULT_AUTHORITY):
    """Return (envelope, sha256). Raises Rejected. Pure: no side effects."""
    env = parse(raw)
    _exact_keys(env, ENVELOPE_KEYS, "envelope")
    if env["envelope_version"] != ENVELOPE_VERSION:
        raise Rejected("WRONG_ENVELOPE_VERSION", repr(env["envelope_version"]))
    validate_packet(env["packet"], load_json(template_path))
    validate_execution(env["execution"], load_json(authority_path))
    return env, hashlib.sha256(raw).hexdigest()


def effective_forbidden(env):
    return list(PROTECTED_PATHS) + list(env["execution"]["forbidden_paths"])
