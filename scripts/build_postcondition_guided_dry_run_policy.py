#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

DEFAULT_MANIFEST = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_policy_candidate_manifest.json")
DEFAULT_OUT_DIR = Path("outputs/artifacts/phase2/postcondition_guided_policy_dry_run_v1/approved_low_risk")
ALLOWED_GAPS = {"read_content", "search_or_find"}
ALLOWED_TOOLS = {"cat", "find", "grep"}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _eligible_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in manifest.get("candidate_records") or []:
        tools = set(row.get("recommended_tools") or [])
        if not row.get("low_risk_dry_run_review_eligible"):
            continue
        if row.get("ambiguity_flags"):
            continue
        if row.get("postcondition_gap") not in ALLOWED_GAPS:
            continue
        if not tools or not tools <= ALLOWED_TOOLS:
            continue
        scan = row.get("forbidden_field_scan") or {}
        if scan.get("forbidden_dependency_present"):
            continue
        rows.append(row)
    return rows


def _fingerprint(manifest: dict[str, Any]) -> str:
    payload = json.dumps({
        "policy_family": manifest.get("policy_family"),
        "candidate_count": manifest.get("candidate_count"),
        "low_risk_dry_run_review_eligible_count": manifest.get("low_risk_dry_run_review_eligible_count"),
        "candidate_ids": [row.get("candidate_id") for row in manifest.get("candidate_records") or []],
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = _load(manifest_path)
    selected = _eligible_rows(manifest)
    grouped: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        grouped[(str(row.get("postcondition_gap")), tuple(row.get("recommended_tools") or []))].append(row)
    policy_units = []
    for (gap, tools), rows in sorted(grouped.items()):
        unit_id = f"postcondition_guided_{gap}_soft_v1"
        policy_units.append({
            "policy_unit_id": unit_id,
            "policy_family": "postcondition_guided_trajectory_policy",
            "theory_class": "postcondition_guided_trajectory_progress",
            "runtime_enabled": False,
            "retention_eligibility": "diagnostic_only",
            "intervention_strength": "guidance_only",
            "tool_choice_mode": "soft",
            "exact_tool_choice": False,
            "trigger": {
                "failure_labels_any": [
                    "(PRE_TOOL,ACTIONABLE_NO_TOOL_DECISION)",
                    "(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)",
                    "(POST_TOOL,POST_TOOL_PROSE_SUMMARY)",
                    "(POST_TOOL,TERMINATION_INADMISSIBLE)",
                ],
                "request_predicates_all": ["prior_tool_outputs_present", "tools_available"],
                "postcondition_gap": gap,
                "postcondition_already_satisfied": False,
            },
            "decision_policy": {
                "recommended_tools": list(tools),
                "argument_policy": "no_argument_creation_or_binding",
                "capability_only": True,
            },
            "evidence_requirements": [
                "recommended_tool_available_in_current_schema",
                "prior_tool_output_present",
                "postcondition_witness_absent",
                "forbidden_field_scan_clean",
            ],
            "support_count": len(rows),
        })
    approval_rows = [{
        "candidate_id": row.get("candidate_id"),
        "source_audit_record_id": row.get("source_audit_record_id"),
        "source_audit_record_pointer": row.get("source_audit_record_pointer"),
        "postcondition_gap": row.get("postcondition_gap"),
        "recommended_tools": row.get("recommended_tools") or [],
        "forbidden_field_scan": row.get("forbidden_field_scan") or {},
    } for row in selected]
    return {
        "report_scope": "postcondition_guided_policy_dry_run_compile",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "runtime_enabled": False,
        "runtime_default_load": False,
        "manifest_path": str(manifest_path),
        "source_manifest_fingerprint": _fingerprint(manifest),
        "input_candidate_count": int(manifest.get("candidate_count") or 0),
        "low_risk_review_eligible_count": int(manifest.get("low_risk_dry_run_review_eligible_count") or 0),
        "selected_non_ambiguous_low_risk_count": len(selected),
        "reviewer_excluded_ambiguous_low_risk_count": int(manifest.get("low_risk_dry_run_review_eligible_count") or 0) - len(selected),
        "policy_unit_count": len(policy_units),
        "policy_units": policy_units,
        "approval_records": approval_rows,
        "candidate_commands": [],
        "planned_commands": [],
        "next_required_action": "offline_dry_run_activation_audit_before_any_runtime_enablement",
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    policy_payload = {
        "policy_units": report["policy_units"],
        "runtime_enabled": False,
        "candidate_commands": [],
        "planned_commands": [],
    }
    (out_dir / "policy_unit.yaml").write_text(yaml.safe_dump(policy_payload, sort_keys=True), encoding="utf-8")
    approval_payload = {key: report[key] for key in [
        "report_scope",
        "offline_only",
        "does_not_call_bfcl_or_model",
        "does_not_authorize_scorer",
        "runtime_enabled",
        "runtime_default_load",
        "manifest_path",
        "source_manifest_fingerprint",
        "input_candidate_count",
        "low_risk_review_eligible_count",
        "selected_non_ambiguous_low_risk_count",
        "reviewer_excluded_ambiguous_low_risk_count",
        "policy_unit_count",
        "approval_records",
        "candidate_commands",
        "planned_commands",
        "next_required_action",
    ]}
    (out_dir / "policy_approval_manifest.json").write_text(json.dumps(approval_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    status_payload = {key: report[key] for key in [
        "report_scope",
        "offline_only",
        "does_not_call_bfcl_or_model",
        "does_not_authorize_scorer",
        "runtime_enabled",
        "runtime_default_load",
        "input_candidate_count",
        "low_risk_review_eligible_count",
        "selected_non_ambiguous_low_risk_count",
        "reviewer_excluded_ambiguous_low_risk_count",
        "policy_unit_count",
        "candidate_commands",
        "planned_commands",
        "next_required_action",
    ]}
    status_payload["dry_run_policy_compile_ready"] = bool(report["policy_unit_count"] and not report["runtime_enabled"])
    (out_dir / "compile_status.json").write_text(json.dumps(status_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "source_manifest_fingerprint.json").write_text(json.dumps({"source_manifest_fingerprint": report["source_manifest_fingerprint"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.manifest)
    write_outputs(report, args.output_dir)
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "input_candidate_count",
            "low_risk_review_eligible_count",
            "selected_non_ambiguous_low_risk_count",
            "reviewer_excluded_ambiguous_low_risk_count",
            "policy_unit_count",
            "runtime_enabled",
            "next_required_action",
        ]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
