#!/usr/bin/env python3
"""Validate same-protocol BFCL baseline/candidate comparison artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.check_bfcl_run_artifact_schema import evaluate as evaluate_run
from scripts.check_provider_green_preflight import evaluate as evaluate_provider

DEFAULT_ACCEPTANCE_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
ALIGNMENT_FIELDS = (
    "artifact_schema_version",
    "protocol_id",
    "bfcl_model_alias",
    "upstream_profile",
    "upstream_model_route",
    "test_category",
    "runtime_config_path",
    "selected_case_count",
    "selected_case_ids_hash",
    "provider_preflight_status_path",
)


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _as_bool(value: Any) -> bool:
    return bool(value is True or str(value).lower() == "true")


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _acc_to_pp(value: float | None) -> float | None:
    if value is None:
        return None
    return value * 100.0 if abs(value) <= 1.0 else value


def _manifest_alignment(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    mismatches: list[dict[str, Any]] = []
    missing: list[str] = []
    for field in ALIGNMENT_FIELDS:
        base_value = baseline.get(field)
        cand_value = candidate.get(field)
        if base_value in (None, "") or cand_value in (None, ""):
            missing.append(field)
        elif base_value != cand_value:
            mismatches.append({"field": field, "baseline": base_value, "candidate": cand_value})
    return {
        "required_alignment_fields": list(ALIGNMENT_FIELDS),
        "missing_alignment_fields": missing,
        "mismatches": mismatches,
        "passed": not missing and not mismatches,
    }


def evaluate(acceptance_root: Path = DEFAULT_ACCEPTANCE_ROOT, *, provider_status: Path | None = None) -> dict[str, Any]:
    paired_path = acceptance_root / "paired_comparison.json"
    decision_path = acceptance_root / "acceptance_decision.json"
    regression_path = acceptance_root / "regression_report.json"
    cost_latency_path = acceptance_root / "cost_latency_report.json"
    paired = _load_json(paired_path, {}) or {}
    decision = _load_json(decision_path, {}) or {}
    regression = _load_json(regression_path, {}) or {}
    cost_latency = _load_json(cost_latency_path, {}) or {}

    baseline_root_value = paired.get("baseline_run_root")
    candidate_root_value = paired.get("candidate_run_root")
    baseline_manifest_value = paired.get("baseline_run_manifest_path")
    candidate_manifest_value = paired.get("candidate_run_manifest_path")

    baseline_root = Path(str(baseline_root_value)) if baseline_root_value else None
    candidate_root = Path(str(candidate_root_value)) if candidate_root_value else None
    if baseline_root is None and baseline_manifest_value:
        manifest_path = Path(str(baseline_manifest_value))
        baseline_root = manifest_path.parent if manifest_path.name == "run_manifest.json" else manifest_path
    if candidate_root is None and candidate_manifest_value:
        manifest_path = Path(str(candidate_manifest_value))
        candidate_root = manifest_path.parent if manifest_path.name == "run_manifest.json" else manifest_path

    baseline_report = evaluate_run(baseline_root) if baseline_root else None
    candidate_report = evaluate_run(candidate_root) if candidate_root else None
    baseline_manifest = (baseline_report or {}).get("manifest") or {}
    candidate_manifest = (candidate_report or {}).get("manifest") or {}
    alignment = _manifest_alignment(baseline_manifest, candidate_manifest)

    provider_report = evaluate_provider(provider_status) if provider_status else None
    baseline_acc = _number((baseline_report or {}).get("metrics", {}).get("accuracy"))
    candidate_acc = _number((candidate_report or {}).get("metrics", {}).get("accuracy"))
    baseline_acc_pp = _acc_to_pp(baseline_acc)
    candidate_acc_pp = _acc_to_pp(candidate_acc)
    target_pp = _number(paired.get("target_absolute_delta_pp") or decision.get("target_absolute_delta_pp")) or 3.0
    explicit_delta = _number(paired.get("absolute_delta_pp"))
    delta_pp = explicit_delta
    if delta_pp is None and baseline_acc_pp is not None and candidate_acc_pp is not None:
        delta_pp = candidate_acc_pp - baseline_acc_pp
    cost_delta_pct = _number(cost_latency.get("cost_delta_pct"))
    latency_delta_pct = _number(cost_latency.get("latency_delta_pct") or cost_latency.get("latency_ms_delta_pct"))
    cost_latency_within_bounds = _as_bool(cost_latency.get("cost_latency_within_bounds"))
    if "cost_latency_within_bounds" not in cost_latency:
        cost_limit = _number(cost_latency.get("max_cost_delta_pct")) or 10.0
        latency_limit = _number(cost_latency.get("max_latency_delta_pct")) or 10.0
        cost_latency_within_bounds = (
            cost_delta_pct is not None
            and latency_delta_pct is not None
            and cost_delta_pct <= cost_limit
            and latency_delta_pct <= latency_limit
        )
    case_regressed_count = _number(regression.get("case_regressed_count"))
    case_fixed_count = _number(regression.get("case_fixed_count"))

    blockers: list[str] = []
    if not paired_path.exists():
        blockers.append("paired_comparison_missing")
    if not decision_path.exists():
        blockers.append("acceptance_decision_missing")
    if not regression_path.exists():
        blockers.append("regression_report_missing")
    if not cost_latency_path.exists():
        blockers.append("cost_latency_report_missing")
    if baseline_report is None or not baseline_report.get("run_artifact_schema_passed"):
        blockers.append("baseline_run_artifact_schema_not_passed")
    if candidate_report is None or not candidate_report.get("run_artifact_schema_passed"):
        blockers.append("candidate_run_artifact_schema_not_passed")
    if baseline_manifest.get("kind") != "baseline":
        blockers.append("baseline_run_kind_invalid")
    if candidate_manifest.get("kind") != "candidate":
        blockers.append("candidate_run_kind_invalid")
    if not alignment["passed"]:
        blockers.append("baseline_candidate_manifest_alignment_not_passed")
    if provider_report and not provider_report.get("provider_green_preflight_passed"):
        blockers.append("provider_green_preflight_not_passed")
    if provider_status is None:
        blockers.append("provider_green_preflight_not_checked")
    if delta_pp is None:
        blockers.append("absolute_delta_missing")
    elif delta_pp < target_pp:
        blockers.append("required_3pp_target_not_passed")
    if baseline_acc_pp is None or candidate_acc_pp is None:
        blockers.append("paired_accuracy_missing")
    elif candidate_acc_pp <= baseline_acc_pp:
        blockers.append("candidate_accuracy_not_greater_than_baseline")
    if not _as_bool(decision.get("required_3pp_target_passed")):
        blockers.append("acceptance_decision_3pp_not_passed")
    if not _as_bool(decision.get("performance_claim_allowed")):
        blockers.append("performance_claim_not_allowed")
    if _as_bool(regression.get("unacceptable_regression_present")):
        blockers.append("unacceptable_regression_present")
    if case_regressed_count is not None and case_regressed_count > 0:
        blockers.append("case_regressions_present")
    if case_fixed_count is not None and case_regressed_count is not None and case_fixed_count <= case_regressed_count:
        blockers.append("fixed_cases_not_greater_than_regressed_cases")
    if not cost_latency_within_bounds:
        blockers.append("cost_latency_not_within_bounds")

    blockers = list(dict.fromkeys(blockers))
    return {
        "report_scope": "bfcl_paired_comparison",
        "acceptance_root": str(acceptance_root),
        "paired_comparison_ready": not blockers,
        "paired_comparison_present": paired_path.exists(),
        "acceptance_decision_present": decision_path.exists(),
        "regression_report_present": regression_path.exists(),
        "cost_latency_report_present": cost_latency_path.exists(),
        "baseline_run": baseline_report,
        "candidate_run": candidate_report,
        "provider": provider_report,
        "manifest_alignment": alignment,
        "baseline_accuracy": baseline_acc,
        "candidate_accuracy": candidate_acc,
        "baseline_accuracy_pp": baseline_acc_pp,
        "candidate_accuracy_pp": candidate_acc_pp,
        "absolute_delta_pp": delta_pp,
        "target_absolute_delta_pp": target_pp,
        "required_3pp_target_passed": _as_bool(decision.get("required_3pp_target_passed")),
        "performance_claim_allowed": _as_bool(decision.get("performance_claim_allowed")),
        "unacceptable_regression_present": _as_bool(regression.get("unacceptable_regression_present")),
        "case_fixed_count": case_fixed_count,
        "case_regressed_count": case_regressed_count,
        "cost_latency": {
            "cost_delta_pct": cost_delta_pct,
            "latency_delta_pct": latency_delta_pct,
            "cost_latency_within_bounds": cost_latency_within_bounds,
        },
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acceptance-root", type=Path, default=DEFAULT_ACCEPTANCE_ROOT)
    parser.add_argument("--provider-status", type=Path)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.acceptance_root, provider_status=args.provider_status)
    print(json.dumps(report if not args.compact else {
        "paired_comparison_ready": report["paired_comparison_ready"],
        "blockers": report["blockers"],
        "absolute_delta_pp": report["absolute_delta_pp"],
        "target_absolute_delta_pp": report["target_absolute_delta_pp"],
    }, indent=2, sort_keys=True))
    if args.strict and not report["paired_comparison_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
