#!/usr/bin/env python3
"""Check the pending BFCL Stage 1 smoke scope manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_stage1_smoke_scope_manifest.json")
SIGNED_SOURCE_CATEGORIES = [
    "agentic_web_search",
    "agentic_memory",
    "multi_turn_base",
    "multi_turn_long_context",
    "multi_turn_miss_param",
    "multi_turn_miss_func",
    "hallucination",
    "irrelevance",
]
KEY_LITERAL_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
ENDPOINT_LITERAL_FRAGMENTS = ("apicz", "boyuerichdata", "http://", "https://")
REQUIRED_FALSE = (
    "authorized",
    "smoke_execution_authorized",
    "provider_call_authorized",
    "bfcl_smoke_authorized",
    "bfcl_full_eval_authorized",
    "scorer_authorized",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "openrouter_allowed",
    "endpoint_value_committed",
    "api_key_value_committed",
)
REQUIRED_TRUE = (
    "smoke_scope_preparation_authorized",
    "candidate_specs_inert",
    "endpoint_env_only",
    "api_key_env_only",
)
FORBIDDEN_ID_KEYS = {"selected_case_ids", "test_case_ids", "case_ids", "ids"}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _walk(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(_walk(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk(child, path + (str(index),)))
    return items


def _leak_blockers(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        key = path[-1] if path else ""
        if key in FORBIDDEN_ID_KEYS and isinstance(value, list) and value:
            blockers.append(f"smoke_scope_raw_case_ids_committed:{'.'.join(path)}")
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if any(fragment in lowered for fragment in ENDPOINT_LITERAL_FRAGMENTS):
            blockers.append(f"smoke_scope_endpoint_literal_forbidden:{'.'.join(path)}")
        if KEY_LITERAL_PATTERN.search(value):
            blockers.append(f"smoke_scope_key_literal_forbidden:{'.'.join(path)}")
    return blockers


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = {
        "artifact_kind": "bfcl_stage1_smoke_scope_manifest",
        "approval_status": "pending",
        "provider_profile": "Chuangzhi/Novacode",
        "active_profile": "novacode",
        "route_model": "gpt-4.1",
        "precondition_commit": "37fa096ed0c9feac8bd24d22183c81ae6913cc04",
        "protocol_debug_artifact": "outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_provider_protocol_debug_compact.json",
        "scope_decision": "stop_before_smoke_execution_existing_runner_needs_reviewed_run_ids_manifest",
    }
    for key, value in expected.items():
        if data.get(key) != value:
            blockers.append(f"smoke_scope_{key}_invalid:{data.get(key)!r}")
    for key in REQUIRED_TRUE:
        if data.get(key) is not True:
            blockers.append(f"smoke_scope_{key}_not_true:{data.get(key)!r}")
    for key in REQUIRED_FALSE:
        if data.get(key) is not False:
            blockers.append(f"smoke_scope_{key}_not_false:{data.get(key)!r}")
    runner = data.get("existing_runner_scope_mechanism") if isinstance(data.get("existing_runner_scope_mechanism"), dict) else {}
    runner_expected = {
        "category_filter_supported": True,
        "run_ids_supported": True,
        "run_ids_env": "GRC_BFCL_USE_RUN_IDS=1",
        "run_ids_path_template": "<run_root>/bfcl/test_case_ids_to_generate.json",
        "case_count_limit_flag_supported": False,
        "reviewed_run_ids_manifest_present": False,
        "scope_enforceable_before_execution_now": False,
    }
    for key, value in runner_expected.items():
        if runner.get(key) != value:
            blockers.append(f"smoke_scope_runner_{key}_invalid:{runner.get(key)!r}")
    future = data.get("required_future_scope") if isinstance(data.get("required_future_scope"), dict) else {}
    if future.get("max_total_cases") != 8:
        blockers.append(f"smoke_scope_max_total_cases_invalid:{future.get('max_total_cases')!r}")
    if future.get("per_category_case_limit") != 1:
        blockers.append(f"smoke_scope_per_category_case_limit_invalid:{future.get('per_category_case_limit')!r}")
    if future.get("preferred_stage1_source_categories") != SIGNED_SOURCE_CATEGORIES:
        blockers.append("smoke_scope_source_categories_invalid")
    if future.get("bfcl_category_mapping_status") != "pending_reviewer_confirmation":
        blockers.append(f"smoke_scope_mapping_status_invalid:{future.get('bfcl_category_mapping_status')!r}")
    if future.get("case_selection_status") != "pending_reviewed_run_ids_materialization":
        blockers.append(f"smoke_scope_case_selection_status_invalid:{future.get('case_selection_status')!r}")
    if future.get("selected_case_ids_committed") is not False:
        blockers.append(f"smoke_scope_selected_case_ids_committed_not_false:{future.get('selected_case_ids_committed')!r}")
    if future.get("nonce_or_raw_case_mapping_committed") is not False:
        blockers.append(f"smoke_scope_nonce_or_raw_case_mapping_committed_not_false:{future.get('nonce_or_raw_case_mapping_committed')!r}")
    claims = data.get("claim_policy") if isinstance(data.get("claim_policy"), dict) else {}
    for key in ["not_full_default_baseline", "not_measurement_evidence", "not_performance_evidence", "not_3pp_claim", "not_huawei_readiness"]:
        if claims.get(key) is not True:
            blockers.append(f"smoke_scope_claim_{key}_not_true:{claims.get(key)!r}")
    blockers.extend(_leak_blockers(data))
    return blockers


def check(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    data = load_json(path)
    blockers = validate(data)
    future = data.get("required_future_scope") if isinstance(data.get("required_future_scope"), dict) else {}
    runner = data.get("existing_runner_scope_mechanism") if isinstance(data.get("existing_runner_scope_mechanism"), dict) else {}
    return {
        "report_scope": "bfcl_stage1_smoke_scope_manifest_check",
        "manifest_path": str(path),
        "approval_status": data.get("approval_status"),
        "route_model": data.get("route_model"),
        "max_total_cases": future.get("max_total_cases"),
        "scope_enforceable_before_execution_now": runner.get("scope_enforceable_before_execution_now"),
        "smoke_execution_authorized": data.get("smoke_execution_authorized"),
        "bfcl_stage1_smoke_scope_manifest_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "bfcl_stage1_smoke_scope_manifest_check",
            "manifest_path": str(args.manifest),
            "bfcl_stage1_smoke_scope_manifest_passed": False,
            "blockers": [f"smoke_scope_manifest_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_stage1_smoke_scope_manifest_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
