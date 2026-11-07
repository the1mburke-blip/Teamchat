import json
import re


def parse_grace_decision(raw: str) -> dict[str, object] | None:
    def json_object(value: object) -> dict[str, object] | None:
        if isinstance(value, str):
            text = value.strip()
            fence = re.fullmatch(
                r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n```",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if fence:
                text = fence[1]
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                return None
        return value if isinstance(value, dict) else None

    decision = json_object(raw)
    if decision is None:
        return None

    for key in ("assigned_chair", "reasoning", "next_action"):
        field = decision.get(key)
        if not isinstance(field, str) or not field.strip():
            return None

    packet = json_object(decision.get("task_packet"))
    if not packet:
        return None
    return {**decision, "task_packet": packet}
