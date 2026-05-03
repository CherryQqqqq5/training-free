#!/usr/bin/env python3
"""Check the pending BFCL measurement-readiness gate packet."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_readiness_gate_packet.json")
FALSE_KEYS = (
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
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "openrouter_allowed",
    "gpt_5_2_active",
    "candidate_specs_activated",
    "scorer_feedback_enabled",
)
TRUE_KEYS = ("candidates_inert",)
REQUIRED_TOP_LEVEL = {
    "artifact_kind",
    "approval_status",
    "target_commit_for_measurement",
    "route_profile",
    "route_model",
    "evaluator_package",
    "bfcl_evaluator_checkout",
    "bfcl_version",
    "bfcl_data_version",
    "bfcl_case_set_protocol",
    "output_policy",
    "scorer_feedback_isolation",
    "reproducibility",
    "stop_gates",
    "target_commit_current_head_mismatch_justification",
}
REQUIRED_CONFIG_FILES = {
    "configs/bfcl_eval_protocol.yaml",
    "configs/runtime_bfcl_structured.yaml",
    "configs/runtime.yaml",
    "configs/bfcl_v4_phase1.env",
}
REQUIRED_STOP_GATES = {
    "route_drift",
    "missing_manifest",
    "raw_or_secret_leak",
    "candidate_activation",
    "scorer_feedback_contamination",
    "output_boundary_failure",
}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw_prompt|raw_case|raw_provider|provider_payload|provider_request_body|provider_response_body|headers|logs?|traces?|model_text|tool_args|tool_arguments|gold|reference|expected|scorer_diff|endpoint_value|api_key_value|secret_value|candidate_output)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|endpoint " + "value|api " + "key|provider " + "payload|raw " + "prompt|raw " + "case|scorer " + "diff|candidate " + "output|openrouter|gpt-4o"),
    re.IGNORECASE,
)


def _current_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


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
            if not (path and path[0] == "output_policy"):
                blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if path and path[-1] == "route_model" and value == "gpt-4.1":
                continue
            if path and path[-1] == "old_signed_model" and value == "gpt-5.2":
                continue
            if path and path[-1] == "bfcl_model_alias" and value == "gpt-4o-mini-2024-07-18-FC":
                continue
            if path and path[0] == "stop_gates":
                continue
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate(data: dict[str, Any], *, current_head: str | None = None) -> list[str]:
    blockers: list[str] = []
    current_head = current_head or _current_head()
    if data.get("artifact_kind") != "bfcl_measurement_readiness_gate_packet":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "pending":
        blockers.append(f"approval_status_not_pending:{data.get('approval_status')!r}")
    for key in FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    for key in TRUE_KEYS:
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true:{data.get(key)!r}")
    missing = sorted(REQUIRED_TOP_LEVEL - set(data))
    if missing:
        blockers.append(f"missing_required_fields:{missing!r}")
    if data.get("target_commit_for_measurement") != current_head:
        if data.get("target_commit_current_head_mismatch_justification") != "gate_artifact_commit_may_follow_frozen_target_without_behavior_or_execution_change":
            blockers.append(f"target_commit_not_current_head:{data.get('target_commit_for_measurement')!r}:{current_head}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    if data.get("old_signed_model") == "gpt-5.2" and data.get("old_signed_model_status") != "historical_superseded_inactive":
        blockers.append("gpt_5_2_not_historical")
    if data.get("measurement_scope_requested_for_future_review") != "current_system_baseline_measurement_only":
        blockers.append("measurement_scope_invalid")
    output_policy = data.get("output_policy") if isinstance(data.get("output_policy"), dict) else {}
    for key in ("commit_raw_traces", "commit_raw_prompts", "commit_provider_payloads", "commit_logs", "commit_bfcl_result_trees", "commit_endpoint_or_key_values"):
        if output_policy.get(key) is not False:
            blockers.append(f"output_policy_{key}_not_false:{output_policy.get(key)!r}")
    if output_policy.get("commit_compact_manifests") is not True or output_policy.get("commit_compact_metrics") is not True:
        blockers.append("compact_output_policy_not_true")
    reproducibility = data.get("reproducibility") if isinstance(data.get("reproducibility"), dict) else {}
    if reproducibility.get("commit") != data.get("target_commit_for_measurement"):
        blockers.append("reproducibility_commit_mismatch")
    if reproducibility.get("env_values_committed") is not False:
        blockers.append("env_values_committed_not_false")
    if not set(reproducibility.get("config_files", [])).issuperset(REQUIRED_CONFIG_FILES):
        blockers.append("reproducibility_config_files_missing")
    if not set(data.get("config_files", [])).issuperset(REQUIRED_CONFIG_FILES):
        blockers.append("config_files_missing")
    if not set(data.get("stop_gates", [])).issuperset(REQUIRED_STOP_GATES):
        blockers.append("stop_gates_missing")
    case_protocol = data.get("bfcl_case_set_protocol") if isinstance(data.get("bfcl_case_set_protocol"), dict) else {}
    if not case_protocol.get("baseline_freeze_categories"):
        blockers.append("bfcl_case_set_categories_missing")
    if data.get("generate_path_readiness_smoke", {}).get("measurement_evidence") is not False:
        blockers.append("smoke_claims_measurement_evidence")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    return {
        "report_scope": "bfcl_measurement_readiness_gate_check",
        "packet_path": str(path),
        "bfcl_measurement_readiness_gate_passed": not blockers,
        "approval_status": data.get("approval_status"),
        "target_commit_for_measurement": data.get("target_commit_for_measurement"),
        "route_profile": data.get("route_profile"),
        "route_model": data.get("route_model"),
        "performance_evidence": data.get("performance_evidence"),
        "authorized": data.get("authorized"),
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
        summary = {"report_scope": "bfcl_measurement_readiness_gate_check", "bfcl_measurement_readiness_gate_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_measurement_readiness_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
