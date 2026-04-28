#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

DEFAULT_ALLOWLIST = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_compiler_allowlist.json")
DEFAULT_OUT_DIR = Path("outputs/artifacts/phase2/memory_operation_obligation_dry_run_v1/first_pass")
ALLOWED_CAPABILITY_FAMILIES = {"memory_key_or_text_search", "memory_list_keys", "memory_value_retrieve"}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _fingerprint(payload: dict[str, Any]) -> str:
    stable = json.dumps({
        "report_scope": payload.get("report_scope"),
        "compiler_scope": payload.get("compiler_scope"),
        "compiler_input_eligible_count": payload.get("compiler_input_eligible_count"),
        "support_record_hashes": [row.get("support_record_hash") for row in payload.get("allowlist_records") or []],
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _eligible_records(allowlist: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in allowlist.get("allowlist_records") or []:
        families = set(row.get("recommended_tool_capability_families") or [])
        if row.get("compiler_input_eligible") is not True:
            continue
        if row.get("support_class") != "first_pass_retrieve":
            continue
        if row.get("memory_witness_strength") != "no_witness":
            continue
        if row.get("requires_separate_weak_witness_approval"):
            continue
        if row.get("runtime_enabled") is not False or row.get("exact_tool_choice") is not False:
            continue
        if not row.get("forbidden_field_scan_clean"):
            continue
        if not families or not families <= ALLOWED_CAPABILITY_FAMILIES:
            continue
        rows.append(row)
    return rows


def evaluate(allowlist_path: Path = DEFAULT_ALLOWLIST) -> dict[str, Any]:
    allowlist = _load(allowlist_path)
    selected = _eligible_records(allowlist)
    capability_families = sorted({family for row in selected for family in row.get("recommended_tool_capability_families") or []})
    policy_units = []
    if selected:
        policy_units.append({
            "policy_unit_id": "memory_first_pass_retrieve_soft_v1",
            "policy_family": "memory_operation_obligation",
            "theory_class": "memory_postcondition_obligation",
            "runtime_enabled": False,
            "retention_eligibility": "diagnostic_only",
            "intervention_strength": "guidance_only",
            "tool_choice_mode": "soft",
            "exact_tool_choice": False,
            "trigger": {
                "operation": "retrieve",
                "operation_scope": "retrieve_only",
                "memory_witness_strength": "no_witness",
                "retrieve_intent_observable": True,
                "memory_tools_available": True,
                "strong_value_witness_present": False,
                "empty_or_error_witness_present": False,
            },
            "decision_policy": {
                "capability_only": True,
                "argument_policy": "no_argument_creation_or_binding",
                "recommended_tool_capability_families": capability_families,
            },
            "evidence_requirements": [
                "compiler_allowlist_first_pass_only",
                "forbidden_field_scan_clean",
                "weak_lookup_witness_excluded",
                "negative_controls_passed",
                "no_raw_audit_or_review_manifest_input",
            ],
            "support_count": len(selected),
        })
    return {
        "report_scope": "memory_operation_obligation_dry_run_compile",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "runtime_enabled": False,
        "runtime_default_load": False,
        "compiler_enabled": False,
        "allowlist_path": str(allowlist_path),
        "source_allowlist_fingerprint": _fingerprint(allowlist),
        "input_allowlist_count": int(allowlist.get("compiler_input_eligible_count") or 0),
        "selected_first_pass_count": len(selected),
        "excluded_weak_witness_count": int(allowlist.get("weak_witness_compiler_input_count") or 0),
        "argument_creation_count": 0,
        "policy_unit_count": len(policy_units),
        "policy_units": policy_units,
        "approval_records": [
            {
                "support_record_hash": row.get("support_record_hash"),
                "category": row.get("category"),
                "support_class": row.get("support_class"),
                "memory_witness_strength": row.get("memory_witness_strength"),
                "recommended_tool_capability_families": row.get("recommended_tool_capability_families") or [],
            }
            for row in selected
        ],
        "candidate_commands": [],
        "planned_commands": [],
        "next_required_action": "tool_family_resolver_audit_before_any_runtime_enablement",
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
        "compiler_enabled",
        "allowlist_path",
        "source_allowlist_fingerprint",
        "input_allowlist_count",
        "selected_first_pass_count",
        "excluded_weak_witness_count",
        "argument_creation_count",
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
        "compiler_enabled",
        "input_allowlist_count",
        "selected_first_pass_count",
        "excluded_weak_witness_count",
        "argument_creation_count",
        "policy_unit_count",
        "candidate_commands",
        "planned_commands",
        "next_required_action",
    ]}
    status_payload["dry_run_policy_compile_ready"] = bool(report["policy_unit_count"] and not report["runtime_enabled"] and report["argument_creation_count"] == 0)
    (out_dir / "compile_status.json").write_text(json.dumps(status_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "source_allowlist_fingerprint.json").write_text(json.dumps({"source_allowlist_fingerprint": report["source_allowlist_fingerprint"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.allowlist)
    write_outputs(report, args.output_dir)
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "input_allowlist_count",
            "selected_first_pass_count",
            "excluded_weak_witness_count",
            "argument_creation_count",
            "policy_unit_count",
            "runtime_enabled",
            "next_required_action",
        ]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
