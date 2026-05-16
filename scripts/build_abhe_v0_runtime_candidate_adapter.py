#!/usr/bin/env python3
"""Build the ABHE-v0 runtime candidate adapter without generating rules/YAML/JSONL."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_v0_materialized_candidates import check as check_candidates
from scripts.check_abhe_no_leakage_boundary import scan_value

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_OUTPUT = ARTIFACT_ROOT / "abhe_v0_runtime_candidate_adapter.json"
DEFAULT_CANDIDATES = ARTIFACT_ROOT / "abhe_v0_materialized_candidates.json"
DEFAULT_FRESH_MANIFEST = ARTIFACT_ROOT / "abhe_v0_bfcl_fresh_dev_slice_manifest.json"
DEFAULT_RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")
EXPECTED_HASH = "sha256:8e28826895c76afd14fb2ec07550b871ea50df25c0666881dad39be86450991f"


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def build_adapter(
    *,
    candidates_path: Path = DEFAULT_CANDIDATES,
    fresh_manifest_path: Path = DEFAULT_FRESH_MANIFEST,
    runtime_config_path: Path = DEFAULT_RUNTIME_CONFIG,
) -> Dict[str, Any]:
    candidate_summary = check_candidates(candidates_path=candidates_path, fresh_manifest_path=fresh_manifest_path)
    manifest = _load(fresh_manifest_path)
    candidates = _load(candidates_path)
    selected_hash = manifest.get("selected_case_ids_hash")
    blockers: List[str] = []
    if selected_hash != EXPECTED_HASH:
        blockers.append("selected_case_ids_hash_mismatch")
    if not runtime_config_path.exists():
        blockers.append("runtime_config_missing")
    if not candidate_summary.get("abhe_v0_materialized_candidates_check_passed"):
        blockers.extend(["materialized_candidates:%s" % b for b in candidate_summary.get("blockers", [])])

    candidate_rows = {row.get("entry_id"): row for row in candidates.get("candidates", []) if isinstance(row, dict)}
    runtime_projection = [
        {
            "entry_id": "state_tracking_v0",
            "candidate_type": "state_summary_injection",
            "activation_scope": "selected_fresh_dev_slice_only",
            "activation_categories": ["multi_turn_base", "multi_turn_long_context", "multi_turn_miss_func", "multi_turn_miss_param"],
            "activation_boundary": "multi_turn_only_state_carryover_evidence_required",
            "non_target_exclusions": ["single_turn", "search_memory_watch", "state_mutation"],
            "runtime_guidance_fragment_id": "state_summary_injection_compact_fragment_v0",
            "no_state_mutation": True,
            "search_memory_watch_excluded": True,
            "telemetry_required": candidate_rows.get("state_tracking_v0", {}).get("telemetry_required", []),
        },
        {
            "entry_id": "hallucination_abstain_v0",
            "candidate_type": "evidence_boundary_verifier",
            "activation_scope": "selected_fresh_dev_slice_only",
            "activation_categories": ["irrelevance", "live_irrelevance", "live_relevance"],
            "activation_boundary": "answerability_failure_only",
            "non_target_exclusions": ["valid_actionable_tool_use", "sufficient_evidence_cases"],
            "runtime_guidance_fragment_id": "evidence_boundary_verifier_compact_fragment_v0",
            "valid_actionable_tool_use_guard": True,
            "false_abstain_telemetry_required": True,
            "telemetry_required": candidate_rows.get("hallucination_abstain_v0", {}).get("telemetry_required", []),
        },
    ]
    adapter = {
        "artifact_kind": "abhe_v0_runtime_candidate_adapter",
        "schema_version": "abhe_v0_runtime_candidate_adapter_v0",
        "selected_case_ids_hash": selected_hash,
        "candidate_artifact_path": str(candidates_path),
        "fresh_slice_manifest_path": str(fresh_manifest_path),
        "runtime_config_path": str(runtime_config_path),
        "candidate_jsonl_generated": False,
        "candidate_rule_generated": False,
        "candidate_yaml_generated": False,
        "candidate_pool_ready": False,
        "adapter_ready": not blockers,
        "runtime_projection": runtime_projection,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "raw_material_absent": True,
        "blockers": sorted(set(blockers)),
        "next_required_action": "run_provider_preflight_then_execution_readiness" if not blockers else "fix_runtime_candidate_adapter_blockers",
    }
    adapter["blockers"] = sorted(set(adapter["blockers"] + scan_value(adapter, label="abhe_v0_runtime_candidate_adapter")))
    adapter["adapter_ready"] = not adapter["blockers"]
    return adapter


def write_adapter(output: Path, adapter: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(adapter, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--fresh-manifest", type=Path, default=DEFAULT_FRESH_MANIFEST)
    parser.add_argument("--runtime-config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        adapter = build_adapter(candidates_path=args.candidates, fresh_manifest_path=args.fresh_manifest, runtime_config_path=args.runtime_config)
        if args.write:
            write_adapter(args.output, adapter)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        adapter = {"report_scope": "abhe_v0_runtime_candidate_adapter", "adapter_ready": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(adapter, sort_keys=True) if args.compact else json.dumps(adapter, indent=2, sort_keys=True))
    return 1 if args.strict and not adapter.get("adapter_ready") else 0


if __name__ == "__main__":
    raise SystemExit(main())
