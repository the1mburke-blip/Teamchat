import ast
import io
import json
import pathlib
import sys
import unittest
import urllib.error
import zipfile
from unittest.mock import MagicMock, patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dsh.provider import call_llm_raw, format_code_prompt


class ProviderChecks(unittest.TestCase):
    def setUp(self):
        loader = patch("dsh.provider._load_env_file")
        loader.start()
        self.addCleanup(loader.stop)

    def check_route(self, env, endpoint, model, key):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "value = 1\n"}}]}
        ).encode("utf-8")
        with patch.dict("os.environ", env, clear=True), patch(
            "dsh.provider.urllib.request.urlopen", return_value=response
        ) as open_url:
            self.assertEqual(call_llm_raw("Update this file"), "value = 1\n")
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, endpoint)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + key)
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(open_url.call_args.kwargs["timeout"], 60)
        self.assertEqual(json.loads(request.data), {
            "model": model,
            "messages": [{"role": "user", "content": "Update this file"}],
            "temperature": 0.0,
            "max_tokens": 2048,
        })

    def test_openrouter_precedence_and_trimmed_key(self):
        self.check_route(
            {"OPENROUTER_API_KEY": "  dummy-or  ", "DEEPSEEK_API_KEY": "dummy-ds"},
            "https://openrouter.ai/api/v1/chat/completions",
            "deepseek/deepseek-chat", "dummy-or",
        )

    def test_deepseek_endpoint_and_trimmed_key(self):
        self.check_route(
            {"DEEPSEEK_API_KEY": "  dummy-ds\n"},
            "https://api.deepseek.com/chat/completions", "deepseek-chat", "dummy-ds",
        )

    def test_blank_openrouter_key_falls_back_to_deepseek(self):
        self.check_route(
            {"OPENROUTER_API_KEY": " \t ", "DEEPSEEK_API_KEY": "dummy-ds"},
            "https://api.deepseek.com/chat/completions", "deepseek-chat", "dummy-ds",
        )

    def test_missing_and_blank_keys_raise_before_request(self):
        for env in ({}, {"OPENROUTER_API_KEY": " \t", "DEEPSEEK_API_KEY": "\n"}):
            with self.subTest(env=env), patch.dict("os.environ", env, clear=True), patch(
                "dsh.provider.urllib.request.urlopen"
            ) as open_url:
                with self.assertRaisesRegex(RuntimeError, "Missing API Key in .env file."):
                    call_llm_raw("Update this file")
                open_url.assert_not_called()

    def test_http_error_surfaces_status_and_replaces_invalid_utf8(self):
        error = urllib.error.HTTPError(
            "https://api.deepseek.com/chat/completions", 429, "rate limited", {},
            io.BytesIO(b"rate limited: \xff"),
        )
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "dummy-ds"}, clear=True), patch(
            "dsh.provider.urllib.request.urlopen", side_effect=error
        ):
            with self.assertRaises(RuntimeError) as result:
                call_llm_raw("Update this file")
        self.assertEqual(str(result.exception), "API Error (HTTP 429): rate limited: \ufffd")

    def test_prompt_formatter_is_complete(self):
        result = format_code_prompt("value = 1", "Change the value")
        self.assertIn("TASK: Change the value", result)
        self.assertIn("CURRENT CODE:", result)
        self.assertIn("value = 1", result)
        self.assertIn("Return ONLY the complete updated file content", result)
        self.assertEqual(result.count("```"), 2)

    def test_token_limited_response_is_rejected(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            "choices": [{"finish_reason": "length", "message": {"content": "incomplete file"}}]
        }).encode("utf-8")
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "dummy-or"}, clear=True), patch(
            "dsh.provider.urllib.request.urlopen", return_value=response
        ):
            with self.assertRaisesRegex(RuntimeError, "output token limit"):
                call_llm_raw("Update this file")
