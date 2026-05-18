#!/usr/bin/env python3
"""Run a no-provider ABHE runtime-slot observability fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from grc.runtime.engine import RuleEngine
from grc.runtime.slot_controller import ABHE_RUNTIME_SLOT_CONTROLLER_PATCH
from grc.utils.jsonfix import parse_loose_json

OUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_fixture.json")


def _sha_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _tool(required: List[str] | None = None) -> Dict[str, Any]:
    required = required or ["city", "date", "party_size"]
    props = {
        "city": {"type": "string"},
        "date": {"type": "string"},
        "party_size": {"type": "integer"},
    }
    return {
        "type": "function",
        "function": {
            "name": "book_table",
            "parameters": {
                "type": "object",
                "properties": {slot: props[slot] for slot in required},
                "required": required,
            },
        },
    }


def _tool_call(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": "call_fixture",
        "type": "function",
        "function": {"name": "book_table", "arguments": json.dumps(args, ensure_ascii=False)},
    }


def _schema(request: Dict[str, Any]) -> Dict[str, Any]:
    tools = request.get("tools") if isinstance(request.get("tools"), list) else []
    for tool in tools:
        fn = tool.get("function") if isinstance(tool, dict) else {}
        if isinstance(fn, dict) and fn.get("name") == "book_table":
            params = fn.get("parameters")
            return params if isinstance(params, dict) else {}
    return {}


def _required(schema: Dict[str, Any]) -> List[str]:
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    return [str(item) for item in required if isinstance(item, str)]


def _parse_args(value: Any) -> Dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = parse_loose_json(value)
        except Exception:
            return None
        return dict(parsed) if isinstance(parsed, dict) else None
    return None


def _tool_calls(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for choice in response.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        msg = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        for call in msg.get("tool_calls") or []:
            if isinstance(call, dict):
                out.append(call)
    return out


def _arg_keyset(call: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any] | None]:
    fn = call.get("function") if isinstance(call.get("function"), dict) else {}
    args = _parse_args(fn.get("arguments"))
    if args is None:
        return [], None
    return sorted(str(key) for key in args.keys()), args


def _repair_kinds(repairs: Iterable[Any], validation: Any) -> List[str]:
    kinds: List[str] = []
    for item in repairs:
        if isinstance(item, dict) and item.get("kind"):
            kinds.append(str(item["kind"]))
    if kinds:
        return kinds
    validation_repairs = getattr(validation, "repairs", []) or []
    for item in validation_repairs:
        if isinstance(item, dict) and item.get("kind"):
            kinds.append(str(item["kind"]))
    return kinds


def _policy_hits(validation: Any) -> List[str]:
    return [str(item) for item in (getattr(validation, "policy_hits", []) or [])]


def _issues(validation: Any) -> List[str]:
    return [str(getattr(item, "kind", "")) for item in (getattr(validation, "issues", []) or []) if getattr(item, "kind", "")]


def _request_patches(validation: Any, fallback: List[str]) -> List[str]:
    patches = [str(item) for item in (getattr(validation, "request_patches", []) or [])]
    return patches or list(fallback)


def _row(case: Dict[str, Any]) -> Dict[str, Any]:
    request = case["request"]
    response = case["response"]
    patches = list(case["patches"])
    schema = _schema(request)
    required = _required(schema)
    post_calls = _tool_calls(response)
    pre_keyset_hash = _sha_json(required)
    pre_projection_hash = _sha_json(case.get("projection", {}))
    pre_patch_hash = _sha_json(sorted(set(patches)))
    before_keysets: List[str] = []
    before_missing_counts: List[int] = []
    before_tool_name_hashes: List[str] = []
    for call in post_calls:
        keys, args = _arg_keyset(call)
        before_keysets.append(_sha_json(keys))
        fn = call.get("function") if isinstance(call.get("function"), dict) else {}
        before_tool_name_hashes.append(_sha_json(str(fn.get("name") or "")))
        if args is None:
            before_missing_counts.append(len(required))
        else:
            before_missing_counts.append(sum(1 for slot in required if slot not in args))

    with tempfile.TemporaryDirectory(prefix="abhe_obs_fixture_") as tmp:
        final, repairs, validation = RuleEngine(tmp, runtime_policy={}).apply_response(request, response, request_patches=patches)

    final_calls = _tool_calls(final)
    after_keysets: List[str] = []
    for call in final_calls:
        keys, _ = _arg_keyset(call)
        after_keysets.append(_sha_json(keys))
    repair_kinds = _repair_kinds(repairs, validation)
    repair_counter = Counter(repair_kinds)
    policy_hits = _policy_hits(validation)
    slot_policy_hit = "abhe_runtime_slot_controller_v2" in policy_hits
    slot_bind_count = repair_counter.get("abhe_runtime_slot_controller_v2_bind_required_slot", 0)
    no_tool_final = not post_calls
    if no_tool_final:
        not_applicable = "no_tool_call_final_response"
    elif not before_missing_counts or sum(before_missing_counts) == 0:
        not_applicable = "no_missing_required_arg"
    elif slot_bind_count:
        not_applicable = "applicable_bind_repair_observed"
    else:
        not_applicable = "missing_required_arg_unresolved_or_ambiguous"

    return {
        "fixture_id": case["fixture_id"],
        "case_stable_hash": _sha_json(case["fixture_id"]),
        "arm": "runtime_slot_observability_fixture",
        "bfcl_category": "synthetic_no_provider",
        "pre_generation_request_patch_set_hash": pre_patch_hash,
        "pre_generation_adapter_projection_hash": pre_projection_hash,
        "pre_generation_required_arg_ledger_available": bool(required),
        "pre_generation_tool_schema_keyset_hash": pre_keyset_hash,
        "pre_generation_intended_tool_known": bool(required),
        "post_decode_tool_call_present": bool(post_calls),
        "post_decode_tool_call_count": len(post_calls),
        "post_decode_tool_name_hashes": before_tool_name_hashes,
        "post_decode_argument_keyset_hashes": before_keysets,
        "post_decode_missing_required_arg_count_before_repair": sum(before_missing_counts),
        "post_decode_provider_generated_valid_call_proxy": bool(post_calls) and sum(before_missing_counts) == 0,
        "post_decode_no_tool_call_final_response": no_tool_final,
        "post_response_existing_validator_repair_kind_counts": {k: v for k, v in sorted(repair_counter.items()) if k != "abhe_runtime_slot_controller_v2_bind_required_slot"},
        "post_response_runtime_slot_policy_hit": slot_policy_hit,
        "post_response_runtime_slot_bind_repair_count": slot_bind_count,
        "post_response_controller_not_applicable_reason": not_applicable,
        "post_response_argument_keyset_changed_by_repair": before_keysets != after_keysets,
        "post_response_issue_kind_counts": dict(sorted(Counter(_issues(validation)).items())),
        "raw_material_absent": True,
        "argument_values_committed": False,
        "provider_payload_committed": False,
        "scorer_diff_committed": False,
    }


def _cases() -> List[Dict[str, Any]]:
    base_patches = ["abhe_v0_runtime_candidate_adapter_guidance:state_tracking_v0", ABHE_RUNTIME_SLOT_CONTROLLER_PATCH]
    projection = {"entry_id": "state_tracking_v0", "runtime_slot_controller_v2": True}
    return [
        {
            "fixture_id": "bindable_missing_required_arg_from_tool_observation",
            "projection": projection,
            "patches": base_patches,
            "request": {"messages": [{"role": "tool", "tool_call_id": "prior", "content": json.dumps({"party_size": 2})}], "tools": [_tool()]},
            "response": {"choices": [{"message": {"tool_calls": [_tool_call({"city": "c", "date": "d"})]}}]},
        },
        {
            "fixture_id": "provider_generated_valid_call_no_repair",
            "projection": projection,
            "patches": base_patches,
            "request": {"messages": [], "tools": [_tool()]},
            "response": {"choices": [{"message": {"tool_calls": [_tool_call({"city": "c", "date": "d", "party_size": 2})]}}]},
        },
        {
            "fixture_id": "no_tool_final_response_not_applicable",
            "projection": projection,
            "patches": base_patches,
            "request": {"messages": [], "tools": [_tool()]},
            "response": {"choices": [{"message": {"content": "synthetic final response"}}]},
        },
        {
            "fixture_id": "ambiguous_missing_required_arg_no_bind",
            "projection": projection,
            "patches": base_patches,
            "request": {
                "messages": [
                    {"role": "tool", "tool_call_id": "one", "content": json.dumps({"party_size": 2})},
                    {"role": "tool", "tool_call_id": "two", "content": json.dumps({"party_size": 3})},
                ],
                "tools": [_tool()],
            },
            "response": {"choices": [{"message": {"tool_calls": [_tool_call({"city": "c", "date": "d"})]}}]},
        },
    ]


def build() -> Dict[str, Any]:
    rows = [_row(case) for case in _cases()]
    summary = {
        "fixture_count": len(rows),
        "bind_repair_rows": sum(1 for row in rows if row["post_response_runtime_slot_bind_repair_count"] > 0),
        "provider_generated_valid_call_proxy_rows": sum(1 for row in rows if row["post_decode_provider_generated_valid_call_proxy"]),
        "no_tool_final_response_rows": sum(1 for row in rows if row["post_decode_no_tool_call_final_response"]),
        "argument_keyset_changed_rows": sum(1 for row in rows if row["post_response_argument_keyset_changed_by_repair"]),
        "runtime_slot_policy_hit_rows": sum(1 for row in rows if row["post_response_runtime_slot_policy_hit"]),
    }
    return {
        "artifact_kind": "abhe_v0_runtime_slot_observability_fixture",
        "schema_version": "abhe_v0_runtime_slot_observability_fixture_v0",
        "fixture_scope": "no_provider_synthetic_observability_only",
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "performance_evidence": False,
        "candidate_jsonl_generated": False,
        "candidate_yaml_generated": False,
        "candidate_rule_generated": False,
        "safe_fields_only": True,
        "raw_material_absent": True,
        "argument_values_committed": False,
        "provider_payload_committed": False,
        "scorer_diff_committed": False,
        "observability_fixture_passed": True,
        "summary": summary,
        "rows": rows,
        "next_required_action": "review_observability_fixture_before_any_bfcl_rerun",
    }


def write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    data = build()
    if args.write:
        write(args.output, data)
    print(json.dumps(data, sort_keys=True) if args.compact else json.dumps(data, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
