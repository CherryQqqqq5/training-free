#!/usr/bin/env python3
"""Build sanitized trace telemetry for ABHE runtime slot-controller residual run."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

RUN_ROOT = Path("/tmp/abhe_v0_runtime_slot_controller_residual_dev_smoke")
OUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_sanitized_trace_audit.json")
ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
CATEGORIES = ["multi_turn_miss_param", "multi_turn_miss_func", "multi_turn_base", "multi_turn_long_context", "irrelevance", "live_irrelevance"]
SLOT_REPAIR_KIND = "abhe_runtime_slot_controller_v2_bind_required_slot"


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_hash_obj(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _tool_schema_required_map(snapshot: Dict[str, Any]) -> Dict[str, List[str]]:
    required_by_name: Dict[str, List[str]] = {}
    if not isinstance(snapshot, dict):
        return required_by_name
    for tool_name, schema in snapshot.items():
        if not isinstance(tool_name, str) or not isinstance(schema, dict):
            continue
        params = schema.get("parameters") if isinstance(schema.get("parameters"), dict) else {}
        required = params.get("required") if isinstance(params.get("required"), list) else []
        required_by_name[tool_name] = sorted(str(item) for item in required if str(item).strip())
    return required_by_name


def _tool_schema_keyset_hash(snapshot: Dict[str, Any]) -> str | None:
    required_by_name = _tool_schema_required_map(snapshot)
    if not required_by_name:
        return None
    safe_shape = {"tool_count": len(required_by_name), "required_arg_keyset_hashes": sorted(_stable_hash_obj(v) for v in required_by_name.values())}
    return _stable_hash_obj(safe_shape)


def _loads_args(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _extract_tool_calls(response: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    calls: List[Tuple[str, Dict[str, Any]]] = []
    choices = response.get("choices") if isinstance(response.get("choices"), list) else []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        tool_calls = message.get("tool_calls") if isinstance(message.get("tool_calls"), list) else []
        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            fn = call.get("function") if isinstance(call.get("function"), dict) else {}
            name = fn.get("name")
            if isinstance(name, str) and name:
                calls.append((name, _loads_args(fn.get("arguments"))))
    output = response.get("output") if isinstance(response.get("output"), list) else []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") in {"function_call", "tool_call"}:
            name = item.get("name")
            if isinstance(name, str) and name:
                calls.append((name, _loads_args(item.get("arguments"))))
    return calls


def _tool_call_observability(data: Dict[str, Any], response_key: str) -> Dict[str, Any]:
    snapshot = data.get("tool_schema_snapshot") if isinstance(data.get("tool_schema_snapshot"), dict) else {}
    required_by_name = _tool_schema_required_map(snapshot)
    response = data.get(response_key) if isinstance(data.get(response_key), dict) else {}
    calls = _extract_tool_calls(response)
    missing_total = 0
    tool_name_hashes: List[str] = []
    arg_keyset_hashes: List[str] = []
    for tool_name, args in calls:
        present_keys = sorted(str(key) for key in args.keys())
        required = required_by_name.get(tool_name, [])
        missing_total += len([key for key in required if key not in args])
        tool_name_hashes.append(_stable_hash_obj(tool_name))
        arg_keyset_hashes.append(_stable_hash_obj(present_keys))
    return {
        "tool_call_count": len(calls),
        "tool_call_present": bool(calls),
        "tool_name_hashes": sorted(tool_name_hashes),
        "argument_keyset_hashes": sorted(arg_keyset_hashes),
        "missing_required_arg_count": missing_total,
    }


def _sample(values: Iterable[str], limit: int = 3) -> List[str]:
    return sorted(set(values))[:limit]


def build() -> Dict[str, Any]:
    rows = []
    summary: Dict[str, Any] = {}
    blockers = []
    if not RUN_ROOT.exists():
        blockers.append("run_root_missing")
    for arm in ARMS:
        arm_counts = Counter()
        arm_categories: Dict[str, Any] = {}
        for category in CATEGORIES:
            trace_dir = RUN_ROOT / arm / category / "traces"
            paths = sorted(trace_dir.glob("*.json")) if trace_dir.exists() else []
            repair_count = 0
            policy_hit_count = 0
            controller_enabled_patch_count = 0
            issue_kinds = Counter()
            repair_kinds = Counter()
            existing_validator_repair_kinds = Counter()
            sample_hashes = []
            tool_schema_keyset_hashes: List[str] = []
            request_patch_set_hashes: List[str] = []
            adapter_projection_hashes: List[str] = []
            tool_name_hashes: List[str] = []
            arg_keyset_hashes: List[str] = []
            final_arg_keyset_hashes: List[str] = []
            tool_call_present_count = 0
            no_tool_final_response_count = 0
            provider_generated_valid_call_proxy_count = 0
            missing_required_before_repair_total = 0
            argument_keyset_changed_by_repair_count = 0
            controller_not_applicable_reasons = Counter()
            for path in paths:
                data = _load(path)
                validation = data.get("validation") if isinstance(data.get("validation"), dict) else {}
                repairs = validation.get("repairs") if isinstance(validation.get("repairs"), list) else []
                repair_kinds.update(str(item.get("kind")) for item in repairs if isinstance(item, dict) and item.get("kind"))
                existing_validator_repair_kinds.update(str(item.get("kind")) for item in repairs if isinstance(item, dict) and item.get("kind") and item.get("kind") != SLOT_REPAIR_KIND)
                trace_bind_repair_count = sum(1 for item in repairs if isinstance(item, dict) and item.get("kind") == SLOT_REPAIR_KIND)
                repair_count += trace_bind_repair_count
                policy_hits = validation.get("policy_hits") if isinstance(validation.get("policy_hits"), list) else []
                request_patches = validation.get("request_patches") if isinstance(validation.get("request_patches"), list) else []
                if "abhe_runtime_slot_controller_v2" in policy_hits:
                    policy_hit_count += 1
                if "abhe_v0_runtime_slot_controller_v2:enabled" in request_patches:
                    controller_enabled_patch_count += 1
                issue_kinds.update(str(item.get("kind")) for item in (validation.get("issues") or []) if isinstance(item, dict) and item.get("kind"))
                schema_hash = _tool_schema_keyset_hash(data.get("tool_schema_snapshot") if isinstance(data.get("tool_schema_snapshot"), dict) else {})
                if schema_hash:
                    tool_schema_keyset_hashes.append(schema_hash)
                request_patch_set_hashes.append(_stable_hash_obj(sorted(str(item) for item in request_patches)))
                adapter_projection_hashes.append(_stable_hash_obj([str(item) for item in request_patches if str(item).startswith("abhe_v0_") or str(item).startswith("prompt_injector:")]))
                raw_obs = _tool_call_observability(data, "raw_response")
                final_obs = _tool_call_observability(data, "final_chat_response")
                tool_name_hashes.extend(raw_obs["tool_name_hashes"])
                arg_keyset_hashes.extend(raw_obs["argument_keyset_hashes"])
                final_arg_keyset_hashes.extend(final_obs["argument_keyset_hashes"])
                if raw_obs["tool_call_present"]:
                    tool_call_present_count += 1
                else:
                    no_tool_final_response_count += 1
                missing_required_before_repair_total += int(raw_obs["missing_required_arg_count"])
                if raw_obs["tool_call_present"] and raw_obs["missing_required_arg_count"] == 0:
                    provider_generated_valid_call_proxy_count += 1
                if raw_obs["argument_keyset_hashes"] != final_obs["argument_keyset_hashes"]:
                    argument_keyset_changed_by_repair_count += 1
                if trace_bind_repair_count:
                    controller_not_applicable_reasons["applicable_bind_repair_observed"] += 1
                elif not raw_obs["tool_call_present"]:
                    controller_not_applicable_reasons["no_tool_call_final_response"] += 1
                elif raw_obs["missing_required_arg_count"] == 0:
                    controller_not_applicable_reasons["no_missing_required_arg"] += 1
                elif "abhe_runtime_slot_controller_v2" in policy_hits or "abhe_v0_runtime_slot_controller_v2:enabled" in request_patches:
                    controller_not_applicable_reasons["missing_required_arg_unresolved_or_ambiguous"] += 1
                else:
                    controller_not_applicable_reasons["controller_not_enabled_or_not_applicable"] += 1
                if len(sample_hashes) < 3:
                    sample_hashes.append(_hash(path))
            row = {
                "arm": arm,
                "bfcl_category": category,
                "sampled_artifact_count": len(paths),
                "slot_controller_policy_hit_count": policy_hit_count,
                "slot_controller_enabled_patch_count": controller_enabled_patch_count,
                "slot_bind_repair_count": repair_count,
                "pre_generation_required_arg_ledger_available_count": len([item for item in tool_schema_keyset_hashes if item]),
                "pre_generation_tool_schema_keyset_hash_sample": _sample(tool_schema_keyset_hashes),
                "pre_generation_request_patch_set_hash_sample": _sample(request_patch_set_hashes),
                "pre_generation_adapter_projection_hash_sample": _sample(adapter_projection_hashes),
                "post_decode_tool_call_present_count": tool_call_present_count,
                "post_decode_tool_name_hash_sample": _sample(tool_name_hashes),
                "post_decode_argument_keyset_hash_sample": _sample(arg_keyset_hashes),
                "post_decode_missing_required_arg_count_before_repair": missing_required_before_repair_total,
                "post_decode_provider_generated_valid_call_proxy_count": provider_generated_valid_call_proxy_count,
                "post_decode_no_tool_call_final_response_count": no_tool_final_response_count,
                "post_response_existing_validator_repair_kind_counts": dict(sorted(existing_validator_repair_kinds.items())),
                "post_response_runtime_slot_policy_hit_count": policy_hit_count,
                "post_response_runtime_slot_bind_repair_count": repair_count,
                "post_response_controller_not_applicable_reason_counts": dict(sorted(controller_not_applicable_reasons.items())),
                "post_response_argument_keyset_changed_by_repair_count": argument_keyset_changed_by_repair_count,
                "post_response_final_argument_keyset_hash_sample": _sample(final_arg_keyset_hashes),
                "issue_kind_counts": dict(sorted(issue_kinds.items())),
                "repair_kind_counts": dict(sorted(repair_kinds.items())),
                "sample_artifact_hashes": sample_hashes,
                "safe_fields_only": True,
                "raw_material_absent": True,
                "argument_values_committed": False,
                "provider_payload_committed": False,
                "scorer_diff_committed": False,
            }
            rows.append(row)
            arm_counts["sampled_artifact_count"] += len(paths)
            arm_counts["slot_controller_policy_hit_count"] += policy_hit_count
            arm_counts["slot_controller_enabled_patch_count"] += controller_enabled_patch_count
            arm_counts["slot_bind_repair_count"] += repair_count
            arm_counts["post_decode_missing_required_arg_count_before_repair"] += missing_required_before_repair_total
            arm_counts["post_decode_provider_generated_valid_call_proxy_count"] += provider_generated_valid_call_proxy_count
            arm_counts["post_response_argument_keyset_changed_by_repair_count"] += argument_keyset_changed_by_repair_count
            arm_categories[category] = {
                "sampled_artifact_count": len(paths),
                "slot_bind_repair_count": repair_count,
                "slot_controller_policy_hit_count": policy_hit_count,
                "slot_controller_enabled_patch_count": controller_enabled_patch_count,
                "post_decode_missing_required_arg_count_before_repair": missing_required_before_repair_total,
                "post_decode_provider_generated_valid_call_proxy_count": provider_generated_valid_call_proxy_count,
                "post_response_argument_keyset_changed_by_repair_count": argument_keyset_changed_by_repair_count,
            }
        summary[arm] = dict(arm_counts)
        summary[arm]["category_summary"] = arm_categories
    return {
        "artifact_kind": "abhe_v0_runtime_slot_controller_sanitized_trace_audit",
        "schema_version": "abhe_v0_runtime_slot_controller_sanitized_trace_audit_v1",
        "run_scope": "bounded_residual_dev_smoke_only",
        "safe_fields_only": True,
        "rows": rows,
        "summary": summary,
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
