#!/usr/bin/env python3
"""Check no-provider BFCL result materialization debug packet and artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_result_materialization_debug_packet.json")
DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_result_materialization_debug.json")
SIGNED_IDS = ["web_search_base_0", "multi_turn_base_0"]
VARIANTS = ["provider_or_proxy_empty", "proxy_tool_call_materialized_empty", "proxy_text_materialized_empty", "result_parser_missed_nonempty", "cli_exception_swallowed_as_empty"]
FALSE_PACKET = ("authorized", "provider_request_authorized", "bfcl_generate_authorized", "bfcl_smoke_authorized", "bfcl_evaluate_authorized", "scorer_authorized", "full_baseline_authorized", "candidate_runtime_activation_authorized", "candidate_generation_authorized", "candidate_jsonl_authorized", "candidate_pool_ready", "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "provider_request_executed", "bfcl_generate_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed", "endpoint_value_committed", "api_key_value_committed", "raw_material_persisted")
FALSE_ARTIFACT = ("provider_request_executed", "bfcl_generate_executed", "bfcl_smoke_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed", "candidate_runtime_activation_authorized", "candidate_jsonl_authorized", "candidate_pool_ready", "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "raw_prompt_persisted", "raw_case_content_persisted", "raw_provider_payload_persisted", "raw_log_persisted", "raw_trace_persisted", "endpoint_or_key_committed")
ALLOWED_FALSE_KEYS = set(FALSE_PACKET) | set(FALSE_ARTIFACT)
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


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers = []
    if data.get("artifact_kind") != "bfcl_result_materialization_debug_packet":
        blockers.append(f"packet_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"packet_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("packet_route_drift")
    if data.get("signed_run_ids") != SIGNED_IDS:
        blockers.append(f"packet_signed_run_ids_invalid:{data.get('signed_run_ids')!r}")
    if data.get("debug_variants") != VARIANTS:
        blockers.append(f"packet_debug_variants_invalid:{data.get('debug_variants')!r}")
    for key in FALSE_PACKET:
        if data.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{data.get(key)!r}")
    for key in ("compact_shape_only", "synthetic_fake_upstream_only", "endpoint_env_only", "api_key_env_only"):
        if data.get(key) is not True:
            blockers.append(f"packet_{key}_not_true:{data.get(key)!r}")
    blockers.extend(f"packet_{item}" for item in _scan(data))
    return sorted(set(blockers))


def validate_artifact(data: dict[str, Any]) -> list[str]:
    blockers = []
    if data.get("artifact_kind") != "bfcl_result_materialization_debug":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("artifact_route_drift")
    if data.get("signed_run_ids") != SIGNED_IDS:
        blockers.append(f"artifact_signed_run_ids_invalid:{data.get('signed_run_ids')!r}")
    if data.get("debug_variants") != VARIANTS:
        blockers.append(f"artifact_debug_variants_invalid:{data.get('debug_variants')!r}")
    if not data.get("suspected_next_isolation_target"):
        blockers.append("artifact_suspected_next_isolation_target_missing")
    for key in FALSE_ARTIFACT:
        if data.get(key) is not False:
            blockers.append(f"artifact_{key}_not_false:{data.get(key)!r}")
    for key in ("compact_shape_only", "synthetic_fake_upstream_only"):
        if data.get(key) is not True:
            blockers.append(f"artifact_{key}_not_true:{data.get(key)!r}")
    records = data.get("records") if isinstance(data.get("records"), list) else []
    if len(records) != len(SIGNED_IDS) * len(VARIANTS):
        blockers.append(f"artifact_record_count_invalid:{len(records)}")
    seen = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            blockers.append(f"artifact_record_{index}_not_object")
            continue
        run_id = record.get("run_id")
        variant = record.get("fake_upstream_variant")
        if run_id not in SIGNED_IDS:
            blockers.append(f"artifact_record_{index}_unsigned_run_id:{run_id!r}")
        if variant not in VARIANTS:
            blockers.append(f"artifact_record_{index}_unknown_variant:{variant!r}")
        if (run_id, variant) in seen:
            blockers.append(f"artifact_record_{index}_duplicate:{run_id}:{variant}")
        seen.add((run_id, variant))
        for key in ("provider_request_executed", "bfcl_generate_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed"):
            if record.get(key) is not False:
                blockers.append(f"artifact_record_{index}_{key}_not_false:{record.get(key)!r}")
        if not record.get("suspected_materialization_stage"):
            blockers.append(f"artifact_record_{index}_suspected_materialization_stage_missing")
        if variant == "provider_or_proxy_empty" and record.get("provider_or_proxy_returned_empty") is not True:
            blockers.append(f"artifact_record_{index}_provider_empty_flag_not_true")
        if variant == "proxy_tool_call_materialized_empty" and record.get("proxy_returned_nonempty_tool_call") is not True:
            blockers.append(f"artifact_record_{index}_tool_call_nonempty_flag_not_true")
        if variant == "proxy_text_materialized_empty" and record.get("proxy_returned_nonempty_text") is not True:
            blockers.append(f"artifact_record_{index}_text_nonempty_flag_not_true")
        if variant == "result_parser_missed_nonempty" and record.get("bfcl_result_file_contains_nonempty_shape") is not True:
            blockers.append(f"artifact_record_{index}_parser_nonempty_shape_flag_not_true")
        if variant == "cli_exception_swallowed_as_empty" and record.get("cli_exception_observed") is not True:
            blockers.append(f"artifact_record_{index}_cli_exception_flag_not_true")
    expected = {(run_id, variant) for run_id in SIGNED_IDS for variant in VARIANTS}
    if seen != expected:
        blockers.append("artifact_record_matrix_incomplete")
    blockers.extend(f"artifact_{item}" for item in _scan(data))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, artifact_path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    packet = _load(packet_path)
    artifact = _load(artifact_path)
    blockers = validate_packet(packet) + validate_artifact(artifact)
    return {"report_scope": "bfcl_result_materialization_debug_check", "packet_path": str(packet_path), "artifact_path": str(artifact_path), "bfcl_result_materialization_debug_passed": not blockers, "suspected_next_isolation_target": artifact.get("suspected_next_isolation_target"), "record_count": len(artifact.get("records", [])) if isinstance(artifact.get("records"), list) else 0, "blockers": sorted(set(blockers))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_result_materialization_debug_check", "bfcl_result_materialization_debug_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_result_materialization_debug_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
