#!/usr/bin/env python3
"""Check compact sanitized BFCL generate failure telemetry artifact."""

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

from scripts.check_bfcl_generate_failure_telemetry_gate import REQUIRED_COMPACT_FIELDS

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_generate_failure_telemetry_compact.json")
PROVIDER_STATUS_CLASSES = {"2xx", "3xx", "4xx", "5xx", "timeout", "proxy_unreachable", "connection_error", "not_observed", "unknown_compact"}
PROVIDER_COMPLETION_CLASSES = {"completed_2xx", "completed_non2xx", "timeout", "connection_error", "not_observed", "unknown_compact"}
BFCL_EXCEPTION_CLASSES = {"command_config_error", "import_error", "runtime_exception", "timeout", "result_path_error", "proxy_or_provider_error", "unknown_nonzero", "none_observed"}
BFCL_EXCEPTION_STAGE_LABELS = {"generate_command_setup", "proxy_request", "result_materialization", "unknown_generate", "none_observed"}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw_prompts?|raw_bfcl_case_content|raw_cases?|raw_commands?|raw_provider_requests?|raw_provider_responses?|raw_response_headers?|raw_logs?|raw_traces?|raw_model_output_text|raw_tool_args?|raw_result_trees?|endpoint_values?|key_values?|api_key_values?|secret_values?|scorer_diffs?|candidate_outputs?|provider_payload_value|prompt_text|case_content|trace_content|log_content|tool_argument_value|gold_value|reference_value|expected_value)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|endpoint value|key value|api key|provider payload|raw prompt|raw case|raw command|raw log|raw trace|raw model output|raw tool arg|raw result tree|scorer diff|candidate output|openrouter|gpt-4o"),
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
    if data.get("artifact_kind") != "bfcl_generate_failure_telemetry_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("measurement_kind") != "sanitized_bfcl_generate_failure_telemetry":
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
        if not isinstance(record.get("generate_exact_exit_code"), int):
            blockers.append("generate_exact_exit_code_not_int")
        if record.get("generate_exit_code_class") not in {"zero", "nonzero_1", "nonzero_other"}:
            blockers.append(f"generate_exit_code_class_invalid:{record.get('generate_exit_code_class')!r}")
        if record.get("route_profile") != "novacode" or record.get("route_model") != "gpt-4.1":
            blockers.append("record_route_drift")
        if record.get("provider_status_class_during_generate") not in PROVIDER_STATUS_CLASSES:
            blockers.append(f"provider_status_class_invalid:{record.get('provider_status_class_during_generate')!r}")
        if record.get("provider_call_completed_class") not in PROVIDER_COMPLETION_CLASSES:
            blockers.append(f"provider_call_completed_class_invalid:{record.get('provider_call_completed_class')!r}")
        if record.get("provider_call_started") is False and (record.get("provider_status_class_during_generate") != "not_observed" or record.get("provider_call_completed_class") != "not_observed"):
            blockers.append("provider_not_observed_labels_inconsistent")
        if record.get("bfcl_cli_exception_class") not in BFCL_EXCEPTION_CLASSES:
            blockers.append(f"bfcl_cli_exception_class_invalid:{record.get('bfcl_cli_exception_class')!r}")
        if record.get("bfcl_cli_exception_stage_label") not in BFCL_EXCEPTION_STAGE_LABELS:
            blockers.append(f"bfcl_cli_exception_stage_label_invalid:{record.get('bfcl_cli_exception_stage_label')!r}")
        if record.get("bfcl_evaluate_started") is not False:
            blockers.append("bfcl_evaluate_started_not_false")
        if record.get("scorer_started") is not False:
            blockers.append("scorer_started_not_false")
        if record.get("raw_outputs_removed") is not True:
            blockers.append("raw_outputs_removed_not_true")
        if record.get("candidate_specs_inert") is not True:
            blockers.append("candidate_specs_inert_not_true")
        if record.get("scorer_feedback_used") is not False:
            blockers.append("scorer_feedback_used_not_false")
        if record.get("performance_evidence") is not False:
            blockers.append("record_performance_evidence_not_false")
        if not record.get("stop_gate_triggered"):
            blockers.append("stop_gate_triggered_missing")
        if not record.get("suspected_generate_failure_stage"):
            blockers.append("suspected_generate_failure_stage_missing")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    record = data.get("records", [{}])[0] if isinstance(data.get("records"), list) and data.get("records") else {}
    return {
        "report_scope": "bfcl_generate_failure_telemetry_artifact_check",
        "artifact_path": str(path),
        "bfcl_generate_failure_telemetry_artifact_passed": not blockers,
        "generate_exit_code_class": record.get("generate_exit_code_class") if isinstance(record, dict) else None,
        "generate_stage_entered": record.get("generate_stage_entered") if isinstance(record, dict) else None,
        "bfcl_evaluate_started": record.get("bfcl_evaluate_started") if isinstance(record, dict) else None,
        "scorer_started": record.get("scorer_started") if isinstance(record, dict) else None,
        "stop_gate_triggered": record.get("stop_gate_triggered") if isinstance(record, dict) else None,
        "suspected_generate_failure_stage": record.get("suspected_generate_failure_stage") if isinstance(record, dict) else None,
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
        summary = {"report_scope": "bfcl_generate_failure_telemetry_artifact_check", "bfcl_generate_failure_telemetry_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_generate_failure_telemetry_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
