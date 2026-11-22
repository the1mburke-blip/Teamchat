import json

import pytest

from icarus.harness import mailbox


@pytest.fixture
def evidence(monkeypatch, tmp_path):
    env = {
        "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": mailbox.REPOSITORY, "GITHUB_TOKEN": "test-only",
        "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40,
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    row = {
        "run_id": "123", "run_attempt": "1", "sha": env["GITHUB_SHA"], "event": "push",
        "ref": env["GITHUB_REF"], "timestamp": "2026-11-10T22:00:00+00:00",
        "build_outcome": "success", "harness_outcome": "success", "harness_exit_code": 0,
        "harness_log_tail": ["this raw log must stay out of the public comment"],
    }
    return tmp_path / "RUN_LOG.jsonl", row


def test_writeback_logs_created_id_and_reuses_comment_on_job_retry(monkeypatch, evidence):
    path, row = evidence
    comments = []

    def github_request(opener, token, url, payload=None):
        assert token == "test-only"
        if payload is None:
            return 200, comments, ""
        assert not comments
        assert url == mailbox.COMMENTS_URL
        assert "Status: PASSED" in payload["body"] and "this raw log" not in payload["body"]
        comment = {**payload, "id": 456, "user": {"id": mailbox.BOT_ID}, "issue_url": mailbox.ISSUE_URL,
                   "created_at": "2026-11-10T22:00:01Z", "updated_at": "2026-11-10T22:00:01Z"}
        comments.append(comment)
        return 201, comment, ""

    monkeypatch.setattr(mailbox, "request", github_request)
    original = json.dumps(row) + "\n"
    path.write_text(original, encoding="utf-8")
    created = mailbox.writeback(path)
    assert created["http_status"] == 201 and created["comment_id"] == 456
    assert [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] == [row, created]

    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    path.write_text(original, encoding="utf-8")
    reused = mailbox.writeback(path)
    assert reused["http_status"] == 200 and reused["comment_id"] == 456
    assert reused["disposition"] == "already_posted" and len(comments) == 1


@pytest.mark.parametrize(("exit_code", "outcome", "status"), [(9, "success", "FAILED"),
    (0, "failure", "FAILED"), (None, "skipped", "BLOCKED")])
def test_writeback_requires_physical_success_for_pass(monkeypatch, evidence, exit_code, outcome, status):
    path, row = evidence
    row.update(harness_exit_code=exit_code, harness_outcome=outcome)
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    def publish(token, body, since):
        assert f"Status: {status}" in body
        return 201, 456, "created"

    monkeypatch.setattr(mailbox, "publish_comment", publish)
    assert mailbox.writeback(path)["status"] == status


def test_pull_request_never_reaches_writeback(monkeypatch, evidence):
    path, _ = evidence
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    with pytest.raises(ValueError, match="main-branch push"):
        mailbox.writeback(path)
