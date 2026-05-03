#!/usr/bin/env python3
"""Check no-live BFCL proxy/preflight failure diagnosis gate and artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_preflight_failure_diagnosis_gate_packet.json")
DEFAULT_DIAGNOSIS = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_preflight_failure_plan_diagnosis.json")
FALSE_KEYS = (
    "authorized",
    "provider_request_authorized",
    "proxy_live_preflight_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "full_baseline_authorized",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
)
REQUIRED_DIAGNOSIS_FIELDS = [
    "prior_suspected_substage",
    "start_proxy_completion_semantics_label",
    "proxy_process_start_command_shape",
    "proxy_port_binding_label",
    "proxy_health_probe_command_shape",
    "proxy_health_probe_target_label",
    "proxy_health_expected_status_class",
    "preflight_command_shape_label",
    "preflight_request_target_label",
    "preflight_expected_response_shape_label",
    "preflight_timeout_label",
    "local_proxy_vs_provider_boundary_label",
    "route_profile_label",
    "route_model_label",
    "provider_not_observed_prior",
    "suspected_proxy_preflight_failure_class",
    "missing_proxy_preflight_observability_fields",
    "next_gate_recommended",
]
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(secret_value|endpoint_value|api_key_value|raw_prompt|raw_case|raw_log|raw_trace|raw_provider|provider_payload|raw_result_tree|prompt_text|case_content|trace_content|log_content|tool_argument_value|scorer_diff|candidate_output|gold_value|reference_value|expected_value|endpoint_literal|key_literal)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|endpoint value|api key value|provider payload|raw prompt|raw case|raw log|raw trace|raw result tree|scorer diff|candidate output|openrouter|gpt-4o"),
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
        parent = path[-2] if len(path) > 1 else ""
        if key and parent != "forbidden_scope" and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key in {"route_model", "route_model_label"} and value == "gpt-4.1":
                continue
            if parent == "forbidden_scope":
                continue
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if packet.get("artifact_kind") != "bfcl_proxy_preflight_failure_diagnosis_gate_packet":
        blockers.append(f"packet_artifact_kind_invalid:{packet.get('artifact_kind')!r}")
    if packet.get("approval_status") not in {"prepared", "pending"}:
        blockers.append(f"packet_approval_status_invalid:{packet.get('approval_status')!r}")
    if packet.get("route_profile") != "novacode" or packet.get("route_model") != "gpt-4.1":
        blockers.append("packet_route_drift")
    if packet.get("no_provider") is not True or packet.get("no_live_preflight") is not True or packet.get("no_bfcl_execution") is not True:
        blockers.append("packet_no_live_scope_not_true")
    if packet.get("candidate_specs_inert") is not True:
        blockers.append("packet_candidate_specs_inert_not_true")
    if packet.get("diagnosis_scope") != "no_live_proxy_preflight_plan_inspection_only":
        blockers.append(f"packet_diagnosis_scope_invalid:{packet.get('diagnosis_scope')!r}")
    for key in FALSE_KEYS:
        if packet.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{packet.get(key)!r}")
    if packet.get("allowed_diagnosis_fields") != REQUIRED_DIAGNOSIS_FIELDS:
        blockers.append("packet_allowed_diagnosis_fields_invalid")
    forbidden_scope = set(packet.get("forbidden_scope", [])) if isinstance(packet.get("forbidden_scope"), list) else set()
    for required in ("provider_call", "live_preflight", "bfcl_generate", "bfcl_evaluate", "scorer", "full_baseline", "candidate_activation", "candidate_jsonl_or_pool", "performance_or_3pp_or_huawei_claim"):
        if required not in forbidden_scope:
            blockers.append(f"forbidden_scope_missing:{required}")
    blockers.extend(_scan(packet))
    return sorted(set(blockers))


def validate_diagnosis(diagnosis: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if diagnosis.get("artifact_kind") != "bfcl_proxy_preflight_failure_plan_diagnosis":
        blockers.append(f"diagnosis_artifact_kind_invalid:{diagnosis.get('artifact_kind')!r}")
    missing = [field for field in REQUIRED_DIAGNOSIS_FIELDS if field not in diagnosis]
    extra = [field for field in diagnosis if field not in {"artifact_kind", *REQUIRED_DIAGNOSIS_FIELDS}]
    if missing:
        blockers.append(f"diagnosis_missing_fields:{missing!r}")
    if extra:
        blockers.append(f"diagnosis_extra_fields:{extra!r}")
    if diagnosis.get("prior_suspected_substage") != "preflight_not_completed":
        blockers.append(f"prior_suspected_substage_invalid:{diagnosis.get('prior_suspected_substage')!r}")
    if diagnosis.get("route_profile_label") != "novacode" or diagnosis.get("route_model_label") != "gpt-4.1":
        blockers.append("diagnosis_route_drift")
    if diagnosis.get("provider_not_observed_prior") is not True:
        blockers.append("provider_not_observed_prior_not_true")
    for key in (
        "start_proxy_completion_semantics_label",
        "proxy_process_start_command_shape",
        "proxy_health_probe_command_shape",
        "preflight_command_shape_label",
        "preflight_request_target_label",
        "suspected_proxy_preflight_failure_class",
    ):
        if not diagnosis.get(key):
            blockers.append(f"{key}_missing")
    missing_obs = diagnosis.get("missing_proxy_preflight_observability_fields")
    if not isinstance(missing_obs, list) or not missing_obs:
        blockers.append("missing_proxy_preflight_observability_fields_empty")
    if not diagnosis.get("next_gate_recommended"):
        blockers.append("next_gate_recommended_missing")
    blockers.extend(_scan(diagnosis))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, diagnosis_path: Path = DEFAULT_DIAGNOSIS) -> dict[str, Any]:
    packet = _load(packet_path)
    diagnosis = _load(diagnosis_path)
    blockers = sorted(set(validate_packet(packet) + validate_diagnosis(diagnosis)))
    return {
        "report_scope": "bfcl_proxy_preflight_failure_diagnosis_gate_check",
        "packet_path": str(packet_path),
        "diagnosis_path": str(diagnosis_path),
        "bfcl_proxy_preflight_failure_diagnosis_gate_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "prior_suspected_substage": diagnosis.get("prior_suspected_substage"),
        "suspected_proxy_preflight_failure_class": diagnosis.get("suspected_proxy_preflight_failure_class"),
        "next_gate_recommended": diagnosis.get("next_gate_recommended"),
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--diagnosis", type=Path, default=DEFAULT_DIAGNOSIS)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.diagnosis)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_proxy_preflight_failure_diagnosis_gate_check", "bfcl_proxy_preflight_failure_diagnosis_gate_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_proxy_preflight_failure_diagnosis_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
