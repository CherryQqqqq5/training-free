#!/usr/bin/env python3
"""Check compact one-ID materialized-entry shape telemetry artifact."""

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

from scripts.check_bfcl_one_id_materialized_entry_shape_telemetry_gate import REQUIRED_COMPACT_FIELDS, SIGNED_ID  # noqa: E402

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_materialized_entry_shape_telemetry_compact.json")
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
TRUE_KEYS = (
    "provider_request_executed",
    "live_materialized_entry_shape_telemetry_executed",
    "bfcl_generate_executed",
    "candidate_specs_inert",
)
ALLOWED_STATUSES = {"generated", "protocol_error", "empty_model_response", "missing_result", "unknown_compact_status"}
ALLOWED_STAGES = {
    "decode_not_nonempty",
    "materialization_not_called_after_decode",
    "materialized_entry_missing_after_decode",
    "materialized_entry_protocol_error_indicator_present",
    "materialized_entry_missing_grc_decoded_execution_output_shape",
    "classifier_missed_materialized_entry_marker",
    "materialized_entry_shape_resolved",
}
ALLOWED_RAWISH_KEYS = {"provider_request_executed"}
RAW_KEY_RE = re.compile(
    r"(^|_)(raw|prompt|case_content|provider_payload|provider_request_body|provider_response_body|response_body|headers|logs?|traces?|model_text|tool_args|tool_arguments|function_name|gold|reference|expected|scorer_diff|endpoint|api_key|secret|candidate_output|raw_path|result_path|file_path)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|provider " + "payload|raw " + "prompt|raw " + "case|raw " + "path|scorer " + "diff|candidate " + "output|endpoint " + "value|api " + "key"),
    re.IGNORECASE,
)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain JSON object")
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
        if key and key not in ALLOWED_RAWISH_KEYS and key not in REQUIRED_COMPACT_FIELDS and RAW_KEY_RE.search(key):
            blockers.append(f"forbidden_raw_or_secret_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append(f"forbidden_raw_or_secret_value:{'.'.join(path)}")
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
    if record.get("classifier_status") not in ALLOWED_STATUSES:
        blockers.append(f"classifier_status_invalid:{record.get('classifier_status')!r}")
    if record.get("compact_result_status") != record.get("classifier_status"):
        blockers.append("compact_status_classifier_status_mismatch")
    if record.get("suspected_materialized_entry_shape_stage") not in ALLOWED_STAGES:
        blockers.append(f"suspected_stage_invalid:{record.get('suspected_materialized_entry_shape_stage')!r}")
    has_marker = record.get("materialized_entry_has_grc_decoded_execution_output_shape") is True
    marker_shape = record.get("materialized_marker_shape_label")
    marker_count = record.get("materialized_marker_decoded_output_count_nonzero") is True
    if has_marker and (marker_shape == "missing" or marker_count is not True):
        blockers.append("marker_presence_inconsistent")
    if not has_marker and (marker_shape != "missing" or marker_count is True):
        blockers.append("marker_absence_inconsistent")
    if record.get("materialized_result_written") is False and record.get("suspected_materialized_entry_shape_stage") != "materialized_entry_missing_after_decode":
        blockers.append("missing_materialized_entry_stage_mismatch")
    if record.get("classifier_detected_nonempty") is True and record.get("classifier_status") != "generated":
        blockers.append("classifier_nonempty_status_mismatch")
    return blockers


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_one_id_materialized_entry_shape_telemetry_compact":
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
        "report_scope": "bfcl_one_id_materialized_entry_shape_telemetry_artifact_check",
        "artifact_path": str(path),
        "bfcl_one_id_materialized_entry_shape_telemetry_artifact_passed": not blockers,
        "run_ids": data.get("run_ids"),
        "route_model": data.get("route_model"),
        "bfcl_decode_execute_nonempty": record.get("bfcl_decode_execute_nonempty") if isinstance(record, dict) else None,
        "bfcl_decode_output_count": record.get("bfcl_decode_output_count") if isinstance(record, dict) else None,
        "materialized_entry_shape_label": record.get("materialized_entry_shape_label") if isinstance(record, dict) else None,
        "materialized_entry_has_grc_decoded_execution_output_shape": record.get("materialized_entry_has_grc_decoded_execution_output_shape") if isinstance(record, dict) else None,
        "materialized_marker_shape_label": record.get("materialized_marker_shape_label") if isinstance(record, dict) else None,
        "classifier_status": record.get("classifier_status") if isinstance(record, dict) else None,
        "compact_result_status": record.get("compact_result_status") if isinstance(record, dict) else None,
        "suspected_materialized_entry_shape_stage": record.get("suspected_materialized_entry_shape_stage") if isinstance(record, dict) else None,
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
        summary = {
            "report_scope": "bfcl_one_id_materialized_entry_shape_telemetry_artifact_check",
            "bfcl_one_id_materialized_entry_shape_telemetry_artifact_passed": False,
            "blockers": [f"load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_one_id_materialized_entry_shape_telemetry_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
