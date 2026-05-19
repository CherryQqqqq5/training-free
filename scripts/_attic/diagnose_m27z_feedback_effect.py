#!/usr/bin/env python3
"""Summarize M2.7y scorer-feedback overlay effects after an M2.7z dev rerun."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
OUT_JSON = "m27z_feedback_effect.json"
OUT_MD = "m27z_feedback_effect.md"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def _read_case_report(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _case_status(case: dict[str, Any] | None) -> dict[str, Any]:
    if not case:
        return {"present": False}
    return {
        "present": True,
        "baseline_success": bool(case.get("baseline_success")),
        "candidate_success": bool(case.get("candidate_success")),
        "case_fixed": bool(case.get("case_fixed")),
        "case_regressed": bool(case.get("case_regressed")),
        "policy_plan_activated": bool(case.get("policy_plan_activated")),
        "selected_next_tool": case.get("selected_next_tool"),
        "recommended_tool_match": bool(case.get("recommended_tool_match")),
        "raw_normalized_arg_match": bool(case.get("raw_normalized_arg_match")),
        "repair_kinds": case.get("repair_kinds") or [],
        "blocked_reason": case.get("blocked_reason"),
    }


def _write_md(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# M2.7z Feedback Effect",
        "",
        f"- Ready: `{report['m27z_feedback_effect_ready']}`",
        f"- Previous regression cases resolved: `{report['previous_regression_cases_resolved_count']}/{report['previous_regression_case_count']}`",
        f"- Previous regression cases still regressed: `{report['previous_regression_cases_still_regressed_count']}`",
        f"- New regression cases: `{len(report['new_regression_cases'])}`",
        f"- Record-only feedback case activations: `{report['record_only_signature_activation_count']}`",
        f"- Diagnostic-only feedback case activations: `{report['diagnostic_only_gap_case_activation_count']}`",
        f"- Previous fixed cases preserved: `{report['fixed_case_preservation_status']['preserved_count']}/{report['fixed_case_preservation_status']['previous_fixed_case_count']}`",
        "",
        "## Previous Regression Cases",
    ]
    for case_id, status in report["previous_regression_cases_status"].items():
        lines.append(
            f"- `{case_id}`: candidate_success=`{status.get('candidate_success')}`, "
            f"regressed=`{status.get('case_regressed')}`, activated=`{status.get('policy_plan_activated')}`, "
            f"selected_tool=`{status.get('selected_next_tool')}`"
        )
    lines.extend(["", "## New Regression Cases"])
    for item in report["new_regression_cases"]:
        lines.append(
            f"- `{item['case_id']}`: activated=`{item.get('policy_plan_activated')}`, "
            f"selected_tool=`{item.get('selected_next_tool')}`, blocked_reason=`{item.get('blocked_reason')}`"
        )
    lines.extend(["", "## Interpretation", report["diagnostic"]["interpretation"]])
    path.write_text("\n".join(lines) + "\n")


def build_report(root: Path) -> dict[str, Any]:
    feedback = _read_json(root / "m27y_scorer_feedback.json", {})
    postmortem = _read_json(root / "m27q_postmortem.json", {})
    summary = _read_json(root / "subset_summary.json", {})
    gap = _read_json(root / "m27x_scorer_proxy_gap.json", {})
    cases = _read_case_report(root / "subset_case_report.jsonl")
    cases_by_id = {str(case.get("case_id")): case for case in cases if case.get("case_id")}

    previous_regression_ids = [str(x) for x in feedback.get("regression_case_ids") or []]
    feedback_cases = feedback.get("feedback_cases") or []
    feedback_by_case = {str(item.get("case_id")): item for item in feedback_cases if isinstance(item, dict) and item.get("case_id")}
    record_only_case_ids = {
        str(item.get("case_id"))
        for item in feedback_cases
        if isinstance(item, dict) and item.get("case_id") and item.get("feedback_action") == "record_only"
    }
    diagnostic_only_case_ids = {
        str(item.get("case_id"))
        for item in feedback_cases
        if isinstance(item, dict) and item.get("case_id") and item.get("feedback_action") == "diagnostic_only"
    }

    previous_regression_status = {
        case_id: {
            **_case_status(cases_by_id.get(case_id)),
            "feedback_action": (feedback_by_case.get(case_id) or {}).get("feedback_action"),
            "previous_gap_type": (feedback_by_case.get(case_id) or {}).get("gap_type"),
        }
        for case_id in previous_regression_ids
    }
    previous_regression_still_regressed = [
        case_id for case_id, status in previous_regression_status.items() if status.get("case_regressed")
    ]
    previous_regression_resolved = [
        case_id
        for case_id, status in previous_regression_status.items()
        if status.get("present") and not status.get("case_regressed")
    ]

    current_regression_ids = {case["case_id"] for case in cases if case.get("case_regressed")}
    new_regressions = [
        {
            "case_id": case_id,
            **_case_status(cases_by_id.get(case_id)),
            "feedback_action": (feedback_by_case.get(case_id) or {}).get("feedback_action"),
        }
        for case_id in sorted(current_regression_ids - set(previous_regression_ids))
    ]

    previous_fixed_ids = [
        str(case.get("case_id"))
        for case in postmortem.get("cases", [])
        if isinstance(case, dict) and case.get("case_fixed") and case.get("case_id")
    ]
    previous_fixed_status = {
        case_id: _case_status(cases_by_id.get(case_id))
        for case_id in previous_fixed_ids
    }
    preserved_fixed = [
        case_id
        for case_id, status in previous_fixed_status.items()
        if status.get("candidate_success") and not status.get("case_regressed")
    ]
    regressed_previous_fixed = [
        case_id for case_id, status in previous_fixed_status.items() if status.get("case_regressed")
    ]

    record_only_activated = [
        {
            "case_id": case_id,
            **_case_status(cases_by_id.get(case_id)),
        }
        for case_id in sorted(record_only_case_ids)
        if cases_by_id.get(case_id, {}).get("policy_plan_activated")
    ]
    diagnostic_only_activated = [
        {
            "case_id": case_id,
            **_case_status(cases_by_id.get(case_id)),
        }
        for case_id in sorted(diagnostic_only_case_ids)
        if cases_by_id.get(case_id, {}).get("policy_plan_activated")
    ]

    status_distribution = Counter()
    for status in previous_regression_status.values():
        if not status.get("present"):
            status_distribution["missing"] += 1
        elif status.get("case_regressed"):
            status_distribution["still_regressed"] += 1
        elif status.get("candidate_success"):
            status_distribution["candidate_success"] += 1
        else:
            status_distribution["no_longer_regressed_but_not_success"] += 1

    stop_loss = {
        "case_regressed_count_le_1": (summary.get("case_regressed_count") or 0) <= 1,
        "net_case_gain_ge_0": (summary.get("net_case_gain") or 0) >= 0,
        "candidate_accuracy_ge_baseline_accuracy": (summary.get("candidate_accuracy") or 0) >= (summary.get("baseline_accuracy") or 0),
        "raw_normalized_arg_match_rate_ge_previous_0_455": (summary.get("raw_normalized_arg_match_rate_among_activated") or 0) >= 0.455,
    }

    report = {
        "report_scope": "m2_7z_feedback_effect",
        "artifact_root": str(root),
        "m27z_feedback_effect_ready": bool(cases) and bool(feedback),
        "source_feedback_path": str(root / "m27y_scorer_feedback.json"),
        "source_gap_path": str(root / "m27x_scorer_proxy_gap.json") if (root / "m27x_scorer_proxy_gap.json").exists() else None,
        "current_summary": {
            "baseline_accuracy": summary.get("baseline_accuracy"),
            "candidate_accuracy": summary.get("candidate_accuracy"),
            "case_fixed_count": summary.get("case_fixed_count"),
            "case_regressed_count": summary.get("case_regressed_count"),
            "net_case_gain": summary.get("net_case_gain"),
            "policy_plan_activated_count": summary.get("policy_plan_activated_count"),
            "recommended_tool_match_rate_among_activated": summary.get("recommended_tool_match_rate_among_activated"),
            "raw_normalized_arg_match_rate_among_activated": summary.get("raw_normalized_arg_match_rate_among_activated"),
            "case_report_trace_mapping": summary.get("case_report_trace_mapping"),
            "case_level_gate_allowed": summary.get("case_level_gate_allowed"),
        },
        "stop_loss": stop_loss,
        "stop_loss_passed": all(stop_loss.values()),
        "previous_regression_case_count": len(previous_regression_ids),
        "previous_regression_cases_status": previous_regression_status,
        "previous_regression_status_distribution": dict(status_distribution),
        "previous_regression_cases_resolved": previous_regression_resolved,
        "previous_regression_cases_resolved_count": len(previous_regression_resolved),
        "previous_regression_cases_still_regressed": previous_regression_still_regressed,
        "previous_regression_cases_still_regressed_count": len(previous_regression_still_regressed),
        "record_only_feedback_case_ids": sorted(record_only_case_ids),
        "record_only_signature_activation_count": len(record_only_activated),
        "record_only_signature_activated_cases": record_only_activated,
        "diagnostic_only_feedback_case_ids": sorted(diagnostic_only_case_ids),
        "diagnostic_only_gap_case_activation_count": len(diagnostic_only_activated),
        "diagnostic_only_gap_activated_cases": diagnostic_only_activated,
        "new_regression_cases": new_regressions,
        "fixed_case_preservation_status": {
            "source": "m27q_postmortem.previous_fixed_cases",
            "previous_fixed_case_ids": previous_fixed_ids,
            "previous_fixed_case_count": len(previous_fixed_ids),
            "preserved_case_ids": preserved_fixed,
            "preserved_count": len(preserved_fixed),
            "regressed_previous_fixed_case_ids": regressed_previous_fixed,
            "cases": previous_fixed_status,
        },
        "current_gap_summary": {
            "m27x_scorer_proxy_gap_explained": gap.get("m27x_scorer_proxy_gap_explained"),
            "m27x_scorer_proxy_gap_passed": gap.get("m27x_scorer_proxy_gap_passed"),
            "fixed_by_code_change": gap.get("fixed_by_code_change"),
            "gap_type_distribution": gap.get("gap_type_distribution"),
            "regressed_case_count": gap.get("regressed_case_count"),
        },
        "diagnostic": {
            "do_not_run_holdout_unless_formal_dev_gate_passes": True,
            "interpretation": (
                "M2.7z dev rerun compact feedback-effect diagnostic. "
                "Use stop_loss and formal M2.7f gate before considering any holdout request."
            ),
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", default=str(DEFAULT_ROOT))
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    root = Path(args.artifact_root)
    report = build_report(root)
    (root / OUT_JSON).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    _write_md(root / OUT_MD, report)

    if args.compact:
        print(json.dumps({
            "m27z_feedback_effect_ready": report["m27z_feedback_effect_ready"],
            "stop_loss_passed": report["stop_loss_passed"],
            "previous_regression_cases_resolved_count": report["previous_regression_cases_resolved_count"],
            "previous_regression_cases_still_regressed_count": report["previous_regression_cases_still_regressed_count"],
            "record_only_signature_activation_count": report["record_only_signature_activation_count"],
            "diagnostic_only_gap_case_activation_count": report["diagnostic_only_gap_case_activation_count"],
            "new_regression_case_count": len(report["new_regression_cases"]),
        }, indent=2, sort_keys=True))
    return 0 if report["m27z_feedback_effect_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
