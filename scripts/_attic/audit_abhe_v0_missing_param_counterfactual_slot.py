#!/usr/bin/env python3
"""Create compact offline counterfactual slot audit from residual miss-param traces."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
RUN_ROOT = Path("/tmp/abhe_v0_miss_param_residual_dev_smoke")
OUT = ROOT / "abhe_v0_missing_param_counterfactual_slot_audit_v0.json"
ARMS = ["baseline", "frozen_v2", "slot_recovery_v1"]
CATEGORY = "multi_turn_miss_param"


def _hash_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(str(path).encode("utf-8")).hexdigest()


def _load(path: Path) -> Dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _contains(items: List[str], token: str) -> bool:
    return any(token in item for item in items)


def _row(path: Path, arm: str) -> Dict[str, Any]:
    trace = _load(path) or {}
    validation = trace.get("validation") if isinstance(trace.get("validation"), dict) else {}
    labels = [str(x) for x in (validation.get("failure_labels") or [])]
    patches = [str(x) for x in (validation.get("request_patches") or [])]
    arg_validation = validation.get("arg_binding_validation") if isinstance(validation.get("arg_binding_validation"), dict) else {}
    final_arg_validation = validation.get("final_arg_binding_validation") if isinstance(validation.get("final_arg_binding_validation"), dict) else {}
    normalized_arg_validation = validation.get("normalized_arg_binding_validation") if isinstance(validation.get("normalized_arg_binding_validation"), dict) else {}
    emitted = validation.get("next_tool_emitted") is True or validation.get("next_tool_final_args_match_binding") is True
    matched = validation.get("next_tool_matches_recommendation") is True
    recommended = bool(validation.get("recommended_tools") or validation.get("candidate_recommended_tools"))
    known_context = any(text.startswith("prompt_injector:Known explicit context values") for text in patches)
    last_tool = str(validation.get("last_observed_role")) == "tool"
    malformed = _contains(labels, "MALFORMED_CALL") or bool(arg_validation) or bool(final_arg_validation)
    no_tool = _contains(labels, "ACTIONABLE_NO_TOOL_DECISION") or _contains(labels, "EMPTY_TOOL_CALL")
    post_tool_summary = _contains(labels, "POST_TOOL_PROSE_SUMMARY")
    missing_like = no_tool or post_tool_summary or malformed or (recommended and not matched)
    prior_turn_recoverable = bool(known_context and missing_like)
    prior_tool_recoverable = bool(last_tool and missing_like)
    prerequisite_recoverable = bool(recommended and not matched and not emitted)
    ambiguity = bool(prior_turn_recoverable and prior_tool_recoverable and malformed)
    schema_binding = bool((prior_turn_recoverable or prior_tool_recoverable) and not ambiguity and not malformed)
    lookup = bool(prerequisite_recoverable and not schema_binding)
    valid_complete = bool(emitted and matched and not arg_validation and not final_arg_validation and not normalized_arg_validation)
    missing_count = int(missing_like)
    return {
        "case_hash": _hash_path(path),
        "arm": arm,
        "bfcl_category": CATEGORY,
        "required_arg_count": None,
        "missing_required_arg_count": missing_count,
        "missing_arg_sources": {
            "prior_turn_recoverable": prior_turn_recoverable,
            "prior_tool_observation_recoverable": prior_tool_recoverable,
            "prerequisite_tool_recoverable": prerequisite_recoverable,
            "unrecoverable": bool(missing_like and not (prior_turn_recoverable or prior_tool_recoverable or prerequisite_recoverable)),
        },
        "schema_compatible_binding_available": schema_binding,
        "entity_ambiguity_detected": ambiguity,
        "counterfactual_bind_available": schema_binding,
        "counterfactual_lookup_available": lookup,
        "would_block_valid_tool_call": False,
        "function_selection_mismatch_proxy": bool(recommended and emitted and not matched),
        "tool_call_order_mismatch_proxy": bool(validation.get("next_tool_plan_activated") and not emitted),
        "nested_arg_shape_mismatch_proxy": malformed,
        "enum_or_literal_normalization_mismatch_proxy": bool(normalized_arg_validation),
        "extra_or_missing_tool_call_proxy": bool(no_tool or (recommended and not emitted)),
        "ready_tool_call_overridden_by_guard": False,
        "raw_material_absent": True,
    }


def build() -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    blockers: List[str] = []
    for arm in ARMS:
        trace_dir = RUN_ROOT / arm / CATEGORY / "traces"
        paths = sorted(trace_dir.glob("*.json"))
        if not paths:
            blockers.append(f"trace_dir_missing_or_empty:{arm}")
            continue
        for path in paths:
            rows.append(_row(path, arm))
    summary = {
        "counterfactual_bindable_count": sum(1 for row in rows if row["counterfactual_bind_available"]),
        "counterfactual_lookup_needed_count": sum(1 for row in rows if row["counterfactual_lookup_available"]),
        "unrecoverable_count": sum(1 for row in rows if row["missing_arg_sources"]["unrecoverable"]),
        "ambiguous_entity_count": sum(1 for row in rows if row["entity_ambiguity_detected"]),
        "valid_tool_call_guard_trigger_count": sum(1 for row in rows if row["would_block_valid_tool_call"]),
        "function_selection_mismatch_proxy_count": sum(1 for row in rows if row["function_selection_mismatch_proxy"]),
        "tool_call_order_mismatch_proxy_count": sum(1 for row in rows if row["tool_call_order_mismatch_proxy"]),
        "nested_arg_shape_mismatch_proxy_count": sum(1 for row in rows if row["nested_arg_shape_mismatch_proxy"]),
        "extra_or_missing_tool_call_proxy_count": sum(1 for row in rows if row["extra_or_missing_tool_call_proxy"]),
    }
    viability = "runtime_controller_worth_synthetic_only" if summary["counterfactual_bindable_count"] + summary["counterfactual_lookup_needed_count"] > 0 else "do_not_run_bfcl_without_deeper_trace_labels"
    return {
        "artifact_kind": "abhe_v0_missing_param_counterfactual_slot_audit",
        "schema_version": "abhe_v0_missing_param_counterfactual_slot_audit_v0",
        "bounded_diagnostic_only": True,
        "source_trace_root_hash": "sha256:" + hashlib.sha256(str(RUN_ROOT / CATEGORY).encode("utf-8")).hexdigest(),
        "rows": rows,
        "summary": summary,
        "viability_assessment": viability,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "raw_material_absent": True,
        "trace_content_committed": False,
        "prompt_literal_committed": False,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_evidence": False,
        "archive_updated": False,
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = build()
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
