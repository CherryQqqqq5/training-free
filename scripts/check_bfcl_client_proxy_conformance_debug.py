#!/usr/bin/env python3
"""Check no-provider BFCL client/proxy conformance debug packet and artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_client_proxy_conformance_debug_packet.json")
DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_client_proxy_conformance_debug.json")
DEFAULT_REPORT = Path("outputs/artifacts/stage1_bfcl_acceptance/stage1_bfcl_baseline_blocker_report.json")
REQUIRED_FALSE_PACKET = (
    "authorized",
    "provider_request_authorized",
    "bfcl_smoke_authorized",
    "bfcl_scorer_authorized",
    "full_baseline_authorized",
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
REQUIRED_FALSE_ARTIFACT = (
    "provider_request_executed",
    "bfcl_smoke_executed",
    "scorer_executed",
    "full_baseline_executed",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "raw_prompt_persisted",
    "raw_provider_payload_persisted",
    "raw_trace_persisted",
)
REQUIRED_RECORD_FIELDS = [
    "bfcl_handler_import_available",
    "proxy_endpoint_tested",
    "instructions_preserved",
    "input_message_count_bucket",
    "tools_count",
    "tool_choice_input_shape",
    "tool_choice_forwarded_shape",
    "token_field_forwarded_shape",
    "fake_upstream_seen_tools",
    "fake_upstream_seen_tool_choice",
    "fake_upstream_seen_nonempty_messages",
    "fake_upstream_returned_tool_call",
    "fake_upstream_returned_nonempty_text",
    "engine_final_has_tool_calls",
    "engine_final_content_empty",
    "engine_coerced_nonempty_text_to_empty",
    "responses_output_has_function_call",
    "responses_output_has_message_text",
    "bfcl_decode_execute_nonempty",
    "true_empty_distinguished_from_coerced_empty",
    "suspected_failure_stage",
]
SECRET_OR_ENDPOINT_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|https?://)", re.IGNORECASE)
RAW_TEXT_MARKERS = (
    "Call lookup_weather for Paris",
    "Synthetic non-tool completion",
    "Synthetic malformed nonempty completion",
    "provider payload",
    "scorer diff",
    "gold/reference/expected",
)
FORBIDDEN_KEYS = {
    "case_id",
    "prompt",
    "gold",
    "expected",
    "reference",
    "scorer_diff",
    "provider_payload",
    "provider_response",
    "headers",
    "logs",
    "traces",
    "endpoint",
    "api_key",
    "candidate_output",
}
ALLOWED_TEXT_PATH_ROOTS = {"allowed_scope", "forbidden_scope"}


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


def _scan_material(data: dict[str, Any], *, allow_scope_text: bool = False) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        if path and path[-1] in FORBIDDEN_KEYS:
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if not isinstance(value, str):
            continue
        if allow_scope_text and path and path[0] in ALLOWED_TEXT_PATH_ROOTS:
            continue
        if SECRET_OR_ENDPOINT_RE.search(value):
            blockers.append(f"secret_or_endpoint_literal:{'.'.join(path)}")
        if any(marker in value for marker in RAW_TEXT_MARKERS):
            blockers.append(f"raw_or_sensitive_text_literal:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = {
        "artifact_kind": "bfcl_client_proxy_conformance_debug_packet",
        "approval_status": "prepared",
        "provider_profile": "Chuangzhi/Novacode",
        "active_profile": "novacode",
        "route_model": "gpt-4.1",
        "runtime_blocker_base_commit": "1006dc95120817bc8b49a7350c1f2f9ab3075433",
    }
    for key, value in expected.items():
        if packet.get(key) != value:
            blockers.append(f"packet_{key}_invalid:{packet.get(key)!r}")
    for key in REQUIRED_FALSE_PACKET:
        if packet.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{packet.get(key)!r}")
    for key in ("endpoint_env_only", "api_key_env_only"):
        if packet.get(key) is not True:
            blockers.append(f"packet_{key}_not_true:{packet.get(key)!r}")
    blockers.extend(f"packet_{item}" for item in _scan_material(packet, allow_scope_text=True))
    return blockers


def validate_artifact(artifact: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if artifact.get("artifact_kind") != "bfcl_client_proxy_conformance_debug":
        blockers.append(f"artifact_kind_invalid:{artifact.get('artifact_kind')!r}")
    if not artifact.get("suspected_failure_stage"):
        blockers.append("artifact_suspected_failure_stage_missing")
    for key in REQUIRED_FALSE_ARTIFACT:
        if artifact.get(key) is not False:
            blockers.append(f"artifact_{key}_not_false:{artifact.get(key)!r}")
    records = artifact.get("records") if isinstance(artifact.get("records"), list) else []
    if not records:
        blockers.append("artifact_records_missing")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            blockers.append(f"artifact_record_{index}_not_object")
            continue
        extra = sorted(set(record) - set(REQUIRED_RECORD_FIELDS))
        missing = sorted(set(REQUIRED_RECORD_FIELDS) - set(record))
        if extra:
            blockers.append(f"artifact_record_{index}_extra_fields:{extra}")
        if missing:
            blockers.append(f"artifact_record_{index}_missing_fields:{missing}")
        if not record.get("suspected_failure_stage"):
            blockers.append(f"artifact_record_{index}_suspected_failure_stage_missing")
        if record.get("provider_request_executed") is True or record.get("bfcl_smoke_executed") is True:
            blockers.append(f"artifact_record_{index}_execution_flag_forbidden")
    blockers.extend(f"artifact_{item}" for item in _scan_material(artifact))
    return blockers


def validate_report(report: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if report.get("artifact_kind") != "stage1_bfcl_baseline_blocker_report":
        blockers.append("blocker_report_kind_invalid")
    if report.get("bfcl_measurement_evidence") is not False:
        blockers.append("blocker_report_measurement_evidence_not_false")
    blockers.extend(f"blocker_report_{item}" for item in _scan_material(report))
    return blockers


def check(packet_path: Path = DEFAULT_PACKET, artifact_path: Path = DEFAULT_ARTIFACT, report_path: Path = DEFAULT_REPORT) -> dict[str, Any]:
    blockers: list[str] = []
    packet = _load(packet_path)
    blockers.extend(validate_packet(packet))
    artifact = _load(artifact_path) if artifact_path.exists() else {}
    if artifact:
        blockers.extend(validate_artifact(artifact))
    else:
        blockers.append("artifact_missing")
    report = _load(report_path) if report_path.exists() else {}
    if report:
        blockers.extend(validate_report(report))
    else:
        blockers.append("blocker_report_missing")
    return {
        "report_scope": "bfcl_client_proxy_conformance_debug_check",
        "packet_path": str(packet_path),
        "artifact_path": str(artifact_path),
        "blocker_report_path": str(report_path),
        "suspected_failure_stage": artifact.get("suspected_failure_stage") if artifact else None,
        "bfcl_client_proxy_conformance_debug_passed": not blockers,
        "blockers": sorted(set(blockers)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--blocker-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.artifact, args.blocker_report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "bfcl_client_proxy_conformance_debug_check",
            "bfcl_client_proxy_conformance_debug_passed": False,
            "blockers": [f"load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_client_proxy_conformance_debug_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
