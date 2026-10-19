import contextlib
import io
import subprocess
from unittest.mock import patch

import pytest

from dsh.cordis.kernel import (
    CordisKernel,
    VerificationError,
    verify_deliverable_integrity,
)


@pytest.mark.parametrize("suffix,source", [
    (".py", "# TODO: finish implementation\nvalue = 1\n"),
    (".js", 'module.exports = ctx => { console.log("Plugin loaded"); };'),
    (".py", 'print("To register, point your DSH manager here.")\n'),
    (".py", "def create():\n    pass\n"),
    (".py", 'def create():\n    """Creates the plugin."""\n'),
    (".py", "async def create():\n    ...\n"),
    (".py", "def create():\n    raise NotImplementedError\n"),
    (".py", "def create():\n    return None\n"),
    (".py", "def create(flag):\n    if flag:\n        pass\n"),
    (".py", "def create():\n    print('done')\n"),
    (".py", "create = lambda: print('done')\n"),
    (".py", "create = lambda: ...\n"),
    (".py", "import json\n"),
    (".py", "# Nothing implemented\n"),
    (".py", "def broken(:\n"),
    (".py", "def create():\n    return json.dumps({})\n"),
    (".js", 'module.exports = function(ctx) { console.log("done"); };'),
    (".js", "module.exports = () => {};"),
    (".js", 'module.exports = () => console.log("done");'),
    (".mjs", 'export default async () => { console.info("done"); };'),
    (".mjs", "export function build() { return; }"),
    (".mjs", "export default () => undefined;"),
    (".cjs", "module.exports = {};"),
    (".mjs", "export {};"),
    (".mjs", 'import fs from "node:fs";'),
    (".js", '// comment only\nconsole.log("done");'),
    (".js", 'module.exports = ctx => { if (ctx) console.log("done"); };'),
    (".js", "module.exports = undefined;"),
    (".js", "this is not a script"),
    (".mjs", "export class Empty {}"),
    (".js", ""),
    (".py", 'path = "../escape.py"\n'),
    (".py", r'path = "..\\escape.py"' + "\n"),
    (".py", r'path = "\x2e\x2e/escape.py"' + "\n"),
    (".js", 'const path = "../escape.js";'),
    (".js", r'const path = "\u002e\u002e/escape.js";'),
    (".js", r'const path = "\u{ffffff}";'),
])
def test_rejects_incomplete_or_escaping_artifacts(tmp_path, suffix, source):
    artifact = tmp_path / ("deliverable" + suffix)
    artifact.write_text(source, encoding="utf-8")
    with pytest.raises(VerificationError):
        verify_deliverable_integrity(str(artifact))


@pytest.mark.parametrize("suffix,source", [
    (".py", "value = 2\n"),
    (".py", "def double(value):\n    return value * 2\n"),
    (".py", "def label():\n    return 'ready'\n"),
    (".py", "label = lambda: 'ready'\n"),
    (".py", "import json\ndef encode(value):\n    return json.dumps(value)\n"),
    (".py", "def encode(json, value):\n    return json.dumps(value)\n"),
    (".py", "import pathlib as paths\ndef exists(path):\n    return paths.Path(path).is_file()\n"),
    (".py", "class Worker:\n    def build(self, value):\n        return value * 2\n"),
    (".js", "module.exports = function(value) { return value * 2; };"),
    (".js", "module.exports = () => 'ready';"),
    (".mjs", "export default () => { return 'ready'; };"),
    (".mjs", "export default value => value * 2;"),
    (".js", 'module.exports = ctx => { console.log("starting"); ctx.tools.register({name: "double"}); };'),
    (".mjs", 'import fs from "node:fs"\nfs.writeFileSync("result.txt", "ready");'),
    (".js", 'const url = "https://example.com"; module.exports = () => url;'),
    (".JS", 'module.exports = function(value) { return value + 1; };'),
    (".md", "TODO: document ../paths here\n"),
])
def test_accepts_implemented_artifacts_and_leaves_non_scripts_alone(tmp_path, suffix, source):
    artifact = tmp_path / ("deliverable" + suffix)
    artifact.write_text(source, encoding="utf-8")
    verify_deliverable_integrity(str(artifact))


def test_requires_a_physical_file(tmp_path):
    for target in (tmp_path, tmp_path / "missing.py"):
        with pytest.raises(VerificationError, match="missing or not a file"):
            verify_deliverable_integrity(str(target))


def test_rejects_non_utf8_script(tmp_path):
    target = tmp_path / "bad.py"
    target.write_bytes(b"\xff\xfe")
    with pytest.raises(VerificationError, match="Cannot read script"):
        verify_deliverable_integrity(str(target))


@pytest.mark.parametrize("had_original", [True, False])
@pytest.mark.parametrize("suffix,patch_content", [
    (".py", "def build():\n    pass\n"),
    (".js", 'module.exports = ctx => { console.log("done"); };'),
    (".py", 'path = "../escaped.py"\n'),
])
def test_integrity_failure_rolls_back_before_pytest(tmp_path, had_original, suffix, patch_content):
    target = tmp_path / ("tool" + suffix)
    original = b"value = 1\r\n# uncommitted original\r\n"
    if had_original:
        target.write_bytes(original)
    with patch("dsh.cordis.kernel.notify_human"), patch(
        "dsh.cordis.kernel.subprocess.run"
    ) as run, contextlib.redirect_stderr(io.StringIO()) as errors:
        with pytest.raises(SystemExit) as result:
            CordisKernel(str(tmp_path)).apply_and_verify(target.name, patch_content)
    assert result.value.code == 1
    run.assert_not_called()
    assert "VerificationError" in errors.getvalue()
    assert "ROLLBACK" in errors.getvalue()
    assert not target.with_suffix(suffix + ".bak").exists()
    if had_original:
        assert target.read_bytes() == original
    else:
        assert not target.exists()


@pytest.mark.parametrize("mutation", ["delete", "stub"])
def test_pytest_success_cannot_hide_a_missing_or_replaced_deliverable(tmp_path, mutation):
    target = tmp_path / "tool.py"
    original = b"value = 1\r\n"
    target.write_bytes(original)

    def test_process(*args, **kwargs):
        if mutation == "delete":
            target.unlink()
        else:
            target.write_text("def build():\n    pass\n", encoding="utf-8")
        return subprocess.CompletedProcess(["pytest"], 0, "", "")

    with patch("dsh.cordis.kernel.notify_human"), patch(
        "dsh.cordis.kernel.shutil.which", return_value="pytest"
    ), patch("dsh.cordis.kernel.subprocess.run", side_effect=test_process), contextlib.redirect_stderr(io.StringIO()):
        with pytest.raises(SystemExit) as result:
            CordisKernel(str(tmp_path)).apply_and_verify("tool.py", "value = 2\n")
    assert result.value.code == 1
    assert target.read_bytes() == original
    assert not target.with_suffix(".py.bak").exists()


def test_does_not_overwrite_or_remove_an_existing_backup(tmp_path):
    target = tmp_path / "tool.py"
    target.write_text("value = 1\n", encoding="utf-8")
    backup = target.with_suffix(".py.bak")
    backup.write_bytes(b"previous recovery copy\r\n")
    with pytest.raises(VerificationError, match="existing backup"):
        CordisKernel(str(tmp_path)).apply_and_verify("tool.py", "value = 2\n")
    assert target.read_text(encoding="utf-8") == "value = 1\n"
    assert backup.read_bytes() == b"previous recovery copy\r\n"
