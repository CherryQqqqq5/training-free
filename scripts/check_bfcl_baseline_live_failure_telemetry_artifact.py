#!/usr/bin/env python3
"""Check compact sanitized BFCL baseline live failure telemetry artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from scripts.check_bfcl_baseline_live_failure_telemetry_gate import REQUIRED_COMPACT_FIELDS

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_baseline_live_failure_telemetry_compact.json")
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw_logs?|raw_traces?|raw_prompts?|raw_cases?|raw_provider_payloads?|endpoint_values?|key_values?|api_key_values?|secret_values?|scorer_diffs?|candidate_outputs?|provider_payload_value|prompt_text|case_content|trace_content|log_content|tool_argument_value)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|endpoint value|key value|api key|provider payload|raw prompt|raw case|raw log|raw trace|scorer diff|candidate output|openrouter|gpt-4o"),
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


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_baseline_live_failure_telemetry_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("measurement_kind") != "sanitized_baseline_live_failure_telemetry":
        blockers.append(f"measurement_kind_invalid:{data.get('measurement_kind')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
        "scorer_feedback_used",
        "raw_outputs_committed",
    ):
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    records = data.get("records")
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        blockers.append("records_invalid")
        record: dict[str, Any] = {}
    else:
        record = records[0]
    missing = [field for field in REQUIRED_COMPACT_FIELDS if field not in record]
    extra = [field for field in record if field not in REQUIRED_COMPACT_FIELDS]
    if missing:
        blockers.append(f"missing_required_fields:{missing!r}")
    if extra:
        blockers.append(f"extra_fields:{extra!r}")
    if record:
        if record.get("baseline_command_executed") is not True:
            blockers.append("baseline_command_executed_not_true")
        if record.get("baseline_exit_code_class") not in {"zero", "nonzero_1", "nonzero_other"}:
            blockers.append(f"baseline_exit_code_class_invalid:{record.get('baseline_exit_code_class')!r}")
        if not record.get("last_started_stage"):
            blockers.append("last_started_stage_missing")
        if not record.get("failed_stage"):
            blockers.append("failed_stage_missing")
        if not record.get("stage_failure_class"):
            blockers.append("stage_failure_class_missing")
        if record.get("raw_outputs_removed") is not True:
            blockers.append("raw_outputs_removed_not_true")
        if record.get("run_root_present") is not False:
            blockers.append("run_root_present_not_false_after_cleanup")
        if record.get("route_profile") != "novacode" or record.get("route_model") != "gpt-4.1":
            blockers.append("record_route_drift")
        if record.get("candidate_specs_inert") is not True:
            blockers.append("candidate_specs_inert_not_true")
        if record.get("scorer_feedback_used") is not False:
            blockers.append("scorer_feedback_used_not_false")
        if record.get("performance_evidence") is not False:
            blockers.append("record_performance_evidence_not_false")
        if not record.get("stop_gate_triggered"):
            blockers.append("stop_gate_triggered_missing")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    record = data.get("records", [{}])[0] if isinstance(data.get("records"), list) and data.get("records") else {}
    return {
        "report_scope": "bfcl_baseline_live_failure_telemetry_artifact_check",
        "artifact_path": str(path),
        "bfcl_baseline_live_failure_telemetry_artifact_passed": not blockers,
        "baseline_exit_code_class": record.get("baseline_exit_code_class") if isinstance(record, dict) else None,
        "last_started_stage": record.get("last_started_stage") if isinstance(record, dict) else None,
        "last_completed_stage": record.get("last_completed_stage") if isinstance(record, dict) else None,
        "failed_stage": record.get("failed_stage") if isinstance(record, dict) else None,
        "stage_failure_class": record.get("stage_failure_class") if isinstance(record, dict) else None,
        "stop_gate_triggered": record.get("stop_gate_triggered") if isinstance(record, dict) else None,
        "raw_outputs_removed": record.get("raw_outputs_removed") if isinstance(record, dict) else None,
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
        summary = {"report_scope": "bfcl_baseline_live_failure_telemetry_artifact_check", "bfcl_baseline_live_failure_telemetry_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_baseline_live_failure_telemetry_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
