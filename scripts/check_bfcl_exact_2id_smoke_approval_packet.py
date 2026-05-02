#!/usr/bin/env python3
"""Check pending exact 2-ID BFCL smoke approval packet."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_smoke_approval_packet.json")
SIGNED_IDS = ["web_search_base_0", "multi_turn_base_0"]
REQUIRED_TRUE_AUTHORIZATION = (
    "authorized",
    "provider_call_authorized",
    "bfcl_smoke_authorized",
    "bfcl_generate_authorized",
)
REQUIRED_FALSE = (
    "scorer_authorized",
    "bfcl_evaluate_authorized",
    "evaluate_command_allowed",
    "scorer_command_allowed",
    "full_default_runner_allowed",
    "baseline_shell_runner_allowed",
    "full_baseline_authorized",
    "default_bfcl_authorized",
    "eight_id_smoke_authorized",
    "candidate_runtime_activation_authorized",
    "candidate_generation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "openrouter_allowed",
    "gpt_5_2_active",
    "raw_logs_committed",
    "raw_traces_committed",
    "raw_provider_payloads_committed",
    "raw_prompts_committed",
    "raw_gold_reference_scorer_diffs_committed",
    "endpoint_value_committed",
    "api_key_value_committed",
)
REQUIRED_TRUE = (
    "current_system_only",
    "candidate_specs_inert",
    "compact_smoke_artifact_only",
    "endpoint_env_only",
    "api_key_env_only",
    "generate_only",
)
FORBIDDEN_KEY_RE = re.compile(r"(raw_(?:prompt|case|provider|payload|log|trace|response)|case_id|gold|reference|expected|scorer_diff|candidate_output|endpoint_value|api_key_value)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|https?://|raw prompt|raw case|provider payload|scorer diff|gold/reference/expected|candidate output)", re.IGNORECASE)
ALLOWED_FALSE_KEYS = set(REQUIRED_FALSE)


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
    if data.get("artifact_kind") != "bfcl_exact_2id_smoke_approval_packet":
        blockers.append(f"packet_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "approved":
        blockers.append(f"packet_approval_status_not_approved:{data.get('approval_status')!r}")
    for key in REQUIRED_TRUE_AUTHORIZATION:
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true:{data.get(key)!r}")
    for key in REQUIRED_FALSE:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    for key in REQUIRED_TRUE:
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true:{data.get(key)!r}")
    if data.get("signed_run_ids") != SIGNED_IDS:
        blockers.append(f"signed_run_ids_invalid:{data.get('signed_run_ids')!r}")
    if data.get("max_cases") != 2:
        blockers.append(f"max_cases_invalid:{data.get('max_cases')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    if data.get("provider_profile") != "Chuangzhi/Novacode":
        blockers.append(f"provider_profile_invalid:{data.get('provider_profile')!r}")
    if data.get("approval_scope") != "exact_2id_generate_only_smoke":
        blockers.append(f"approval_scope_invalid:{data.get('approval_scope')!r}")
    if data.get("bfcl_run_ids_manifest_mode") != "temporary_bfcl_package_path_with_backup_restore":
        blockers.append(f"bfcl_run_ids_manifest_mode_invalid:{data.get('bfcl_run_ids_manifest_mode')!r}")
    if data.get("bfcl_run_ids_manifest_content") != "exact_signed_ids_only":
        blockers.append(f"bfcl_run_ids_manifest_content_invalid:{data.get('bfcl_run_ids_manifest_content')!r}")
    if data.get("bfcl_run_ids_manifest_schema") != "category_to_signed_id_list":
        blockers.append(f"bfcl_run_ids_manifest_schema_invalid:{data.get('bfcl_run_ids_manifest_schema')!r}")
    if data.get("bfcl_run_ids_manifest_cleanup_required") is not True:
        blockers.append(f"bfcl_run_ids_manifest_cleanup_required_not_true:{data.get('bfcl_run_ids_manifest_cleanup_required')!r}")
    expected_paths = {
        "generate_only_runner_path": "scripts/run_bfcl_exact_2id_generate_smoke.py",
        "approved_for_runner_path": "scripts/run_bfcl_exact_2id_generate_smoke.py",
        "compact_artifact_checker_path": "scripts/check_bfcl_exact_2id_generate_smoke_artifact.py",
        "approved_for_artifact_checker_path": "scripts/check_bfcl_exact_2id_generate_smoke_artifact.py",
        "compact_output_artifact": "outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_generate_smoke_compact.json",
    }
    for key, expected in expected_paths.items():
        if data.get(key) != expected:
            blockers.append(f"{key}_invalid:{data.get(key)!r}")
    stop_gates = data.get("stop_gates") if isinstance(data.get("stop_gates"), list) else []
    for required in ("empty_model_response", "protocol_or_schema_failure", "raw_leakage", "route_drift", "candidate_activation", "extra_run_id"):
        if required not in stop_gates:
            blockers.append(f"stop_gate_missing:{required}")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = _load(packet_path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "bfcl_exact_2id_smoke_approval_packet_check",
        "packet_path": str(packet_path),
        "bfcl_exact_2id_smoke_approval_packet_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "signed_run_ids": packet.get("signed_run_ids"),
        "route_model": packet.get("route_model"),
        "provider_call_authorized": packet.get("provider_call_authorized"),
        "bfcl_smoke_authorized": packet.get("bfcl_smoke_authorized"),
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_exact_2id_smoke_approval_packet_check", "bfcl_exact_2id_smoke_approval_packet_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_exact_2id_smoke_approval_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
