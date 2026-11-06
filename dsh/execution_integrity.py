"""Admission checks for supervisor-recorded task execution receipts.

The supervisor owns both inputs. Model-authored counters or events are not
attestations. This check must run in addition to physical artifact readback.
"""


class ExecutionRejected(ValueError):
    pass


def validate_execution(task, receipt):
    if not isinstance(task, dict) or not isinstance(receipt, dict):
        raise ExecutionRejected("INVALID_EXECUTION_RECEIPT")
    if not task.get("task_id") or receipt.get("task_id") != task["task_id"]:
        raise ExecutionRejected("EXECUTION_TASK_ID_MISMATCH")
    flags = (task.get("requires_tools", False), task.get("requires_state_mutation", False))
    if any(type(flag) is not bool for flag in flags):
        raise ExecutionRejected("INVALID_EXECUTION_REQUIREMENTS")
    count = receipt.get("tools_executed")
    if type(count) is not int or count < 0:
        raise ExecutionRejected("INVALID_TOOL_EXECUTION_COUNT")
    if any(flags) and count == 0:
        raise ExecutionRejected("ZERO_TOOL_EXECUTION_REJECTED")
    events = receipt.get("tool_events")
    if not isinstance(events, list) or any(
            not isinstance(event, dict) or type(event.get("executed")) is not bool
            or type(event.get("success")) is not bool for event in events):
        raise ExecutionRejected("INVALID_TOOL_EXECUTION_EVENTS")
    executed = [event for event in events if event["executed"]]
    if count != len(executed):
        raise ExecutionRejected("TOOL_EXECUTION_COUNT_MISMATCH")
    if any(not event["executed"] or not event["success"] for event in events):
        raise ExecutionRejected("TOOL_EXECUTION_FAILED")
    if flags[1] and not any(event.get("state_mutation") is True for event in executed):
        raise ExecutionRejected("STATE_MUTATION_NOT_EXECUTED")
    if receipt.get("readback_status") != "VERIFIED":
        raise ExecutionRejected("EXECUTION_READBACK_NOT_VERIFIED")
    return count
