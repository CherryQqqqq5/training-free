#!/usr/bin/env python3
"""Check compact one-ID live decode exception shape capture artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from scripts.check_bfcl_live_decode_exception_shape_capture_gate import REQUIRED_COMPACT_FIELDS, SIGNED_ID

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_live_decode_exception_shape_capture_compact.json")
FALSE_KEYS = (
    "bfcl_smoke_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed",
    "candidate_runtime_activation_authorized", "candidate_jsonl_authorized", "candidate_pool_ready",
    "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "fallback_allowed",
    "gpt_4o_fallback_allowed", "gpt_5_2_active", "openrouter_allowed",
)
FORBIDDEN_KEY_RE = re.compile(r"(raw|prompt|case_content|provider_request_body|provider_response_body|headers|logs?|traces?|model_output_text|tool_arguments|function_name|gold|reference|expected|scorer_diff|endpoint|api_key|secret|candidate_output)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(("s" + "k-" + r"[A-Za-z0-9_-]{16,}|" + "api" + "cz" + "|" + "boyue" + "richdata|provider payload|endpoint value|api key|scorer diff|candidate output"), re.IGNORECASE)


def _load(path: Path) -> dict[str, Any]:
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


def _scan(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        key = path[-1] if path else ""
        if key and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_live_decode_exception_shape_capture_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    if data.get("run_ids") != [SIGNED_ID]:
        blockers.append(f"run_ids_invalid:{data.get('run_ids')!r}")
    if data.get("provider_request_executed") is not True:
        blockers.append(f"provider_request_executed_not_true:{data.get('provider_request_executed')!r}")
    if data.get("live_shape_capture_executed") is not True:
        blockers.append(f"live_shape_capture_executed_not_true:{data.get('live_shape_capture_executed')!r}")
    if data.get("bfcl_generate_executed") is not True:
        blockers.append(f"bfcl_generate_executed_not_true:{data.get('bfcl_generate_executed')!r}")
    for key in FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    records = data.get("records") if isinstance(data.get("records"), list) else []
    if len(records) != 1:
        blockers.append(f"record_count_invalid:{len(records)}")
    record = records[0] if records and isinstance(records[0], dict) else {}
    if record:
        if sorted(record.keys()) != sorted(REQUIRED_COMPACT_FIELDS):
            missing = [field for field in REQUIRED_COMPACT_FIELDS if field not in record]
            extra = [field for field in record if field not in REQUIRED_COMPACT_FIELDS]
            if missing:
                blockers.append(f"record_missing_fields:{missing!r}")
            if extra:
                blockers.append(f"record_extra_fields:{extra!r}")
        if record.get("run_id") != SIGNED_ID:
            blockers.append(f"record_run_id_invalid:{record.get('run_id')!r}")
        if record.get("route_profile") != "novacode" or record.get("route_model") != "gpt-4.1":
            blockers.append("record_route_drift")
        if not record.get("suspected_live_decode_failure_stage"):
            blockers.append("suspected_live_decode_failure_stage_missing")
        if record.get("proxy_responses_output_has_function_call") is True:
            for key in ("proxy_function_call_item_count", "proxy_function_call_has_call_id", "proxy_function_call_has_name", "proxy_function_call_has_arguments", "proxy_arguments_shape_label"):
                if key not in record:
                    blockers.append(f"function_call_shape_field_missing:{key}")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    record = data.get("records", [{}])[0] if isinstance(data.get("records"), list) and data.get("records") else {}
    return {
        "report_scope": "bfcl_live_decode_exception_shape_capture_artifact_check",
        "artifact_path": str(path),
        "bfcl_live_decode_exception_shape_capture_artifact_passed": not blockers,
        "run_ids": data.get("run_ids"),
        "route_model": data.get("route_model"),
        "provider_response_has_tool_calls": record.get("provider_response_has_tool_calls") if isinstance(record, dict) else None,
        "proxy_responses_output_has_function_call": record.get("proxy_responses_output_has_function_call") if isinstance(record, dict) else None,
        "bfcl_decode_exception_class": record.get("bfcl_decode_exception_class") if isinstance(record, dict) else None,
        "suspected_live_decode_failure_stage": record.get("suspected_live_decode_failure_stage") if isinstance(record, dict) else None,
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
        summary = {"report_scope": "bfcl_live_decode_exception_shape_capture_artifact_check", "bfcl_live_decode_exception_shape_capture_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_live_decode_exception_shape_capture_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
