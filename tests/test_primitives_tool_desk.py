import json

import pytest

from icarus.primitives.daemon import model_task
from icarus.primitives.reasoner import ReasonerError, parse_plan
from icarus.primitives.tool_desk import ToolDesk, ToolDeskError, model_tool_contract
from icarus.primitives.verify import verify

ACCOUNT = "buffer-account"
ORG = "org-1"
CHANNEL = "channel-1"
TEXT = "A human-made draft, saved for review."
SPEC = {"allowed_tools": {"BUFFER_CREATE_POST_DRAFT": {
    "connected_account_id": ACCOUNT, "organization_id": ORG,
    "allowed_channel_ids": [CHANNEL]}}}
PLAN = [{"tool_slug": "BUFFER_CREATE_POST_DRAFT",
         "arguments": {"channel_id": CHANNEL, "text": TEXT}}]


class Response:
    def __init__(self, payload, status=200):
        self.payload = json.dumps(payload).encode()
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def fake_opener(responses, seen):
    def open_request(req, timeout=30):
        body = json.loads(req.data.decode())
        seen.append({"url": req.full_url, "body": body,
                     "key": req.get_header("X-api-key"), "timeout": timeout})
        payload = responses.pop(0)
        return Response(payload)
    return open_request


def empty_posts():
    return {"successful": True, "data": {"items": [], "next_cursor": None}}


def matching_posts():
    return {"successful": True, "data": {"items": [{
        "id": "post-1", "text": TEXT, "status": "draft", "channel_id": CHANNEL}],
        "next_cursor": None}}


def test_buffer_draft_is_created_outside_sandbox_and_read_back(tmp_path):
    seen, durable = [], []
    responses = [empty_posts(), {"successful": True, "data": {"id": "post-1"}, "log_id": "create-1"},
                 matching_posts()]
    desk = ToolDesk(api_key="test-key", opener=fake_opener(responses, seen),
                    event_logger=durable.append)
    receipts = desk.execute_calls(PLAN, SPEC, tmp_path)
    result = desk.verify_calls(PLAN, receipts, SPEC, tmp_path)
    assert receipts[0]["status"] == "created"
    assert result["pass"] is True and result["calls"][0]["external_id"] == "post-1"
    assert [r["url"].rsplit("/", 1)[-1] for r in seen] == [
        "BUFFER_LIST_POSTS", "BUFFER_CREATE_POST_DRAFT", "BUFFER_LIST_POSTS"]
    assert all(r["body"]["connected_account_id"] == ACCOUNT for r in seen)
    assert all(r["key"] == "test-key" for r in seen)
    log = (tmp_path / "tool_calls.jsonl").read_text()
    assert len(log.splitlines()) == 6  # start + completion for every API call
    assert len(durable) == 6
    assert TEXT not in log and "test-key" not in log and ACCOUNT not in log


def test_existing_matching_draft_prevents_duplicate_on_retry(tmp_path):
    seen = []
    desk = ToolDesk(api_key="test-key", opener=fake_opener([matching_posts(), matching_posts()], seen))
    receipts = desk.execute_calls(PLAN, SPEC, tmp_path)
    assert receipts[0]["status"] == "already_exists"
    assert len(seen) == 1 and seen[0]["url"].endswith("BUFFER_LIST_POSTS")
    assert desk.verify_calls(PLAN, receipts, SPEC, tmp_path)["pass"] is True
    assert len(seen) == 2


def test_unlisted_action_is_rejected_before_any_network_call(tmp_path):
    seen = []
    desk = ToolDesk(api_key="test-key", opener=fake_opener([], seen))
    with pytest.raises(ToolDeskError, match="not in job allowlist"):
        desk.execute_calls([{"tool_slug": "BUFFER_PUBLISH_POSTS", "arguments": {}}], SPEC, tmp_path)
    assert seen == []


def test_unapproved_channel_is_rejected_before_any_network_call(tmp_path):
    seen = []
    desk = ToolDesk(api_key="test-key", opener=fake_opener([], seen))
    bad = [{"tool_slug": "BUFFER_CREATE_POST_DRAFT",
            "arguments": {"channel_id": "other-channel", "text": TEXT}}]
    with pytest.raises(ToolDeskError, match="not authorized"):
        desk.execute_calls(bad, SPEC, tmp_path)
    assert seen == []


def test_missing_composio_key_fails_closed_and_logs(tmp_path):
    seen, durable = [], []
    desk = ToolDesk(api_key="", opener=fake_opener([], seen), event_logger=durable.append)
    with pytest.raises(ToolDeskError, match="COMPOSIO_API_KEY"):
        desk.execute_calls(PLAN, SPEC, tmp_path)
    assert seen == [] and len(durable) == 2
    assert "missing_api_key" in (tmp_path / "tool_calls.jsonl").read_text()


def test_readback_failure_prevents_verifier_pass(tmp_path):
    seen = []
    desk = ToolDesk(api_key="test-key", opener=fake_opener([empty_posts(),
        {"successful": True, "data": {"id": "post-1"}}, empty_posts()], seen))
    receipts = desk.execute_calls(PLAN, SPEC, tmp_path)
    result = desk.verify_calls(PLAN, receipts, SPEC, tmp_path)
    assert result["pass"] is False


def test_model_sees_only_job_allowed_tool_not_account_or_org_ids():
    contract = model_tool_contract(SPEC)
    assert contract[0]["tool_slug"] == "BUFFER_CREATE_POST_DRAFT"
    assert ACCOUNT not in json.dumps(contract) and ORG not in json.dumps(contract)
    task = model_task({"task": {"objective": "draft"}, "verify_spec": SPEC})
    assert "BUFFER_CREATE_POST_DRAFT" in json.dumps(task)
    assert ACCOUNT not in json.dumps(task) and ORG not in json.dumps(task)


def test_plan_parser_validates_tool_call_shape():
    plan = parse_plan(json.dumps({"tool_calls": PLAN}))
    assert plan["tool_calls"] == PLAN
    with pytest.raises(ReasonerError):
        parse_plan('{"tool_calls":[{"tool_slug":4,"arguments":{}}]}')


def test_verifier_fails_closed_when_tool_readback_fails(tmp_path):
    class FailedDesk:
        def verify_calls(self, *args):
            return {"pass": False, "reasons": ["not found"]}
    execution = {"plan_valid": True, "commands": [], "tool_calls": [{}], "error": None}
    receipt = verify(tmp_path, {"expected_files": []}, execution,
                     tool_desk=FailedDesk(), planned_tools=PLAN)
    assert receipt["verdict"] == "FAIL"
    assert receipt["tool_readback"]["pass"] is False
