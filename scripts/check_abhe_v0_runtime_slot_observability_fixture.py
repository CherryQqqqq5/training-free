#!/usr/bin/env python3
"""Validate ABHE runtime-slot no-provider observability fixture output."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_fixture.json")
FALSE_FIELDS = [
    "provider_calls_made",
    "bfcl_generate_called",
    "bfcl_evaluate_called",
    "scorer_called",
    "holdout_touched",
    "full_suite_touched",
    "archive_updated",
    "performance_evidence",
    "candidate_jsonl_generated",
    "candidate_yaml_generated",
    "candidate_rule_generated",
    "argument_values_committed",
    "provider_payload_committed",
    "scorer_diff_committed",
]
ROW_FALSE_FIELDS = ["argument_values_committed", "provider_payload_committed", "scorer_diff_committed"]
REQUIRED_ROW_KEYS = [
    "pre_generation_request_patch_set_hash",
    "pre_generation_adapter_projection_hash",
    "pre_generation_required_arg_ledger_available",
    "pre_generation_tool_schema_keyset_hash",
    "pre_generation_intended_tool_known",
    "post_decode_tool_call_present",
    "post_decode_argument_keyset_hashes",
    "post_decode_missing_required_arg_count_before_repair",
    "post_decode_provider_generated_valid_call_proxy",
    "post_decode_no_tool_call_final_response",
    "post_response_existing_validator_repair_kind_counts",
    "post_response_runtime_slot_policy_hit",
    "post_response_runtime_slot_bind_repair_count",
    "post_response_controller_not_applicable_reason",
    "post_response_argument_keyset_changed_by_repair",
]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_observability_fixture":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_observability_fixture_v0":
        blockers.append("schema_version_invalid")
    if data.get("fixture_scope") != "no_provider_synthetic_observability_only":
        blockers.append("fixture_scope_invalid")
    if data.get("safe_fields_only") is not True or data.get("raw_material_absent") is not True:
        blockers.append("safe_boundary_not_true")
    for key in FALSE_FIELDS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    if len(rows) < 4:
        blockers.append("fixture_rows_missing")
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            blockers.append(f"row_invalid:{idx}")
            continue
        for key in REQUIRED_ROW_KEYS:
            if key not in row:
                blockers.append(f"row_key_missing:{idx}:{key}")
        if row.get("raw_material_absent") is not True:
            blockers.append(f"row_raw_material_absent_not_true:{idx}")
        for key in ROW_FALSE_FIELDS:
            if row.get(key) is not False:
                blockers.append(f"row_{key}_not_false:{idx}")
        for suspicious_key in ("argument_values", "prompt_text", "provider_payload", "scorer_diff", "gold", "expected"):
            if suspicious_key in row:
                blockers.append(f"row_forbidden_key:{idx}:{suspicious_key}")
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    if int(summary.get("bind_repair_rows") or 0) <= 0:
        blockers.append("bind_repair_rows_missing")
    if int(summary.get("provider_generated_valid_call_proxy_rows") or 0) <= 0:
        blockers.append("provider_generated_valid_call_proxy_rows_missing")
    if int(summary.get("no_tool_final_response_rows") or 0) <= 0:
        blockers.append("no_tool_final_response_rows_missing")
    if int(summary.get("argument_keyset_changed_rows") or 0) <= 0:
        blockers.append("argument_keyset_changed_rows_missing")
    if data.get("next_required_action") != "review_observability_fixture_before_any_bfcl_rerun":
        blockers.append("next_required_action_invalid")
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    try:
        data = _load(path)
        blockers = validate(data)
    except Exception as exc:
        data = {}
        blockers = [f"load_failed:{exc.__class__.__name__}"]
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return {
        "report_scope": "abhe_v0_runtime_slot_observability_fixture_check",
        "artifact_path": str(path),
        "observability_fixture_check_passed": not blockers,
        "blockers": blockers,
        "fixture_count": summary.get("fixture_count"),
        "bind_repair_rows": summary.get("bind_repair_rows"),
        "provider_generated_valid_call_proxy_rows": summary.get("provider_generated_valid_call_proxy_rows"),
        "no_tool_final_response_rows": summary.get("no_tool_final_response_rows"),
        "performance_evidence": data.get("performance_evidence", False),
        "next_required_action": data.get("next_required_action"),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.path)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["observability_fixture_check_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
