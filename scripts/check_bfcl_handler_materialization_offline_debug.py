#!/usr/bin/env python3
"""Check Stage 1C no-provider BFCL handler/materialization offline debug artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_handler_materialization_offline_debug.json")
SIGNED_IDS = ["web_search_base_0", "multi_turn_base_0"]
VARIANTS = ["responses_function_call", "chat_tool_call", "text_only", "true_empty", "malformed_nonempty", "handler_exception"]
FALSE_KEYS = ("provider_request_executed", "bfcl_generate_executed", "bfcl_smoke_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed", "candidate_runtime_activation_authorized", "candidate_jsonl_authorized", "candidate_pool_ready", "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "raw_prompt_persisted", "raw_case_content_persisted", "raw_provider_payload_persisted", "raw_log_persisted", "raw_trace_persisted", "endpoint_or_key_committed")
ALLOWED_FALSE_KEYS = set(FALSE_KEYS) | {"exception_path_swallowed_as_empty", "result_classifier_false_empty_for_nonempty"}
FORBIDDEN_KEY_RE = re.compile(r"(raw_(?:prompt|case|provider|payload|log|trace|response|output)|case_id|gold|reference|expected|scorer_diff|candidate_output|endpoint_value|api_key_value)", re.I)
FORBIDDEN_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|https?://|raw prompt|raw case|provider payload|scorer diff|gold/reference/expected|candidate output|endpoint value|api key)", re.I)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain object")
    return data


def _walk(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    result = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            result.extend(_walk(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(_walk(child, path + (str(index),)))
    return result


def _scan(data: dict[str, Any]) -> list[str]:
    blockers = []
    for path, value in _walk(data):
        if path:
            key = path[-1]
            if FORBIDDEN_KEY_RE.search(key) and key not in ALLOWED_FALSE_KEYS:
                blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate(data: dict[str, Any]) -> list[str]:
    blockers = []
    if data.get("artifact_kind") != "bfcl_handler_materialization_offline_debug":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    if data.get("signed_run_ids") != SIGNED_IDS:
        blockers.append(f"signed_run_ids_invalid:{data.get('signed_run_ids')!r}")
    if data.get("variants") != VARIANTS:
        blockers.append(f"variants_invalid:{data.get('variants')!r}")
    if data.get("no_provider") is not True:
        blockers.append(f"no_provider_not_true:{data.get('no_provider')!r}")
    if data.get("synthetic_fake_upstream_only") is not True:
        blockers.append(f"synthetic_fake_upstream_only_not_true:{data.get('synthetic_fake_upstream_only')!r}")
    if not data.get("suspected_failure_stage"):
        blockers.append("suspected_failure_stage_missing")
    for key in FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    if data.get("handler_import_available") is True and data.get("decode_execute_exercised") is not True:
        blockers.append("decode_execute_not_exercised_when_handler_available")
    records = data.get("records") if isinstance(data.get("records"), list) else []
    if len(records) != len(SIGNED_IDS) * len(VARIANTS):
        blockers.append(f"record_count_invalid:{len(records)}")
    seen = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            blockers.append(f"record_{index}_not_object")
            continue
        run_id = record.get("run_id")
        variant = record.get("variant")
        if run_id not in SIGNED_IDS:
            blockers.append(f"record_{index}_unsigned_run_id:{run_id!r}")
        if variant not in VARIANTS:
            blockers.append(f"record_{index}_unknown_variant:{variant!r}")
        if (run_id, variant) in seen:
            blockers.append(f"record_{index}_duplicate:{run_id}:{variant}")
        seen.add((run_id, variant))
        for key in ("provider_request_executed", "bfcl_generate_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed"):
            if record.get(key) is not False:
                blockers.append(f"record_{index}_{key}_not_false:{record.get(key)!r}")
        if not record.get("suspected_failure_stage"):
            blockers.append(f"record_{index}_suspected_failure_stage_missing")
        if variant in {"responses_function_call", "chat_tool_call"} and record.get("classifier_detected_tool_call") is not True:
            blockers.append(f"record_{index}_tool_call_not_detected")
        if variant == "text_only" and (record.get("classifier_detected_no_tool_text") is not True or record.get("classifier_empty_model_response") is not False):
            blockers.append(f"record_{index}_text_not_distinguished_from_empty")
        if variant == "true_empty" and record.get("classifier_empty_model_response") is not True:
            blockers.append(f"record_{index}_true_empty_not_empty")
        if variant == "handler_exception" and record.get("exception_swallowed_as_empty") is not False:
            blockers.append(f"record_{index}_exception_swallowed_as_empty")
    if seen != {(run_id, variant) for run_id in SIGNED_IDS for variant in VARIANTS}:
        blockers.append("record_matrix_incomplete")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    return {
        "report_scope": "bfcl_handler_materialization_offline_debug_check",
        "artifact_path": str(path),
        "bfcl_handler_materialization_offline_debug_passed": not blockers,
        "handler_import_available": data.get("handler_import_available"),
        "decode_execute_exercised": data.get("decode_execute_exercised"),
        "nonempty_tool_call_materialized_nonempty": data.get("nonempty_tool_call_materialized_nonempty"),
        "nonempty_text_distinguished_from_true_empty": data.get("nonempty_text_distinguished_from_true_empty"),
        "result_classifier_false_empty_for_nonempty": data.get("result_classifier_false_empty_for_nonempty"),
        "exception_path_swallowed_as_empty": data.get("exception_path_swallowed_as_empty"),
        "suspected_failure_stage": data.get("suspected_failure_stage"),
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_handler_materialization_offline_debug_check", "bfcl_handler_materialization_offline_debug_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_handler_materialization_offline_debug_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
