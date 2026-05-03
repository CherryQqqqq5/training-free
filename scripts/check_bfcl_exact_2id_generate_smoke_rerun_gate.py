#!/usr/bin/env python3
"""Check the pending exact 2-ID BFCL generate-only smoke rerun gate."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_generate_smoke_rerun_gate_packet.json")
SIGNED_IDS = ["web_search_base_0", "multi_turn_base_0"]
REQUIRED_STOP_GATES = [
    "empty_model_response",
    "protocol_error",
    "missing_result",
    "route_drift",
    "raw_or_secret_material",
    "extra_run_id",
    "second_run",
    "candidate_activation",
]
REQUIRED_COMPACT_FIELDS = [
    "run_id_count",
    "signed_run_ids",
    "route_profile",
    "route_model",
    "candidate_specs_inert",
    "bfcl_generate_executed",
    "bfcl_evaluate_executed",
    "scorer_executed",
    "full_baseline_executed",
    "per_id_compact_status",
    "per_id_empty_model_response_detected",
    "per_id_protocol_error_detected",
    "per_id_generated_detected",
    "per_id_result_present",
    "stop_gate_triggered",
    "smoke_passed",
    "suspected_remaining_stage",
]
AUTH_KEYS = (
    "authorized",
    "provider_request_authorized",
    "bfcl_generate_authorized",
    "bfcl_smoke_authorized",
)
ALWAYS_FALSE_KEYS = (
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "full_baseline_authorized",
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
    "evaluate_command_allowed",
    "scorer_command_allowed",
    "full_default_runner_allowed",
    "baseline_shell_runner_allowed",
)
ALLOWED_KEYS = {
    "artifact_kind",
    "approval_status",
    "authorized",
    "provider_request_authorized",
    "bfcl_generate_authorized",
    "bfcl_smoke_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "full_baseline_authorized",
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
    "route_profile",
    "route_model",
    "signed_run_ids",
    "run_id_count",
    "requested_future_scope",
    "candidate_specs_inert",
    "generate_only",
    "evaluate_command_allowed",
    "scorer_command_allowed",
    "full_default_runner_allowed",
    "baseline_shell_runner_allowed",
    "compact_artifact_only",
    "data_boundary",
    "runner_path",
    "gate_checker_path",
    "future_output_artifact",
    "preserve_prior_artifacts",
    "stop_gates",
    "allowed_future_compact_fields",
}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw|prompt|case_content|provider_payload|provider_request_body|provider_response_body|response_body|headers|logs?|traces?|model_text|tool_args|tool_arguments|gold|reference|expected|scorer_diff|endpoint|api_key|secret|candidate_output|path)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz" + "|" + "boyue" + "richdata|endpoint " + "value|api " + "key|provider " + "payload|raw " + "prompt|raw " + "case|scorer " + "diff|candidate " + "output|gpt-4o|openrouter|gpt-5.2"),
    re.IGNORECASE,
)


def load_packet(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
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
        if key and key not in ALLOWED_KEYS and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if path and path[-1] == "route_model" and value == "gpt-4.1":
                continue
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_exact_2id_generate_smoke_rerun_gate_packet":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    status = data.get("approval_status")
    if status not in {"pending", "approved"}:
        blockers.append(f"approval_status_invalid:{status!r}")
    auth_expected = status == "approved"
    for key in AUTH_KEYS:
        if data.get(key) is not auth_expected:
            blockers.append(f"{key}_not_{str(auth_expected).lower()}:{data.get(key)!r}")
    for key in ALWAYS_FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    if data.get("signed_run_ids") != SIGNED_IDS:
        blockers.append(f"signed_run_ids_invalid:{data.get('signed_run_ids')!r}")
    if data.get("run_id_count") != 2:
        blockers.append(f"run_id_count_invalid:{data.get('run_id_count')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    if data.get("requested_future_scope") != "exact_2id_generate_only_smoke_rerun":
        blockers.append(f"requested_future_scope_invalid:{data.get('requested_future_scope')!r}")
    if data.get("candidate_specs_inert") is not True:
        blockers.append(f"candidate_specs_inert_not_true:{data.get('candidate_specs_inert')!r}")
    if data.get("generate_only") is not True:
        blockers.append(f"generate_only_not_true:{data.get('generate_only')!r}")
    if data.get("compact_artifact_only") is not True:
        blockers.append(f"compact_artifact_only_not_true:{data.get('compact_artifact_only')!r}")
    if data.get("data_boundary") != "compact_flags_enums_counts_path_class_labels_only":
        blockers.append(f"data_boundary_invalid:{data.get('data_boundary')!r}")
    if data.get("runner_path") != "scripts/run_bfcl_exact_2id_generate_smoke_rerun.py":
        blockers.append(f"runner_path_invalid:{data.get('runner_path')!r}")
    if data.get("gate_checker_path") != "scripts/check_bfcl_exact_2id_generate_smoke_rerun_gate.py":
        blockers.append(f"gate_checker_path_invalid:{data.get('gate_checker_path')!r}")
    if data.get("future_output_artifact") != "outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_generate_smoke_rerun_compact.json":
        blockers.append(f"future_output_artifact_invalid:{data.get('future_output_artifact')!r}")
    stop_gates = data.get("stop_gates") if isinstance(data.get("stop_gates"), list) else []
    for gate in REQUIRED_STOP_GATES:
        if gate not in stop_gates:
            blockers.append(f"stop_gate_missing:{gate}")
    fields = data.get("allowed_future_compact_fields") if isinstance(data.get("allowed_future_compact_fields"), list) else []
    if fields != REQUIRED_COMPACT_FIELDS:
        missing = [field for field in REQUIRED_COMPACT_FIELDS if field not in fields]
        extra = [field for field in fields if field not in REQUIRED_COMPACT_FIELDS]
        if missing:
            blockers.append(f"missing_required_compact_fields:{missing!r}")
        if extra:
            blockers.append(f"extra_compact_fields:{extra!r}")
        if fields and not missing and not extra:
            blockers.append("compact_fields_order_invalid")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = load_packet(path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "bfcl_exact_2id_generate_smoke_rerun_gate_check",
        "packet_path": str(path),
        "bfcl_exact_2id_generate_smoke_rerun_gate_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "provider_request_authorized": packet.get("provider_request_authorized"),
        "bfcl_generate_authorized": packet.get("bfcl_generate_authorized"),
        "bfcl_smoke_authorized": packet.get("bfcl_smoke_authorized"),
        "signed_run_ids": packet.get("signed_run_ids"),
        "route_profile": packet.get("route_profile"),
        "route_model": packet.get("route_model"),
        "stop_gate_count": len(packet.get("stop_gates", [])) if isinstance(packet.get("stop_gates"), list) else 0,
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
        summary = {
            "report_scope": "bfcl_exact_2id_generate_smoke_rerun_gate_check",
            "bfcl_exact_2id_generate_smoke_rerun_gate_passed": False,
            "blockers": [f"load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_exact_2id_generate_smoke_rerun_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
