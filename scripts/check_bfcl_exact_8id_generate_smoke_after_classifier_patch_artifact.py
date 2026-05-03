#!/usr/bin/env python3
"""Check compact exact 8-ID BFCL generate-only smoke after classifier patch artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_exact_8id_generate_smoke_after_classifier_patch_gate import SIGNED_IDS  # noqa: E402

DEFAULT_ARTIFACT = Path(
    "outputs/artifacts/stage1_bfcl_acceptance/"
    "bfcl_exact_8id_generate_smoke_after_classifier_patch_compact.json"
)
FALSE_KEYS = (
    "bfcl_evaluate_executed",
    "scorer_executed",
    "full_baseline_executed",
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
)
TRUE_KEYS = ("provider_request_executed", "bfcl_generate_executed", "bfcl_smoke_executed", "candidate_specs_inert")
REQUIRED_MAP_KEYS = (
    "per_id_compact_status",
    "per_id_empty_model_response_detected",
    "per_id_protocol_error_detected",
    "per_id_generated_detected",
    "per_id_result_present",
)
ALLOWED_STATUSES = {"generated", "empty_model_response", "protocol_error", "missing_result", "generate_failed", "unknown_compact_status"}
ALLOWED_STOP_GATES = {"none", "empty_model_response", "protocol_error", "unknown_compact_status", "missing_result", "bfcl_generate_failed", "extra_or_missing_id"}
ALLOWED_STAGES = {"none", "generate_failed", "empty_model_response", "protocol_error", "unknown_compact_status_after_classifier_patch", "result_materialization_missing", "run_id_set_mismatch"}
RAW_KEY_RE = re.compile(r"(^|_)(raw|prompt|case_content|provider_payload|provider_request_body|provider_response_body|headers|logs?|traces?|model_text|tool_args|tool_arguments|gold|reference|expected|scorer_diff|endpoint|api_key|secret|candidate_output|path)(_|$)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|provider " + "payload|raw " + "prompt|raw " + "case|scorer " + "diff|candidate " + "output"), re.IGNORECASE)


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
        if key and RAW_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_exact_8id_generate_smoke_after_classifier_patch_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("signed_run_ids") != SIGNED_IDS:
        blockers.append(f"signed_run_ids_invalid:{data.get('signed_run_ids')!r}")
    if data.get("run_id_count") != 8:
        blockers.append(f"run_id_count_invalid:{data.get('run_id_count')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    for key in TRUE_KEYS:
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true:{data.get(key)!r}")
    for key in FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    for key in REQUIRED_MAP_KEYS:
        value = data.get(key)
        if not isinstance(value, dict):
            blockers.append(f"{key}_not_object")
            continue
        if set(value.keys()) != set(SIGNED_IDS):
            blockers.append(f"{key}_ids_invalid:{sorted(value.keys())!r}")
    statuses = data.get("per_id_compact_status") if isinstance(data.get("per_id_compact_status"), dict) else {}
    for run_id, status in statuses.items():
        if status not in ALLOWED_STATUSES:
            blockers.append(f"status_invalid:{run_id}:{status!r}")
    stop_gate = data.get("stop_gate_triggered")
    if stop_gate not in ALLOWED_STOP_GATES:
        blockers.append(f"stop_gate_triggered_invalid:{stop_gate!r}")
    stage = data.get("suspected_remaining_stage")
    if stage not in ALLOWED_STAGES:
        blockers.append(f"suspected_remaining_stage_invalid:{stage!r}")
    smoke_passed = data.get("smoke_passed") is True
    any_empty = any(bool(v) for v in (data.get("per_id_empty_model_response_detected") or {}).values())
    any_protocol = any(bool(v) for v in (data.get("per_id_protocol_error_detected") or {}).values())
    any_unknown = any(status == "unknown_compact_status" for status in statuses.values())
    all_present = all(bool(v) for v in (data.get("per_id_result_present") or {}).values()) if isinstance(data.get("per_id_result_present"), dict) else False
    all_generated = all(status == "generated" for status in statuses.values()) if statuses else False
    if smoke_passed:
        if stop_gate != "none" or stage != "none":
            blockers.append("smoke_passed_stage_mismatch")
        if any_empty or any_protocol or any_unknown or not all_present or not all_generated:
            blockers.append("smoke_passed_status_mismatch")
    else:
        if stop_gate == "none":
            blockers.append("failed_smoke_missing_stop_gate")
        if any_protocol and stop_gate != "protocol_error":
            blockers.append("protocol_error_stop_gate_mismatch")
        if any_empty and stop_gate != "empty_model_response":
            blockers.append("empty_model_response_stop_gate_mismatch")
        if any_unknown and stop_gate != "unknown_compact_status":
            blockers.append("unknown_compact_status_stop_gate_mismatch")
        if not all_present and stop_gate != "missing_result":
            blockers.append("missing_result_stop_gate_mismatch")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    return {
        "report_scope": "bfcl_exact_8id_generate_smoke_after_classifier_patch_artifact_check",
        "artifact_path": str(path),
        "bfcl_exact_8id_generate_smoke_after_classifier_patch_artifact_passed": not blockers,
        "signed_run_ids": data.get("signed_run_ids"),
        "per_id_compact_status": data.get("per_id_compact_status"),
        "stop_gate_triggered": data.get("stop_gate_triggered"),
        "smoke_passed": data.get("smoke_passed"),
        "suspected_remaining_stage": data.get("suspected_remaining_stage"),
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_exact_8id_generate_smoke_after_classifier_patch_artifact_check", "bfcl_exact_8id_generate_smoke_after_classifier_patch_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_exact_8id_generate_smoke_after_classifier_patch_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
