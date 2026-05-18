#!/usr/bin/env python3
"""Build a compact bindability audit for ABHE runtime slot-controller target traces."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from grc.runtime.slot_controller import ABHE_RUNTIME_SLOT_CONTROLLER_PATCH
from grc.utils.jsonfix import parse_loose_json

RUN_ROOT = Path("/tmp/abhe_v0_runtime_slot_controller_residual_dev_smoke")
OUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_bindability_audit_v1.json")
TARGET_ARM = "runtime_slot_controller_v2"
TARGET_CATEGORY = "multi_turn_miss_param"
SLOT_POLICY_HIT = "abhe_runtime_slot_controller_v2"
SLOT_BIND_REPAIR_KIND = "abhe_runtime_slot_controller_v2_bind_required_slot"


def _load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha_text(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))


def _sha_json(value: Any) -> str:
    return _sha_text(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def _schema_required(schema: Dict[str, Any]) -> List[str]:
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    return [str(item) for item in required if isinstance(item, str) and item]


def _schema_types(schema: Dict[str, Any]) -> Dict[str, str]:
    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    out: Dict[str, str] = {}
    for key, meta in props.items():
        if isinstance(key, str) and isinstance(meta, dict):
            out[key] = str(meta.get("type") or "unknown")
    return out


def _type_compatible(value: Any, expected_type: str | None) -> bool:
    if value is None:
        return False
    if not expected_type or expected_type == "unknown":
        return True
    if expected_type == "string":
        return isinstance(value, str) and bool(value.strip())
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    return True


def _parse_args(value: Any) -> Tuple[Dict[str, Any] | None, str]:
    if isinstance(value, dict):
        return dict(value), "parsed_object"
    if isinstance(value, str):
        try:
            parsed = parse_loose_json(value)
        except Exception:
            return None, "invalid_or_unparsed_args"
        if isinstance(parsed, dict):
            return dict(parsed), "parsed_object"
        return None, "non_object_args"
    return None, "args_absent_or_unknown_type"


def _parse_jsonlike(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        return json.loads(stripped)
    except Exception:
        try:
            return parse_loose_json(stripped)
        except Exception:
            return None


def _walk_key_values(value: Any, slot: str) -> Iterable[Any]:
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, child in item.items():
                if key == slot:
                    yield child
                if isinstance(child, (dict, list)):
                    stack.append(child)
        elif isinstance(item, list):
            stack.extend(child for child in item if isinstance(child, (dict, list)))


def _candidate_sources_from_request(request_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for message in _safe_list(request_json.get("messages")):
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role == "assistant":
            for call in _safe_list(message.get("tool_calls")):
                fn = _safe_dict(call.get("function")) if isinstance(call, dict) else {}
                args, status = _parse_args(fn.get("arguments"))
                if args and status == "parsed_object":
                    sources.append({"source_type": "prior_assistant_tool_call", "values": args})
        elif role == "tool":
            parsed = _parse_jsonlike(message.get("content"))
            if parsed is not None:
                sources.append({"source_type": "prior_tool_observation", "values": parsed})
    return sources


def _compatible_source_count(slot: str, expected_type: str | None, sources: List[Dict[str, Any]]) -> Tuple[int, Counter]:
    seen: set[str] = set()
    by_source: Counter = Counter()
    count = 0
    for source in sources:
        source_type = str(source.get("source_type") or "unknown")
        for value in _walk_key_values(source.get("values"), slot):
            if not _type_compatible(value, expected_type):
                continue
            marker = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            if marker in seen:
                continue
            seen.add(marker)
            by_source[source_type] += 1
            count += 1
    return count, by_source


def _chat_tool_calls(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    for choice in _safe_list(payload.get("choices")):
        message = _safe_dict(choice.get("message")) if isinstance(choice, dict) else {}
        for call in _safe_list(message.get("tool_calls")):
            if isinstance(call, dict):
                calls.append(call)
    return calls


def _tool_schema_from_trace(trace: Dict[str, Any], name: str) -> Dict[str, Any]:
    snapshot = _safe_dict(trace.get("tool_schema_snapshot"))
    schema = snapshot.get(name)
    if isinstance(schema, dict):
        if isinstance(schema.get("parameters"), dict):
            return schema["parameters"]
        return schema
    request = _safe_dict(trace.get("request"))
    for tool in _safe_list(request.get("tools")):
        if not isinstance(tool, dict):
            continue
        fn = _safe_dict(tool.get("function"))
        if fn.get("name") == name and isinstance(fn.get("parameters"), dict):
            return fn["parameters"]
    return {}


def _validation(trace: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(trace.get("validation"))


def _repair_kinds(trace: Dict[str, Any]) -> List[str]:
    kinds: List[str] = []
    validation = _validation(trace)
    for repair in _safe_list(validation.get("repairs")):
        if isinstance(repair, dict) and repair.get("kind"):
            kinds.append(str(repair["kind"]))
    for kind in _safe_list(validation.get("repair_kinds")):
        if isinstance(kind, str):
            kinds.append(kind)
    for repair in _safe_list(trace.get("repairs")):
        if isinstance(repair, dict) and repair.get("kind"):
            kinds.append(str(repair["kind"]))
    return kinds


def _issue_kinds(trace: Dict[str, Any]) -> List[str]:
    return [str(item.get("kind")) for item in _safe_list(_validation(trace).get("issues")) if isinstance(item, dict) and item.get("kind")]


def _response_shape_kinds(trace: Dict[str, Any]) -> List[str]:
    return [str(item.get("kind")) for item in _safe_list(_validation(trace).get("response_shapes")) if isinstance(item, dict) and item.get("kind")]


def _keyset_hash(args: Dict[str, Any]) -> str:
    return _sha_json(sorted(str(key) for key in args.keys()))


def _source_type_counts(sources: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(str(source.get("source_type") or "unknown") for source in sources)
    return dict(sorted(counts.items()))


def _analyze_call(trace: Dict[str, Any], call: Dict[str, Any], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    fn = _safe_dict(call.get("function"))
    name = fn.get("name") if isinstance(fn.get("name"), str) else ""
    args, parse_status = _parse_args(fn.get("arguments"))
    if not name:
        return {"bindability_reason": "missing_tool_name", "tool_name_hash": None}
    schema = _tool_schema_from_trace(trace, name)
    if not schema:
        return {"bindability_reason": "unknown_tool_schema", "tool_name_hash": _sha_text(name)}
    if args is None:
        return {"bindability_reason": parse_status, "tool_name_hash": _sha_text(name)}
    required = _schema_required(schema)
    types = _schema_types(schema)
    missing = [slot for slot in required if slot not in args or not _type_compatible(args.get(slot), types.get(slot))]
    compatible_source_counts = Counter()
    compatible_source_type_counts = Counter()
    missing_source_state_counts = Counter()
    bindable_missing_slot_count = 0
    ambiguous_missing_slot_count = 0
    missing_without_source_count = 0
    for slot in missing:
        count, by_source = _compatible_source_count(slot, types.get(slot), sources)
        compatible_source_counts[str(count)] += 1
        compatible_source_type_counts.update(by_source)
        if count == 1:
            bindable_missing_slot_count += 1
            missing_source_state_counts["exactly_one_compatible_prior_source"] += 1
        elif count == 0:
            missing_without_source_count += 1
            missing_source_state_counts["no_compatible_prior_source"] += 1
        else:
            ambiguous_missing_slot_count += 1
            missing_source_state_counts["ambiguous_multiple_compatible_prior_sources"] += 1
    if not required:
        reason = "schema_has_no_required_args"
    elif not missing:
        reason = "no_missing_required_arg"
    elif bindable_missing_slot_count:
        reason = "bindable_missing_required_arg_present"
    elif ambiguous_missing_slot_count:
        reason = "missing_required_arg_ambiguous_source"
    else:
        reason = "missing_required_arg_no_compatible_prior_source"
    return {
        "bindability_reason": reason,
        "tool_name_hash": _sha_text(name),
        "required_arg_count": len(required),
        "required_keyset_hash": _sha_json(sorted(required)),
        "argument_keyset_hash": _keyset_hash(args),
        "argument_key_count": len(args),
        "missing_required_arg_count_before": len(missing),
        "bindable_missing_slot_count": bindable_missing_slot_count,
        "ambiguous_missing_slot_count": ambiguous_missing_slot_count,
        "missing_without_source_count": missing_without_source_count,
        "compatible_source_count_distribution": dict(sorted(compatible_source_counts.items())),
        "compatible_source_type_counts": dict(sorted(compatible_source_type_counts.items())),
        "missing_source_state_counts": dict(sorted(missing_source_state_counts.items())),
    }


def _origin_label(trace: Dict[str, Any]) -> str:
    repairs = _repair_kinds(trace)
    if SLOT_BIND_REPAIR_KIND in repairs:
        return "runtime_slot_controller_repaired_call"
    if repairs:
        return "existing_validator_repaired_or_normalized_call"
    if _chat_tool_calls(_safe_dict(trace.get("final_chat_response"))) or _chat_tool_calls(_safe_dict(trace.get("raw_response"))):
        return "provider_generated_or_unrepaired_tool_call"
    return "no_tool_call_final_response"


def _row(path: Path, arm: str, category: str) -> Dict[str, Any]:
    trace = _load_json(path)
    validation = _validation(trace)
    request_patches = [str(item) for item in _safe_list(validation.get("request_patches"))]
    policy_hits = [str(item) for item in _safe_list(validation.get("policy_hits"))]
    sources = _candidate_sources_from_request(_safe_dict(trace.get("request")))
    raw_calls = _chat_tool_calls(_safe_dict(trace.get("raw_response")))
    final_calls = _chat_tool_calls(_safe_dict(trace.get("final_chat_response")))
    calls = raw_calls or final_calls
    call_rows = [_analyze_call(trace, call, sources) for call in calls]
    reason_counts = Counter(str(item.get("bindability_reason")) for item in call_rows)
    if not calls:
        reason_counts["no_tool_call"] += 1
    repair_kinds = _repair_kinds(trace)
    issue_kinds = _issue_kinds(trace)
    response_shape_kinds = _response_shape_kinds(trace)
    return {
        "trace_artifact_hash": _sha_bytes(path.read_bytes()),
        "arm": arm,
        "bfcl_category": category,
        "runtime_marker_present": ABHE_RUNTIME_SLOT_CONTROLLER_PATCH in request_patches,
        "slot_policy_hit": SLOT_POLICY_HIT in policy_hits,
        "slot_bind_repair_count": repair_kinds.count(SLOT_BIND_REPAIR_KIND),
        "final_call_origin": _origin_label(trace),
        "raw_tool_call_count": len(raw_calls),
        "final_tool_call_count": len(final_calls),
        "candidate_source_type_counts": _source_type_counts(sources),
        "bindability_reason_counts": dict(sorted(reason_counts.items())),
        "call_bindability_summaries": call_rows,
        "repair_kind_counts": dict(sorted(Counter(repair_kinds).items())),
        "issue_kind_counts": dict(sorted(Counter(issue_kinds).items())),
        "response_shape_kind_counts": dict(sorted(Counter(response_shape_kinds).items())),
        "request_patch_set_hash": _sha_json(sorted(set(request_patches))),
        "safe_fields_only": True,
        "raw_material_absent": True,
        "argument_values_committed": False,
        "provider_payload_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
    }


def _trace_paths(arm: str, category: str) -> List[Path]:
    trace_dir = RUN_ROOT / arm / category / "traces"
    return sorted(trace_dir.glob("*.json")) if trace_dir.exists() else []


def build() -> Dict[str, Any]:
    blockers: List[str] = []
    if not RUN_ROOT.exists():
        blockers.append("residual_run_root_missing")
    rows = [_row(path, TARGET_ARM, TARGET_CATEGORY) for path in _trace_paths(TARGET_ARM, TARGET_CATEGORY)] if not blockers else []
    if not rows and not blockers:
        blockers.append("target_trace_rows_missing")
    reason_counts = Counter()
    origin_counts = Counter()
    source_counts = Counter()
    repair_counts = Counter()
    issue_counts = Counter()
    response_shape_counts = Counter()
    runtime_marker_count = 0
    slot_policy_hit_count = 0
    slot_bind_repair_count = 0
    bindable_rows = 0
    no_tool_rows = 0
    no_missing_rows = 0
    unknown_schema_rows = 0
    invalid_args_rows = 0
    for row in rows:
        runtime_marker_count += int(row["runtime_marker_present"])
        slot_policy_hit_count += int(row["slot_policy_hit"])
        slot_bind_repair_count += int(row["slot_bind_repair_count"])
        origin_counts[row["final_call_origin"]] += 1
        source_counts.update(row["candidate_source_type_counts"])
        repair_counts.update(row["repair_kind_counts"])
        issue_counts.update(row["issue_kind_counts"])
        response_shape_counts.update(row["response_shape_kind_counts"])
        reason_counts.update(row["bindability_reason_counts"])
        if row["bindability_reason_counts"].get("bindable_missing_required_arg_present"):
            bindable_rows += 1
        if row["bindability_reason_counts"].get("no_tool_call"):
            no_tool_rows += 1
        if row["bindability_reason_counts"].get("no_missing_required_arg"):
            no_missing_rows += 1
        if row["bindability_reason_counts"].get("unknown_tool_schema"):
            unknown_schema_rows += 1
        if row["bindability_reason_counts"].get("invalid_or_unparsed_args") or row["bindability_reason_counts"].get("non_object_args"):
            invalid_args_rows += 1
    next_action = "design_pre_generation_or_post_decode_observability_for_provider_generated_valid_calls_before_bfcl_rerun"
    if bindable_rows:
        next_action = "debug_why_bindable_target_rows_do_not_emit_slot_policy_hits_before_bfcl_rerun"
    return {
        "artifact_kind": "abhe_v0_runtime_slot_controller_bindability_audit_v1",
        "schema_version": "abhe_v0_runtime_slot_controller_bindability_audit_v1",
        "run_scope": "compact_bindability_audit_only_no_provider_no_bfcl_no_scorer",
        "target_arm": TARGET_ARM,
        "target_category": TARGET_CATEGORY,
        "safe_fields_only": True,
        "raw_material_absent": True,
        "prompt_literal_committed": False,
        "argument_values_committed": False,
        "provider_payload_committed": False,
        "bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_evidence": False,
        "archive_updated": False,
        "summary": {
            "target_trace_row_count": len(rows),
            "runtime_marker_present_count": runtime_marker_count,
            "slot_policy_hit_count": slot_policy_hit_count,
            "slot_bind_repair_count": slot_bind_repair_count,
            "bindable_missing_required_arg_row_count": bindable_rows,
            "no_tool_call_row_count": no_tool_rows,
            "no_missing_required_arg_row_count": no_missing_rows,
            "unknown_tool_schema_row_count": unknown_schema_rows,
            "invalid_or_non_object_args_row_count": invalid_args_rows,
            "final_call_origin_counts": dict(sorted(origin_counts.items())),
            "bindability_reason_counts": dict(sorted(reason_counts.items())),
            "candidate_source_type_counts": dict(sorted(source_counts.items())),
            "repair_kind_counts": dict(sorted(repair_counts.items())),
            "issue_kind_counts": dict(sorted(issue_counts.items())),
            "response_shape_kind_counts": dict(sorted(response_shape_counts.items())),
        },
        "interpretation": {
            "direct_slot_binding_causality_supported": False,
            "target_rows_present_bindable_missing_slots": bindable_rows > 0,
            "target_rows_emit_slot_policy_hits": slot_policy_hit_count > 0,
            "mechanism_promotion_allowed": False,
            "next_required_action": next_action,
        },
        "rows": rows,
        "blockers": blockers,
    }


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
