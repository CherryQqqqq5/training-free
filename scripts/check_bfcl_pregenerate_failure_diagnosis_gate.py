#!/usr/bin/env python3
"""Check no-provider BFCL pre-generate failure diagnosis gate and artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_pregenerate_failure_diagnosis_gate_packet.json")
DEFAULT_DIAGNOSIS = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_pregenerate_failure_plan_diagnosis.json")
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
    "prior_suspected_stage",
    "command_template_present",
    "command_shape_label",
    "category_scope_label",
    "category_arg_shape_label",
    "category_arg_validation_label",
    "model_alias_label",
    "runtime_config_path_present",
    "rules_path_present",
    "bfcl_checkout_path_present",
    "bfcl_package_label",
    "env_presence_keys_label",
    "profile_sourcing_inspection_label",
    "proxy_preflight_dependency_label",
    "stage_marker_boundary_label",
    "pre_generate_failure_candidate_class",
    "missing_observability_fields",
    "next_gate_recommended",
]
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(secret_value|endpoint_value|api_key_value|raw_prompt|raw_case|raw_log|raw_trace|raw_provider|provider_payload|prompt_text|case_content|trace_content|log_content|tool_argument_value|scorer_diff|candidate_output|gold_value|reference_value|expected_value)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|endpoint value|api key value|provider payload|raw prompt|raw case|raw log|raw trace|scorer diff|candidate output|openrouter|gpt-4o"),
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
            if key == "route_model" and value == "gpt-4.1":
                continue
            if parent == "forbidden_scope":
                continue
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if packet.get("artifact_kind") != "bfcl_pregenerate_failure_diagnosis_gate_packet":
        blockers.append(f"packet_artifact_kind_invalid:{packet.get('artifact_kind')!r}")
    if packet.get("approval_status") not in {"prepared", "pending"}:
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
    if diagnosis.get("artifact_kind") != "bfcl_pregenerate_failure_plan_diagnosis":
        blockers.append(f"diagnosis_artifact_kind_invalid:{diagnosis.get('artifact_kind')!r}")
    missing = [field for field in REQUIRED_DIAGNOSIS_FIELDS if field not in diagnosis]
    extra = [field for field in diagnosis if field not in {"artifact_kind", *REQUIRED_DIAGNOSIS_FIELDS}]
    if missing:
        blockers.append(f"diagnosis_missing_fields:{missing!r}")
    if extra:
        blockers.append(f"diagnosis_extra_fields:{extra!r}")
    if diagnosis.get("prior_suspected_stage") != "pre_generate_failure":
        blockers.append(f"prior_suspected_stage_invalid:{diagnosis.get('prior_suspected_stage')!r}")
    if diagnosis.get("command_template_present") is not True:
        blockers.append("command_template_present_not_true")
    for key in ("runtime_config_path_present", "rules_path_present", "bfcl_checkout_path_present"):
        if diagnosis.get(key) is not True:
            blockers.append(f"{key}_not_true:{diagnosis.get(key)!r}")
    if not diagnosis.get("pre_generate_failure_candidate_class"):
        blockers.append("pre_generate_failure_candidate_class_missing")
    missing_obs = diagnosis.get("missing_observability_fields")
    if not isinstance(missing_obs, list) or not missing_obs:
        blockers.append("missing_observability_fields_empty")
    if not diagnosis.get("next_gate_recommended"):
        blockers.append("next_gate_recommended_missing")
    blockers.extend(_scan(diagnosis))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, diagnosis_path: Path = DEFAULT_DIAGNOSIS) -> dict[str, Any]:
    packet = _load(packet_path)
    diagnosis = _load(diagnosis_path)
    blockers = sorted(set(validate_packet(packet) + validate_diagnosis(diagnosis)))
    return {
        "report_scope": "bfcl_pregenerate_failure_diagnosis_gate_check",
        "packet_path": str(packet_path),
        "diagnosis_path": str(diagnosis_path),
        "bfcl_pregenerate_failure_diagnosis_gate_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "prior_suspected_stage": diagnosis.get("prior_suspected_stage"),
        "pre_generate_failure_candidate_class": diagnosis.get("pre_generate_failure_candidate_class"),
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
        summary = {"report_scope": "bfcl_pregenerate_failure_diagnosis_gate_check", "bfcl_pregenerate_failure_diagnosis_gate_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_pregenerate_failure_diagnosis_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
