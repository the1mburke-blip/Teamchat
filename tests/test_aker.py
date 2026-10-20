import json
import pytest

from icarus import aker


def c(rc=0, out="", before=1, after=0, hb="a", ha="b"):
    return aker.classify(rc, out, before, after, hb, ha)[0]


def test_idle_when_nothing_pending():
    assert c(before=0, after=0, ha="a") == "IDLE"


def test_verifying_only_with_progress_and_new_head():
    assert c() == "VERIFYING"
    assert c(ha="a") == "FAIL"          # clean exit, no commit -> not progress
    assert c(after=1) == "FAIL"         # nothing completed


def test_yield_is_not_success_claim():
    assert c(out="[ICARUS YIELD] x", after=1, ha="a") == "YIELDED"


def test_task_limit_and_failure():
    assert c(rc=2, before=2, after=1) == "EXECUTING"
    assert c(rc=2, after=1, ha="a") == "BLOCKED"
    assert c(rc=1) == "FAIL"


def test_never_emits_handoff_or_pass(tmp_path):
    for bad in ("HANDOFF_READY", "PASS"):
        with pytest.raises(ValueError):
            aker.write_receipt(bad, {}, str(tmp_path / "r.json"))


def test_main_idle_skips_loop(tmp_path):
    called = []
    receipt = tmp_path / "r.json"
    rc = aker.main(["--receipt", str(receipt)], count=lambda r: 0, head=lambda r: "a",
                   loop=lambda *a: called.append(1))
    assert rc == 0 and not called
    assert json.loads(receipt.read_text())["status"] == "IDLE"


def test_main_runs_loop_and_records_verifying(tmp_path):
    state = {"n": 2, "h": "a"}

    def loop(root, max_tasks):
        state.update(n=0, h="b")
        return 0, "ok\n", ""

    receipt = tmp_path / "r.json"
    rc = aker.main(["--receipt", str(receipt)], count=lambda r: state["n"],
                   head=lambda r: state["h"], loop=loop)
    data = json.loads(receipt.read_text())
    assert rc == 0 and data["status"] == "VERIFYING"
    assert data["details"]["head_before"] == "a" and data["details"]["head_after"] == "b"


def test_main_records_exception_as_fail(tmp_path):
    def boom(r):
        raise RuntimeError("x")

    receipt = tmp_path / "r.json"
    assert aker.main(["--receipt", str(receipt)], count=boom) == 1
    assert json.loads(receipt.read_text())["status"] == "FAIL"
