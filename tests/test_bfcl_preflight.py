from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_bfcl_preflight.py"
_INJECTED_YAML_STUB = False
try:
    import yaml as _yaml  # noqa: F401
except ModuleNotFoundError:
    def _safe_load(value: str):
        lines = [line.rstrip() for line in value.splitlines() if line.strip()]
        payload: dict[str, object] = {"upstream": {"profiles": {}}}
        if any("active_profile: openrouter" in line for line in lines):
            payload["upstream"]["active_profile"] = "openrouter"  # type: ignore[index]
        if any("api_key_env: OPENROUTER_API_KEY" in line for line in lines):
            payload["upstream"]["profiles"] = {"openrouter": {"api_key_env": "OPENROUTER_API_KEY"}}  # type: ignore[index]
        return payload
    sys.modules["yaml"] = types.SimpleNamespace(safe_load=_safe_load)
    _INJECTED_YAML_STUB = True

SPEC = importlib.util.spec_from_file_location("run_bfcl_preflight", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
if _INJECTED_YAML_STUB:
    sys.modules.pop("yaml", None)


class BfclPreflightTests(unittest.TestCase):
    def test_post_json_includes_authorization_header_when_openai_api_key_set(self) -> None:
        captured_headers: dict[str, str] = {}

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def getcode(self) -> int:
                return 200

            def read(self) -> bytes:
                return b"{}"

        def _fake_urlopen(request, timeout=120):  # type: ignore[no-untyped-def]
            nonlocal captured_headers
            captured_headers = dict(request.header_items())
            return _FakeResponse()

        previous = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ["OPENAI_API_KEY"] = "dummy"
            with mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
                status, payload = MODULE._post_json("http://127.0.0.1:8011", "/v1/chat/completions", {"x": 1})
            self.assertEqual(status, 200)
            self.assertEqual(payload, {})
            self.assertEqual(captured_headers.get("Authorization"), "Bearer dummy")
        finally:
            if previous is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous

    def test_post_json_falls_back_to_dummy_authorization_when_openai_api_key_missing(self) -> None:
        captured_headers: dict[str, str] = {}

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def getcode(self) -> int:
                return 200

            def read(self) -> bytes:
                return b"{}"

        def _fake_urlopen(request, timeout=120):  # type: ignore[no-untyped-def]
            nonlocal captured_headers
            captured_headers = dict(request.header_items())
            return _FakeResponse()

        previous = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ.pop("OPENAI_API_KEY", None)
            with mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
                status, payload = MODULE._post_json("http://127.0.0.1:8011", "/v1/chat/completions", {"x": 1})
            self.assertEqual(status, 200)
            self.assertEqual(payload, {})
            self.assertEqual(captured_headers.get("Authorization"), "Bearer dummy")
        finally:
            if previous is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous

    def test_validate_chat_tool_response_accepts_expected_tool_call(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "echo",
                                    "arguments": json.dumps({"text": "ping"}),
                                }
                            }
                        ]
                    }
                }
            ]
        }
        passed, reason = MODULE.validate_chat_tool_response(payload)
        self.assertTrue(passed)
        self.assertEqual(reason, "ok")

    def test_validate_responses_tool_response_accepts_expected_tool_call(self) -> None:
        payload = {
            "output": [
                {
                    "type": "function_call",
                    "name": "echo",
                    "arguments": json.dumps({"text": "ping"}),
                }
            ]
        }
        passed, reason = MODULE.validate_responses_tool_response(payload)
        self.assertTrue(passed)
        self.assertEqual(reason, "ok")

    def test_validate_chat_text_response_requires_pong(self) -> None:
        payload = {"choices": [{"message": {"content": "PONG"}}]}
        passed, reason = MODULE.validate_chat_text_response(payload)
        self.assertTrue(passed)
        self.assertEqual(reason, "ok")

        bad_payload = {"choices": [{"message": {"content": "hello"}}]}
        passed, reason = MODULE.validate_chat_text_response(bad_payload)
        self.assertFalse(passed)
        self.assertIn("pong", reason.lower())

    def test_resolve_expected_api_key_env_uses_active_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "runtime.yaml"
            config_path.write_text(
                """
upstream:
  active_profile: openrouter
  profiles:
    openrouter:
      api_key_env: OPENROUTER_API_KEY
""".strip(),
                encoding="utf-8",
            )
            previous = os.environ.get("GRC_UPSTREAM_PROFILE")
            try:
                os.environ.pop("GRC_UPSTREAM_PROFILE", None)
                self.assertEqual(MODULE._resolve_expected_api_key_env(str(config_path)), "OPENROUTER_API_KEY")
            finally:
                if previous is None:
                    os.environ.pop("GRC_UPSTREAM_PROFILE", None)
                else:
                    os.environ["GRC_UPSTREAM_PROFILE"] = previous


if __name__ == "__main__":
    unittest.main()
