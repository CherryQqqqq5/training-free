from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

_INJECTED_YAML_STUB = False
try:
    import yaml as _yaml  # noqa: F401
except ModuleNotFoundError:
    sys.modules["yaml"] = types.SimpleNamespace(
        safe_dump=lambda data, **_: json.dumps(data, ensure_ascii=False, indent=2),
        safe_load=json.loads,
    )
    _INJECTED_YAML_STUB = True

from scripts.run_next_action_live_smoke import _request_for_upstream, run_live_smoke, summarize_results

if _INJECTED_YAML_STUB:
    sys.modules.pop("yaml", None)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "phase2_next_action_smoke"


class NextActionLiveSmokeTests(unittest.TestCase):
    def test_request_for_upstream_converts_orphan_tool_messages(self) -> None:
        request = {
            "messages": [
                {"role": "user", "content": "Read the first match."},
                {"role": "tool", "name": "find", "content": "{\"matches\":[\"notes.txt\"]}"},
                {"role": "tool", "tool_call_id": "call_1", "name": "cat", "content": "ok"},
            ],
            "tools": [],
        }

        converted = _request_for_upstream(request)

        self.assertEqual(converted["messages"][1]["role"], "user")
        self.assertIn("Prior tool output from find", converted["messages"][1]["content"])
        self.assertEqual(converted["messages"][2]["role"], "tool")
        self.assertEqual(request["messages"][1]["role"], "tool")

    def test_summarize_results_counts_conversion_metrics(self) -> None:
        results = []
        for index in range(15):
            results.append(
                {
                    "case_id": f"active_{index}",
                    "family": "find_to_cat",
                    "should_activate": True,
                    "next_tool_plan_activated": True,
                    "next_tool_plan_blocked_reason": "activated",
                    "next_tool_emitted": index < 8,
                    "next_tool_matches_recommendation": index < 8,
                    "next_tool_args_emitted": index < 7,
                    "next_tool_args_match_binding": index < 6,
                    "next_tool_args_match_binding_normalized": index < 10,
                    "next_tool_final_args_match_binding": index < 5,
                    "next_tool_final_args_match_binding_normalized": index < 9,
                    "stop_allowed_false_positive": False,
                }
            )
        for index in range(5):
            results.append(
                {
                    "case_id": f"stop_{index}",
                    "family": "stop_allowed",
                    "should_activate": False,
                    "next_tool_plan_activated": False,
                    "next_tool_plan_blocked_reason": "no_policy_candidate",
                    "next_tool_emitted": None,
                    "next_tool_matches_recommendation": None,
                    "next_tool_args_emitted": None,
                    "next_tool_args_match_binding": None,
                    "next_tool_args_match_binding_normalized": None,
                    "next_tool_final_args_match_binding": None,
                    "next_tool_final_args_match_binding_normalized": None,
                    "stop_allowed_false_positive": False,
                }
            )

        summary = summarize_results(results)

        self.assertEqual(summary["case_count"], 20)
        self.assertEqual(summary["policy_plan_activated_count"], 15)
        self.assertEqual(summary["next_tool_emitted_count"], 8)
        self.assertEqual(summary["recommended_tool_match_count"], 8)
        self.assertEqual(summary["arg_emitted_count"], 7)
        self.assertEqual(summary["arg_binding_match_count"], 6)
        self.assertEqual(summary["normalized_arg_binding_match_count"], 10)
        self.assertEqual(summary["final_arg_binding_match_count"], 5)
        self.assertEqual(summary["final_normalized_arg_binding_match_count"], 9)
        self.assertEqual(summary["stop_allowed_false_positive_count"], 0)
        self.assertTrue(summary["accepted"])
        self.assertEqual(summary["family_summary"]["stop_allowed"]["stop_allowed_false_positive"], 0)

    def test_dry_run_compiles_and_writes_trace_summaries_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            runtime_config = tmp / "runtime.json"
            runtime_config.write_text(
                json.dumps(
                    {
                        "timeout_sec": 5,
                        "runtime_policy": {
                            "inject_structured_tool_guidance": True,
                            "inject_context_literal_hints": True,
                            "resolve_contextual_string_args": True,
                        },
                        "upstream": {
                            "active_profile": "local",
                            "profiles": {
                                "local": {
                                    "base_url": "http://127.0.0.1:1/v1",
                                    "api_key_env": "DUMMY_API_KEY",
                                    "model": "demo-live-smoke",
                                }
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            out_root = tmp / "out"
            summary = run_live_smoke(
                fixtures_dir=FIXTURES_DIR,
                runtime_config=runtime_config,
                out_root=out_root,
                max_cases=20,
                compiler_generated=True,
                dry_run=True,
            )

            manifest = json.loads((out_root / "run_manifest.json").read_text(encoding="utf-8"))
            saved_summary = json.loads((out_root / "live_smoke_summary.json").read_text(encoding="utf-8"))
            traces = sorted((out_root / "traces").glob("*.json"))

        self.assertTrue(manifest["dry_run"])
        self.assertEqual(summary["case_count"], 20)
        self.assertEqual(saved_summary["policy_plan_activated_count"], 13)
        self.assertEqual(saved_summary["next_tool_emitted_count"], 13)
        self.assertEqual(saved_summary["recommended_tool_match_count"], 13)
        self.assertEqual(saved_summary["arg_binding_match_count"], 13)
        self.assertEqual(saved_summary["normalized_arg_binding_match_count"], 13)
        self.assertEqual(saved_summary["final_arg_binding_match_count"], 8)
        self.assertEqual(saved_summary["final_normalized_arg_binding_match_count"], 13)
        self.assertEqual(saved_summary["blocked_reason_distribution"].get("action_candidate_guard_rejected", 0), 2)
        self.assertEqual(saved_summary["stop_allowed_false_positive_count"], 0)
        self.assertEqual(len(traces), 20)


if __name__ == "__main__":
    unittest.main()
