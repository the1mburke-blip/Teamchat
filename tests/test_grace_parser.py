import json

import pytest

from scripts.grace_parser import parse_grace_decision


@pytest.mark.parametrize("fence", [None, "", "json"])
def test_parse_grace_decision_preserves_packet(fence):
    packet = {"command": "Run `pytest`"}
    decision = {
        "assigned_chair": "CODEX",
        "reasoning": "Repository repair",
        "next_action": "Run the regression test",
        "task_packet": packet,
    }
    if fence is None:
        raw = json.dumps(decision)
    else:
        wrapped_packet = f"```{fence}\n{json.dumps(packet)}\n```"
        wrapped_decision = json.dumps({**decision, "task_packet": wrapped_packet})
        raw = f"```{fence}\r\n{wrapped_decision}\r\n```"

    assert parse_grace_decision(raw) == decision


@pytest.mark.parametrize("key", ["assigned_chair", "reasoning", "next_action", "task_packet"])
def test_parse_grace_decision_rejects_missing_keys(key):
    decision = {
        "assigned_chair": "CODEX",
        "reasoning": "Repository repair",
        "next_action": "Run the regression test",
        "task_packet": {"command": "Run pytest"},
    }
    del decision[key]

    assert parse_grace_decision(json.dumps(decision)) is None


def test_parse_grace_decision_rejects_malformed_payloads():
    assert parse_grace_decision('```json\n{"assigned_chair":\n```') is None
    assert parse_grace_decision("[]") is None
    assert parse_grace_decision(json.dumps({
        "assigned_chair": "CODEX",
        "reasoning": "Repository repair",
        "next_action": "Run the regression test",
        "task_packet": "[object Object]",
    })) is None
