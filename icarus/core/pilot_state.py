"""GitHub-backed admission state for the serialized, default-branch Pulse."""

import datetime
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SEATS = frozenset({"CODEX", "SOL", "LUNA", "GRACE"})
PULSE_ACTOR_ID = 41898282
SEAT_REPORT = "[ICARUS SEAT AVAILABILITY]"
PILOT_RESERVATION = "[ICARUS PILOT ATTEMPT RESERVED]"
PILOT_APPROVAL = "[ICARUS LIVE PILOT APPROVAL]"
POLICY_PATH = Path(__file__).resolve().parents[1] / "runtime" / "live-pilot.json"
MAX_REPORT_AGE = datetime.timedelta(minutes=15)
APPROVAL_AGE = datetime.timedelta(days=1)
PROOF_PATH = "icarus-pilot-proof.bin"


def actor_id(comment):
    return (comment.get("user") or {}).get("id")


def fields(comment, header):
    first, _, body = (comment.get("body") or "").partition("\n")
    if first.strip() != header:
        return {}
    result = {}
    for line in body.splitlines():
        name, sep, value = line.partition(":")
        if not sep or name in result:
            return {}
        result[name] = value.strip()
    return result


def load_policy(path=POLICY_PATH):
    raw = path.read_bytes()
    policy = json.loads(raw)
    if not isinstance(policy, dict) or set(policy) != {"seat_reporters", "verifier_user_id", "approved_pilots"}:
        raise ValueError("Invalid live pilot policy")
    reporters = policy["seat_reporters"]
    verifier = policy["verifier_user_id"]
    if (not isinstance(reporters, dict) or set(reporters) - SEATS
            or any(type(actor) is not int or actor <= 0 or actor == PULSE_ACTOR_ID
                   for actor in reporters.values())
            or (verifier is not None and (type(verifier) is not int or verifier <= 0
                                         or verifier in {*reporters.values(), PULSE_ACTOR_ID}))):
        raise ValueError("Invalid or overlapping live pilot principals")
    pilots = policy["approved_pilots"]
    if not isinstance(pilots, dict) or any(
        not re.fullmatch(r"BACKLOG-[1-9][0-9]*", task_id)
        or not isinstance(spec, dict) or set(spec) != {"path", "sha256"}
        or not isinstance(spec["path"], str) or not spec["path"]
        or not isinstance(spec["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", spec["sha256"])
        for task_id, spec in pilots.items()
    ):
        raise ValueError("Invalid approved pilot task")
    return policy, hashlib.sha256(raw).hexdigest()


def parse_timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        timestamp = datetime.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return timestamp if timestamp.utcoffset() == datetime.timedelta(0) else None


def availability(comments, reporters, now):
    """Only a fresh, unedited report from the enrolled GitHub actor counts."""
    states = dict.fromkeys(SEATS, "unknown")
    expiries = {}
    reported = set()
    for comment in sorted(comments, key=lambda row: row["id"], reverse=True):
        packet = fields(comment, SEAT_REPORT)
        seat = packet.get("Seat")
        if seat not in reporters or seat in reported or actor_id(comment) != reporters[seat]:
            continue
        reported.add(seat)
        created_at = comment.get("created_at")
        timestamp = parse_timestamp(created_at)
        if (set(packet) == {"Seat", "Availability"} and timestamp is not None
                and created_at == comment.get("updated_at")
                and datetime.timedelta(0) <= now - timestamp < MAX_REPORT_AGE
                and packet["Availability"] in {"available", "unavailable"}):
            states[seat] = packet["Availability"]
            expiries[seat] = timestamp + MAX_REPORT_AGE
    return states, expiries


def reserved(comments, task_id):
    return any(actor_id(comment) == PULSE_ACTOR_ID
               and fields(comment, PILOT_RESERVATION).get("Task ID") == task_id
               for comment in comments)


def reserve_attempt(task_id, comments_url, token, fetch_pages, post_comment):
    """Consume the sole attempt before effect, using Pulse's single writer.

    A failed or ambiguous POST or readback must stop the caller. A later wake
    rereads the full history before trying to reserve. An existing reservation
    is consumed even if the job stopped before launching the child process.
    """
    if not re.fullmatch(r"BACKLOG-[1-9][0-9]*", task_id):
        raise ValueError("Pilot attempt requires a canonical backlog task ID")
    if reserved(fetch_pages(comments_url, token), task_id):
        return None
    body = f"{PILOT_RESERVATION}\nTask ID: {task_id}"
    comment_id = post_comment(comments_url, token, body)
    matches = [row for row in fetch_pages(comments_url, token)
               if actor_id(row) == PULSE_ACTOR_ID and fields(row, PILOT_RESERVATION).get("Task ID") == task_id]
    if len(matches) != 1 or matches[0]["id"] != comment_id or matches[0].get("body") != body:
        raise RuntimeError("Pilot reservation readback failed")
    return comment_id


def owner_approved(comments, task_id, policy_digest, now):
    for comment in sorted(comments, key=lambda row: row["id"], reverse=True):
        packet = fields(comment, PILOT_APPROVAL)
        if comment.get("author_association") != "OWNER" or packet.get("Task ID") != task_id:
            continue
        created_at = comment.get("created_at")
        timestamp = parse_timestamp(created_at)
        return (packet == {"Task ID": task_id, "Policy SHA-256": policy_digest}
                and timestamp is not None and created_at == comment.get("updated_at")
                and datetime.timedelta(0) <= now - timestamp < APPROVAL_AGE)
    return False


def on_live_schedule(repo):
    return (os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_EVENT_NAME") == "schedule"
            and os.environ.get("GITHUB_REF") == "refs/heads/main"
            and os.environ.get("GITHUB_WORKFLOW_REF") == f"{repo}/.github/workflows/icarus-pulse.yml@refs/heads/main")


def execute_readback(task_id, chair, states, expires_at, spec):
    """The live pilot can materialize a preapproved repository artifact."""
    root = POLICY_PATH.parents[2].resolve()
    relative = Path(spec["path"])
    source = (root / relative).resolve()
    if (relative.is_absolute() or not source.is_relative_to(root) or not source.is_file()
            or any(part.startswith(".") for part in relative.parts) or source.stat().st_size > 4 * 1024 * 1024):
        raise ValueError("Pilot source must be an approved regular repository file")
    with tempfile.TemporaryDirectory() as attempts:
        proof = Path(attempts) / "proof.bin"
        route = {
            "target_chair": chair, "seat_availability": states, "allow_pilot": True,
            "availability_expires_at": expires_at.isoformat(),
            "task": {"task_id": task_id, "cost_tier": "LOW", "decision_changing": True,
                     "owner_preauthorized": True,
                     "command": [sys.executable, "-I", "-S", "-c",
                                 "import sys; from pathlib import Path; "
                                 "Path(sys.argv[2]).write_bytes(Path(sys.argv[1]).read_bytes())",
                                 str(source), str(proof)],
                     "readback": {"type": "file_hash", "path": str(proof), "expected_hash": spec["sha256"]}},
        }
        result = subprocess.run([sys.executable, "-m", "icarus.harness.runner", "--route-task", "-", attempts],
                                input=json.dumps(route), text=True, capture_output=True,
                                cwd=root, env={"PATH": os.defpath, "PYTHONUTF8": "1"},
                                timeout=60, check=False)
        if result.returncode != 0:
            return {"runner_exit_code": result.returncode, "diagnostic": result.stderr.strip()}
        evidence = json.loads(result.stdout)
        if (evidence.get("task_id") != task_id or evidence.get("verdict") != "VERIFYING"
                or evidence.get("exit_code") != 0 or not isinstance(evidence.get("sha256"), str)
                or not hmac.compare_digest(evidence["sha256"], spec["sha256"])):
            raise ValueError("Invalid physical pilot readback")
        with proof.open("rb") as verified, Path(PROOF_PATH).open("xb") as artifact:
            shutil.copyfileobj(verified, artifact)
    return {"runner_exit_code": 0, "process_exit_code": 0, "sha256": evidence["sha256"],
            "proof_artifact": PROOF_PATH}
