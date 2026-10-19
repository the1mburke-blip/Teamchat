import contextlib
import io
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from dsh.runner import extract_code_block, run_harness_task, sync_repository_state


class RunnerChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        for scope in (
            contextlib.chdir(self.root),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            scope.__enter__()
            self.addCleanup(scope.__exit__, None, None, None)

    def test_runner_applies_mocked_model_patch_and_real_compile(self):
        with patch("dsh.runner.call_llm_raw", return_value="```python\nvalue = 7\n```") as model, patch(
            "dsh.cordis.kernel.shutil.which", return_value=None
        ), patch("dsh.cordis.kernel.notify_human"), patch("dsh.runner.sync_repository_state") as sync:
            run_harness_task("sample.py", "Set value to seven")
        sync.assert_called_once_with()
        self.assertEqual((self.root / "sample.py").read_text(), "value = 7\n")
        self.assertIn("Set value to seven", model.call_args.args[0])

    def test_runner_denies_protected_target_before_provider_call(self):
        with patch("dsh.runner.call_llm_raw") as model, patch("dsh.cordis.kernel.notify_human"), patch(
            "dsh.runner.sync_repository_state"
        ):
            with self.assertRaises(SystemExit) as result:
                run_harness_task("DSH/CORDIS/kernel.py", "Change file")
        self.assertEqual(result.exception.code, 1)
        model.assert_not_called()

    def test_sync_invokes_expected_git_command(self):
        with patch("dsh.runner.subprocess.run") as run:
            sync_repository_state()
        run.assert_called_once_with(
            ["git", "pull", "--rebase", "origin", "main"],
            check=False, capture_output=True, text=True,
        )

    def test_sync_handles_missing_git_with_warning(self):
        errors = io.StringIO()
        with patch("dsh.runner.subprocess.run", side_effect=FileNotFoundError("git missing")), contextlib.redirect_stderr(errors):
            sync_repository_state()
        self.assertIn("[DSH SYNC WARNING]", errors.getvalue())

    def test_sync_nonzero_exit_is_best_effort(self):
        with patch("dsh.runner.subprocess.run", return_value=subprocess.CompletedProcess(
            ["git", "pull", "--rebase", "origin", "main"], 1, "", "pull failed"
        )):
            sync_repository_state()

    def test_sync_occurs_before_target_is_read_and_provider_is_called(self):
        target = self.root / "sample.py"
        target.write_text("value = 1\n", encoding="utf-8")

        def simulated_sync():
            target.write_text("value = 2\n", encoding="utf-8")

        def simulated_model(prompt):
            self.assertIn("value = 2", prompt)
            return "value = 3\n"

        with patch("dsh.runner.sync_repository_state", side_effect=simulated_sync), patch(
            "dsh.runner.call_llm_raw", side_effect=simulated_model
        ), patch("dsh.cordis.kernel.shutil.which", return_value=None), patch("dsh.cordis.kernel.notify_human"):
            run_harness_task("sample.py", "Set value to three")
        self.assertEqual(target.read_text(), "value = 3")

    def test_code_extraction(self):
        self.assertEqual(extract_code_block("```python\nvalue = 1\n```"), "value = 1\n")
        self.assertEqual(extract_code_block(" value = 1 "), "value = 1")

    def test_runner_includes_existing_file_contents_in_prompt(self):
        (self.root / "sample.py").write_text("value = 7\n", encoding="utf-8")
        with patch("dsh.runner.sync_repository_state"), patch(
            "dsh.runner.call_llm_raw", return_value="value = 8"
        ) as model, patch("dsh.cordis.kernel.CordisKernel.apply_and_verify") as apply:
            run_harness_task("sample.py", "Set value to eight")
        self.assertIn("value = 7", model.call_args.args[0])
        apply.assert_called_once_with("sample.py", "value = 8")

    def test_runner_provider_failure_keeps_original_file(self):
        target = self.root / "sample.py"
        target.write_text("value = 7\n", encoding="utf-8")
        with patch("dsh.runner.sync_repository_state"), patch(
            "dsh.runner.call_llm_raw", side_effect=RuntimeError("provider unavailable")
        ), patch("dsh.cordis.kernel.CordisKernel.apply_and_verify") as apply:
            with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
                run_harness_task("sample.py", "Change the value")
        self.assertEqual(target.read_text(), "value = 7\n")
        apply.assert_not_called()

    def test_runner_verification_failure_restores_original_file(self):
        target = self.root / "sample.py"
        target.write_text("value = 7\n", encoding="utf-8")
        with patch("dsh.runner.sync_repository_state"), patch(
            "dsh.runner.call_llm_raw", return_value="```python\ndef broken(:\n```"
        ), patch("dsh.cordis.kernel.shutil.which", return_value=None), patch("dsh.cordis.kernel.notify_human"):
            with self.assertRaises(SystemExit) as result:
                run_harness_task("sample.py", "Change the value")
        self.assertEqual(result.exception.code, 1)
        self.assertEqual(target.read_text(), "value = 7\n")
        self.assertFalse(target.with_suffix(".py.bak").exists())
