#!/usr/bin/env python3
"""Run no-provider runtime slot-controller path fixture and same-request replay."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Tuple

import yaml

from grc.runtime.engine import RuleEngine
from grc.runtime.proxy import _apply_abhe_v0_adapter_guidance
from grc.runtime.slot_controller import ABHE_RUNTIME_SLOT_CONTROLLER_PATCH
from grc.utils.jsonfix import parse_loose_json

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
OUT = ROOT / "abhe_v0_runtime_slot_controller_path_replay.json"
RUN_ROOT = Path("/tmp/abhe_v0_runtime_slot_controller_residual_dev_smoke")
ADAPTER = ROOT / "abhe_v0_runtime_slot_controller_candidate_adapter_runtime_slot_controller_v2.json"
RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")
TARGET_CATEGORY = "multi_turn_miss_param"
SLOT_REPAIR_KIND = "abhe_runtime_slot_controller_v2_bind_required_slot"
SLOT_POLICY_HIT = "abhe_runtime_slot_controller_v2"


def _load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _load_runtime_policy() -> Dict[str, Any]:
    if not RUNTIME_CONFIG.exists():
        return {}
    data = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8")) or {}
    policy = data.get("runtime_policy") if isinstance(data, dict) else {}
    return policy if isinstance(policy, dict) else {}


def _engine() -> RuleEngine:
    return RuleEngine(".", runtime_policy=_load_runtime_policy())


def _sha_json(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


@contextlib.contextmanager
def _patched_env(values: Dict[str, str]) -> Iterator[None]:
    old = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _tool_schema() -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "book_table",
            "description": "synthetic no-provider fixture tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                    "party_size": {"type": "integer"},
                },
                "required": ["city", "date", "party_size"],
            },
        },
    }


def _fixture_request() -> Dict[str, Any]:
    return {
        "model": "gpt-4.1",
        "messages": [
            {"role": "tool", "tool_call_id": "prior_lookup", "content": json.dumps({"party_size": 2})},
            {"role": "user", "content": "synthetic slot-binding fixture"},
        ],
        "tools": [_tool_schema()],
        "tool_choice": "auto",
    }


def _fixture_response() -> Dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_fixture",
                            "type": "function",
                            "function": {
                                "name": "book_table",
                                "arguments": json.dumps({"city": "x", "date": "y"}),
                            },
                        }
                    ],
                }
            }
        ]
    }


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _repair_kinds(repairs: Iterable[Any], validation: Any) -> List[str]:
    returned_kinds: List[str] = []
    for item in repairs:
        if isinstance(item, dict) and item.get("kind"):
            returned_kinds.append(str(item["kind"]))
    if returned_kinds:
        return returned_kinds
    kinds: List[str] = []
    val = validation.model_dump(mode="json") if hasattr(validation, "model_dump") else (validation if isinstance(validation, dict) else {})
    for item in _safe_list(val.get("repairs")):
        if isinstance(item, dict) and item.get("kind"):
            kinds.append(str(item["kind"]))
    if kinds:
        return kinds
    for item in _safe_list(val.get("repair_kinds")):
        if isinstance(item, str):
            kinds.append(item)
    return kinds


def _issue_kinds(validation: Any) -> List[str]:
    val = validation.model_dump(mode="json") if hasattr(validation, "model_dump") else (validation if isinstance(validation, dict) else {})
    return [str(item.get("kind")) for item in _safe_list(val.get("issues")) if isinstance(item, dict) and item.get("kind")]


def _policy_hits(validation: Any) -> List[str]:
    val = validation.model_dump(mode="json") if hasattr(validation, "model_dump") else (validation if isinstance(validation, dict) else {})
    return [str(item) for item in _safe_list(val.get("policy_hits"))]


def _request_patches(validation: Any, fallback: List[str]) -> List[str]:
    val = validation.model_dump(mode="json") if hasattr(validation, "model_dump") else (validation if isinstance(validation, dict) else {})
    patches = [str(item) for item in _safe_list(val.get("request_patches"))]
    return patches or list(fallback)


def _chat_tool_calls(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    for choice in _safe_list(payload.get("choices")):
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        for call in _safe_list(message.get("tool_calls")):
            if isinstance(call, dict):
                calls.append(call)
    return calls


def _argument_keyset_counts(payload: Dict[str, Any]) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for call in _chat_tool_calls(payload):
        function = call.get("function") if isinstance(call.get("function"), dict) else {}
        args = function.get("arguments")
        parsed: Any = None
        if isinstance(args, str):
            try:
                parsed = parse_loose_json(args)
            except Exception:
                parsed = None
        elif isinstance(args, dict):
            parsed = args
        if isinstance(parsed, dict):
            counts[_sha_json(sorted(str(key) for key in parsed.keys()))] += 1
        else:
            counts["unparsed_or_absent"] += 1
    return dict(sorted(counts.items()))


def _tool_call_name_hash_counts(payload: Dict[str, Any]) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for call in _chat_tool_calls(payload):
        function = call.get("function") if isinstance(call.get("function"), dict) else {}
        name = function.get("name")
        if isinstance(name, str) and name:
            counts[_sha_json(name)] += 1
    return dict(sorted(counts.items()))


def _run_apply_response(request_json: Dict[str, Any], response_json: Dict[str, Any], patches: List[str]) -> Dict[str, Any]:
    final_json, repairs, validation = _engine().apply_response(request_json, response_json, request_patches=patches)
    repair_kinds = _repair_kinds(repairs, validation)
    issue_kinds = _issue_kinds(validation)
    policy_hits = _policy_hits(validation)
    return {
        "slot_bind_repair_count": repair_kinds.count(SLOT_REPAIR_KIND),
        "slot_policy_hit_count": policy_hits.count(SLOT_POLICY_HIT),
        "repair_kind_counts": dict(sorted(Counter(repair_kinds).items())),
        "issue_kind_counts": dict(sorted(Counter(issue_kinds).items())),
        "argument_keyset_hash_counts": _argument_keyset_counts(final_json),
        "tool_call_name_hash_counts": _tool_call_name_hash_counts(final_json),
        "tool_call_count": len(_chat_tool_calls(final_json)),
        "request_patch_set_hash": _sha_json(sorted(set(patches))),
        "raw_material_absent": True,
        "argument_values_committed": False,
    }


def build_fixture_report() -> Dict[str, Any]:
    with _patched_env(
        {
            "ABHE_V0_RUNTIME_CANDIDATE_ADAPTER": str(ADAPTER),
            "ABHE_V0_RUNTIME_ACTIVATION_CATEGORIES": TARGET_CATEGORY,
            "ABHE_V0_RUNTIME_ACTIVATION_ENTRY": "",
        }
    ):
        adapter_req, adapter_patches = _apply_abhe_v0_adapter_guidance(_fixture_request())
    req_json, engine_patches = _engine().apply_request(adapter_req)
    patches = list(engine_patches) + list(adapter_patches)
    replay = _run_apply_response(req_json, _fixture_response(), patches)
    request_patch_classes = {
        "adapter_guidance_present": any(patch.startswith("abhe_v0_runtime_candidate_adapter_guidance:") for patch in patches),
        "runtime_slot_controller_marker_present": ABHE_RUNTIME_SLOT_CONTROLLER_PATCH in patches,
        "prompt_injector_present": any(patch.startswith("prompt_injector:") for patch in patches),
    }
    return {
        "fixture_id": "synthetic_prior_tool_observation_missing_required_slot_v0",
        "proxy_fixture_runtime_path_confirmed": replay["slot_bind_repair_count"] > 0 and replay["slot_policy_hit_count"] > 0,
        "slot_bind_repair_count": replay["slot_bind_repair_count"],
        "slot_policy_hit_count": replay["slot_policy_hit_count"],
        "request_patch_classes": request_patch_classes,
        "request_patch_count": len(patches),
        "repair_kind_counts": replay["repair_kind_counts"],
        "issue_kind_counts": replay["issue_kind_counts"],
        "argument_keyset_hash_counts": replay["argument_keyset_hash_counts"],
        "tool_call_name_hash_counts": replay["tool_call_name_hash_counts"],
        "raw_material_absent": True,
        "argument_values_committed": False,
        "provider_payload_committed": False,
        "scorer_diff_committed": False,
    }


def _target_trace_paths() -> List[Path]:
    return sorted((RUN_ROOT / "runtime_slot_controller_v2" / TARGET_CATEGORY / "traces").glob("*.json"))


def _strip_runtime_patch(patches: List[str]) -> List[str]:
    return [patch for patch in patches if patch != ABHE_RUNTIME_SLOT_CONTROLLER_PATCH]


def build_same_request_replay() -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    changed_keyset = 0
    changed_repair = 0
    changed_issue = 0
    runtime_slot_bind_total = 0
    runtime_policy_hit_total = 0
    control_slot_bind_total = 0
    for path in _target_trace_paths():
        trace = _load_json(path)
        request_json = trace.get("request") if isinstance(trace.get("request"), dict) else {}
        response_json = trace.get("raw_response") if isinstance(trace.get("raw_response"), dict) else {}
        validation = trace.get("validation") if isinstance(trace.get("validation"), dict) else {}
        observed_patches = [str(item) for item in _safe_list(validation.get("request_patches"))]
        runtime_patches = sorted(set(observed_patches + [ABHE_RUNTIME_SLOT_CONTROLLER_PATCH]))
        control_patches = _strip_runtime_patch(runtime_patches)
        control = _run_apply_response(request_json, response_json, control_patches)
        runtime = _run_apply_response(request_json, response_json, runtime_patches)
        keyset_changed = control["argument_keyset_hash_counts"] != runtime["argument_keyset_hash_counts"]
        repair_changed = control["repair_kind_counts"] != runtime["repair_kind_counts"]
        issue_changed = control["issue_kind_counts"] != runtime["issue_kind_counts"]
        changed_keyset += int(keyset_changed)
        changed_repair += int(repair_changed)
        changed_issue += int(issue_changed)
        runtime_slot_bind_total += runtime["slot_bind_repair_count"]
        runtime_policy_hit_total += runtime["slot_policy_hit_count"]
        control_slot_bind_total += control["slot_bind_repair_count"]
        rows.append(
            {
                "trace_artifact_hash": _sha_file(path),
                "bfcl_category": TARGET_CATEGORY,
                "control_slot_bind_repair_count": control["slot_bind_repair_count"],
                "runtime_slot_bind_repair_count": runtime["slot_bind_repair_count"],
                "control_slot_policy_hit_count": control["slot_policy_hit_count"],
                "runtime_slot_policy_hit_count": runtime["slot_policy_hit_count"],
                "argument_keyset_changed_by_runtime_marker": keyset_changed,
                "repair_kinds_changed_by_runtime_marker": repair_changed,
                "issue_kinds_changed_by_runtime_marker": issue_changed,
                "runtime_marker_noop_for_slot_binding": runtime["slot_bind_repair_count"] == 0,
                "control_argument_keyset_hash_counts": control["argument_keyset_hash_counts"],
                "runtime_argument_keyset_hash_counts": runtime["argument_keyset_hash_counts"],
                "control_repair_kind_counts": control["repair_kind_counts"],
                "runtime_repair_kind_counts": runtime["repair_kind_counts"],
                "control_issue_kind_counts": control["issue_kind_counts"],
                "runtime_issue_kind_counts": runtime["issue_kind_counts"],
                "safe_fields_only": True,
                "raw_material_absent": True,
                "argument_values_committed": False,
            }
        )
    trace_count = len(rows)
    return {
        "same_request_replay_trace_count": trace_count,
        "same_request_noop_replay_confirmed": trace_count > 0 and runtime_slot_bind_total == 0 and changed_keyset == 0,
        "runtime_slot_bind_repair_count": runtime_slot_bind_total,
        "runtime_slot_policy_hit_count": runtime_policy_hit_total,
        "control_slot_bind_repair_count": control_slot_bind_total,
        "argument_keyset_changed_count": changed_keyset,
        "repair_kinds_changed_count": changed_repair,
        "issue_kinds_changed_count": changed_issue,
        "rows": rows,
        "safe_fields_only": True,
        "raw_material_absent": True,
        "argument_values_committed": False,
    }


def build() -> Dict[str, Any]:
    blockers: List[str] = []
    if not ADAPTER.exists():
        blockers.append("runtime_adapter_missing")
    if not RUN_ROOT.exists():
        blockers.append("residual_run_root_missing")
    fixture = build_fixture_report() if not blockers else {}
    same_request = build_same_request_replay() if not blockers else {}
    if fixture and fixture.get("proxy_fixture_runtime_path_confirmed") is not True:
        blockers.append("proxy_fixture_runtime_path_not_confirmed")
    if same_request and same_request.get("same_request_noop_replay_confirmed") is not True:
        blockers.append("same_request_noop_replay_not_confirmed")
    return {
        "artifact_kind": "abhe_v0_runtime_slot_controller_path_replay",
        "schema_version": "abhe_v0_runtime_slot_controller_path_replay_v0",
        "run_scope": "no_provider_proxy_fixture_and_same_request_noop_replay_only",
        "no_provider": True,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "provider_calls_made": False,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "proxy_fixture": fixture,
        "same_request_replay": same_request,
        "summary": {
            "proxy_fixture_runtime_path_confirmed": fixture.get("proxy_fixture_runtime_path_confirmed") if fixture else False,
            "proxy_fixture_slot_bind_repair_count": fixture.get("slot_bind_repair_count", 0) if fixture else 0,
            "same_request_noop_replay_confirmed": same_request.get("same_request_noop_replay_confirmed") if same_request else False,
            "same_request_runtime_slot_bind_repair_count": same_request.get("runtime_slot_bind_repair_count", 0) if same_request else 0,
            "same_request_runtime_slot_policy_hit_count": same_request.get("runtime_slot_policy_hit_count", 0) if same_request else 0,
            "same_request_argument_keyset_changed_count": same_request.get("argument_keyset_changed_count", 0) if same_request else 0,
        },
        "interpretation": {
            "runtime_path_can_bind_in_no_provider_fixture": fixture.get("proxy_fixture_runtime_path_confirmed") if fixture else False,
            "observed_bfcl_target_traces_remain_noop_for_slot_binding": same_request.get("same_request_noop_replay_confirmed") if same_request else False,
            "mechanism_promotion_allowed": False,
            "next_required_action": "instrument_why_target_bfcl_requests_do_not_present_bindable_missing_slots_before_next_bfcl_run",
        },
        "safe_fields_only": True,
        "raw_material_absent": True,
        "prompt_literal_committed": False,
        "argument_values_committed": False,
        "provider_payload_committed": False,
        "bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
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
