#!/usr/bin/env python3
"""Check the no-provider BFCL generate failure diagnosis gate and artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_generate_failure_diagnosis_gate_packet.json")
DEFAULT_DIAGNOSIS = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_generate_failure_plan_diagnosis.json")
FALSE_KEYS = (
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
)
REQUIRED_DIAGNOSIS_FIELDS = [
    "prior_failed_stage",
    "prior_stage_failure_class",
    "generate_command_template_present",
    "generate_command_category_scope_label",
    "generate_env_handoff_complete",
    "proxy_preflight_stage_completed",
    "provider_call_started_prior",
    "generate_output_root_expected",
    "generate_result_count_observable",
    "generate_error_class_observable",
    "missing_generate_stage_observability_fields",
    "suspected_generate_failure_plan_stage",
    "next_gate_recommended",
]
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(secret_value|endpoint_value|api_key_value|raw_prompt|raw_case|raw_log|raw_trace|provider_payload|prompt_text|case_content|trace_content|log_content|tool_argument_value|scorer_diff|candidate_output|gold_value|reference_value|expected_value)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|endpoint value|api key|provider payload|raw prompt|raw case|raw log|raw trace|scorer diff|candidate output|gold reference value|openrouter|gpt-4o"),
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
        if key and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key == "route_model" and value == "gpt-4.1":
                continue
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if packet.get("artifact_kind") != "bfcl_generate_failure_diagnosis_gate_packet":
        blockers.append(f"packet_artifact_kind_invalid:{packet.get('artifact_kind')!r}")
    if packet.get("approval_status") not in {"pending", "prepared"}:
        blockers.append(f"packet_approval_status_invalid:{packet.get('approval_status')!r}")
    if packet.get("route_profile") != "novacode" or packet.get("route_model") != "gpt-4.1":
        blockers.append("packet_route_drift")
    if packet.get("no_provider") is not True or packet.get("no_bfcl_execution") is not True:
        blockers.append("packet_no_provider_or_no_bfcl_execution_not_true")
    for key in FALSE_KEYS:
        if packet.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{packet.get(key)!r}")
    fields = packet.get("allowed_diagnosis_fields")
    if fields != REQUIRED_DIAGNOSIS_FIELDS:
        blockers.append("packet_allowed_diagnosis_fields_invalid")
    blockers.extend(_scan(packet))
    return sorted(set(blockers))


def validate_diagnosis(diagnosis: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if diagnosis.get("artifact_kind") != "bfcl_generate_failure_plan_diagnosis":
        blockers.append(f"diagnosis_artifact_kind_invalid:{diagnosis.get('artifact_kind')!r}")
    missing = [field for field in REQUIRED_DIAGNOSIS_FIELDS if field not in diagnosis]
    extra = [field for field in diagnosis if field not in {"artifact_kind", *REQUIRED_DIAGNOSIS_FIELDS}]
    if missing:
        blockers.append(f"diagnosis_missing_fields:{missing!r}")
    if extra:
        blockers.append(f"diagnosis_extra_fields:{extra!r}")
    for key in (
        "generate_command_template_present",
        "generate_env_handoff_complete",
        "proxy_preflight_stage_completed",
        "provider_call_started_prior",
        "generate_output_root_expected",
    ):
        if diagnosis.get(key) is not True:
            blockers.append(f"diagnosis_{key}_not_true:{diagnosis.get(key)!r}")
    for key in ("generate_result_count_observable", "generate_error_class_observable"):
        if diagnosis.get(key) is not False:
            blockers.append(f"diagnosis_{key}_not_false:{diagnosis.get(key)!r}")
    if diagnosis.get("prior_failed_stage") != "bfcl_generate":
        blockers.append(f"diagnosis_prior_failed_stage_invalid:{diagnosis.get('prior_failed_stage')!r}")
    if not diagnosis.get("suspected_generate_failure_plan_stage"):
        blockers.append("suspected_generate_failure_plan_stage_missing")
    if not diagnosis.get("next_gate_recommended"):
        blockers.append("next_gate_recommended_missing")
    missing_obs = diagnosis.get("missing_generate_stage_observability_fields")
    if not isinstance(missing_obs, list) or not missing_obs:
        blockers.append("missing_generate_stage_observability_fields_empty")
    blockers.extend(_scan(diagnosis))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, diagnosis_path: Path = DEFAULT_DIAGNOSIS) -> dict[str, Any]:
    packet = _load(packet_path)
    diagnosis = _load(diagnosis_path)
    blockers = validate_packet(packet) + validate_diagnosis(diagnosis)
    return {
        "report_scope": "bfcl_generate_failure_diagnosis_gate_check",
        "packet_path": str(packet_path),
        "diagnosis_path": str(diagnosis_path),
        "bfcl_generate_failure_diagnosis_gate_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "prior_failed_stage": diagnosis.get("prior_failed_stage"),
        "suspected_generate_failure_plan_stage": diagnosis.get("suspected_generate_failure_plan_stage"),
        "next_gate_recommended": diagnosis.get("next_gate_recommended"),
        "blockers": sorted(set(blockers)),
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
        summary = {"report_scope": "bfcl_generate_failure_diagnosis_gate_check", "bfcl_generate_failure_diagnosis_gate_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_generate_failure_diagnosis_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
