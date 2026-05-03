#!/usr/bin/env python3
"""Check compact one-ID post-decode materialization telemetry artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_one_id_post_decode_materialization_telemetry_gate import REQUIRED_COMPACT_FIELDS, SIGNED_ID

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_post_decode_materialization_telemetry_compact.json")
FALSE_KEYS = (
    "bfcl_smoke_executed",
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
    "gpt_5_2_active",
    "openrouter_allowed",
)
TRUE_KEYS = ("provider_request_executed", "live_post_decode_telemetry_executed", "bfcl_generate_executed")
ALLOWED_STAGES = {
    "decode_not_nonempty",
    "post_decode_exception_after_decode",
    "materialization_not_called_after_decode",
    "result_layout_or_path_lookup_missing_after_decode",
    "result_layout_mismatch_after_decode",
    "materialization_empty_after_decode",
    "classifier_protocol_error_after_nonempty_decode",
    "protocol_status_classifier_false_error_after_nonempty_decode",
    "classifier_missed_nonempty_after_decode",
    "live_post_decode_nonempty",
}
ALLOWED_RAWISH_KEYS = {"result_layout_expected_label", "result_file_path_class_label"}
RAW_KEY_RE = re.compile(r"(^|_)(raw|prompt|case_content|provider_payload|provider_request_body|provider_response_body|response_body|headers|logs|traces|model_output_text|tool_arguments|function_name|gold|reference|expected|scorer_diff|candidate_output|endpoint_value|api_key_value|file_path)(_|$)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz" + "|" + "boyue" + "richdata|provider payload|endpoint value|api key|scorer diff|candidate output"), re.IGNORECASE)


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
        if key and key not in ALLOWED_RAWISH_KEYS and RAW_KEY_RE.search(key):
            blockers.append(f"forbidden_raw_or_secret_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append(f"endpoint_or_key_literal:{'.'.join(path)}")
    return sorted(set(blockers))


def _validate_record(record: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
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
    stage = record.get("suspected_post_decode_failure_stage")
    if stage not in ALLOWED_STAGES:
        blockers.append(f"suspected_post_decode_failure_stage_invalid:{stage!r}")
    decode_nonempty = record.get("bfcl_decode_execute_nonempty") is True
    written = record.get("materialized_result_written") is True
    mat_nonempty = record.get("materialized_result_nonempty") is True
    classifier_nonempty = record.get("classifier_detected_nonempty") is True
    post_exception = record.get("post_decode_exception_observed") is True
    classifier_status = str(record.get("classifier_status") or "")
    protocol_label = str(record.get("protocol_status_classifier_label") or "")
    if post_exception:
        if stage != "post_decode_exception_after_decode":
            blockers.append("post_decode_exception_stage_mismatch")
    elif not decode_nonempty:
        if stage != "decode_not_nonempty":
            blockers.append("decode_not_nonempty_stage_mismatch")
    elif record.get("materialization_called") is not True:
        if stage != "materialization_not_called_after_decode":
            blockers.append("materialization_not_called_stage_mismatch")
    elif not written:
        if stage != "result_layout_or_path_lookup_missing_after_decode":
            blockers.append("missing_result_stage_mismatch")
    elif record.get("result_layout_match") is not True:
        if stage != "result_layout_mismatch_after_decode":
            blockers.append("layout_mismatch_stage_mismatch")
    elif not mat_nonempty:
        if stage != "materialization_empty_after_decode":
            blockers.append("materialization_empty_stage_mismatch")
    elif not classifier_nonempty and classifier_status == "protocol_error":
        if stage != "classifier_protocol_error_after_nonempty_decode":
            blockers.append("classifier_protocol_error_stage_mismatch")
    elif classifier_nonempty and protocol_label == "protocol_error":
        if stage != "protocol_status_classifier_false_error_after_nonempty_decode":
            blockers.append("protocol_status_false_error_stage_mismatch")
    elif not classifier_nonempty:
        if stage != "classifier_missed_nonempty_after_decode":
            blockers.append("classifier_missed_nonempty_stage_mismatch")
    else:
        if stage != "live_post_decode_nonempty":
            blockers.append("live_post_decode_nonempty_stage_mismatch")
    return blockers


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_one_id_post_decode_materialization_telemetry_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    if data.get("run_ids") != [SIGNED_ID]:
        blockers.append(f"run_ids_invalid:{data.get('run_ids')!r}")
    for key in TRUE_KEYS:
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true:{data.get(key)!r}")
    for key in FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    records = data.get("records") if isinstance(data.get("records"), list) else []
    if len(records) != 1:
        blockers.append(f"record_count_invalid:{len(records)}")
    elif not isinstance(records[0], dict):
        blockers.append("record_0_not_object")
    else:
        blockers.extend(_validate_record(records[0]))
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    record = data.get("records", [{}])[0] if isinstance(data.get("records"), list) and data.get("records") else {}
    return {
        "report_scope": "bfcl_one_id_post_decode_materialization_telemetry_artifact_check",
        "artifact_path": str(path),
        "bfcl_one_id_post_decode_materialization_telemetry_artifact_passed": not blockers,
        "run_ids": data.get("run_ids"),
        "route_model": data.get("route_model"),
        "bfcl_decode_execute_nonempty": record.get("bfcl_decode_execute_nonempty") if isinstance(record, dict) else None,
        "bfcl_decode_output_count": record.get("bfcl_decode_output_count") if isinstance(record, dict) else None,
        "classifier_status": record.get("classifier_status") if isinstance(record, dict) else None,
        "compact_result_status": record.get("compact_result_status") if isinstance(record, dict) else None,
        "suspected_post_decode_failure_stage": record.get("suspected_post_decode_failure_stage") if isinstance(record, dict) else None,
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
        summary = {"report_scope": "bfcl_one_id_post_decode_materialization_telemetry_artifact_check", "bfcl_one_id_post_decode_materialization_telemetry_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_one_id_post_decode_materialization_telemetry_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
