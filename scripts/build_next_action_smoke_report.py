from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

from grc.compiler.mine import mine_failures
from grc.compiler.trace_to_patch import compile_patch
from grc.runtime.engine import RuleEngine
from grc.types import Rule


def load_cases(fixtures_dir: Path) -> list[dict[str, Any]]:
    payload = json.loads((fixtures_dir / "cases.json").read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("cases.json must contain a top-level cases list")
    return [case for case in cases if isinstance(case, dict)]


def _failure_like_trace(case: dict[str, Any]) -> dict[str, Any]:
    if not case.get("should_activate"):
        return {
            "trace_id": case["id"],
            "request": case["request"],
            "raw_response": case["mock_response"],
            "validation": {"issues": []},
        }
    issue_kind = "post_tool_prose_summary" if case.get("family") in {"find_to_cat", "path_sensitive_action"} else "empty_tool_call"
    return {
        "trace_id": case["id"],
        "request": case["request"],
        "raw_response": {"choices": [{"message": {"role": "assistant", "content": "I can do that."}}]},
        "validation": {"issues": [{"kind": issue_kind}]},
    }


def _compile_rules_from_case(case: dict[str, Any], root: Path) -> list[dict[str, Any]]:
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
    compile_patch(
        str(failure_path),
        str(out_path),
        patch_id=f"patch_{case['id']}",
        candidate_dir=str(root / "candidate"),
    )
    bundle = yaml.safe_load(out_path.read_text(encoding="utf-8")) if out_path.exists() else {"rules": []}
    return list((bundle or {}).get("rules") or [])


def evaluate_case(case: dict[str, Any], *, compiler_generated: bool = False) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as rules_dir:
        engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
        rules = _compile_rules_from_case(case, Path(rules_dir)) if compiler_generated else list(case.get("rules", []))
        engine.rules = [Rule(**rule) for rule in rules]
        patched, request_patches = engine.apply_request(case["request"])
        _, _, validation = engine.apply_response(
            patched,
            case["mock_response"],
            request_patches=request_patches,
        )

    expected_plan = case.get("expected_plan") or {}
    should_activate = bool(case.get("should_activate"))
    expected_patches = list(case.get("expected_request_patch") or [])
    request_patch_list = list(request_patches)

    blocked_reason_ok = validation.next_tool_plan_blocked_reason == expected_plan.get("blocked_reason")
    if compiler_generated and not should_activate:
        blocked_reason_ok = validation.next_tool_plan_blocked_reason != "activated"
    checks = {
        "attempted": validation.next_tool_plan_attempted is True,
        "activation": validation.next_tool_plan_activated is should_activate,
        "blocked_reason": blocked_reason_ok,
        "expected_request_patches": all(patch in request_patch_list for patch in expected_patches),
    }
    if should_activate:
        checks.update(
            {
                "candidate_recommended_tools": bool(validation.candidate_recommended_tools),
                "matched_recommended_tools": bool(validation.matched_recommended_tools),
                "selected_next_tool": bool(validation.selected_next_tool),
                "required_tool_choice": patched.get("tool_choice") == "required",
            }
        )
        if expected_plan.get("selected_next_tool"):
            checks["selected_next_tool_value"] = validation.selected_next_tool == expected_plan["selected_next_tool"]
    else:
        checks["no_required_tool_choice"] = "tool_choice" not in patched

    action_candidate_count = 1 if validation.selected_action_candidate else 0
    arg_binding_present = bool(
        validation.selected_action_candidate
        and isinstance(validation.selected_action_candidate.get("arg_bindings"), dict)
        and validation.selected_action_candidate.get("arg_bindings")
    )
    expected_selected_tool = expected_plan.get("selected_next_tool")
    selected_tool_match = bool(expected_selected_tool and validation.selected_next_tool == expected_selected_tool)
    passed = all(checks.values())
    return {
        "id": case["id"],
        "family": case["family"],
        "mode": "compiler_generated" if compiler_generated else "fixture_rules",
        "should_activate": should_activate,
        "passed": passed,
        "checks": checks,
        "blocked_reason": validation.next_tool_plan_blocked_reason,
        "next_tool_plan_attempted": validation.next_tool_plan_attempted,
        "next_tool_plan_activated": validation.next_tool_plan_activated,
        "available_tools": validation.available_tools,
        "candidate_recommended_tools": validation.candidate_recommended_tools,
        "matched_recommended_tools": validation.matched_recommended_tools,
        "selected_next_tool": validation.selected_next_tool,
        "selected_action_candidate": validation.selected_action_candidate,
        "tool_choice_mode": validation.tool_choice_mode,
        "next_tool_args_emitted": validation.next_tool_args_emitted,
        "next_tool_args_match_binding": validation.next_tool_args_match_binding,
        "arg_binding_validation": validation.arg_binding_validation,
        "action_candidate_count": action_candidate_count,
        "arg_binding_present": arg_binding_present,
        "selected_tool_match": selected_tool_match,
        "request_patches": request_patch_list,
        "patched_tool_choice": patched.get("tool_choice"),
    }


def evaluate_cases(cases: list[dict[str, Any]], *, compiler_generated: bool = False) -> dict[str, Any]:
    results = [evaluate_case(case, compiler_generated=compiler_generated) for case in cases]
    family_index: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "expected_activate": 0, "actual_activate": 0}
    )
    blocked_reasons = Counter()
    arg_binding_match_count = 0
    selected_tool_match_count = 0
    stop_allowed_false_positive_count = 0
    for result in results:
        family = family_index[result["family"]]
        family["total"] += 1
        family["passed"] += int(result["passed"])
        family["expected_activate"] += int(result["should_activate"])
        family["actual_activate"] += int(result["next_tool_plan_activated"])
        blocked_reasons[str(result["blocked_reason"] or "unknown")] += 1
        selected_tool_match_count += int(bool(result.get("selected_tool_match")))
        arg_binding_match_count += int(result.get("next_tool_args_match_binding") is True)
        stop_allowed_false_positive_count += int(
            result["family"] == "stop_allowed" and result["next_tool_plan_activated"]
        )

    expected_activate = sum(int(result["should_activate"]) for result in results)
    actual_expected_activate = sum(
        int(result["should_activate"] and result["next_tool_plan_activated"]) for result in results
    )
    return {
        "case_count": len(results),
        "mode": "compiler_generated" if compiler_generated else "fixture_rules",
        "passed_count": sum(int(result["passed"]) for result in results),
        "expected_activate_count": expected_activate,
        "expected_activation_rate": actual_expected_activate / expected_activate if expected_activate else 0.0,
        "action_candidate_count": sum(int(result.get("action_candidate_count") or 0) for result in results),
        "arg_binding_present_count": sum(int(bool(result.get("arg_binding_present"))) for result in results),
        "selected_tool_match_count": selected_tool_match_count,
        "arg_binding_match_count": arg_binding_match_count,
        "stop_allowed_false_positive_count": stop_allowed_false_positive_count,
        "blocked_reason_distribution": dict(sorted(blocked_reasons.items())),
        "family_summary": dict(sorted(family_index.items())),
        "results": results,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Next-Action Smoke Report",
        "",
        f"- Mode: `{summary['mode']}`",
        f"- Cases: `{summary['case_count']}`",
        f"- Passed: `{summary['passed_count']}`",
        f"- Expected activation rate: `{summary['expected_activation_rate']:.4f}`",
        f"- Action candidates: `{summary['action_candidate_count']}`",
        f"- Arg bindings present: `{summary['arg_binding_present_count']}`",
        f"- Selected tool matches: `{summary['selected_tool_match_count']}`",
        f"- Arg binding matches: `{summary['arg_binding_match_count']}`",
        f"- Stop-allowed false positives: `{summary['stop_allowed_false_positive_count']}`",
        "",
        "## Family Summary",
        "",
        "| Family | Total | Passed | Expected Activate | Actual Activate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for family, row in summary["family_summary"].items():
        lines.append(
            f"| {family} | {row['total']} | {row['passed']} | {row['expected_activate']} | {row['actual_activate']} |"
        )
    lines.extend(["", "## Blocked Reasons", "", "| Reason | Count |", "| --- | ---: |"])
    for reason, count in summary["blocked_reason_distribution"].items():
        lines.append(f"| {reason} | {count} |")
    lines.extend(["", "## Cases", "", "| Case | Family | Expected Activate | Actual Activate | Selected Tool | Arg Match | Passed |", "| --- | --- | ---: | ---: | --- | ---: | ---: |"])
    for result in summary["results"]:
        lines.append(
            f"| {result['id']} | {result['family']} | {int(result['should_activate'])} | "
            f"{int(result['next_tool_plan_activated'])} | {result.get('selected_next_tool') or '-'} | "
            f"{int(result.get('next_tool_args_match_binding') is True)} | {int(result['passed'])} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a deterministic next-action smoke report.")
    parser.add_argument("--fixtures-dir", type=Path, default=Path("tests/fixtures/phase2_next_action_smoke"))
    parser.add_argument("--compiler-generated", action="store_true", help="Compile rules from fixture-shaped traces before evaluation.")
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args()

    summary = evaluate_cases(load_cases(args.fixtures_dir), compiler_generated=args.compiler_generated)
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(render_markdown(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
