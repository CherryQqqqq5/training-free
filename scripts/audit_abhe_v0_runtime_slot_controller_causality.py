#!/usr/bin/env python3
"""Build a compact causality audit for the ABHE runtime slot-controller residual run."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

RUN_ROOT = Path("/tmp/abhe_v0_runtime_slot_controller_residual_dev_smoke")
OUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_causality_audit.json")
RESULT_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_residual_dev_smoke_result.json")
FAILURE_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_residual_failure_analysis.json")
ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
CATEGORIES = [
    "multi_turn_miss_param",
    "multi_turn_miss_func",
    "multi_turn_base",
    "multi_turn_long_context",
    "irrelevance",
    "live_irrelevance",
]
RUNTIME_PATCH = "abhe_v0_runtime_slot_controller_v2:enabled"
SLOT_POLICY_HIT = "abhe_runtime_slot_controller_v2"
SLOT_BIND_REPAIR_KIND = "abhe_runtime_slot_controller_v2_bind_required_slot"
KNOWN_EXISTING_REPAIR_KINDS = {
    "resolve_contextual_string_arg",
    "strip_assistant_content_with_tool_calls",
    "wrap_openai_chat_tool_call",
    "convert_responses_tool_call_to_chat",
}


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _sha_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha_json(value: Any) -> str:
    return _sha_text(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _trace_paths(arm: str, category: str) -> List[Path]:
    trace_dir = RUN_ROOT / arm / category / "traces"
    return sorted(trace_dir.glob("*.json")) if trace_dir.exists() else []


def _guidance_hashes(request: Dict[str, Any]) -> List[str]:
    hashes: List[str] = []
    for msg in _safe_list(request.get("messages")):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "developer":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            hashes.append(_sha_text(content))
    return sorted(set(hashes))


def _repair_kinds(validation: Dict[str, Any], top_level_repairs: Any) -> List[str]:
    kinds: List[str] = []
    for repair in _safe_list(validation.get("repairs")):
        if isinstance(repair, dict) and repair.get("kind"):
            kinds.append(str(repair["kind"]))
    for kind in _safe_list(validation.get("repair_kinds")):
        if isinstance(kind, str):
            kinds.append(kind)
    for repair in _safe_list(top_level_repairs):
        if isinstance(repair, dict) and repair.get("kind"):
            kinds.append(str(repair["kind"]))
    return kinds


def _tool_calls_from_chat_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    for choice in _safe_list(payload.get("choices")):
        message = _safe_dict(choice.get("message")) if isinstance(choice, dict) else {}
        for call in _safe_list(message.get("tool_calls")):
            if isinstance(call, dict):
                calls.append(call)
    return calls


def _tool_call_shape_hashes(trace: Dict[str, Any]) -> Tuple[int, Counter, Counter, Counter]:
    calls = []
    calls.extend(_tool_calls_from_chat_payload(_safe_dict(trace.get("final_chat_response"))))
    if not calls:
        calls.extend(_tool_calls_from_chat_payload(_safe_dict(trace.get("raw_response"))))
    tool_name_hashes: Counter = Counter()
    keyset_hashes: Counter = Counter()
    key_count_distribution: Counter = Counter()
    for call in calls:
        function = _safe_dict(call.get("function"))
        name = function.get("name")
        if isinstance(name, str) and name:
            tool_name_hashes[_sha_text(name)] += 1
        args = function.get("arguments")
        parsed: Any = None
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
            except json.JSONDecodeError:
                parsed = None
        elif isinstance(args, dict):
            parsed = args
        if isinstance(parsed, dict):
            keys = sorted(str(k) for k in parsed.keys())
            keyset_hashes[_sha_json(keys)] += 1
            key_count_distribution[str(len(keys))] += 1
        else:
            keyset_hashes["unparsed_or_absent"] += 1
            key_count_distribution["unparsed_or_absent"] += 1
    return len(calls), tool_name_hashes, keyset_hashes, key_count_distribution


def _field_presence_hash(trace: Dict[str, Any]) -> str:
    top = sorted(trace.keys())
    validation = sorted(_safe_dict(trace.get("validation")).keys())
    request = sorted(_safe_dict(trace.get("request")).keys())
    return _sha_json({"top": top, "validation": validation, "request": request})


def _score_rows_by_category() -> Dict[str, Dict[str, Any]]:
    failure = _load_json(FAILURE_PATH)
    rows = {}
    for row in _safe_list(failure.get("scorer_unit_rows")):
        if isinstance(row, dict) and row.get("bfcl_category"):
            rows[str(row["bfcl_category"])] = row
    return rows


def _summarize_trace(path: Path) -> Dict[str, Any]:
    trace = _load_json(path)
    validation = _safe_dict(trace.get("validation"))
    request = _safe_dict(trace.get("request"))
    request_patches = [str(x) for x in _safe_list(validation.get("request_patches"))]
    policy_hits = [str(x) for x in _safe_list(validation.get("policy_hits"))]
    repair_kinds = _repair_kinds(validation, trace.get("repairs"))
    issue_kinds = [str(x.get("kind")) for x in _safe_list(validation.get("issues")) if isinstance(x, dict) and x.get("kind")]
    failure_labels = [str(x) for x in _safe_list(validation.get("failure_labels"))]
    response_shape_kinds = [str(x.get("kind")) for x in _safe_list(validation.get("response_shapes")) if isinstance(x, dict) and x.get("kind")]
    tool_call_count, tool_name_hashes, keyset_hashes, key_count_distribution = _tool_call_shape_hashes(trace)
    marker_present = RUNTIME_PATCH in request_patches
    slot_bind_count = repair_kinds.count(SLOT_BIND_REPAIR_KIND)
    slot_policy_hit = SLOT_POLICY_HIT in policy_hits
    existing_repairs = [kind for kind in repair_kinds if kind != SLOT_BIND_REPAIR_KIND]
    return {
        "field_presence_hash": _field_presence_hash(trace),
        "guidance_hashes": _guidance_hashes(request),
        "request_patch_set_hash": _sha_json(sorted(set(request_patches))),
        "request_patch_count": len(request_patches),
        "runtime_patch_present": marker_present,
        "slot_policy_hit": slot_policy_hit,
        "slot_bind_repair_count": slot_bind_count,
        "repair_kinds": repair_kinds,
        "existing_repair_kinds": existing_repairs,
        "issue_kinds": issue_kinds,
        "failure_labels": failure_labels,
        "response_shape_kinds": response_shape_kinds,
        "tool_call_count": tool_call_count,
        "tool_name_hashes": dict(tool_name_hashes),
        "argument_keyset_hashes": dict(keyset_hashes),
        "argument_key_count_distribution": dict(key_count_distribution),
        "runtime_marker_noop": marker_present and not slot_policy_hit and slot_bind_count == 0,
        "provider_generated_valid_call_proxy": tool_call_count > 0 and not repair_kinds and not issue_kinds,
        "existing_validator_repair_present": bool(existing_repairs),
    }


def _aggregate_trace_summaries(paths: Iterable[Path]) -> Dict[str, Any]:
    counts = Counter()
    repair_kinds = Counter()
    existing_repair_kinds = Counter()
    issue_kinds = Counter()
    failure_labels = Counter()
    response_shape_kinds = Counter()
    guidance_hashes = Counter()
    request_patch_set_hashes = Counter()
    field_presence_hashes = Counter()
    tool_name_hashes = Counter()
    argument_keyset_hashes = Counter()
    argument_key_count_distribution = Counter()
    trace_count = 0
    sampled_trace_artifact_hashes: List[str] = []
    for path in paths:
        trace_count += 1
        item = _summarize_trace(path)
        if len(sampled_trace_artifact_hashes) < 5:
            sampled_trace_artifact_hashes.append("sha256:" + hashlib.sha256(path.read_bytes()).hexdigest())
        counts["runtime_patch_present_count"] += int(item["runtime_patch_present"])
        counts["slot_policy_hit_count"] += int(item["slot_policy_hit"])
        counts["slot_bind_repair_count"] += int(item["slot_bind_repair_count"])
        counts["runtime_marker_noop_count"] += int(item["runtime_marker_noop"])
        counts["provider_generated_valid_call_proxy_count"] += int(item["provider_generated_valid_call_proxy"])
        counts["existing_validator_repair_present_count"] += int(item["existing_validator_repair_present"])
        counts["tool_call_presence_count"] += int(item["tool_call_count"] > 0)
        counts["tool_call_total_count"] += int(item["tool_call_count"])
        for kind in item["repair_kinds"]:
            repair_kinds[kind] += 1
        for kind in item["existing_repair_kinds"]:
            existing_repair_kinds[kind] += 1
        for kind in item["issue_kinds"]:
            issue_kinds[kind] += 1
        for kind in item["failure_labels"]:
            failure_labels[kind] += 1
        for kind in item["response_shape_kinds"]:
            response_shape_kinds[kind] += 1
        for value in item["guidance_hashes"]:
            guidance_hashes[value] += 1
        request_patch_set_hashes[item["request_patch_set_hash"]] += 1
        field_presence_hashes[item["field_presence_hash"]] += 1
        tool_name_hashes.update(item["tool_name_hashes"])
        argument_keyset_hashes.update(item["argument_keyset_hashes"])
        argument_key_count_distribution.update(item["argument_key_count_distribution"])
    return {
        "trace_artifact_count": trace_count,
        "sampled_trace_artifact_hashes": sampled_trace_artifact_hashes,
        "runtime_patch_present_count": counts["runtime_patch_present_count"],
        "slot_policy_hit_count": counts["slot_policy_hit_count"],
        "slot_bind_repair_count": counts["slot_bind_repair_count"],
        "runtime_marker_noop_count": counts["runtime_marker_noop_count"],
        "provider_generated_valid_call_proxy_count": counts["provider_generated_valid_call_proxy_count"],
        "existing_validator_repair_present_count": counts["existing_validator_repair_present_count"],
        "tool_call_presence_count": counts["tool_call_presence_count"],
        "tool_call_total_count": counts["tool_call_total_count"],
        "guidance_hash_counts": dict(sorted(guidance_hashes.items())),
        "request_patch_set_hash_counts": dict(sorted(request_patch_set_hashes.items())),
        "field_presence_hash_counts": dict(sorted(field_presence_hashes.items())),
        "repair_kind_counts": dict(sorted(repair_kinds.items())),
        "existing_repair_kind_counts": dict(sorted(existing_repair_kinds.items())),
        "issue_kind_counts": dict(sorted(issue_kinds.items())),
        "failure_label_counts": dict(sorted(failure_labels.items())),
        "response_shape_kind_counts": dict(sorted(response_shape_kinds.items())),
        "tool_name_hash_counts": dict(sorted(tool_name_hashes.items())),
        "argument_keyset_hash_counts": dict(sorted(argument_keyset_hashes.items())),
        "argument_key_count_distribution": dict(sorted(argument_key_count_distribution.items())),
        "safe_fields_only": True,
        "raw_material_absent": True,
        "argument_values_committed": False,
        "provider_payload_committed": False,
        "scorer_diff_committed": False,
    }


def _compare_category(arm_rows: Dict[str, Dict[str, Any]], category: str, score_row: Dict[str, Any]) -> Dict[str, Any]:
    conditional = arm_rows.get("conditional_frozen_v2", {})
    runtime = arm_rows.get("runtime_slot_controller_v2", {})
    cond_guidance_hashes = set(conditional.get("guidance_hash_counts", {}).keys())
    runtime_guidance_hashes = set(runtime.get("guidance_hash_counts", {}).keys())
    cond_request_patch_hashes = set(conditional.get("request_patch_set_hash_counts", {}).keys())
    runtime_request_patch_hashes = set(runtime.get("request_patch_set_hash_counts", {}).keys())
    runtime_slot_bind = int(runtime.get("slot_bind_repair_count") or 0)
    runtime_marker_noop = int(runtime.get("runtime_marker_noop_count") or 0)
    runtime_trace_count = int(runtime.get("trace_artifact_count") or 0)
    conditional_passed = int(score_row.get("conditional_frozen_v2_passed_count") or 0)
    runtime_passed = int(score_row.get("runtime_slot_controller_v2_passed_count") or 0)
    score_delta = runtime_passed - conditional_passed
    cause_labels: List[str] = []
    if score_delta > 0 and runtime_slot_bind == 0:
        cause_labels.append("score_delta_with_zero_slot_bind_repair")
    if cond_guidance_hashes == runtime_guidance_hashes and cond_guidance_hashes:
        cause_labels.append("developer_guidance_hash_same_as_conditional")
    elif cond_guidance_hashes != runtime_guidance_hashes:
        cause_labels.append("developer_guidance_hash_differs_from_conditional")
    if runtime_marker_noop:
        cause_labels.append("runtime_marker_noop_observed")
    if cond_request_patch_hashes != runtime_request_patch_hashes:
        cause_labels.append("request_patch_set_differs_from_conditional")
    if score_row.get("conditional_frozen_v2_unique_scorer_unit_count") == 1 and score_row.get("runtime_slot_controller_v2_unique_scorer_unit_count") == 1:
        cause_labels.append("single_scorer_unit_category_level_resolution")
    if runtime.get("existing_validator_repair_present_count"):
        cause_labels.append("existing_validator_repairs_present_in_runtime_arm")
    if runtime.get("provider_generated_valid_call_proxy_count"):
        cause_labels.append("provider_generated_or_unrepaired_tool_call_proxy_present")
    if score_delta > 0 and runtime_slot_bind == 0 and runtime_marker_noop == runtime_trace_count:
        primary_assessment = "score_positive_but_direct_slot_bind_causality_not_supported"
    elif score_delta > 0 and runtime_slot_bind > 0:
        primary_assessment = "score_positive_with_observed_slot_bind_repair"
    elif score_delta == 0:
        primary_assessment = "no_score_delta"
    else:
        primary_assessment = "score_regressed_or_unresolved"
    return {
        "bfcl_category": category,
        "conditional_frozen_v2_passed_count": conditional_passed,
        "runtime_slot_controller_v2_passed_count": runtime_passed,
        "score_delta_vs_conditional_frozen_v2": score_delta,
        "selected_compact_case_count": score_row.get("selected_compact_case_count"),
        "conditional_frozen_v2_unique_scorer_unit_count": score_row.get("conditional_frozen_v2_unique_scorer_unit_count"),
        "runtime_slot_controller_v2_unique_scorer_unit_count": score_row.get("runtime_slot_controller_v2_unique_scorer_unit_count"),
        "guidance_hashes_equal_between_conditional_and_runtime": cond_guidance_hashes == runtime_guidance_hashes,
        "request_patch_sets_equal_between_conditional_and_runtime": cond_request_patch_hashes == runtime_request_patch_hashes,
        "runtime_slot_bind_repair_count": runtime_slot_bind,
        "runtime_slot_policy_hit_count": runtime.get("slot_policy_hit_count", 0),
        "runtime_marker_noop_count": runtime_marker_noop,
        "runtime_trace_artifact_count": runtime_trace_count,
        "runtime_existing_validator_repair_present_count": runtime.get("existing_validator_repair_present_count", 0),
        "runtime_provider_generated_valid_call_proxy_count": runtime.get("provider_generated_valid_call_proxy_count", 0),
        "cause_labels": cause_labels,
        "primary_assessment": primary_assessment,
        "safe_fields_only": True,
    }


def build() -> Dict[str, Any]:
    blockers: List[str] = []
    if not RUN_ROOT.exists():
        blockers.append("run_root_missing")
    score_rows = _score_rows_by_category()
    arm_category_rows: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    rows: List[Dict[str, Any]] = []
    for arm in ARMS:
        for category in CATEGORIES:
            summary = _aggregate_trace_summaries(_trace_paths(arm, category))
            summary.update({"arm": arm, "bfcl_category": category})
            if summary["trace_artifact_count"] == 0:
                blockers.append("trace_artifacts_missing:%s:%s" % (arm, category))
            rows.append(summary)
            arm_category_rows[category][arm] = summary
    category_causality = []
    for category in CATEGORIES:
        category_causality.append(_compare_category(arm_category_rows[category], category, score_rows.get(category, {})))
    total_slot_bind = sum(int(row.get("slot_bind_repair_count") or 0) for row in rows if row.get("arm") == "runtime_slot_controller_v2")
    total_runtime_noop = sum(int(row.get("runtime_marker_noop_count") or 0) for row in rows if row.get("arm") == "runtime_slot_controller_v2")
    total_runtime_traces = sum(int(row.get("trace_artifact_count") or 0) for row in rows if row.get("arm") == "runtime_slot_controller_v2")
    target = next((row for row in category_causality if row["bfcl_category"] == "multi_turn_miss_param"), {})
    binder_causality_confirmed = total_slot_bind > 0 and target.get("score_delta_vs_conditional_frozen_v2", 0) > 0
    if target.get("score_delta_vs_conditional_frozen_v2", 0) > 0 and total_slot_bind == 0:
        overall_assessment = "score_gain_real_but_binder_causality_not_confirmed"
    elif binder_causality_confirmed:
        overall_assessment = "score_gain_with_observed_binder_repair"
    else:
        overall_assessment = "no_confirmed_target_score_gain"
    result = _load_json(RESULT_PATH)
    payload = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_causality_audit",
        "schema_version": "abhe_v0_runtime_slot_controller_causality_audit_v0",
        "run_scope": "bounded_residual_dev_smoke_only",
        "selected_case_ids_hash": result.get("selected_case_ids_hash"),
        "audit_resolution": "sanitized_trace_hash_and_counter_level_plus_category_scorer_unit_summary",
        "binder_causality_confirmed": binder_causality_confirmed,
        "overall_assessment": overall_assessment,
        "target_category_assessment": target,
        "summary": {
            "runtime_trace_artifact_count": total_runtime_traces,
            "runtime_marker_noop_count": total_runtime_noop,
            "runtime_slot_bind_repair_count": total_slot_bind,
            "runtime_slot_policy_hit_count": sum(int(row.get("slot_policy_hit_count") or 0) for row in rows if row.get("arm") == "runtime_slot_controller_v2"),
            "runtime_existing_validator_repair_present_count": sum(int(row.get("existing_validator_repair_present_count") or 0) for row in rows if row.get("arm") == "runtime_slot_controller_v2"),
            "runtime_provider_generated_valid_call_proxy_count": sum(int(row.get("provider_generated_valid_call_proxy_count") or 0) for row in rows if row.get("arm") == "runtime_slot_controller_v2"),
            "target_score_delta_vs_conditional_frozen_v2": target.get("score_delta_vs_conditional_frozen_v2"),
            "strict_per_compact_case_paired_available": False,
            "strict_scorer_unit_paired_available": True,
        },
        "category_causality": category_causality,
        "trace_counter_rows": rows,
        "causal_interpretation": {
            "actual_slot_bind_repair": "not_supported" if total_slot_bind == 0 else "observed",
            "adapter_guidance_text_change": "not_supported_for_target" if target.get("guidance_hashes_equal_between_conditional_and_runtime") else "possible_guidance_difference_detected",
            "runtime_marker_or_validator_path_change": "plausible_unproven" if total_runtime_noop else "not_observed",
            "existing_validator_repair": "present_but_not_sufficient_for_direct_binder_claim",
            "provider_or_sampling_variability": "not_ruled_out_without_same_request_noop_replay",
            "scorer_unit_aggregation": "material_caveat_category_level_only",
        },
        "next_required_action": "run_no_provider_proxy_fixture_and_same_request_noop_replay_before_promoting_runtime_slot_controller_v2",
        "safe_fields_only": True,
        "raw_material_absent": True,
        "prompt_literal_committed": False,
        "argument_values_committed": False,
        "provider_payload_committed": False,
        "bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_evidence": False,
        "archive_updated": False,
        "blockers": blockers,
    }
    return payload


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    payload = build()
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True) if args.compact else json.dumps(payload, indent=2, sort_keys=True))
    return 1 if args.strict and payload.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
