from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from grc.runtime.engine import RuleEngine
from grc.types import Rule


def load_cases(fixtures_dir: Path) -> list[dict[str, Any]]:
    payload = json.loads((fixtures_dir / "cases.json").read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("cases.json must contain a top-level cases list")
    return [case for case in cases if isinstance(case, dict)]


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as rules_dir:
        engine = RuleEngine(rules_dir, runtime_policy={"enable_required_next_tool_choice": True})
        engine.rules = [Rule(**rule) for rule in case.get("rules", [])]
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

    checks = {
        "attempted": validation.next_tool_plan_attempted is True,
        "activation": validation.next_tool_plan_activated is should_activate,
        "blocked_reason": validation.next_tool_plan_blocked_reason == expected_plan.get("blocked_reason"),
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

    passed = all(checks.values())
    return {
        "id": case["id"],
        "family": case["family"],
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
        "tool_choice_mode": validation.tool_choice_mode,
        "request_patches": request_patch_list,
        "patched_tool_choice": patched.get("tool_choice"),
    }


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = [evaluate_case(case) for case in cases]
    family_index: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "expected_activate": 0, "actual_activate": 0}
    )
    blocked_reasons = Counter()
    for result in results:
        family = family_index[result["family"]]
        family["total"] += 1
        family["passed"] += int(result["passed"])
        family["expected_activate"] += int(result["should_activate"])
        family["actual_activate"] += int(result["next_tool_plan_activated"])
        blocked_reasons[str(result["blocked_reason"] or "unknown")] += 1

    expected_activate = sum(int(result["should_activate"]) for result in results)
    actual_expected_activate = sum(
        int(result["should_activate"] and result["next_tool_plan_activated"]) for result in results
    )
    return {
        "case_count": len(results),
        "passed_count": sum(int(result["passed"]) for result in results),
        "expected_activate_count": expected_activate,
        "expected_activation_rate": actual_expected_activate / expected_activate if expected_activate else 0.0,
        "blocked_reason_distribution": dict(sorted(blocked_reasons.items())),
        "family_summary": dict(sorted(family_index.items())),
        "results": results,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Next-Action Smoke Report",
        "",
        f"- Cases: `{summary['case_count']}`",
        f"- Passed: `{summary['passed_count']}`",
        f"- Expected activation rate: `{summary['expected_activation_rate']:.4f}`",
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
    lines.extend(["", "## Cases", "", "| Case | Family | Expected Activate | Actual Activate | Selected Tool | Passed |", "| --- | --- | ---: | ---: | --- | ---: |"])
    for result in summary["results"]:
        lines.append(
            f"| {result['id']} | {result['family']} | {int(result['should_activate'])} | "
            f"{int(result['next_tool_plan_activated'])} | {result.get('selected_next_tool') or '-'} | {int(result['passed'])} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a deterministic next-action smoke report.")
    parser.add_argument("--fixtures-dir", type=Path, default=Path("tests/fixtures/phase2_next_action_smoke"))
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args()

    summary = evaluate_cases(load_cases(args.fixtures_dir))
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
