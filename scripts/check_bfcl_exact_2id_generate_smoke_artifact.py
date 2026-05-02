#!/usr/bin/env python3
"""Check compact exact 2-ID BFCL generate-only smoke artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_generate_smoke_compact.json")
SIGNED_IDS = ["web_search_base_0", "multi_turn_base_0"]
ALLOWED_RECORD_KEYS = {
    "run_id",
    "status",
    "empty_model_response_detected",
    "no_tool_text_recorded",
    "tool_call_detected",
    "protocol_error_detected",
    "route_profile",
    "route_model",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "bfcl_evaluate_executed",
    "scorer_executed",
    "full_baseline_executed",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
}
ALLOWED_TOP_KEYS = {
    "artifact_kind",
    "approval_status",
    "route_profile",
    "route_model",
    "provider_profile",
    "run_ids",
    "case_count",
    "provider_call_executed",
    "bfcl_generate_executed",
    "bfcl_evaluate_executed",
    "scorer_executed",
    "full_baseline_executed",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "openrouter_allowed",
    "gpt_5_2_active",
    "raw_prompt_persisted",
    "raw_case_persisted",
    "raw_provider_payload_persisted",
    "raw_log_persisted",
    "raw_trace_persisted",
    "endpoint_or_key_committed",
    "records",
}
FALSE_KEYS = (
    "bfcl_evaluate_executed",
    "scorer_executed",
    "full_baseline_executed",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "openrouter_allowed",
    "gpt_5_2_active",
    "raw_prompt_persisted",
    "raw_case_persisted",
    "raw_provider_payload_persisted",
    "raw_log_persisted",
    "raw_trace_persisted",
    "endpoint_or_key_committed",
)
RECORD_FALSE_KEYS = (
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "bfcl_evaluate_executed",
    "scorer_executed",
    "full_baseline_executed",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
)
ALLOWED_STATUSES = {"generated", "no_tool_text", "empty_model_response", "protocol_error", "missing_result", "generate_failed", "unknown_compact_status"}
KEY_LITERAL_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
FORBIDDEN_VALUE_RE = re.compile(r"(https?://|raw prompt|raw case|provider payload|scorer diff|gold/reference/expected|candidate output)", re.IGNORECASE)
FORBIDDEN_KEY_RE = re.compile(r"(prompt|case_id|gold|reference|expected|scorer_diff|provider_payload|trace|endpoint_value|api_key_value|raw_text)", re.IGNORECASE)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain object")
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


def _raw_blockers(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    allowed_false_keys = set(FALSE_KEYS) | set(RECORD_FALSE_KEYS)
    for path, value in _walk(data):
        key = path[-1] if path else ""
        if FORBIDDEN_KEY_RE.search(key) and key not in allowed_false_keys:
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str):
            if KEY_LITERAL_PATTERN.search(value):
                blockers.append(f"key_literal_forbidden:{'.'.join(path)}")
            if FORBIDDEN_VALUE_RE.search(value):
                blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    extra_top = set(data) - ALLOWED_TOP_KEYS
    if extra_top:
        blockers.append(f"top_level_extra_keys:{sorted(extra_top)!r}")
    if data.get("artifact_kind") != "bfcl_exact_2id_generate_smoke_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    if data.get("provider_profile") != "Chuangzhi/Novacode":
        blockers.append(f"provider_profile_invalid:{data.get('provider_profile')!r}")
    if data.get("run_ids") != SIGNED_IDS:
        blockers.append(f"run_ids_invalid:{data.get('run_ids')!r}")
    if data.get("case_count") != 2:
        blockers.append(f"case_count_invalid:{data.get('case_count')!r}")
    for key in FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    records = data.get("records") if isinstance(data.get("records"), list) else []
    if len(records) != 2:
        blockers.append(f"record_count_invalid:{len(records)}")
    seen = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            blockers.append(f"record_{index}_not_object")
            continue
        extra_record = set(record) - ALLOWED_RECORD_KEYS
        if extra_record:
            blockers.append(f"record_{index}_extra_keys:{sorted(extra_record)!r}")
        run_id = record.get("run_id")
        seen.append(run_id)
        if run_id not in SIGNED_IDS:
            blockers.append(f"record_{index}_unsigned_run_id:{run_id!r}")
        if record.get("route_profile") != "novacode" or record.get("route_model") != "gpt-4.1":
            blockers.append(f"record_{index}_route_drift")
        if record.get("status") not in ALLOWED_STATUSES:
            blockers.append(f"record_{index}_status_invalid:{record.get('status')!r}")
        for key in RECORD_FALSE_KEYS:
            if record.get(key) is not False:
                blockers.append(f"record_{index}_{key}_not_false:{record.get(key)!r}")
        for key in ("empty_model_response_detected", "no_tool_text_recorded", "tool_call_detected", "protocol_error_detected"):
            if not isinstance(record.get(key), bool):
                blockers.append(f"record_{index}_{key}_not_bool:{record.get(key)!r}")
    if seen != SIGNED_IDS:
        blockers.append(f"record_run_id_order_invalid:{seen!r}")
    blockers.extend(_raw_blockers(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = load_json(path)
    blockers = validate(data)
    return {
        "report_scope": "bfcl_exact_2id_generate_smoke_artifact_check",
        "artifact_path": str(path),
        "bfcl_exact_2id_generate_smoke_artifact_passed": not blockers,
        "run_ids": data.get("run_ids"),
        "case_count": data.get("case_count"),
        "bfcl_generate_executed": data.get("bfcl_generate_executed"),
        "bfcl_evaluate_executed": data.get("bfcl_evaluate_executed"),
        "scorer_executed": data.get("scorer_executed"),
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
        summary = {"report_scope": "bfcl_exact_2id_generate_smoke_artifact_check", "bfcl_exact_2id_generate_smoke_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_exact_2id_generate_smoke_artifact_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
