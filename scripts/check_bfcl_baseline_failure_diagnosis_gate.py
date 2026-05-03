#!/usr/bin/env python3
"""Check the no-provider BFCL baseline failure diagnosis gate and diagnosis artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_baseline_failure_diagnosis_gate_packet.json")
DEFAULT_DIAGNOSIS = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_baseline_failure_plan_diagnosis.json")
EXECUTION_FALSE_KEYS = (
    "authorized",
    "provider_call_authorized",
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
DIAG_REQUIRED_FIELDS = {
    "no_provider",
    "no_bfcl_execution",
    "baseline_failure_summary_present",
    "command_template_present",
    "runner_script_present",
    "env_name_handoff_complete",
    "output_root_expected",
    "compact_metrics_expected",
    "compact_manifest_expected",
    "run_manifest_expected",
    "postcondition_checker_present",
    "sanitized_stage_codes_available",
    "missing_stage_observability",
    "suspected_failure_diagnosis_stage",
    "live_failure_telemetry_gate_recommended",
}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(secret_value|endpoint_value|api_key_value|provider_payload_value|prompt_text|case_content|trace_content|log_content|tool_argument_value|scorer_diff_content|candidate_output_content|raw_prompt|raw_case|raw_trace|raw_log)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|provider payload|prompt text|case content|trace content|log content|scorer diff|candidate output|openrouter|gpt-4o"),
    re.IGNORECASE,
)


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


def _scan(payload: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(payload):
        key = path[-1] if path else ""
        if key and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key == "route_model" and value == "gpt-4.1":
                continue
            if value == "gpt-4o-mini-2024-07-18-FC":
                continue
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return blockers


def validate_packet(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if packet.get("artifact_kind") != "bfcl_baseline_failure_diagnosis_gate_packet":
        blockers.append("packet_artifact_kind_invalid")
    if packet.get("approval_status") != "pending":
        blockers.append(f"packet_approval_status_not_pending:{packet.get('approval_status')!r}")
    if packet.get("measurement_kind") != "baseline_failure_plan_diagnosis_only":
        blockers.append("packet_measurement_kind_invalid")
    if packet.get("route_profile") != "novacode" or packet.get("route_model") != "gpt-4.1":
        blockers.append("packet_route_drift")
    if packet.get("no_provider") is not True or packet.get("no_bfcl_execution") is not True:
        blockers.append("packet_no_provider_or_no_bfcl_execution_not_true")
    if packet.get("candidates_inert") is not True:
        blockers.append("packet_candidates_inert_not_true")
    for key in EXECUTION_FALSE_KEYS:
        if packet.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{packet.get(key)!r}")
    if not packet.get("required_env_name_labels"):
        blockers.append("packet_env_labels_missing")
    if not packet.get("required_runner_stages"):
        blockers.append("packet_runner_stages_missing")
    blockers.extend(_scan(packet))
    return sorted(set(blockers))


def validate_diagnosis(diagnosis: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if diagnosis.get("artifact_kind") != "bfcl_baseline_failure_plan_diagnosis":
        blockers.append("diagnosis_artifact_kind_invalid")
    missing = sorted(DIAG_REQUIRED_FIELDS - set(diagnosis))
    if missing:
        blockers.append(f"diagnosis_missing_required_fields:{missing!r}")
    for key in ("no_provider", "no_bfcl_execution", "baseline_failure_summary_present", "command_template_present", "runner_script_present", "env_name_handoff_complete", "output_root_expected", "compact_metrics_expected", "compact_manifest_expected", "run_manifest_expected", "postcondition_checker_present"):
        if diagnosis.get(key) is not True:
            blockers.append(f"diagnosis_{key}_not_true:{diagnosis.get(key)!r}")
    for key in EXECUTION_FALSE_KEYS:
        if key in diagnosis and diagnosis.get(key) is not False:
            blockers.append(f"diagnosis_{key}_not_false:{diagnosis.get(key)!r}")
    if not diagnosis.get("suspected_failure_diagnosis_stage"):
        blockers.append("diagnosis_suspected_stage_missing")
    if diagnosis.get("env_value_material_present") is not False:
        blockers.append("diagnosis_env_value_material_present_not_false")
    if diagnosis.get("raw_outputs_committed") is not False:
        blockers.append("diagnosis_raw_outputs_committed_not_false")
    if diagnosis.get("secret_values_printed_or_artifacted") is not False:
        blockers.append("diagnosis_secret_values_printed_or_artifacted_not_false")
    blockers.extend(_scan(diagnosis))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, diagnosis_path: Path = DEFAULT_DIAGNOSIS) -> dict[str, Any]:
    packet = _load(packet_path)
    blockers = validate_packet(packet)
    diagnosis_present = diagnosis_path.exists()
    diagnosis: dict[str, Any] | None = None
    if diagnosis_present:
        diagnosis = _load(diagnosis_path)
        blockers.extend(validate_diagnosis(diagnosis))
    return {
        "report_scope": "bfcl_baseline_failure_diagnosis_gate_check",
        "packet_path": str(packet_path),
        "diagnosis_path": str(diagnosis_path),
        "bfcl_baseline_failure_diagnosis_gate_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "no_provider": packet.get("no_provider") if diagnosis is None else diagnosis.get("no_provider"),
        "no_bfcl_execution": packet.get("no_bfcl_execution") if diagnosis is None else diagnosis.get("no_bfcl_execution"),
        "suspected_failure_diagnosis_stage": None if diagnosis is None else diagnosis.get("suspected_failure_diagnosis_stage"),
        "live_failure_telemetry_gate_recommended": None if diagnosis is None else diagnosis.get("live_failure_telemetry_gate_recommended"),
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
        summary = {"report_scope": "bfcl_baseline_failure_diagnosis_gate_check", "bfcl_baseline_failure_diagnosis_gate_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_baseline_failure_diagnosis_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
