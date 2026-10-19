import contextlib
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from dsh.provider import _load_env_file, call_llm_raw


class EnvironmentChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        for scope in (contextlib.chdir(self.root), patch.dict(os.environ, {}, clear=True)):
            scope.__enter__()
            self.addCleanup(scope.__exit__, None, None, None)

    def test_env_quotes_comments_and_equals(self):
        (self.root / ".env").write_text(
            '# comment\n\nOPENROUTER_API_KEY="dummy-key"\n'
            "DEEPSEEK_API_KEY='dummy-deepseek'\nTOKEN=a=b\nignored line\n",
            encoding="utf-8",
        )
        _load_env_file()
        self.assertEqual(os.environ["OPENROUTER_API_KEY"], "dummy-key")
        self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "dummy-deepseek")
        self.assertEqual(os.environ["TOKEN"], "a=b")

    def test_env_does_not_override_existing_environment(self):
        os.environ["OPENROUTER_API_KEY"] = "shell-key"
        (self.root / ".env").write_text('OPENROUTER_API_KEY="file-key"\n', encoding="utf-8")
        _load_env_file()
        self.assertEqual(os.environ["OPENROUTER_API_KEY"], "shell-key")

    def test_missing_env_file_is_allowed_until_provider_is_called(self):
        _load_env_file()
        with patch("dsh.provider.urllib.request.urlopen") as open_url:
            with self.assertRaisesRegex(RuntimeError, "Missing API Key"):
                call_llm_raw("test")
            open_url.assert_not_called()

    def test_provider_loads_env_before_building_request(self):
        (self.root / ".env").write_text('OPENROUTER_API_KEY="dummy-key"\n', encoding="utf-8")
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "answer"}}]}
        ).encode("utf-8")
        with patch("dsh.provider.urllib.request.urlopen", return_value=response) as open_url:
            self.assertEqual(call_llm_raw("test"), "answer")
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer dummy-key")
