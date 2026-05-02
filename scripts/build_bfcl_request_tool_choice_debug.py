#!/usr/bin/env python3
"""Build no-provider BFCL request tool-choice debug artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from grc.runtime.proxy import _responses_token_fields_to_chat_fields, _responses_tools_to_chat_tools  # noqa: E402

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_OUTPUT = ARTIFACT_ROOT / "bfcl_request_tool_choice_debug.json"
DEFAULT_MD = ARTIFACT_ROOT / "bfcl_request_tool_choice_debug.md"
ONE_ID_TELEMETRY = ARTIFACT_ROOT / "bfcl_one_id_live_shape_telemetry_compact.json"
EXACT_CAPTURE = ARTIFACT_ROOT / "bfcl_exact_request_shape_capture.json"
REVIEWED_TELEMETRY = ARTIFACT_ROOT / "bfcl_live_shape_telemetry_compact.json"
SIGNED_RUN_ID = "web_search_base_0"
SIGNED_ROUTE_PROFILE = "novacode"
SIGNED_ROUTE_MODEL = "gpt-4.1"


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _bucket_count(value: Any) -> str:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return "unknown"
    if count == 0:
        return "zero"
    if count == 1:
        return "one"
    if count == 2:
        return "two"
    if count <= 8:
        return "small"
    return "many"


def _shape(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, str):
        return f"{value}_string" if value in {"required", "auto", "none"} else "string"
    if isinstance(value, dict):
        function = value.get("function")
        if value.get("type") == "function" and isinstance(function, dict):
            return "function_object"
        return "object"
    return type(value).__name__


def _one_id_record(path: Path = ONE_ID_TELEMETRY) -> dict[str, Any]:
    data = _load(path)
    records = data.get("records") if isinstance(data.get("records"), list) else []
    for record in records:
        if isinstance(record, dict) and record.get("run_id") == SIGNED_RUN_ID:
            return record
    raise ValueError("signed one-id telemetry record missing")


def _exact_capture_record(path: Path = EXACT_CAPTURE) -> dict[str, Any]:
    data = _load(path)
    records = data.get("records") if isinstance(data.get("records"), list) else []
    for record in records:
        if isinstance(record, dict) and record.get("run_id_label") == SIGNED_RUN_ID:
            return record
    return {}


def _reviewed_telemetry_record(path: Path = REVIEWED_TELEMETRY) -> dict[str, Any]:
    data = _load(path)
    records = data.get("records") if isinstance(data.get("records"), list) else []
    for record in records:
        if isinstance(record, dict) and record.get("run_id_label") == SIGNED_RUN_ID:
            return record
    return {}


def _proposed_proxy_shape() -> dict[str, str]:
    toy_responses_request = {
        "max_output_tokens": 64,
        "tools": [
            {"type": "function", "name": "shape_tool", "parameters": {"type": "object", "properties": {}}},
            {"type": "function", "name": "shape_tool_alt", "parameters": {"type": "object", "properties": {}}},
        ],
        "tool_choice": "required",
    }
    chat_tools = _responses_tools_to_chat_tools(toy_responses_request["tools"])
    chat_fields = _responses_token_fields_to_chat_fields(toy_responses_request)
    return {
        "expected_tool_choice_shape_if_fixed": _shape(toy_responses_request.get("tool_choice")),
        "proposed_proxy_forwarded_tool_choice_shape": _shape(toy_responses_request.get("tool_choice")),
        "proposed_proxy_forwarded_tools_count_bucket": _bucket_count(len(chat_tools)),
        "proposed_proxy_forwarded_token_field_shape": "max_tokens" if "max_tokens" in chat_fields else "none",
    }


def build_report() -> dict[str, Any]:
    one_id = _one_id_record()
    exact = _exact_capture_record()
    reviewed = _reviewed_telemetry_record()
    tools_present = one_id.get("request_has_tools") is True
    original_tool_choice_shape = str(one_id.get("request_tool_choice_shape") or "missing")
    tools_count = one_id.get("request_tool_count")
    exact_tool_choice_shape = str(exact.get("tool_choice_shape") or "unknown")
    reviewed_tool_choice_shape = str(reviewed.get("tool_choice_forwarding_label") or "unknown")
    suspected = "tool_choice_none_with_tools_present_confirmed" if tools_present and original_tool_choice_shape == "none" else "tool_choice_none_not_confirmed_offline"
    patch_kind = "proxy_normalization" if suspected == "tool_choice_none_with_tools_present_confirmed" else "not_recommended"
    patch_surface = "bfcl_measurement_responses_to_chat_tool_choice_normalization" if patch_kind == "proxy_normalization" else "none"
    proposed = _proposed_proxy_shape()
    record = {
        "run_id": SIGNED_RUN_ID,
        "tools_present": tools_present,
        "tools_count_bucket": _bucket_count(tools_count),
        "original_tool_choice_shape": original_tool_choice_shape,
        "original_tool_choice_source_label": "one_id_live_shape_telemetry_proxy_forwarded_request",
        "bfcl_handler_tool_choice_shape": exact_tool_choice_shape,
        "reviewed_telemetry_tool_choice_shape": reviewed_tool_choice_shape,
        "proxy_forwarded_tool_choice_shape": original_tool_choice_shape,
        "upstream_chat_tool_choice_shape": original_tool_choice_shape,
        "request_token_field_shape": str(one_id.get("request_token_field_shape") or "unknown"),
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        **proposed,
        "can_enforce_required_without_raw_case": True,
        "patch_surface_label": patch_surface,
        "candidate_patch_kind": patch_kind,
        "suspected_failure_stage": suspected,
    }
    return {
        "artifact_kind": "bfcl_request_tool_choice_debug",
        "approval_status": "prepared",
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "signed_run_ids": [SIGNED_RUN_ID],
        "provider_request_executed": False,
        "live_telemetry_executed": False,
        "bfcl_generate_executed": False,
        "bfcl_smoke_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "records": [record],
        "tool_choice_none_with_tools_present_confirmed": bool(tools_present and original_tool_choice_shape == "none"),
        "recommended_next_gate": "minimal_offline_patch_gate_enforce_required_for_bfcl_measurement_proxy_only" if patch_kind != "not_recommended" else "stop_report_mismatch",
        "suspected_failure_stage": suspected,
    }


def write_report(output: Path = DEFAULT_OUTPUT, md_output: Path = DEFAULT_MD) -> dict[str, Any]:
    report = build_report()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record = report["records"][0]
    md_output.write_text(
        "# BFCL Request Tool Choice Debug\n\n"
        "No provider request, live telemetry, BFCL generate, smoke, evaluate, scorer, full baseline, candidate, or performance path was executed.\n\n"
        f"run_id: `{record['run_id']}`\n\n"
        f"tools_present: `{record['tools_present']}`\n\n"
        f"original_tool_choice_shape: `{record['original_tool_choice_shape']}`\n\n"
        f"bfcl_handler_tool_choice_shape: `{record['bfcl_handler_tool_choice_shape']}`\n\n"
        f"reviewed_telemetry_tool_choice_shape: `{record['reviewed_telemetry_tool_choice_shape']}`\n\n"
        f"candidate_patch_kind: `{record['candidate_patch_kind']}`\n\n"
        f"patch_surface_label: `{record['patch_surface_label']}`\n\n"
        f"suspected_failure_stage: `{record['suspected_failure_stage']}`\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    report = write_report(args.output, args.md_output)
    summary = {
        "report_scope": "bfcl_request_tool_choice_debug_build",
        "artifact_path": str(args.output),
        "tool_choice_none_with_tools_present_confirmed": report["tool_choice_none_with_tools_present_confirmed"],
        "recommended_next_gate": report["recommended_next_gate"],
        "suspected_failure_stage": report["suspected_failure_stage"],
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
