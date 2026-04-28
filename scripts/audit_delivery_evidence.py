#!/usr/bin/env python3
"""Build a compact first-stage delivery evidence audit.

This script is offline-only. It reads committed compact artifacts and optional
server-local trace files, then summarizes whether the repository is ready for a
Huawei first-stage delivery claim. It does not call BFCL, models, or scorers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import scripts.check_artifact_boundary as artifact_boundary
from scripts.check_m28pre_offline import evaluate as evaluate_m28pre

DEFAULT_SUBSET = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_LOW_RISK = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1")
DEFAULT_PHASE2_VALIDATION = Path("outputs/phase2_validation/required_next_tool_choice_v1")
DEFAULT_OUT = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1/delivery_evidence_audit.json")
DEFAULT_MD = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1/delivery_evidence_audit.md")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _iter_json_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return root.rglob("*.json")


def _walk_values(obj: Any) -> Iterable[Any]:
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _walk_values(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_values(value)


def _truthy_count(value: Any) -> int:
    if value is None or value is False or value == "":
        return 0
    if isinstance(value, list):
        return len([item for item in value if item])
    if isinstance(value, (int, float)):
        return int(value)
    return 1


def policy_conversion_counters(trace_root: Path = DEFAULT_PHASE2_VALIDATION, *, max_files: int = 5000) -> dict[str, Any]:
    counters = {
        "trace_root": str(trace_root),
        "trace_files_scanned": 0,
        "rule_hits": 0,
        "policy_hits": 0,
        "recommended_tools": 0,
        "selected_next_tool": 0,
        "next_tool_emitted": 0,
        "required_tool_choice_records": 0,
    }
    for path in _iter_json_files(trace_root):
        if counters["trace_files_scanned"] >= max_files:
            counters["truncated_at_max_files"] = max_files
            break
        counters["trace_files_scanned"] += 1
        data = _load_json(path)
        if data is None:
            continue
        for node in _walk_values(data):
            if not isinstance(node, dict):
                continue
            counters["rule_hits"] += _truthy_count(node.get("rule_hits"))
            counters["policy_hits"] += _truthy_count(node.get("policy_hits"))
            counters["recommended_tools"] += _truthy_count(node.get("recommended_tools"))
            counters["selected_next_tool"] += _truthy_count(node.get("selected_next_tool"))
            counters["next_tool_emitted"] += _truthy_count(node.get("next_tool_emitted"))
            if node.get("tool_choice_mode") == "required":
                counters["required_tool_choice_records"] += 1
    counters["policy_conversion_observed"] = bool(
        counters["policy_hits"]
        or counters["recommended_tools"]
        or counters["selected_next_tool"]
        or counters["next_tool_emitted"]
        or counters["required_tool_choice_records"]
    )
    return counters


def artifact_boundary_status(max_print: int = 20) -> dict[str, Any]:
    bad = artifact_boundary.forbidden_outputs(artifact_boundary.collect_output_paths())
    return {
        "artifact_boundary_passed": not bad,
        "forbidden_artifact_count": len(bad),
        "forbidden_artifact_examples": bad[:max_print],
    }


def source_result_layout_status(low_risk_root: Path = DEFAULT_LOW_RISK) -> dict[str, Any]:
    availability = _load_json(low_risk_root / "m28pre_source_result_availability_audit.json", {}) or {}
    alias = _load_json(low_risk_root / "wrong_arg_key_alias_coverage_audit.json", {}) or {}
    deterministic = _load_json(low_risk_root / "deterministic_schema_local_coverage_audit.json", {}) or {}
    return {
        "source_result_availability_ready": availability.get("source_result_availability_ready"),
        "availability_hard_issue_counts": availability.get("hard_issue_counts") or {},
        "availability_issue_counts": availability.get("issue_counts") or {},
        "wrong_arg_key_alias_family_coverage_zero": alias.get("wrong_arg_key_alias_family_coverage_zero"),
        "wrong_arg_key_alias_rejection_reason_counts": alias.get("rejection_reason_counts") or {},
        "deterministic_schema_local_family_coverage_zero": deterministic.get("deterministic_schema_local_family_coverage_zero"),
        "deterministic_schema_local_rejection_reason_counts": deterministic.get("rejection_reason_counts") or {},
        "route_recommendation": deterministic.get("route_recommendation") or alias.get("route_recommendation"),
    }


def evaluate(
    subset_root: Path = DEFAULT_SUBSET,
    low_risk_root: Path = DEFAULT_LOW_RISK,
    phase2_validation_root: Path = DEFAULT_PHASE2_VALIDATION,
) -> dict[str, Any]:
    m28 = evaluate_m28pre(subset_root, low_risk_root)
    ctspc_status = _load_json(subset_root / "m27ae_ctspc_v0_status.json", {}) or {}
    ctspc_summary = _load_json(subset_root / "subset_summary.json", {}) or {}
    boundary = artifact_boundary_status()
    policy = policy_conversion_counters(phase2_validation_root)
    source_layout = source_result_layout_status(low_risk_root)
    p0_blockers: list[str] = []
    if not boundary["artifact_boundary_passed"]:
        p0_blockers.append("artifact_boundary_not_clean")
    if not m28.get("m2_8pre_offline_passed"):
        p0_blockers.append("m2_8pre_offline_not_passed")
    if not m28.get("scorer_authorization_ready"):
        p0_blockers.append("scorer_authorization_not_ready")
    if not policy.get("policy_conversion_observed"):
        p0_blockers.append("policy_conversion_not_observed_in_existing_traces")
    if ctspc_status.get("retain") != 0:
        p0_blockers.append("ctspc_v0_retain_not_zero")
    if ctspc_status.get("scorer_default") != "off":
        p0_blockers.append("ctspc_v0_not_off_by_default")
    return {
        "report_scope": "first_stage_delivery_evidence_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "delivery_claim_status": "scaffold_and_diagnostic_package_only",
        "sota_3pp_claim_ready": False,
        "p0_blockers": p0_blockers,
        "artifact_boundary": boundary,
        "m28pre_gate": {
            "m2_8pre_offline_passed": m28.get("m2_8pre_offline_passed"),
            "scorer_authorization_ready": m28.get("scorer_authorization_ready"),
            "remaining_gap_to_35_demote_candidates": m28.get("remaining_gap_to_35_demote_candidates"),
            "blockers": m28.get("blockers"),
            "route_recommendation": m28.get("route_recommendation"),
        },
        "ctspc_v0": {
            "status": ctspc_status.get("status"),
            "ctspc_v0_frozen": ctspc_status.get("ctspc_v0_frozen"),
            "scorer_default": ctspc_status.get("scorer_default"),
            "retain": ctspc_status.get("retain"),
            "dev_rerun_authorized": ctspc_status.get("dev_rerun_authorized"),
            "holdout_authorized": ctspc_status.get("holdout_authorized"),
            "latest_candidate_accuracy": ctspc_summary.get("candidate_accuracy"),
            "latest_baseline_accuracy": ctspc_summary.get("baseline_accuracy"),
            "latest_net_case_gain": ctspc_summary.get("net_case_gain"),
        },
        "policy_conversion": policy,
        "source_result_layout": source_layout,
        "next_required_action": "root_cause_audit_before_any_scorer",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# First-Stage Delivery Evidence Audit",
        "",
        f"- Claim status: `{report['delivery_claim_status']}`",
        f"- SOTA +3pp claim ready: `{report['sota_3pp_claim_ready']}`",
        f"- Offline only: `{report['offline_only']}`",
        f"- P0 blockers: `{report['p0_blockers']}`",
        "",
        "## Gate Snapshot",
        "",
        f"- Artifact boundary passed: `{report['artifact_boundary']['artifact_boundary_passed']}`",
        f"- Forbidden artifact count: `{report['artifact_boundary']['forbidden_artifact_count']}`",
        f"- M2.8-pre passed: `{report['m28pre_gate']['m2_8pre_offline_passed']}`",
        f"- Scorer authorization ready: `{report['m28pre_gate']['scorer_authorization_ready']}`",
        f"- Remaining gap to 35 demote candidates: `{report['m28pre_gate']['remaining_gap_to_35_demote_candidates']}`",
        "",
        "## Policy Conversion Evidence",
        "",
        f"- Trace files scanned: `{report['policy_conversion']['trace_files_scanned']}`",
        f"- Rule hits: `{report['policy_conversion']['rule_hits']}`",
        f"- Policy hits: `{report['policy_conversion']['policy_hits']}`",
        f"- Recommended tools: `{report['policy_conversion']['recommended_tools']}`",
        f"- Selected next tool: `{report['policy_conversion']['selected_next_tool']}`",
        f"- Next tool emitted: `{report['policy_conversion']['next_tool_emitted']}`",
        f"- Policy conversion observed: `{report['policy_conversion']['policy_conversion_observed']}`",
        "",
        "## Source/Layout Evidence",
        "",
        f"- Source result availability ready: `{report['source_result_layout']['source_result_availability_ready']}`",
        f"- Alias family coverage zero: `{report['source_result_layout']['wrong_arg_key_alias_family_coverage_zero']}`",
        f"- Deterministic family coverage zero: `{report['source_result_layout']['deterministic_schema_local_family_coverage_zero']}`",
        f"- Route recommendation: `{report['source_result_layout']['route_recommendation']}`",
        "",
        "This audit is diagnostic. It does not authorize BFCL/model/scorer runs.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset-root", type=Path, default=DEFAULT_SUBSET)
    parser.add_argument("--low-risk-root", type=Path, default=DEFAULT_LOW_RISK)
    parser.add_argument("--phase2-validation-root", type=Path, default=DEFAULT_PHASE2_VALIDATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.subset_root, args.low_risk_root, args.phase2_validation_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "delivery_claim_status": report["delivery_claim_status"],
            "sota_3pp_claim_ready": report["sota_3pp_claim_ready"],
            "p0_blockers": report["p0_blockers"],
            "artifact_boundary_passed": report["artifact_boundary"]["artifact_boundary_passed"],
            "m2_8pre_offline_passed": report["m28pre_gate"]["m2_8pre_offline_passed"],
            "scorer_authorization_ready": report["m28pre_gate"]["scorer_authorization_ready"],
            "policy_conversion_observed": report["policy_conversion"]["policy_conversion_observed"],
            "next_required_action": report["next_required_action"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
