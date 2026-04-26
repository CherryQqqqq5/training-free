from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_SUMMARY_PATH = DEFAULT_ROOT / "subset_summary.json"


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _criterion(*, passed: bool, actual: Any, expected: str) -> dict[str, Any]:
    return {"passed": passed, "actual": actual, "expected": expected}


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _category_from_summary(summary: dict[str, Any]) -> str:
    manifest = summary.get("manifest") if isinstance(summary.get("manifest"), dict) else {}
    return str(manifest.get("category") or "multi_turn_miss_param")


def _run_source_paths(root: Path, run: str, category: str) -> list[Path]:
    run_root = root / run
    paths = [
        run_root / "artifacts" / "run_manifest.json",
        run_root / "artifacts" / "metrics.json",
        run_root / "artifacts" / "preflight_report.json",
        run_root / "artifacts" / "failure_summary.json",
    ]
    score_glob = f"**/BFCL_v4_{category}_score.json"
    result_glob = f"**/BFCL_v4_{category}_result.json"
    paths.extend(sorted((run_root / "bfcl").glob(score_glob)))
    paths.extend(sorted((run_root / "bfcl").glob(result_glob)))
    return [path for path in paths if path.exists()]


def _freshness_report(summary: dict[str, Any], *, summary_path: Path | None, artifact_root: Path | None) -> dict[str, Any]:
    if summary_path is None or artifact_root is None:
        return {"checked": False, "passed": True, "reason": "no_summary_or_artifact_root"}
    if not artifact_root.exists() or not _is_relative_to(summary_path, artifact_root):
        return {"checked": False, "passed": True, "reason": "summary_outside_artifact_root"}

    report_path = artifact_root / "subset_case_report.jsonl"
    category = _category_from_summary(summary)
    source_paths = _run_source_paths(artifact_root, "baseline", category) + _run_source_paths(artifact_root, "candidate", category)
    if not source_paths:
        return {"checked": False, "passed": True, "reason": "no_run_sources_found"}

    missing_outputs = [str(path) for path in [summary_path, report_path] if not path.exists()]
    freshest_source_mtime = max(path.stat().st_mtime for path in source_paths)
    stale_outputs = [
        str(path)
        for path in [summary_path, report_path]
        if path.exists() and path.stat().st_mtime + 1e-6 < freshest_source_mtime
    ]

    metadata = summary.get("report_build_metadata") if isinstance(summary.get("report_build_metadata"), dict) else {}
    metadata_missing = not metadata
    run_id_mismatches: dict[str, dict[str, Any]] = {}
    for run in ("baseline", "candidate"):
        manifest_path = artifact_root / run / "artifacts" / "run_manifest.json"
        if not manifest_path.exists():
            continue
        current_run_id = _safe_json(manifest_path).get("run_id")
        recorded_run_id = (metadata.get(run) if isinstance(metadata.get(run), dict) else {}).get("run_id")
        if current_run_id and recorded_run_id != current_run_id:
            run_id_mismatches[run] = {"recorded": recorded_run_id, "current": current_run_id}

    passed = not missing_outputs and not stale_outputs and not metadata_missing and not run_id_mismatches
    return {
        "checked": True,
        "passed": passed,
        "missing_outputs": missing_outputs,
        "stale_outputs": stale_outputs,
        "metadata_missing": metadata_missing,
        "run_id_mismatches": run_id_mismatches,
        "freshest_source_mtime": freshest_source_mtime,
        "summary_mtime": summary_path.stat().st_mtime if summary_path.exists() else None,
        "case_report_mtime": report_path.stat().st_mtime if report_path.exists() else None,
        "source_paths_checked": [str(path) for path in source_paths],
    }


def evaluate_m27f_gate(
    summary: dict[str, Any],
    *,
    summary_path: str | None = None,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    baseline_accuracy = _number(summary.get("baseline_accuracy"))
    candidate_accuracy = _number(summary.get("candidate_accuracy"))
    case_fixed_count = _number(summary.get("case_fixed_count"))
    case_regressed_count = _number(summary.get("case_regressed_count"))
    net_case_gain = _number(summary.get("net_case_gain"))
    policy_plan_activated_count = _number(summary.get("policy_plan_activated_count"))
    recommended_tool_match_rate = _number(summary.get("recommended_tool_match_rate_among_activated"))
    raw_normalized_arg_match_rate = _number(summary.get("raw_normalized_arg_match_rate_among_activated"))
    stop_allowed_false_positive_count = _number(summary.get("stop_allowed_false_positive_count"))

    freshness = _freshness_report(
        summary,
        summary_path=Path(summary_path) if summary_path else None,
        artifact_root=Path(artifact_root) if artifact_root is not None else None,
    )
    case_level_gate_allowed = summary.get("case_level_gate_allowed")
    criteria = {
        "stale_case_report_or_summary": _criterion(
            passed=freshness["passed"],
            actual=freshness,
            expected="summary/report are newer than run artifacts and record current baseline/candidate run_id",
        ),
        "case_level_gate_allowed": _criterion(
            passed=case_level_gate_allowed is not False,
            actual=case_level_gate_allowed,
            expected="not false; case-level gate must be explicitly allowed when present",
        ),
        "case_report_trace_mapping": _criterion(
            passed=summary.get("case_report_trace_mapping") == "prompt_user_prefix",
            actual=summary.get("case_report_trace_mapping"),
            expected="prompt_user_prefix",
        ),
        "candidate_accuracy_gt_baseline_accuracy": _criterion(
            passed=(candidate_accuracy is not None and baseline_accuracy is not None and candidate_accuracy > baseline_accuracy),
            actual={"candidate_accuracy": summary.get("candidate_accuracy"), "baseline_accuracy": summary.get("baseline_accuracy")},
            expected="candidate_accuracy > baseline_accuracy",
        ),
        "case_fixed_count_gt_case_regressed_count": _criterion(
            passed=(case_fixed_count is not None and case_regressed_count is not None and case_fixed_count > case_regressed_count),
            actual={"case_fixed_count": summary.get("case_fixed_count"), "case_regressed_count": summary.get("case_regressed_count")},
            expected="case_fixed_count > case_regressed_count",
        ),
        "net_case_gain_min_2": _criterion(
            passed=(net_case_gain is not None and net_case_gain >= 2),
            actual=summary.get("net_case_gain"),
            expected=">= 2",
        ),
        "policy_plan_activated_count_positive": _criterion(
            passed=(policy_plan_activated_count is not None and policy_plan_activated_count > 0),
            actual=summary.get("policy_plan_activated_count"),
            expected="> 0",
        ),
        "recommended_tool_match_rate_among_activated_min_0_6": _criterion(
            passed=(recommended_tool_match_rate is not None and recommended_tool_match_rate >= 0.6),
            actual=summary.get("recommended_tool_match_rate_among_activated"),
            expected=">= 0.6",
        ),
        "raw_normalized_arg_match_rate_among_activated_min_0_6": _criterion(
            passed=(raw_normalized_arg_match_rate is not None and raw_normalized_arg_match_rate >= 0.6),
            actual=summary.get("raw_normalized_arg_match_rate_among_activated"),
            expected=">= 0.6",
        ),
        "stop_allowed_false_positive_count_zero": _criterion(
            passed=(stop_allowed_false_positive_count is not None and stop_allowed_false_positive_count == 0),
            actual=summary.get("stop_allowed_false_positive_count"),
            expected="== 0",
        ),
    }
    failed = [name for name, item in criteria.items() if not item["passed"]]
    gate_passed = not failed
    mapping_stable = criteria["case_report_trace_mapping"]["passed"] and criteria["case_level_gate_allowed"]["passed"] and criteria["stale_case_report_or_summary"]["passed"]
    return {
        "summary_path": summary_path,
        "m2_7f_gate_passed": gate_passed,
        "summary_accepted_ignored": summary.get("accepted"),
        "criteria": criteria,
        "diagnostic": {
            "case_level_evidence": "durable" if mapping_stable else "diagnostic_only",
            "first_failed_criterion": failed[0] if failed else None,
            "failed_criteria": failed,
            "do_not_expand_to_100_case_m28_or_full_bfcl": not gate_passed,
            "recommended_next_focus": _recommended_next_focus(summary, criteria),
        },
    }


def _recommended_next_focus(summary: dict[str, Any], criteria: dict[str, dict[str, Any]]) -> str:
    if not criteria["stale_case_report_or_summary"]["passed"]:
        return "rebuild_case_report_or_summary"
    if not criteria["case_level_gate_allowed"]["passed"]:
        return "trace_completeness_or_prompt_prefix_fallback"
    if not criteria["case_report_trace_mapping"]["passed"]:
        return "prompt_prefix_fallback"
    baseline_accuracy = _number(summary.get("baseline_accuracy"))
    candidate_accuracy = _number(summary.get("candidate_accuracy"))
    if candidate_accuracy is not None and baseline_accuracy is not None and candidate_accuracy <= baseline_accuracy:
        return "over_actuation_or_repair_interaction"
    if _number(summary.get("policy_plan_activated_count")) == 0:
        return "predicates_or_rule_scope"
    if not criteria["recommended_tool_match_rate_among_activated_min_0_6"]["passed"]:
        return "actuation_or_prompt_guidance"
    if not criteria["raw_normalized_arg_match_rate_among_activated_min_0_6"]["passed"]:
        return "arg_binding"
    if not criteria["net_case_gain_min_2"]["passed"]:
        return "trajectory_continuation_or_final_answer"
    return "none"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the explicit M2.7f BFCL phase gate from subset_summary.json.")
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--compact", action="store_true", help="Print compact JSON instead of indented JSON.")
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    report = evaluate_m27f_gate(summary, summary_path=str(args.summary), artifact_root=args.artifact_root)
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if report["m2_7f_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

