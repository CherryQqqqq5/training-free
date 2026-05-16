#!/usr/bin/env python3
"""Validate the ABHE-v0 runtime candidate adapter remains compact and non-generative."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_ADAPTER = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_candidate_adapter.json")
EXPECTED_HASH = "sha256:8e28826895c76afd14fb2ec07550b871ea50df25c0666881dad39be86450991f"
EXPECTED_ENTRIES = {"state_tracking_v0", "hallucination_abstain_v0"}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_adapter(adapter: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if adapter.get("artifact_kind") != "abhe_v0_runtime_candidate_adapter":
        blockers.append("artifact_kind_invalid")
    if adapter.get("schema_version") != "abhe_v0_runtime_candidate_adapter_v0":
        blockers.append("schema_version_invalid")
    if adapter.get("selected_case_ids_hash") != EXPECTED_HASH:
        blockers.append("selected_case_ids_hash_invalid")
    if not Path(str(adapter.get("candidate_artifact_path") or "")).exists():
        blockers.append("candidate_artifact_missing")
    if not Path(str(adapter.get("fresh_slice_manifest_path") or "")).exists():
        blockers.append("fresh_slice_manifest_missing")
    if not Path(str(adapter.get("runtime_config_path") or "")).exists():
        blockers.append("runtime_config_missing")
    for key in ["candidate_jsonl_generated", "candidate_rule_generated", "candidate_yaml_generated", "candidate_pool_ready", "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called", "scorer_called", "performance_evidence", "holdout_touched", "full_suite_touched"]:
        if adapter.get(key) is not False:
            blockers.append(f"{key}_not_false")
    if adapter.get("raw_material_absent") is not True:
        blockers.append("raw_material_absent_not_true")
    if adapter.get("entry_specific_activation_required") is not True:
        blockers.append("entry_specific_activation_required_not_true")
    if adapter.get("fallback_global_activation_allowed") is not False:
        blockers.append("fallback_global_activation_allowed_not_false")
    if adapter.get("runtime_context_source") != "runner_env_activation_entry_or_categories":
        blockers.append("runtime_context_source_invalid")
    projections = adapter.get("runtime_projection")
    if not isinstance(projections, list):
        blockers.append("runtime_projection_not_list")
        projections = []
    by_entry = {row.get("entry_id"): row for row in projections if isinstance(row, dict)}
    if set(by_entry) != EXPECTED_ENTRIES:
        blockers.append("runtime_projection_entries_invalid")
    state = by_entry.get("state_tracking_v0", {})
    if state.get("candidate_type") != "state_summary_injection":
        blockers.append("state_candidate_type_invalid")
    if state.get("activation_scope") != "selected_fresh_dev_slice_only":
        blockers.append("state_activation_scope_invalid")
    if state.get("no_state_mutation") is not True:
        blockers.append("state_no_state_mutation_not_true")
    if state.get("search_memory_watch_excluded") is not True:
        blockers.append("state_search_memory_watch_excluded_not_true")
    hallucination = by_entry.get("hallucination_abstain_v0", {})
    if hallucination.get("candidate_type") != "evidence_boundary_verifier":
        blockers.append("hallucination_candidate_type_invalid")
    if hallucination.get("activation_scope") != "selected_fresh_dev_slice_only":
        blockers.append("hallucination_activation_scope_invalid")
    if hallucination.get("valid_actionable_tool_use_guard") is not True:
        blockers.append("hallucination_valid_tool_guard_not_true")
    if hallucination.get("false_abstain_telemetry_required") is not True:
        blockers.append("hallucination_false_abstain_telemetry_missing")
    if adapter.get("adapter_ready") is not True:
        blockers.append("adapter_ready_not_true")
    blockers.extend(scan_value(adapter, label="abhe_v0_runtime_candidate_adapter"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ADAPTER) -> Dict[str, Any]:
    if not path.exists():
        return {"report_scope": "abhe_v0_runtime_candidate_adapter_check", "adapter_path": str(path), "adapter_present": False, "adapter_ready": False, "blockers": ["runtime_candidate_adapter_missing"]}
    adapter = _load(path)
    blockers = validate_adapter(adapter)
    return {
        "report_scope": "abhe_v0_runtime_candidate_adapter_check",
        "adapter_path": str(path),
        "adapter_present": True,
        "adapter_ready": not blockers,
        "selected_case_ids_hash": adapter.get("selected_case_ids_hash"),
        "candidate_jsonl_generated": adapter.get("candidate_jsonl_generated"),
        "candidate_rule_generated": adapter.get("candidate_rule_generated"),
        "candidate_yaml_generated": adapter.get("candidate_yaml_generated"),
        "provider_calls_made": adapter.get("provider_calls_made"),
        "bfcl_generate_called": adapter.get("bfcl_generate_called"),
        "bfcl_evaluate_called": adapter.get("bfcl_evaluate_called"),
        "scorer_called": adapter.get("scorer_called"),
        "performance_evidence": adapter.get("performance_evidence"),
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, default=DEFAULT_ADAPTER)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.adapter)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "abhe_v0_runtime_candidate_adapter_check", "adapter_ready": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 1 if args.strict and not summary.get("adapter_ready") else 0


if __name__ == "__main__":
    raise SystemExit(main())
