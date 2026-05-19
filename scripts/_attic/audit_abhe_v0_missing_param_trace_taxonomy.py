#!/usr/bin/env python3
"""Create sanitized miss-param trace taxonomy from residual stress traces."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
RUN_ROOT = Path("/tmp/abhe_v0_miss_param_residual_dev_smoke")
OUT = ROOT / "abhe_v0_missing_param_trace_taxonomy_audit_v0.json"
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


def _contains_label(labels: List[str], token: str) -> bool:
    return any(token in label for label in labels)


def _taxonomy(trace: Dict[str, Any]) -> Dict[str, bool]:
    validation = trace.get("validation") if isinstance(trace.get("validation"), dict) else {}
    labels = [str(x) for x in (validation.get("failure_labels") or [])]
    request_patches = [str(x) for x in (validation.get("request_patches") or [])]
    recommended_tools = validation.get("recommended_tools") or []
    matched_tools = validation.get("matched_recommended_tools") or []
    arg_validation = validation.get("arg_binding_validation") if isinstance(validation.get("arg_binding_validation"), dict) else {}
    final_arg_validation = validation.get("final_arg_binding_validation") if isinstance(validation.get("final_arg_binding_validation"), dict) else {}
    has_known_context_patch = any(text.startswith("prompt_injector:Known explicit context values") for text in request_patches)
    emitted_tool = validation.get("next_tool_emitted") is True or validation.get("next_tool_final_args_match_binding") is True
    recoverable_tool_signal = bool(recommended_tools) and not bool(matched_tools)
    asked = _contains_label(labels, "CLARIFICATION_REQUEST")
    no_tool = _contains_label(labels, "ACTIONABLE_NO_TOOL_DECISION") or _contains_label(labels, "EMPTY_TOOL_CALL")
    malformed = _contains_label(labels, "MALFORMED_CALL") or bool(arg_validation) or bool(final_arg_validation)
    post_tool_summary = _contains_label(labels, "POST_TOOL_PROSE_SUMMARY")
    return {
        "required_slot_missing_before_tool_call": no_tool or asked,
        "slot_present_in_prior_turn_not_bound": has_known_context_patch and (asked or no_tool or post_tool_summary),
        "slot_present_in_prior_tool_observation_not_bound": str(validation.get("last_observed_role")) == "tool" and (asked or no_tool or post_tool_summary),
        "slot_tool_recoverable_but_lookup_not_called": recoverable_tool_signal and not emitted_tool,
        "wrong_argument_value_bound": malformed,
        "wrong_argument_key_or_alias": malformed,
        "premature_final_after_partial_state": post_tool_summary,
        "asked_when_slot_recoverable": asked and (has_known_context_patch or recoverable_tool_signal),
        "hallucinated_required_argument": malformed,
        "valid_tool_call_suppressed": no_tool,
    }


def build() -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    counts: Dict[str, Dict[str, int]] = {}
    blockers: List[str] = []
    for arm in ARMS:
        trace_dir = RUN_ROOT / arm / CATEGORY / "traces"
        paths = sorted(trace_dir.glob("*.json"))
        if not paths:
            blockers.append(f"trace_dir_empty:{arm}")
            continue
        selected = paths[:12] + (paths[-8:] if len(paths) > 20 else [])
        seen = set()
        for path in selected:
            if path in seen:
                continue
            seen.add(path)
            trace = _load(path)
            if trace is None:
                rows.append({"arm": arm, "bfcl_category": CATEGORY, "trace_file_hash": _hash_path(path), "malformed_trace": True, "safe_trace_fields_only": True, "raw_material_absent": True})
                continue
            tax = _taxonomy(trace)
            row = {
                "arm": arm,
                "bfcl_category": CATEGORY,
                "trace_file_hash": _hash_path(path),
                "failure_taxonomy": tax,
                "safe_trace_fields_only": True,
                "raw_material_absent": True,
            }
            rows.append(row)
            bucket = counts.setdefault(arm, {key: 0 for key in tax})
            for key, value in tax.items():
                if value:
                    bucket[key] += 1
    report = {
        "artifact_kind": "abhe_v0_missing_param_trace_taxonomy_audit",
        "schema_version": "abhe_v0_missing_param_trace_taxonomy_audit_v0",
        "bounded_dev_smoke_only": True,
        "target_category": CATEGORY,
        "sample_strategy": "first_12_and_last_8_sorted_trace_files_per_arm_when_available",
        "sampled_trace_count": len(rows),
        "taxonomy_counts_by_arm": counts,
        "rows": rows,
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
    return report


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
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
