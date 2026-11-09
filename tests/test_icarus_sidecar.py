import base64
import datetime
import hashlib
import io
import json
import zipfile

import pytest

from icarus.core import pilot_state, sidecar


CHAIRS = {"SOL": 100, "CLAUDE": 200, "CODEX": 300}


@pytest.mark.parametrize("author,verifier", [(100, ("CLAUDE", 200)), (200, ("SOL", 100)), (300, ("SOL", 100))])
def test_sidecar_rotation(author, verifier):
    assert sidecar.rotation({author}, CHAIRS, 400) == verifier


@pytest.mark.parametrize("authors,sidecar_id", [({100, 200}, 400), ({400}, 400), ({None}, 400), ({300}, 100)])
def test_sidecar_rejects_self_review_or_ambiguous_identity(authors, sidecar_id):
    with pytest.raises(ValueError):
        sidecar.rotation(authors, CHAIRS, sidecar_id)


def test_expired_edited_or_spoofed_seat_reports_are_unknown():
    now = datetime.datetime(2026, 11, 9, 13, 0, tzinfo=datetime.timezone.utc)
    def row(id, actor, created, updated, state):
        return {"id": id, "user": {"id": actor}, "created_at": created, "updated_at": updated,
                "body": f"{pilot_state.SEAT_REPORT}\nSeat: SOL\nAvailability: {state}"}
    fresh = "2026-11-09T12:55:00Z"
    valid = row(1, 100, fresh, fresh, "available")
    forged = row(2, 999, fresh, fresh, "unavailable")
    edited = row(3, 100, fresh, "2026-11-09T12:59:00Z", "unavailable")
    assert pilot_state.availability([valid, forged], {"SOL": 100}, now)["SOL"] == "available"
    assert pilot_state.availability([valid, edited], {"SOL": 100}, now)["SOL"] == "unknown"
    assert pilot_state.availability([valid], {"SOL": 100}, now + datetime.timedelta(minutes=15))["SOL"] == "unknown"


def test_ambiguous_reservation_post_cannot_buy_another_attempt():
    events = []
    def post(url, token, body):
        events.append({"id": 1, "user": {"id": pilot_state.PULSE_ACTOR_ID}, "body": body})
        raise RuntimeError("response lost after GitHub write")
    def read(url, token):
        return list(events)
    with pytest.raises(RuntimeError, match="response lost"):
        pilot_state.reserve_attempt("BACKLOG-1", "url", "token", read, post)
    assert pilot_state.reserve_attempt("BACKLOG-1", "url", "token", read, post) is None
    assert len(events) == 1


def test_receipt_requires_a_verified_append_only_commit():
    source, head = "a" * 40, "b" * 40
    original = b'{"task_id":"prior"}\n'
    receipt = {"record_type": "sidecar_ci_verification", "pr_number": 188,
               "source_commit": source, "verifier_user_id": 100, "exit_code": 0}
    class Api:
        def get(self, suffix):
            raw = original if suffix.endswith(source) else original + json.dumps(receipt).encode() + b"\n"
            return {"encoding": "base64", "content": base64.b64encode(raw)}
    commit = {"parents": [{"sha": source}], "files": [{"filename": sidecar.LEDGER}],
              "author": {"id": 100}, "committer": {"id": 100},
              "commit": {"verification": {"verified": True}}}
    assert sidecar.independent_receipt(Api(), head, commit, 100, 188) == receipt
    with pytest.raises(ValueError, match="not authenticated"):
        sidecar.independent_receipt(Api(), head, commit, 200, 188)


@pytest.mark.parametrize("exit_code,count,accepted", [(0, 215, True), (0, 214, False), (7, 215, False)])
def test_sidecar_reads_physical_harness_artifact(exit_code, count, accepted):
    source = "a" * 40
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("RUN_LOG.jsonl", json.dumps({"run_id": "123", "harness_outcome": "success",
                                                     "harness_status": "PASS", "harness_exit_code": exit_code,
                                                     "pytest_summary": f"{count} passed in 1.50s"}))
    raw = buf.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    class Api:
        def get(self, suffix):
            if suffix == "/actions/runs/123":
                return {"id": 123, "head_sha": source, "workflow_id": sidecar.PULSE_WORKFLOW_ID,
                        "event": "pull_request", "conclusion": "success", "run_attempt": 1,
                        "repository": {"id": sidecar.REPOSITORY_ID}, "head_repository": {"id": sidecar.REPOSITORY_ID}}
            assert suffix == "/actions/artifacts/222"
            return {"workflow_run": {"id": 123}, "name": "harness-run-log-123-1", "expired": False,
                    "digest": f"sha256:{digest}"}
        def archive(self, id):
            assert id == 222
            return raw
    receipt = {"harness_run_id": 123, "artifact_id": 222, "source_commit": source,
               "artifact_sha256": digest, "tests_passed": count}
    if accepted:
        assert sidecar.physical_ci(Api(), receipt) == 215
    else:
        with pytest.raises(ValueError, match="Physical test count"):
            sidecar.physical_ci(Api(), receipt)
