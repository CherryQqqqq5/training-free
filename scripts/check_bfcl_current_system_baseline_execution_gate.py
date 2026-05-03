#!/usr/bin/env python3
"""Check the BFCL current-system baseline execution gate."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_execution_gate_packet.json")
EXECUTION_AUTH_KEYS = (
    "authorized",
    "provider_call_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "full_baseline_authorized",
)
ALWAYS_FALSE_KEYS = (
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
    "measurement_kind",
    "target_commit_for_measurement",
    "target_commit_current_head_mismatch_justification",
    "route_profile",
    "route_model",
    "evaluator_package",
    "bfcl_version",
    "bfcl_evaluator_checkout",
    "case_scope_protocol",
    "runner_command_template",
    "output_roots",
    "compact_manifest_schema",
    "compact_metrics_schema",
    "output_boundary_policy",
    "scorer_feedback_isolation",
    "stop_gates",
    "claim_policy",
}
REQUIRED_STOP_GATES = {
    "route_drift",
    "candidate_activation",
    "raw_or_secret_leak",
    "manifest_mismatch",
    "scorer_feedback_contamination",
    "missing_metrics_or_manifest",
    "output_boundary_failure",
}
REQUIRED_CATEGORIES = {
    "simple",
    "multiple",
    "parallel",
    "parallel_multiple",
    "multi_turn_base",
    "multi_turn_miss_func",
    "multi_turn_miss_param",
    "multi_turn_long_context",
}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(secret_value|endpoint_value|api_key_value|provider_payload_value|prompt_text|case_content|trace_content|log_content|tool_argument_value|scorer_diff_content|candidate_output_content)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|endpoint " + "value|api " + "key|provider " + "payload|prompt " + "text|case " + "content|scorer " + "diff|candidate " + "output|openrouter|gpt-4o"),
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
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if path and path[-1] == "route_model" and value == "gpt-4.1":
                continue
            if path and path[-1] == "old_signed_model" and value == "gpt-5.2":
                continue
            if path and path[-1] == "bfcl_model_alias" and value == "gpt-4o-mini-2024-07-18-FC":
                continue
            if path and path[0] in {"runner_command_template", "stop_gates"}:
                continue
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate(data: dict[str, Any], *, current_head: str | None = None) -> list[str]:
    blockers: list[str] = []
    current_head = current_head or _current_head()
    if data.get("artifact_kind") != "bfcl_current_system_baseline_execution_gate_packet":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    approval_status = data.get("approval_status")
    if approval_status not in {"pending", "approved"}:
        blockers.append(f"approval_status_invalid:{approval_status!r}")
    execution_expected = approval_status == "approved"
    for key in EXECUTION_AUTH_KEYS:
        if data.get(key) is not execution_expected:
            blockers.append(f"{key}_not_{str(execution_expected).lower()}:{data.get(key)!r}")
    for key in ALWAYS_FALSE_KEYS:
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
    if data.get("measurement_kind") != "current_system_baseline_only":
        blockers.append(f"measurement_kind_invalid:{data.get('measurement_kind')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    if data.get("old_signed_model") == "gpt-5.2" and data.get("old_signed_model_status") != "historical_superseded_inactive":
        blockers.append("gpt_5_2_not_historical")
    case_scope = data.get("case_scope_protocol") if isinstance(data.get("case_scope_protocol"), dict) else {}
    if case_scope.get("scope_kind") != "baseline_freeze_categories_from_configs":
        blockers.append("case_scope_kind_invalid")
    if not set(case_scope.get("categories", [])).issuperset(REQUIRED_CATEGORIES):
        blockers.append("case_scope_categories_missing")
    if case_scope.get("run_ids_manifest_required") is not False:
        blockers.append("run_ids_manifest_required_not_false")
    command = data.get("runner_command_template") if isinstance(data.get("runner_command_template"), list) else []
    if "scripts/run_bfcl_v4_baseline.sh" not in command:
        blockers.append("baseline_runner_missing")
    joined = " ".join(str(item) for item in command)
    if "novacode" not in joined or "gpt-4.1" not in joined:
        blockers.append("runner_route_not_frozen")
    if "outputs/bfcl_v4/current_system_baseline" not in joined:
        blockers.append("runner_output_root_not_frozen")
    roots = data.get("output_roots") if isinstance(data.get("output_roots"), dict) else {}
    for key in ("run_root", "bfcl_root", "artifact_dir", "compact_manifest", "compact_metrics"):
        if not roots.get(key):
            blockers.append(f"output_root_missing:{key}")
    manifest_schema = data.get("compact_manifest_schema") if isinstance(data.get("compact_manifest_schema"), dict) else {}
    metrics_schema = data.get("compact_metrics_schema") if isinstance(data.get("compact_metrics_schema"), dict) else {}
    if not manifest_schema.get("required_fields") or manifest_schema.get("raw_outputs_committed") is not False:
        blockers.append("compact_manifest_schema_invalid")
    if not metrics_schema.get("required_fields") or metrics_schema.get("performance_evidence") is not False:
        blockers.append("compact_metrics_schema_invalid")
    boundary = data.get("output_boundary_policy") if isinstance(data.get("output_boundary_policy"), dict) else {}
    for key, value in boundary.items():
        if key in {"commit_compact_manifest", "commit_compact_metrics"}:
            if value is not True:
                blockers.append(f"boundary_{key}_not_true")
        elif value is not False:
            blockers.append(f"boundary_{key}_not_false")
    if data.get("scorer_feedback_isolation") != "baseline_feedback_may_not_update_implementation_or_candidate_without_later_gate":
        blockers.append("scorer_feedback_isolation_invalid")
    if not set(data.get("stop_gates", [])).issuperset(REQUIRED_STOP_GATES):
        blockers.append("stop_gates_missing")
    claims = data.get("claim_policy") if isinstance(data.get("claim_policy"), dict) else {}
    for key in ("baseline_current_system_measurement_only", "not_candidate_comparison", "not_performance_evidence", "not_3pp_claim", "not_huawei_readiness", "not_sota_claim"):
        if claims.get(key) is not True:
            blockers.append(f"claim_policy_{key}_not_true")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    return {
        "report_scope": "bfcl_current_system_baseline_execution_gate_check",
        "packet_path": str(path),
        "bfcl_current_system_baseline_execution_gate_passed": not blockers,
        "approval_status": data.get("approval_status"),
        "authorized": data.get("authorized"),
        "measurement_kind": data.get("measurement_kind"),
        "target_commit_for_measurement": data.get("target_commit_for_measurement"),
        "route_profile": data.get("route_profile"),
        "route_model": data.get("route_model"),
        "performance_evidence": data.get("performance_evidence"),
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
        summary = {"report_scope": "bfcl_current_system_baseline_execution_gate_check", "bfcl_current_system_baseline_execution_gate_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_current_system_baseline_execution_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
