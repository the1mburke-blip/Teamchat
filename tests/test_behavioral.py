import contextlib
import io
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

from dsh.cordis.kernel import CordisKernel


class BehavioralVerificationChecks(unittest.TestCase):
    def test_real_pytest_success_then_failure_restores_original_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "test_sample.py").write_text(
                'import pathlib\nimport runpy\n\n'
                'def test_value():\n'
                '    source = pathlib.Path(__file__).with_name("sample.py")\n'
                '    assert runpy.run_path(str(source))["value"] == 2\n',
                encoding="utf-8",
            )
            kernel = CordisKernel(str(root))
            output, errors = io.StringIO(), io.StringIO()
            executable_directory = str(pathlib.Path(sys.executable).parent)
            with patch.dict(os.environ, {"PATH": executable_directory + os.pathsep + os.environ.get("PATH", "")}), patch(
                "dsh.cordis.kernel.notify_human"
            ), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                kernel.apply_and_verify("sample.py", "value = 2\n")
                self.assertEqual((root / "sample.py").read_text(), "value = 2\n")
                with self.assertRaises(SystemExit) as result:
                    kernel.apply_and_verify("sample.py", "value = 3\n")
            self.assertEqual(result.exception.code, 1)
            self.assertEqual((root / "sample.py").read_text(), "value = 2\n")
            self.assertFalse((root / "sample.py.bak").exists())
            self.assertIn("via pytest test suite", output.getvalue())
            self.assertIn("via pytest test suite", errors.getvalue())
            self.assertIn("1 failed", errors.getvalue())
