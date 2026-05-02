#!/usr/bin/env python3
"""Capture exact BFCL handler request shape without provider execution."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from bfcl_eval._llm_response_generation import populate_initial_settings_for_web_search_test_cases  # noqa: E402
from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING  # noqa: E402
from bfcl_eval.model_handler.api_inference.openai_response import OpenAIResponsesHandler  # noqa: E402
from bfcl_eval.utils import load_dataset_entry  # noqa: E402
from grc.utils.bfcl_request_policy import apply_bfcl_fc_request_policy, apply_bfcl_memory_request_policy  # noqa: E402

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_request_shape_capture.json")
DEFAULT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_request_shape_capture.md")
RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")
BFCL_ALIAS = "gpt-4o-mini-2024-07-18-FC"
SIGNED_IDS = {
    "web_search_base_0": "web_search_base",
    "multi_turn_base_0": "multi_turn_base",
}


class _CapturedRequest(Exception):
    pass


def _bucket(value: int) -> str:
    if value == 0:
        return "zero"
    if value == 1:
        return "one"
    if value == 2:
        return "two"
    if value <= 8:
        return "small"
    return "many"


def _shape(value: Any) -> str:
    if isinstance(value, dict) and value.get("type") == "function":
        return "function_object"
    if isinstance(value, str):
        return f"{value}_string"
    if value is None:
        return "absent"
    return type(value).__name__


def _load_runtime_policy_shape() -> dict[str, Any]:
    data = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8"))
    policy = data.get("runtime_policy") if isinstance(data, dict) and isinstance(data.get("runtime_policy"), dict) else {}
    coercion = policy.get("coerce_no_tool_response_to_empty_kinds")
    return {
        "runtime_policy_text_to_empty_enabled": bool(coercion),
        "runtime_policy_text_to_empty_kind_count": len(coercion) if isinstance(coercion, list) else 0,
        "exact_next_tool_choice_mode": str(policy.get("exact_next_tool_choice_mode") or "absent"),
        "scorer_feedback_enabled": bool(policy.get("scorer_feedback_enabled")),
        "scorer_feedback_status": str(policy.get("scorer_feedback_status") or "absent"),
    }


def _load_entry(run_id: str) -> dict[str, Any]:
    category = SIGNED_IDS[run_id]
    entries = load_dataset_entry(category)
    if category == "web_search_base":
        entries = populate_initial_settings_for_web_search_test_cases(entries)
    for entry in entries:
        if entry.get("id") == run_id:
            return deepcopy(entry)
    raise ValueError(f"signed run id not found: {run_id}")


def _role_sequence(input_value: Any) -> list[str]:
    if not isinstance(input_value, list):
        return ["unknown"]
    sequence = []
    for item in input_value:
        if isinstance(item, dict):
            sequence.append(str(item.get("role") or item.get("type") or "object"))
        else:
            sequence.append(type(item).__name__)
    return sequence


def _item_type_counts(input_value: Any) -> dict[str, int]:
    counts = {"message": 0, "function_call": 0, "function_call_output": 0, "other": 0}
    if not isinstance(input_value, list):
        counts["other"] += 1
        return counts
    for item in input_value:
        if isinstance(item, dict):
            item_type = str(item.get("type") or "message")
            if item_type in counts:
                counts[item_type] += 1
            else:
                counts["other"] += 1
        else:
            counts["other"] += 1
    return counts


def _tools_count_bucket(tools: Any) -> str:
    return _bucket(len(tools) if isinstance(tools, list) else 0)


def _tool_schema_shape(tools: Any) -> str:
    if not isinstance(tools, list) or not tools:
        return "none"
    object_count = 0
    additional_false_count = 0
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        params = None
        function = tool.get("function")
        if isinstance(function, dict):
            params = function.get("parameters")
        elif tool.get("type") == "function":
            params = tool.get("parameters")
        if isinstance(params, dict) and params.get("type") == "object":
            object_count += 1
            if params.get("additionalProperties") is False:
                additional_false_count += 1
    return f"function_tools_object_schema_count_{object_count}_additionalProperties_false_count_{additional_false_count}"


def _token_presence(kwargs: dict[str, Any]) -> dict[str, str]:
    return {
        "max_output_tokens": "present" if "max_output_tokens" in kwargs else "missing",
        "max_tokens": "present" if "max_tokens" in kwargs else "missing",
        "max_completion_tokens": "present" if "max_completion_tokens" in kwargs else "missing",
    }


def _capture_kwargs_for_entry(handler: OpenAIResponsesHandler, entry: dict[str, Any]) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    original = OpenAIResponsesHandler.generate_with_backoff

    def capture(self: OpenAIResponsesHandler, **kwargs: Any) -> tuple[Any, float]:
        patched = apply_bfcl_fc_request_policy(kwargs, api_path="responses")
        patched = apply_bfcl_memory_request_policy(patched)
        captured.clear()
        captured.update(patched)
        raise _CapturedRequest()

    OpenAIResponsesHandler.generate_with_backoff = capture
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            handler.inference(deepcopy(entry), include_input_log=False, exclude_state_log=True)
    except _CapturedRequest:
        return dict(captured)
    finally:
        OpenAIResponsesHandler.generate_with_backoff = original
    raise RuntimeError("bfcl_handler_request_not_captured")


def _record_for(run_id: str, handler: OpenAIResponsesHandler) -> dict[str, Any]:
    entry = _load_entry(run_id)
    kwargs = _capture_kwargs_for_entry(handler, entry)
    input_value = kwargs.get("input")
    counts = _item_type_counts(input_value)
    tools = kwargs.get("tools")
    tool_choice = kwargs.get("tool_choice")
    has_developer = any(role in {"developer", "system"} for role in _role_sequence(input_value))
    suspected = "exact_bfcl_shape_captured"
    if "tool_choice" not in kwargs:
        suspected = "exact_request_missing_tool_choice"
    elif "max_output_tokens" not in kwargs and "max_tokens" not in kwargs:
        suspected = "exact_request_missing_token_limit"
    elif _shape(tool_choice) != "function_object":
        suspected = "exact_request_tool_choice_required_for_multi_tool_not_telemetry_function_object"
    elif run_id.startswith("multi_turn") and counts["function_call_output"] == 0:
        suspected = "first_turn_capture_no_multiturn_history_yet"
    return {
        "run_id_label": run_id,
        "handler_class_label": "OpenAIResponsesHandler",
        "api_path_label": "responses",
        "proxy_invocation_mode_label": "bfcl_runner_to_local_grc_proxy_v1_responses_no_provider_capture",
        "model_route_label": "gpt-4.1",
        "profile_route_label": "novacode",
        "input_or_messages_shape": {
            "role_sequence": _role_sequence(input_value),
            "item_type_sequence": [key for key, value in counts.items() for _ in range(value) if value > 0],
            "message_count_bucket": _bucket(len(input_value) if isinstance(input_value, list) else 0),
        },
        "has_instructions_or_system_or_developer": has_developer,
        "multiturn_history_present": counts["function_call"] > 0 or counts["function_call_output"] > 0,
        "history_item_type_counts": counts,
        "function_call_output_history_present": counts["function_call_output"] > 0,
        "tools_count_bucket": _tools_count_bucket(tools),
        "tool_schema_shape_summary": _tool_schema_shape(tools),
        "tool_choice_presence": "present" if "tool_choice" in kwargs else "missing",
        "tool_choice_shape": _shape(tool_choice),
        "token_fields_presence": _token_presence(kwargs),
        "stream_flag": "present_false" if kwargs.get("stream") is False else ("present_true" if kwargs.get("stream") is True else "missing"),
        "timeout_bucket": "present_120s" if kwargs.get("timeout") == 120 else ("present_other" if "timeout" in kwargs else "missing"),
        "temperature_presence": "present" if "temperature" in kwargs else "missing",
        "top_p_presence": "present" if "top_p" in kwargs else "missing",
        "response_format_presence": "present" if "response_format" in kwargs else "missing",
        "parallel_tool_calls_presence": "present" if "parallel_tool_calls" in kwargs else "missing",
        **_load_runtime_policy_shape(),
        "decode_extraction_path_label": "OpenAIResponsesHandler._parse_query_response_FC_then_decode_execute",
        "provider_request_executed": False,
        "no_provider_request_executed": True,
        "suspected_exact_request_gap": suspected,
    }


def build_report() -> dict[str, Any]:
    old_key = os.environ.get("OPENAI_API_KEY")
    old_base = os.environ.get("OPENAI_BASE_URL")
    os.environ["OPENAI_API_KEY"] = "dummy"
    os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:1/v1"
    try:
        config = MODEL_CONFIG_MAPPING[BFCL_ALIAS]
        handler = config.model_handler(
            model_name=config.model_name,
            temperature=0.001,
            registry_name=BFCL_ALIAS,
            is_fc_model=config.is_fc_model,
        )
        records = [_record_for(run_id, handler) for run_id in SIGNED_IDS]
    finally:
        if old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old_key
        if old_base is None:
            os.environ.pop("OPENAI_BASE_URL", None)
        else:
            os.environ["OPENAI_BASE_URL"] = old_base
    gaps = [record["suspected_exact_request_gap"] for record in records]
    primary = "exact_request_shape_captured_tool_choice_and_token_present"
    if any(gap not in {"exact_bfcl_shape_captured", "first_turn_capture_no_multiturn_history_yet"} for gap in gaps):
        primary = next(gap for gap in gaps if gap not in {"exact_bfcl_shape_captured", "first_turn_capture_no_multiturn_history_yet"})
    elif any(gap == "first_turn_capture_no_multiturn_history_yet" for gap in gaps):
        primary = "exact_first_turn_capture_does_not_cover_later_multiturn_history"
    return {
        "artifact_kind": "bfcl_exact_request_shape_capture",
        "approval_status": "prepared",
        "route_model": "gpt-4.1",
        "active_profile": "novacode",
        "provider_request_executed": False,
        "bfcl_smoke_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_prompt_persisted": False,
        "raw_case_content_persisted": False,
        "raw_provider_payload_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "endpoint_or_key_committed": False,
        "signed_run_ids": list(SIGNED_IDS),
        "records": records,
        "suspected_exact_request_gap": primary,
        "missing_tool_choice_confirmed": any(record["tool_choice_presence"] == "missing" for record in records),
        "missing_token_limit_confirmed": any(
            record["token_fields_presence"]["max_output_tokens"] == "missing" and record["token_fields_presence"]["max_tokens"] == "missing"
            for record in records
        ),
        "minimal_patch_recommended_next": "no_patch_before_review_exact_capture_shows_tool_choice_and_token_present" if primary == "exact_request_shape_captured_tool_choice_and_token_present" else "no_direct_patch_recommended_review_tool_choice_shape_alignment",
        "not_measurement_evidence": True,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# BFCL Exact Request Shape Capture",
        "",
        "Status: no-provider exact handler request-shape capture. No provider request, live telemetry rerun, BFCL smoke, scorer, full/default baseline, candidate activation, performance, +3pp, or Huawei path was run.",
        "",
        f"- suspected_exact_request_gap: `{report['suspected_exact_request_gap']}`",
        f"- missing_tool_choice_confirmed: `{report['missing_tool_choice_confirmed']}`",
        f"- missing_token_limit_confirmed: `{report['missing_token_limit_confirmed']}`",
        f"- minimal_patch_recommended_next: `{report['minimal_patch_recommended_next']}`",
        f"- captured_run_ids: `{', '.join(report['signed_run_ids'])}`",
        "",
        "The artifact stores shape labels and buckets only. It omits raw prompt/case text, full tool names or arguments, gold/reference/expected material, scorer diffs, provider payloads, headers, logs, traces, endpoint/key values, and candidate outputs.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_OUTPUT.with_suffix(".md"))
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(args.md_output, report)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
