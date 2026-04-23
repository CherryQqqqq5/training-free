from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

_INJECTED_YAML_STUB = False
try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    sys.modules["yaml"] = types.SimpleNamespace(
        safe_dump=lambda data, **_: json.dumps(data, ensure_ascii=False, indent=2),
        safe_load=json.loads,
    )
    _INJECTED_YAML_STUB = True

from grc.compiler.trace_to_patch import compile_patch

if _INJECTED_YAML_STUB:
    sys.modules.pop("yaml", None)


def _load_bundle(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml

        return yaml.safe_load(text)
    except ModuleNotFoundError:
        return json.loads(text)


class TraceToPatchTests(unittest.TestCase):
    def test_compile_patch_emits_actionable_continuation_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            candidate_dir = root / "candidate"
            failure_path.write_text(
                json.dumps(
                    {
                        "trace_id": "trace_1",
                        "turn_index": 0,
                        "tool_name": "__none__",
                        "error_type": "actionable_no_tool_decision",
                        "stage": "PRE_TOOL",
                        "failure_type": "ACTIONABLE_NO_TOOL_DECISION",
                        "failure_label": "(PRE_TOOL,ACTIONABLE_NO_TOOL_DECISION)",
                        "request_predicates": ["tools_available", "prior_explicit_literals_present"],
                        "request_literals": ["report.txt"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            compile_status = compile_patch(
                str(failure_path),
                str(out_path),
                patch_id="patch_actionable_no_tool_v1",
                candidate_dir=str(candidate_dir),
            )
            bundle = _load_bundle(out_path)
            policy_units = _load_bundle(candidate_dir / "policy_unit.yaml")

        self.assertEqual(compile_status["status"], "actionable_patch")
        self.assertEqual(len(bundle["rules"]), 1)
        rule = bundle["rules"][0]
        self.assertEqual(
            rule["rule_id"],
            "rule_global_no_tool_actionable_no_tool_decision_prior_explicit_literals_present_tools_available_v1",
        )
        self.assertEqual(rule["trigger"]["request_predicates"], ["prior_explicit_literals_present", "tools_available"])
        self.assertEqual(rule["scope"]["patch_sites"], ["prompt_injector", "policy_executor"])
        self.assertEqual(
            rule["action"]["decision_policy"]["request_predicates"],
            ["prior_explicit_literals_present", "tools_available"],
        )
        self.assertEqual(
            rule["action"]["decision_policy"]["forbidden_terminations"],
            ["prose_only_no_tool_termination"],
        )
        self.assertEqual(
            rule["action"]["decision_policy"]["evidence_requirements"],
            ["prior_explicit_literals_present", "tools_available"],
        )
        self.assertEqual(rule["validation_contract"]["forbidden_terminations"], [])
        self.assertEqual(rule["validation_contract"]["evidence_requirements"], [])
        self.assertTrue(rule["action"]["prompt_injection"]["fragments"])
        self.assertFalse(any("report.txt" in fragment for fragment in rule["action"]["prompt_fragments"]))
        self.assertEqual(
            policy_units["policy_units"][0]["source_failure_signature"]["type"],
            "ACTIONABLE_NO_TOOL_DECISION",
        )

    def test_compile_patch_emits_post_tool_policy_first_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            candidate_dir = root / "candidate"
            failure_path.write_text(
                json.dumps(
                    {
                        "trace_id": "trace_1",
                        "turn_index": 0,
                        "tool_name": "__none__",
                        "error_type": "post_tool_prose_summary",
                        "stage": "POST_TOOL",
                        "failure_type": "POST_TOOL_PROSE_SUMMARY",
                        "failure_label": "(POST_TOOL,POST_TOOL_PROSE_SUMMARY)",
                        "request_predicates": ["tools_available", "prior_tool_outputs_present"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            compile_status = compile_patch(
                str(failure_path),
                str(out_path),
                patch_id="patch_post_tool_prose_v1",
                candidate_dir=str(candidate_dir),
            )
            bundle = _load_bundle(out_path)
            policy_units = _load_bundle(candidate_dir / "policy_unit.yaml")

        self.assertEqual(compile_status["status"], "actionable_patch")
        self.assertEqual(len(bundle["rules"]), 1)
        rule = bundle["rules"][0]
        self.assertEqual(
            rule["rule_id"],
            "rule_global_no_tool_post_tool_prose_summary_prior_tool_outputs_present_tools_available_v1",
        )
        self.assertEqual(rule["trigger"]["request_predicates"], ["prior_tool_outputs_present", "tools_available"])
        self.assertEqual(rule["scope"]["patch_sites"], ["prompt_injector", "policy_executor"])
        self.assertEqual(
            rule["action"]["decision_policy"]["forbidden_terminations"],
            ["prose_only_no_tool_termination"],
        )
        self.assertEqual(
            rule["action"]["decision_policy"]["evidence_requirements"],
            ["prior_tool_outputs_present", "tools_available"],
        )
        self.assertIn(
            "prior tool outputs already provide enough local evidence",
            rule["action"]["decision_policy"]["continue_condition"],
        )
        self.assertTrue(rule["action"]["prompt_injection"]["fragments"])
        self.assertEqual(
            policy_units["policy_units"][0]["source_failure_signature"]["type"],
            "POST_TOOL_PROSE_SUMMARY",
        )

    def test_compile_patch_emits_split_global_hallucinated_completion_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            failure_path.write_text(
                json.dumps(
                    {
                        "trace_id": "trace_1",
                        "turn_index": 0,
                        "tool_name": "__none__",
                        "error_type": "hallucinated_completion",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            compile_status = compile_patch(str(failure_path), str(out_path), patch_id="patch_hallucinated_v1")
            bundle = _load_bundle(out_path)
            status_payload = json.loads((root / "compile_status.json").read_text(encoding="utf-8"))

        self.assertEqual(bundle["patch_id"], "patch_hallucinated_v1")
        self.assertEqual(bundle["source_failure_count"], 1)
        self.assertEqual(len(bundle["rules"]), 1)
        self.assertEqual(compile_status["status"], "actionable_patch")
        self.assertEqual(status_payload["status"], "actionable_patch")

        rule = bundle["rules"][0]
        self.assertEqual(rule["rule_id"], "rule_global_no_tool_hallucinated_completion_v1")
        self.assertEqual(rule["scope"]["patch_sites"], ["tool_guard", "verification_hook", "fallback_router"])
        self.assertEqual(rule["action"]["prompt_injection"]["fragments"], [])
        self.assertEqual(
            rule["action"]["fallback_router"]["strategy"],
            "record_only",
        )
        self.assertEqual(
            rule["action"]["fallback_router"]["on_issue_kinds"],
            ["hallucinated_completion"],
        )
        self.assertEqual(rule["action"]["decision_policy"]["request_predicates"], [])
        self.assertEqual(
            rule["action"]["decision_policy"]["forbidden_terminations"],
            ["claim_progress_without_corresponding_tool_call"],
        )
        self.assertEqual(
            rule["action"]["decision_policy"]["continue_condition"],
            "emit the concrete tool call before describing progress or completion",
        )
        self.assertFalse(rule["validation_contract"]["require_known_tool"])
        self.assertIn(
            "Do not claim that work has already started or completed",
            rule["action"]["prompt_fragments"][0],
        )

    def test_compile_patch_emits_global_continuation_prompt_for_empty_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            failure_path.write_text(
                json.dumps(
                    {
                        "trace_id": "trace_1",
                        "turn_index": 0,
                        "tool_name": "__none__",
                        "error_type": "empty_tool_call",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            compile_patch(str(failure_path), str(out_path), patch_id="patch_empty_tool_v1")
            bundle = _load_bundle(out_path)

        rule = bundle["rules"][0]
        prompt_fragments = rule["action"]["prompt_fragments"]
        self.assertEqual(rule["rule_id"], "rule_global_no_tool_empty_tool_call_v1")
        self.assertEqual(rule["scope"]["patch_sites"], ["tool_guard", "verification_hook", "fallback_router"])
        self.assertEqual(rule["action"]["prompt_injection"]["fragments"], [])
        self.assertEqual(rule["action"]["fallback_router"]["strategy"], "record_only")
        self.assertEqual(
            rule["action"]["decision_policy"]["continue_condition"],
            "a tool-enabled turn produced no tool call and should continue with a concrete tool action",
        )
        self.assertEqual(rule["action"]["decision_policy"]["forbidden_terminations"], [])
        self.assertTrue(
            any("emit the next tool call instead of replying with explanatory prose" in fragment for fragment in prompt_fragments)
        )
        self.assertTrue(
            any("avoid adding a free-form status summary" in fragment for fragment in prompt_fragments)
        )
        self.assertEqual(bundle["failure_ir"][0]["tool_name"], "__none__")

    def test_compile_patch_splits_global_no_tool_failures_by_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            failure_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "trace_id": "trace_1",
                                "turn_index": 0,
                                "tool_name": "__none__",
                                "error_type": "empty_tool_call",
                            }
                        ),
                        json.dumps(
                            {
                                "trace_id": "trace_2",
                                "turn_index": 0,
                                "tool_name": "__none__",
                                "error_type": "natural_language_termination",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            compile_patch(str(failure_path), str(out_path), patch_id="patch_split_global_v1")
            bundle = _load_bundle(out_path)

        self.assertEqual(
            [rule["rule_id"] for rule in bundle["rules"]],
            [
                "rule_global_no_tool_empty_tool_call_v1",
                "rule_global_no_tool_natural_language_termination_v1",
            ],
        )
        self.assertEqual(
            [failure_ir["error_types"] for failure_ir in bundle["failure_ir"]],
            [["empty_tool_call"], ["natural_language_termination"]],
        )

    def test_compile_patch_emits_state_reuse_prompt_for_redundant_clarification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            failure_path.write_text(
                json.dumps(
                    {
                        "trace_id": "trace_1",
                        "turn_index": 0,
                        "tool_name": "__none__",
                        "error_type": "redundant_clarification_request",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            compile_patch(str(failure_path), str(out_path), patch_id="patch_redundant_clarification_v1")
            bundle = _load_bundle(out_path)

        rule = bundle["rules"][0]
        self.assertEqual(rule["rule_id"], "rule_global_no_tool_redundant_clarification_request_v1")
        self.assertEqual(rule["action"]["fallback_router"]["strategy"], "record_only")
        self.assertEqual(
            rule["action"]["decision_policy"]["evidence_requirements"],
            ["prior_explicit_literals_present"],
        )
        self.assertEqual(
            rule["action"]["decision_policy"]["continue_condition"],
            "reuse already available explicit literals before asking the user to restate them",
        )
        self.assertTrue(
            any("inspect prior user turns, tool outputs, and current state" in fragment for fragment in rule["action"]["prompt_fragments"])
        )
        self.assertTrue(
            any("reuse it and emit the next tool call instead of asking again" in fragment for fragment in rule["action"]["prompt_fragments"])
        )

    def test_compile_patch_marks_no_failure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            failure_path.write_text("", encoding="utf-8")

            compile_status = compile_patch(str(failure_path), str(out_path), patch_id="patch_empty")

        self.assertEqual(compile_status["status"], "no_failure_evidence")
        self.assertEqual(compile_status["source_failure_count"], 0)

    def test_compile_patch_marks_uncompilable_failure_evidence_for_unknown_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failure_path = root / "failures.jsonl"
            out_path = root / "rule.yaml"
            failure_path.write_text(
                json.dumps(
                    {
                        "trace_id": "trace_1",
                        "turn_index": 0,
                        "tool_name": "__none__",
                        "error_type": "clarification_request",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            compile_status = compile_patch(str(failure_path), str(out_path), patch_id="patch_uncompilable")

        self.assertEqual(compile_status["status"], "uncompilable_failure_evidence")
        self.assertEqual(compile_status["source_failure_count"], 1)


if __name__ == "__main__":
    unittest.main()
