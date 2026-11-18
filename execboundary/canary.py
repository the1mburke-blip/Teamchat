"""Build bounded canary envelopes from the canonical v3 template (used by tests and the e2e proof)."""
import copy
import json

from execboundary import schema


def packet(task_id, objective="Bounded canary: write one output file and pass a test."):
    t = schema.load_json(schema.DEFAULT_TEMPLATE)
    p = copy.deepcopy(t)
    p.update(authority_scope="BOUNDED_CANARY_NO_EXTERNAL_SIDE_EFFECTS", task_id=task_id, objective=objective)
    p["stages_to_execute"] = [{"stage_id": "STAGE_1", "name": "Write canary output",
                               "description": "Write a single file under the canary output directory.",
                               "attempt_limit": 3, "timeout_seconds": 300}]
    p["adjudication"] = dict(t["adjudication"], verifier_tier="TIER_1_MACHINE")
    p["acceptance_criteria"] = {
        "success_condition": "Independent verifier passes Gate 1 and Gate 2.",
        "blocker_condition": "BLOCKER_DISCOVERED after 3 attempts or 300s.",
        "human_escalation_condition": "Not expected for a canary.",
        "verification_file": "receipts/<task_id>/*-VERDICT.json"}
    return p


def envelope(task_id, out_rel, content="canary-ok", sleep=0, extra_cmd=None, tests=None):
    code = ("import pathlib,time;time.sleep(%r);p=pathlib.Path(%r);p.parent.mkdir(parents=True,exist_ok=True);"
            "p.write_text(%r)" % (sleep, out_rel, content))
    cmds = [["python3", "-c", code]] + ([extra_cmd] if extra_cmd else [])
    return {"envelope_version": schema.ENVELOPE_VERSION, "packet": packet(task_id),
            "execution": {"authorized_by": "Michael", "commands": cmds, "required_outputs": [out_rel],
                          "tests": tests or [["python3", "-c",
                                              "import pathlib,sys;sys.exit(0 if pathlib.Path(%r).read_text()==%r else 1)"
                                              % (out_rel, content)]],
                          "forbidden_paths": ["GOAL.md"], "forbidden_patterns": ["SIMULATED_EXECUTION"]}}


def dump(env):
    return json.dumps(env, indent=2).encode()
