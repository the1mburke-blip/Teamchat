import ast
import contextlib
import io
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dsh.cordis.kernel import CordisKernel


class KernelChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.kernel = CordisKernel(str(self.root))
        self.target = self.root / "sample.py"
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        notification = patch("dsh.cordis.kernel.notify_human")
        self.notify = notification.start()
        self.addCleanup(notification.stop)
        for interception in (
            contextlib.redirect_stdout(self.stdout),
            contextlib.redirect_stderr(self.stderr),
        ):
            interception.__enter__()
            self.addCleanup(interception.__exit__, None, None, None)

    def assert_rollback_exit(self, target, content):
        with self.assertRaises(SystemExit) as result:
            self.kernel.apply_and_verify(target, content)
        self.assertEqual(result.exception.code, 1)

    def test_real_compile_success_keeps_update_and_removes_backup(self):
        self.target.write_text("value = 1\n", encoding="utf-8")
        with patch("dsh.cordis.kernel.shutil.which", return_value=None):
            self.kernel.apply_and_verify("sample.py", "value = 2\n")
        self.assertEqual(self.target.read_text(), "value = 2\n")
        self.assertFalse(self.target.with_suffix(".py.bak").exists())
        self.assertIn("py_compile syntax check (pytest not installed)", self.stdout.getvalue())
        self.assertIn("py_compile syntax check (pytest not installed)", self.notify.call_args.args[1])

    def test_real_compile_failure_restores_existing_file(self):
        self.target.write_text("value = 1\n", encoding="utf-8")
        with patch("dsh.cordis.kernel.shutil.which", return_value=None):
            self.assert_rollback_exit("sample.py", "def broken(:\n")
        self.assertEqual(self.target.read_text(), "value = 1\n")
        self.assertFalse(self.target.with_suffix(".py.bak").exists())
        self.assertIn("py_compile syntax check (pytest not installed)", self.stderr.getvalue())
        self.assertIn("py_compile syntax check (pytest not installed)", self.notify.call_args.args[1])

    def test_real_compile_failure_removes_new_file(self):
        with patch("dsh.cordis.kernel.shutil.which", return_value=None):
            self.assert_rollback_exit("sample.py", "def broken(:\n")
        self.assertFalse(self.target.exists())

    def test_missing_test_executable_restores_existing_file(self):
        self.target.write_text("value = 1\n", encoding="utf-8")
        with patch("dsh.cordis.kernel.shutil.which", return_value="pytest.exe"), patch(
            "dsh.cordis.kernel.subprocess.run", side_effect=FileNotFoundError("missing executable")
        ) as run:
            self.assert_rollback_exit("sample.py", "value = 2\n")
        self.assertEqual(self.target.read_text(), "value = 1\n")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], ["pytest"])

    def test_simulated_pytest_failure_restores_uncommitted_content_without_git(self):
        self.target.write_text("uncommitted = 1\n", encoding="utf-8")
        with patch("dsh.cordis.kernel.shutil.which", return_value="pytest.exe"), patch(
            "dsh.cordis.kernel.subprocess.run",
            return_value=subprocess.CompletedProcess(["pytest"], 1, "test failure", ""),
        ) as run:
            self.assert_rollback_exit("sample.py", "uncommitted = 2\n")
        self.assertEqual(self.target.read_text(), "uncommitted = 1\n")
        self.assertEqual(run.call_count, 1)
        self.assertIn("pytest test suite", self.stderr.getvalue())
        self.assertIn("pytest test suite", self.notify.call_args.args[1])

    def test_simulated_pytest_success_reports_mode(self):
        with patch("dsh.cordis.kernel.shutil.which", return_value="pytest.exe"), patch(
            "dsh.cordis.kernel.subprocess.run",
            return_value=subprocess.CompletedProcess(["pytest"], 0, "", ""),
        ) as run:
            self.kernel.apply_and_verify("sample.py", "value = 2\n")
        self.assertEqual(self.target.read_text(), "value = 2\n")
        self.assertEqual(run.call_args.args[0], ["pytest"])
        self.assertIn("pytest test suite", self.stdout.getvalue())
        self.assertIn("pytest test suite", self.notify.call_args.args[1])

    def test_all_named_protected_directories_are_denied(self):
        for target in (
            ".git/config", ".github/workflows/check.yml", "dsh/cordis/kernel.py",
            "icarus/runtime/icarus_run.py", "icarus/core/runtime.py",
            "nested/dsh/cordis/secret.py",
        ):
            with self.subTest(target=target):
                with self.assertRaises(SystemExit) as result:
                    self.kernel.validate_path(target)
                self.assertEqual(result.exception.code, 1)

    def test_case_variants_of_protected_paths_are_denied(self):
        for target in (
            ".GIT/config", ".GitHub/workflows/check.yml", "DSH/CORDIS/kernel.py",
            "ICARUS/RUNTIME/icarus_run.py", "ICARUS/CORE/runtime.py",
            "nested/DsH/CoRdIs/secret.py",
        ):
            with self.subTest(target=target):
                with self.assertRaises(SystemExit) as result:
                    self.kernel.validate_path(target)
                self.assertEqual(result.exception.code, 1)

    def test_relative_escape_halts_before_file_mutation_or_test_runner(self):
        outside = self.root.parent / (self.root.name + "-outside.py")
        self.assertFalse(outside.exists())
        with patch("dsh.cordis.kernel.subprocess.run") as run:
            self.assert_rollback_exit("../" + outside.name, "value = 2\n")
        self.assertFalse(outside.exists())
        self.assertFalse(outside.with_suffix(".py.bak").exists())
        run.assert_not_called()
        self.assertIn("Path outside workspace", self.stderr.getvalue())
        self.assertIn("Out-of-workspace", self.notify.call_args.args[1])

    def test_absolute_escape_halts_before_file_mutation_or_test_runner(self):
        outside = self.root.parent / (self.root.name + "-outside.py")
        with patch("dsh.cordis.kernel.subprocess.run") as run:
            self.assert_rollback_exit(str(outside), "value = 2\n")
        self.assertFalse(outside.exists())
        run.assert_not_called()

    def test_current_directory_is_resolved_as_root(self):
        self.assertEqual(CordisKernel().root, ROOT)
