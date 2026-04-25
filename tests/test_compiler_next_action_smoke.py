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

from grc.compiler.action_candidates import generate_action_candidates
from grc.compiler.mine import mine_failures
from grc.compiler.tool_state import extract_tool_state
from grc.compiler.trace_to_patch import compile_patch
from grc.runtime.engine import RuleEngine
from grc.types import Rule
from scripts.build_next_action_smoke_report import load_cases

if _INJECTED_YAML_STUB:
    sys.modules.pop("yaml", None)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "phase2_next_action_smoke"


def _load_bundle(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml

        return yaml.safe_load(text)
    except ModuleNotFoundError:
        return json.loads(text)


def _failure_like_trace(case: dict) -> dict:
    if not case["should_activate"]:
        return {
            "trace_id": case["id"],
            "request": case["request"],
            "raw_response": case["mock_response"],
            "validation": {"issues": []},
        }
    issue_kind = "post_tool_prose_summary" if case["family"] in {"find_to_cat", "path_sensitive_action"} else "empty_tool_call"
    return {
        "trace_id": case["id"],
        "request": case["request"],
        "raw_response": {"choices": [{"message": {"role": "assistant", "content": "I can do that."}}]},
        "validation": {"issues": [{"kind": issue_kind}]},
    }


def _compile_rules_from_case(case: dict, root: Path) -> tuple[list[dict], dict, dict]:
    trace_dir = root / "trace"
    trace_dir.mkdir()
    (trace_dir / f"{case['id']}.json").write_text(
        json.dumps(_failure_like_trace(case), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    failures = mine_failures(str(trace_dir))
    failure_path = root / "failures.jsonl"
    failure_path.write_text(
        "".join(failure.model_dump_json() + "\n" for failure in failures),
        encoding="utf-8",
    )
    out_path = root / "rule.yaml"
    candidate_dir = root / "candidate"
    compile_status = compile_patch(
        str(failure_path),
        str(out_path),
        patch_id=f"patch_{case['id']}",
        candidate_dir=str(candidate_dir),
    )
    bundle = _load_bundle(out_path) if out_path.exists() else {"rules": []}
    policy_units = _load_bundle(candidate_dir / "policy_unit.yaml") if (candidate_dir / "policy_unit.yaml").exists() else {"policy_units": []}
    return list(bundle.get("rules") or []), policy_units, compile_status


class CompilerNextActionSmokeTests(unittest.TestCase):
    def test_tool_state_extracts_fixture_families_and_stop_allowed(self) -> None:
        cases = load_cases(FIXTURES_DIR)
        by_id = {case["id"]: case for case in cases}

        find_state = extract_tool_state({"request": by_id["find_cat_01"]["request"]})
        self.assertEqual(find_state.last_tool, "find")
        self.assertIn("matches", find_state.prior_output_keys)
        self.assertEqual(find_state.user_intent_family, "read_file_content")
        self.assertFalse(find_state.stop_allowed)

        literal_state = extract_tool_state({"request": by_id["literal_arg_03"]["request"]})
        self.assertEqual(literal_state.user_intent_family, "explicit_literal_action")
        self.assertIn("A-1042", literal_state.explicit_literals)

        stop_state = extract_tool_state({"request": by_id["stop_allowed_01"]["request"]})
        self.assertEqual(stop_state.user_intent_family, "final_answer_allowed")
        self.assertTrue(stop_state.stop_allowed)

    def test_action_candidates_are_grounded_and_have_negative_guards(self) -> None:
        cases = load_cases(FIXTURES_DIR)
        by_id = {case["id"]: case for case in cases}

        find_state = extract_tool_state({"request": by_id["find_cat_01"]["request"]})
        find_candidates = generate_action_candidates(find_state)
        self.assertEqual(find_candidates[0].tool, "cat")
        self.assertIn("file_name", find_candidates[0].arg_bindings)
        self.assertEqual(find_candidates[0].binding_source, "prior_tool_output.matches[0]|basename")

        empty_matches = json.loads(json.dumps(by_id["find_cat_01"]["request"]))
        empty_matches["messages"][1]["content"] = "{\"matches\":[]}"
        self.assertEqual(generate_action_candidates(extract_tool_state({"request": empty_matches})), [])

        non_read = json.loads(json.dumps(by_id["find_cat_01"]["request"]))
        non_read["messages"][0]["content"] = "Count the matches."
        self.assertEqual(generate_action_candidates(extract_tool_state({"request": non_read})), [])

        stop_state = extract_tool_state({"request": by_id["stop_allowed_01"]["request"]})
        self.assertEqual(generate_action_candidates(stop_state), [])

    def test_compiler_generated_rules_activate_existing_smoke_fixtures(self) -> None:
        cases = load_cases(FIXTURES_DIR)
        compiler_generated_policy_count = 0
        recommended_tools_non_empty_count = 0
        argument_binding_present_count = 0
        runtime_arg_binding_match_count = 0
        runtime_activated_count = 0
        stop_allowed_actual_activate = 0
        blocked_reasons: dict[str, int] = {}

        for case in cases:
            with tempfile.TemporaryDirectory() as tmp:
                rules, policy_units, _ = _compile_rules_from_case(case, Path(tmp))
                compiler_generated_policy_count += int(bool(policy_units.get("policy_units")))
                if policy_units.get("policy_units"):
                    unit = policy_units["policy_units"][0]
                    recommended_tools_non_empty_count += int(bool(unit.get("recommended_tools")))
                    action_candidates = unit.get("action_candidates") or []
                    argument_binding_present_count += int(
                        any(candidate.get("arg_bindings") for candidate in action_candidates if isinstance(candidate, dict))
                    )
                for rule in rules:
                    policy = (rule.get("action") or {}).get("decision_policy") or {}
                    if policy.get("action_candidates"):
                        self.assertTrue(policy["action_candidates"][0].get("arg_bindings"))
                engine = RuleEngine(tmp, runtime_policy={"enable_required_next_tool_choice": True})
                engine.rules = [Rule(**rule) for rule in rules]
                patched, request_patches = engine.apply_request(case["request"])
                _, _, validation = engine.apply_response(
                    patched,
                    case["mock_response"],
                    request_patches=request_patches,
                )

            runtime_activated_count += int(validation.next_tool_plan_activated)
            runtime_arg_binding_match_count += int(validation.next_tool_args_match_binding is True)
            if case["family"] == "stop_allowed":
                stop_allowed_actual_activate += int(validation.next_tool_plan_activated)
            reason = validation.next_tool_plan_blocked_reason or "unknown"
            blocked_reasons[reason] = blocked_reasons.get(reason, 0) + 1

        self.assertGreaterEqual(compiler_generated_policy_count, 15)
        self.assertGreaterEqual(recommended_tools_non_empty_count, 15)
        self.assertGreaterEqual(argument_binding_present_count, 10)
        self.assertEqual(runtime_activated_count, 13)
        self.assertGreaterEqual(runtime_arg_binding_match_count, 13)
        self.assertEqual(blocked_reasons.get("action_candidate_guard_rejected", 0), 2)
        self.assertEqual(stop_allowed_actual_activate, 0)
        self.assertLess(blocked_reasons.get("recommended_tools_empty", 0), blocked_reasons.get("activated", 0))


if __name__ == "__main__":
    unittest.main()
