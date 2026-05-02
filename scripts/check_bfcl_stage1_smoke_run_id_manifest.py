#!/usr/bin/env python3
"""Check the prepared BFCL Stage 1 smoke run-id manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (REPO_ROOT, SRC_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bfcl_eval.utils import load_dataset_entry  # noqa: E402

DEFAULT_MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_stage1_smoke_run_id_manifest.json")
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
SIGNED_CATEGORY_ORDER = [
    "web_search_base",
    "memory_kv",
    "multi_turn_base",
    "multi_turn_long_context",
    "multi_turn_miss_param",
    "multi_turn_miss_func",
    "irrelevance",
    "live_irrelevance",
]
SIGNED_RUN_IDS_BY_CATEGORY = {
    "web_search_base": ["web_search_base_0"],
    "memory_kv": ["memory_kv_0-customer-0"],
    "multi_turn_base": ["multi_turn_base_0"],
    "multi_turn_long_context": ["multi_turn_long_context_0"],
    "multi_turn_miss_param": ["multi_turn_miss_param_0"],
    "multi_turn_miss_func": ["multi_turn_miss_func_0"],
    "irrelevance": ["irrelevance_0"],
    "live_irrelevance": ["live_irrelevance_0-0-0"],
}
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
    "raw_prompt_committed",
    "raw_trace_committed",
    "provider_payload_committed",
    "provider_response_committed",
    "gold_reference_expected_committed",
    "scorer_diff_committed",
    "endpoint_or_key_committed",
    "source_nonce_mapping_committed",
)
REQUIRED_TRUE = (
    "smoke_run_id_manifest_prepared",
    "candidate_specs_inert",
    "endpoint_env_only",
    "api_key_env_only",
    "compact_only_output_policy",
)


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


def _secret_blockers(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if any(fragment in lowered for fragment in ENDPOINT_LITERAL_FRAGMENTS):
            blockers.append(f"smoke_run_id_endpoint_literal_forbidden:{'.'.join(path)}")
        if KEY_LITERAL_PATTERN.search(value):
            blockers.append(f"smoke_run_id_key_literal_forbidden:{'.'.join(path)}")
    return blockers


def _all_run_ids(data: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    by_category = data.get("run_ids_by_category") if isinstance(data.get("run_ids_by_category"), dict) else {}
    for values in by_category.values():
        if isinstance(values, list):
            ids.extend(str(value) for value in values)
    return ids


def _valid_ids_for_category(category: str) -> set[str]:
    return {str(entry.get("id")) for entry in load_dataset_entry(category) if isinstance(entry, dict) and entry.get("id")}


def validate(data: dict[str, Any], *, validate_installed_ids: bool = True) -> list[str]:
    blockers: list[str] = []
    expected = {
        "artifact_kind": "bfcl_stage1_smoke_run_id_manifest",
        "approval_status": "prepared",
        "provider_profile": "Chuangzhi/Novacode",
        "active_profile": "novacode",
        "route_model": "gpt-4.1",
        "old_signed_model": "gpt-5.2",
        "old_signed_model_status": "historical_superseded_inactive",
        "precondition_commit": "761c57cd7b103a532d423623a440f84460d75cc8",
        "protocol_debug_commit": "37fa096ed0c9feac8bd24d22183c81ae6913cc04",
        "scope_manifest_commit": "761c57cd7b103a532d423623a440f84460d75cc8",
        "max_total_cases": 8,
        "total_case_count": 8,
        "per_category_case_limit": 1,
        "mapping_status": "prepared_pending_reviewer_approval",
        "run_ids_path_template": "<run_root>/bfcl/test_case_ids_to_generate.json",
    }
    for key, value in expected.items():
        if data.get(key) != value:
            blockers.append(f"smoke_run_id_{key}_invalid:{data.get(key)!r}")
    for key in REQUIRED_TRUE:
        if data.get(key) is not True:
            blockers.append(f"smoke_run_id_{key}_not_true:{data.get(key)!r}")
    for key in REQUIRED_FALSE:
        if data.get(key) is not False:
            blockers.append(f"smoke_run_id_{key}_not_false:{data.get(key)!r}")
    if data.get("scorer_feedback_enabled") is not False:
        blockers.append(f"smoke_run_id_scorer_feedback_enabled_not_false:{data.get('scorer_feedback_enabled')!r}")
    if data.get("scorer_feedback_status") != "disabled_inert_for_measurement_only":
        blockers.append(f"smoke_run_id_scorer_feedback_status_invalid:{data.get('scorer_feedback_status')!r}")
    env = data.get("execution_env_required") if isinstance(data.get("execution_env_required"), dict) else {}
    if env.get("GRC_BFCL_USE_RUN_IDS") != "1":
        blockers.append(f"smoke_run_id_env_use_run_ids_invalid:{env.get('GRC_BFCL_USE_RUN_IDS')!r}")
    if env.get("GRC_BFCL_TEST_CATEGORY") != ",".join(SIGNED_CATEGORY_ORDER):
        blockers.append(f"smoke_run_id_env_test_category_invalid:{env.get('GRC_BFCL_TEST_CATEGORY')!r}")
    mappings = data.get("source_category_mappings") if isinstance(data.get("source_category_mappings"), list) else []
    if len(mappings) != 8:
        blockers.append(f"smoke_run_id_mapping_count_invalid:{len(mappings)}")
    source_categories = [row.get("source_category") for row in mappings if isinstance(row, dict)]
    if source_categories != SIGNED_SOURCE_CATEGORIES:
        blockers.append(f"smoke_run_id_source_category_order_invalid:{source_categories!r}")
    by_category = data.get("run_ids_by_category") if isinstance(data.get("run_ids_by_category"), dict) else {}
    if by_category != SIGNED_RUN_IDS_BY_CATEGORY:
        blockers.append("smoke_run_id_run_ids_by_category_drift")
    all_ids = _all_run_ids(data)
    if len(all_ids) != data.get("total_case_count"):
        blockers.append(f"smoke_run_id_total_case_count_mismatch:{len(all_ids)}")
    if len(all_ids) > 8:
        blockers.append(f"smoke_run_id_total_case_count_exceeds_8:{len(all_ids)}")
    if len(set(all_ids)) != len(all_ids):
        blockers.append("smoke_run_id_duplicate_run_ids")
    for category, values in by_category.items():
        if category not in SIGNED_CATEGORY_ORDER:
            blockers.append(f"smoke_run_id_unapproved_category:{category}")
        if not isinstance(values, list) or len(values) != 1:
            blockers.append(f"smoke_run_id_per_category_count_invalid:{category}:{values!r}")
    if validate_installed_ids and by_category:
        for category, values in by_category.items():
            valid_ids = _valid_ids_for_category(category)
            for run_id in values:
                if run_id not in valid_ids:
                    blockers.append(f"smoke_run_id_not_in_installed_bfcl_category:{category}:{run_id}")
    claims = data.get("claim_policy") if isinstance(data.get("claim_policy"), dict) else {}
    for key in ["not_full_default_baseline", "not_measurement_evidence", "not_performance_evidence", "not_3pp_claim", "not_huawei_readiness"]:
        if claims.get(key) is not True:
            blockers.append(f"smoke_run_id_claim_{key}_not_true:{claims.get(key)!r}")
    blockers.extend(_secret_blockers(data))
    return blockers


def check(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    data = load_json(path)
    blockers = validate(data)
    return {
        "report_scope": "bfcl_stage1_smoke_run_id_manifest_check",
        "manifest_path": str(path),
        "approval_status": data.get("approval_status"),
        "route_model": data.get("route_model"),
        "total_case_count": data.get("total_case_count"),
        "max_total_cases": data.get("max_total_cases"),
        "categories": sorted((data.get("run_ids_by_category") or {}).keys()) if isinstance(data.get("run_ids_by_category"), dict) else [],
        "smoke_execution_authorized": data.get("smoke_execution_authorized"),
        "bfcl_stage1_smoke_run_id_manifest_passed": not blockers,
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
            "report_scope": "bfcl_stage1_smoke_run_id_manifest_check",
            "manifest_path": str(args.manifest),
            "bfcl_stage1_smoke_run_id_manifest_passed": False,
            "blockers": [f"smoke_run_id_manifest_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_stage1_smoke_run_id_manifest_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
