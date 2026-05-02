#!/usr/bin/env python3
"""Check compact BFCL live-shape telemetry artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_live_shape_telemetry_compact.json")
SIGNED_IDS = ["web_search_base_0", "multi_turn_base_0"]
ALLOWED_RECORD_FIELDS = {
    "run_id_label",
    "endpoint_path_label",
    "request_shape_label",
    "response_shape_label",
    "status_code_class",
    "output_empty",
    "tool_call_present",
    "parser_decode_path_label",
    "token_forwarding_label",
    "tool_choice_forwarding_label",
    "instructions_forwarding_label",
    "engine_content_empty_label",
    "engine_coercion_label",
    "raw_text_persisted",
    "raw_body_persisted",
    "raw_payload_persisted",
    "raw_header_persisted",
    "raw_log_persisted",
    "raw_trace_persisted",
}
SECRET_OR_ENDPOINT_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|https?://)", re.IGNORECASE)
RAW_MARKERS = ("prompt", "case_id", "gold", "expected", "reference", "scorer_diff", "provider_payload", "provider_response", "candidate_output")


def _load(path: Path) -> dict[str, Any]:
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


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_live_shape_telemetry_compact":
        blockers.append(f"telemetry_artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("route_model") != "gpt-4.1" or data.get("active_profile") != "novacode":
        blockers.append("telemetry_artifact_route_drift")
    if data.get("provider_request_executed") not in (True, False):
        blockers.append("telemetry_artifact_provider_request_executed_not_boolean:%r" % data.get("provider_request_executed"))
    for key in ("bfcl_smoke_executed", "bfcl_scorer_executed", "candidate_runtime_activation_authorized", "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "fallback_allowed", "gpt_4o_fallback_allowed", "openrouter_allowed"):
        if data.get(key) is not False:
            blockers.append(f"telemetry_artifact_{key}_not_false:{data.get(key)!r}")
    run_ids = data.get("run_ids") if isinstance(data.get("run_ids"), list) else []
    if len(run_ids) > 2:
        blockers.append(f"telemetry_artifact_too_many_run_ids:{len(run_ids)}")
    if run_ids and run_ids != SIGNED_IDS:
        blockers.append(f"telemetry_artifact_run_ids_drift:{run_ids!r}")
    records = data.get("records") if isinstance(data.get("records"), list) else []
    if not records:
        blockers.append("telemetry_artifact_records_missing")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            blockers.append(f"telemetry_artifact_record_{index}_not_object")
            continue
        extra = sorted(set(record) - ALLOWED_RECORD_FIELDS)
        missing = sorted(ALLOWED_RECORD_FIELDS - set(record))
        if extra:
            blockers.append(f"telemetry_artifact_record_{index}_extra_fields:{extra}")
        if missing:
            blockers.append(f"telemetry_artifact_record_{index}_missing_fields:{missing}")
        for flag in ("raw_text_persisted", "raw_body_persisted", "raw_payload_persisted", "raw_header_persisted", "raw_log_persisted", "raw_trace_persisted"):
            if record.get(flag) is not False:
                blockers.append(f"telemetry_artifact_record_{index}_{flag}_not_false:{record.get(flag)!r}")
    for path, value in _walk(data):
        if path and path[-1] in RAW_MARKERS:
            blockers.append(f"telemetry_artifact_forbidden_key:{'.'.join(path)}")
        if isinstance(value, str):
            if SECRET_OR_ENDPOINT_RE.search(value):
                blockers.append(f"telemetry_artifact_secret_or_endpoint_literal:{'.'.join(path)}")
            if any(marker in value.lower() for marker in RAW_MARKERS):
                blockers.append(f"telemetry_artifact_raw_marker_literal:{'.'.join(path)}")
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    return {
        "report_scope": "bfcl_live_shape_telemetry_artifact_check",
        "artifact_path": str(path),
        "bfcl_live_shape_telemetry_artifact_passed": not blockers,
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
        summary = {"report_scope": "bfcl_live_shape_telemetry_artifact_check", "bfcl_live_shape_telemetry_artifact_passed": False, "blockers": [f"telemetry_artifact_load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_live_shape_telemetry_artifact_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
