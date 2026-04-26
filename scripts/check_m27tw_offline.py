#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
HOLD = Path("outputs/artifacts/bfcl_ctspc_holdout30_v1")
SRC = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
OUT = ROOT / "m27tw_offline_summary.json"
MD = ROOT / "m27tw_offline_summary.md"


def _j(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _holdout_ready(manifest: dict[str, Any]) -> bool:
    return bool(manifest.get("m27tw_holdout_manifest_ready")) and int(manifest.get("selected_case_count") or 0) >= 20 and int(manifest.get("candidate_generatable_count") or 0) >= 15 and not (manifest.get("overlap_with_dev_case_ids") or [])



def _guidance_only_ready(root: Path) -> dict[str, Any]:
    m = _j(root / "m27m_guidance_only_readiness.json", {}) or {}
    i = _j(root / "m27i_guard_preflight.json", {}) or {}
    activated = m.get("plan_activated_count_after_guard", i.get("plan_activated_count_after_guard"))
    dominant = m.get("dominant_selected_next_tool_rate_after_guard", i.get("dominant_selected_next_tool_rate_after_guard"))
    fixed_keeps = i.get("guard_keeps_fixed_cases")
    exact_coverage = m.get("exact_tool_choice_coverage")
    activated_ok = isinstance(activated, int) and 10 <= activated <= 25
    dominant_ok = isinstance(dominant, (int, float)) and dominant <= 0.8
    fixed_ok = isinstance(fixed_keeps, int) and fixed_keeps >= 1
    exact_ok = isinstance(exact_coverage, (int, float)) and exact_coverage == 0.0
    passed = bool(
        m.get("m2_7m_preflight_passed")
        and m.get("m2_7m_guidance_only_readiness_passed")
        and i.get("m2_7i_guard_preflight_passed")
        and activated_ok
        and dominant_ok
        and fixed_ok
        and exact_ok
    )
    first_failed = None
    for key, ok in [
        ("m2_7m_preflight_passed", bool(m.get("m2_7m_preflight_passed"))),
        ("m2_7m_guidance_only_readiness_passed", bool(m.get("m2_7m_guidance_only_readiness_passed"))),
        ("m2_7i_guard_preflight_passed", bool(i.get("m2_7i_guard_preflight_passed"))),
        ("plan_activated_count_after_guard_range", activated_ok),
        ("dominant_selected_next_tool_rate_after_guard", dominant_ok),
        ("guard_keeps_fixed_cases", fixed_ok),
        ("exact_tool_choice_coverage", exact_ok),
    ]:
        if not ok:
            first_failed = key
            break
    return {
        "m27m_guidance_only_readiness_passed": passed,
        "m2_7m_preflight_passed": bool(m.get("m2_7m_preflight_passed")),
        "m2_7m_guidance_only_readiness_passed": bool(m.get("m2_7m_guidance_only_readiness_passed")),
        "m2_7i_guard_preflight_passed": bool(i.get("m2_7i_guard_preflight_passed")),
        "plan_activated_count_after_guard": activated,
        "dominant_selected_next_tool_rate_after_guard": dominant,
        "guard_keeps_fixed_cases": fixed_keeps,
        "exact_tool_choice_coverage": exact_coverage,
        "first_failed_criterion": first_failed,
        "m27m_guidance_only_readiness_path": str(root / "m27m_guidance_only_readiness.json") if (root / "m27m_guidance_only_readiness.json").exists() else None,
        "m27i_guard_preflight_path": str(root / "m27i_guard_preflight.json") if (root / "m27i_guard_preflight.json").exists() else None,
    }

def _proxy_calibration(root: Path, summary: dict[str, Any], x: dict[str, Any]) -> dict[str, Any]:
    tool = summary.get("recommended_tool_match_rate_among_activated")
    arg = summary.get("raw_normalized_arg_match_rate_among_activated")
    tool_ok = isinstance(tool, (int, float)) and tool >= 0.6
    arg_ok = isinstance(arg, (int, float)) and arg >= 0.6
    scorer_floor_ok = tool_ok and arg_ok
    gap_fixed = bool(x.get("m27x_scorer_proxy_gap_explained") and x.get("fixed_by_code_change"))
    needs_gap_fix = not scorer_floor_ok
    return {
        "proxy_calibration_passed": (not needs_gap_fix) or gap_fixed,
        "needs_gap_fix": needs_gap_fix,
        "last_scorer_tool_match_rate": tool,
        "last_scorer_raw_arg_match_rate": arg,
        "m27x_scorer_proxy_gap_explained": bool(x.get("m27x_scorer_proxy_gap_explained")),
        "fixed_by_code_change": bool(x.get("fixed_by_code_change")),
        "gap_report_path": str(root / "m27x_scorer_proxy_gap.json") if (root / "m27x_scorer_proxy_gap.json").exists() else None,
    }


def _pattern_proxy_calibration(root: Path, summary: dict[str, Any], aa: dict[str, Any]) -> dict[str, Any]:
    tool = summary.get("recommended_tool_match_rate_among_activated")
    arg = summary.get("raw_normalized_arg_match_rate_among_activated")
    tool_ok = isinstance(tool, (int, float)) and tool >= 0.6
    arg_ok = isinstance(arg, (int, float)) and arg >= 0.6
    needs_pattern_fix = not (tool_ok and arg_ok)
    old_unresolved = int(aa.get("old_regression_unresolved_count") or 0)
    new_patterns = int(aa.get("new_regression_pattern_count") or 0)
    coverage = aa.get("regression_pattern_coverage")
    coverage_ok = isinstance(coverage, (int, float)) and coverage >= 1.0
    effective_coverage = aa.get("pattern_effective_coverage")
    effective_coverage_ok = isinstance(effective_coverage, (int, float)) and effective_coverage >= 1.0
    unsafe = int(aa.get("diagnostic_unsafe_gap_count") or 0)
    covers_patterns = bool(aa.get("scorer_feedback_covers_regression_patterns"))
    effective_patterns = bool(aa.get("scorer_feedback_effective_for_regression_patterns"))
    aa_passed = bool(aa.get("m27aa_regression_patterns_passed"))
    pattern_passed = (not needs_pattern_fix) or (aa_passed and old_unresolved == 0 and new_patterns == 0 and coverage_ok and effective_coverage_ok and unsafe == 0 and covers_patterns and effective_patterns)
    return {
        "pattern_proxy_calibration_passed": pattern_passed,
        "needs_pattern_fix": needs_pattern_fix,
        "m27aa_regression_patterns_passed": aa_passed,
        "old_regression_unresolved_count": old_unresolved,
        "new_regression_pattern_count": new_patterns,
        "regression_pattern_coverage": coverage,
        "pattern_effective_coverage": effective_coverage,
        "diagnostic_unsafe_gap_count": unsafe,
        "scorer_feedback_covers_regression_patterns": covers_patterns,
        "scorer_feedback_effective_for_regression_patterns": effective_patterns,
        "pattern_report_path": str(root / "m27aa_regression_patterns.json") if (root / "m27aa_regression_patterns.json").exists() else None,
    }


def evaluate(root: Path = ROOT, holdout: Path = HOLD, source: Path = SRC) -> dict[str, Any]:
    source_manifest = _j(source / "source_collection_manifest.json", {}) or {}
    holdout_manifest = _j(holdout / "holdout_manifest.json", {}) or {}
    u = _j(root / "m27u_tool_ranking.json", {}) or {}
    v = _j(root / "m27v_arg_realization.json", {}) or {}
    w = _j(root / "m27w_rule_retention.json", {}) or {}
    summary = _j(root / "subset_summary.json", {}) or {}
    x = _j(root / "m27x_scorer_proxy_gap.json", {}) or {}
    aa = _j(root / "m27aa_regression_patterns.json", {}) or {}
    calibration = _proxy_calibration(root, summary, x)
    pattern_calibration = _pattern_proxy_calibration(root, summary, aa)
    guidance_calibration = _guidance_only_ready(root)
    checks = {
        "m27t_source_pool_ready": bool(source_manifest.get("m27t_source_pool_ready")),
        "m27tw_holdout_manifest_ready": _holdout_ready(holdout_manifest),
        "m27u_tool_ranking_passed": bool(u.get("m27u_tool_ranking_passed")),
        "m27v_arg_realization_passed": bool(v.get("m27v_arg_realization_passed")),
        "m27w_rule_retention_passed": bool(w.get("m27w_rule_retention_passed")),
        "m27m_guidance_only_readiness_passed": bool(guidance_calibration.get("m27m_guidance_only_readiness_passed")),
        "proxy_calibration_passed": bool(calibration.get("proxy_calibration_passed")),
        "pattern_proxy_calibration_passed": bool(pattern_calibration.get("pattern_proxy_calibration_passed")),
    }
    return {
        "report_scope": "m2_7tw_offline_summary",
        **checks,
        "m2_7tw_offline_passed": all(checks.values()),
        "source_pool": {key: source_manifest.get(key) for key in ["m27t_source_pool_ready", "planned_source_collection_commands", "candidate_commands"]},
        "holdout": {key: holdout_manifest.get(key) for key in ["selected_case_count", "candidate_generatable_count", "overlap_with_dev_case_ids", "planned_commands"]},
        "tool_ranking": {key: u.get(key) for key in ["tool_mismatch_before_arg_realization_count", "offline_recommended_tool_match_proxy", "dominant_selected_next_tool_rate", "last_scorer_tool_match_rate"]},
        "arg_realization": {key: v.get(key) for key in ["raw_arg_match_rate_proxy", "emitted_arg_wrong_or_guidance_not_followed_count", "canonical_arg_validation_coverage", "last_scorer_raw_arg_match_rate"]},
        "rule_retention": {key: w.get(key) for key in ["decision_distribution", "holdout_manifest_ready", "holdout_scorer_evidence_available", "offline_u_v_readiness_passed", "scorer_override_applied"]},
        "guidance_only_readiness": guidance_calibration,
        "proxy_calibration": calibration,
        "pattern_proxy_calibration": pattern_calibration,
        "diagnostic": {
            "offline_readiness_only": True,
            "last_scorer_metrics_retained_for_postmortem_only": True,
            "offline_proxy_requires_scorer_gap_calibration": True,
            "no_bfcl_rerun": True,
            "no_100_case": True,
            "no_m2_8": True,
            "no_full_bfcl": True,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# M2.7tw Offline Summary", "", f"- Passed: `{report['m2_7tw_offline_passed']}`", "", "| Check | Passed |", "| --- | ---: |"]
    for key in ["m27t_source_pool_ready", "m27tw_holdout_manifest_ready", "m27u_tool_ranking_passed", "m27v_arg_realization_passed", "m27w_rule_retention_passed", "m27m_guidance_only_readiness_passed", "proxy_calibration_passed", "pattern_proxy_calibration_passed"]:
        lines.append(f"| `{key}` | `{report[key]}` |")
    lines.extend(["", "This summary is an offline readiness gate only. Proxy readiness is blocked when scorer gaps are unexplained, unfixed, or not covered by regression patterns.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--holdout-root", type=Path, default=HOLD)
    parser.add_argument("--source-pool-root", type=Path, default=SRC)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.root, args.holdout_root, args.source_pool_root)
    _write_json(args.output, report)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in ["m2_7tw_offline_passed", "m27t_source_pool_ready", "m27tw_holdout_manifest_ready", "m27u_tool_ranking_passed", "m27v_arg_realization_passed", "m27w_rule_retention_passed", "m27m_guidance_only_readiness_passed", "proxy_calibration_passed", "pattern_proxy_calibration_passed"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

