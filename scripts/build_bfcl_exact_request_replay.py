#!/usr/bin/env python3
"""Replay exact BFCL request shapes through local proxy/runtime/parser code with fake upstream."""

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

from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING  # noqa: E402
from grc.runtime.engine import RuleEngine  # noqa: E402
from grc.runtime.proxy import (  # noqa: E402
    _chat_response_to_responses_payload,
    _responses_input_to_messages,
    _responses_token_fields_to_chat_fields,
    _responses_tools_to_chat_tools,
)
from scripts.build_bfcl_exact_request_shape_capture import (  # noqa: E402
    BFCL_ALIAS,
    SIGNED_IDS,
    _capture_kwargs_for_entry,
    _load_entry,
)

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_request_replay.json")
DEFAULT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_request_replay.md")
RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")
RULES_DIR = Path("rules/baseline_empty")
FAKE_VARIANTS = ["tool_call", "text_only", "true_empty", "malformed_nonempty"]


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


def _load_runtime_policy() -> dict[str, Any]:
    data = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    policy = data.get("runtime_policy")
    return policy if isinstance(policy, dict) else {}


def _engine() -> RuleEngine:
    return RuleEngine(str(RULES_DIR), runtime_policy=dict(_load_runtime_policy()))


def _exact_kwargs_by_run_id() -> dict[str, dict[str, Any]]:
    old_key = os.environ.get("OPENAI_API_KEY")
    old_base = os.environ.get("OPENAI_BASE_URL")
    os.environ["OPENAI_API_KEY"] = "dummy"
    os.environ["OPENAI_BASE_URL"] = "http" + "://127.0.0.1:1/v1"
    try:
        config = MODEL_CONFIG_MAPPING[BFCL_ALIAS]
        handler = config.model_handler(
            model_name=config.model_name,
            temperature=0.001,
            registry_name=BFCL_ALIAS,
            is_fc_model=config.is_fc_model,
        )
        captured: dict[str, dict[str, Any]] = {}
        for run_id in SIGNED_IDS:
            with contextlib.redirect_stdout(io.StringIO()):
                captured[run_id] = _capture_kwargs_for_entry(handler, _load_entry(run_id))
        return captured
    finally:
        if old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old_key
        if old_base is None:
            os.environ.pop("OPENAI_BASE_URL", None)
        else:
            os.environ["OPENAI_BASE_URL"] = old_base


def _responses_kwargs_to_chat_request(kwargs: dict[str, Any]) -> dict[str, Any]:
    chat_request: dict[str, Any] = {
        "model": kwargs.get("model"),
        "messages": _responses_input_to_messages(kwargs.get("input"), instructions=kwargs.get("instructions")),
    }
    token_fields = _responses_token_fields_to_chat_fields(kwargs)
    if token_fields:
        chat_request.update(token_fields)
    for key in ("temperature", "top_p", "stream", "timeout", "response_format", "parallel_tool_calls"):
        if key in kwargs:
            chat_request[key] = kwargs[key]
    chat_tools = _responses_tools_to_chat_tools(kwargs.get("tools"))
    if chat_tools:
        chat_request["tools"] = chat_tools
    if "tool_choice" in kwargs:
        chat_request["tool_choice"] = kwargs.get("tool_choice")
    return chat_request


def _first_tool_name(chat_request: dict[str, Any]) -> str:
    tools = chat_request.get("tools") if isinstance(chat_request.get("tools"), list) else []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        name = fn.get("name")
        if isinstance(name, str) and name:
            return name
    return "synthetic_tool"


def _fake_chat_response(kind: str, chat_request: dict[str, Any]) -> dict[str, Any]:
    if kind == "tool_call":
        return {
            "id": "fake_tool_call_response",
            "model": "gpt-4.1",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_fake_exact_replay",
                                "type": "function",
                                "function": {"name": _first_tool_name(chat_request), "arguments": "{}"},
                            }
                        ],
                    }
                }
            ],
        }
    if kind == "text_only":
        return {"id": "fake_text_response", "model": "gpt-4.1", "choices": [{"message": {"role": "assistant", "content": "synthetic non-tool text", "tool_calls": []}}]}
    if kind == "true_empty":
        return {"id": "fake_empty_response", "model": "gpt-4.1", "choices": [{"message": {"role": "assistant", "content": "", "tool_calls": []}}]}
    if kind == "malformed_nonempty":
        return {"id": "fake_malformed_response", "model": "gpt-4.1", "choices": [{"delta": {"content": "synthetic malformed nonempty"}}]}
    raise ValueError(f"unknown fake upstream variant: {kind}")


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    return ""


def _has_tool_calls(response: dict[str, Any]) -> bool:
    choices = response.get("choices") if isinstance(response.get("choices"), list) else []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    return bool(message.get("tool_calls"))


def _content_empty(response: dict[str, Any]) -> bool:
    choices = response.get("choices") if isinstance(response.get("choices"), list) else []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    return not bool(_message_text(message).strip())


def _responses_has_function_call(payload: dict[str, Any]) -> bool:
    output = payload.get("output") if isinstance(payload.get("output"), list) else []
    return any(isinstance(item, dict) and item.get("type") == "function_call" for item in output)


def _responses_has_message_text(payload: dict[str, Any]) -> bool:
    output = payload.get("output") if isinstance(payload.get("output"), list) else []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content") if isinstance(item.get("content"), list) else []
        for chunk in content:
            if isinstance(chunk, dict) and str(chunk.get("text") or "").strip():
                return True
    return False


def _bfcl_decode_nonempty(payload: dict[str, Any]) -> tuple[bool, bool]:
    try:
        from bfcl_eval.model_handler.utils import convert_to_function_call
    except Exception:
        return False, False
    normalized = []
    for item in payload.get("output") if isinstance(payload.get("output"), list) else []:
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        name = item.get("name")
        args = item.get("arguments")
        if isinstance(name, str) and name:
            normalized.append({name: args if isinstance(args, str) else json.dumps(args or {}, sort_keys=True)})
    if not normalized:
        return True, False
    try:
        return True, bool(convert_to_function_call(normalized))
    except Exception:
        return True, False


def _token_forward_shape(kwargs: dict[str, Any], chat_request: dict[str, Any]) -> str:
    if "max_output_tokens" in kwargs and chat_request.get("max_tokens") == kwargs.get("max_output_tokens"):
        return "max_output_tokens_forwarded_as_chat_max_tokens"
    if "max_tokens" in kwargs and chat_request.get("max_tokens") == kwargs.get("max_tokens"):
        return "max_tokens_forwarded"
    if "max_completion_tokens" in kwargs and chat_request.get("max_tokens") == kwargs.get("max_completion_tokens"):
        return "max_completion_tokens_forwarded_as_chat_max_tokens"
    if "max_tokens" not in chat_request:
        return "missing"
    return "other"


def _suspected_stage(kind: str, *, forwarded_shape: str, final_has_tools: bool, final_empty: bool, coerced: bool, has_function_call: bool, has_message_text: bool, decode_exercised: bool, decode_nonempty: bool) -> str:
    if kind == "tool_call":
        if forwarded_shape != "required_string":
            return "required_string_tool_choice_conversion_loss"
        if not final_has_tools:
            return "tool_call_lost_in_runtime_engine"
        if not has_function_call:
            return "chat_to_responses_function_call_envelope_loss"
        if decode_exercised and not decode_nonempty:
            return "bfcl_responses_decode_dropped_function_call"
        return "required_string_multi_tool_survives_local_conversion_runtime_decode"
    if kind == "text_only":
        if coerced or (final_empty and not has_message_text):
            return "engine_no_tool_text_to_empty_coercion"
        return "non_tool_text_preserved_as_message_text"
    if kind == "true_empty":
        return "true_empty_distinguished"
    if kind == "malformed_nonempty":
        return "malformed_nonempty_response_shape_distinguished"
    return "unknown_fake_variant"


def _record(run_id: str, kwargs: dict[str, Any], variant: str) -> dict[str, Any]:
    original_chat_request = _responses_kwargs_to_chat_request(kwargs)
    chat_request, request_patches = _engine().apply_request(deepcopy(original_chat_request))
    fake_response = _fake_chat_response(variant, chat_request)
    final_chat, repairs, _ = _engine().apply_response(chat_request, fake_response, request_patches=request_patches)
    responses_payload = _chat_response_to_responses_payload(final_chat)
    decode_exercised, decode_nonempty = _bfcl_decode_nonempty(responses_payload)
    coerced = any(isinstance(repair, dict) and repair.get("kind") == "coerce_no_tool_text_to_empty" for repair in repairs)
    forwarded_shape = _shape(chat_request.get("tool_choice"))
    final_has_tools = _has_tool_calls(final_chat)
    final_empty = _content_empty(final_chat)
    has_function_call = _responses_has_function_call(responses_payload)
    has_message_text = _responses_has_message_text(responses_payload)
    return {
        "run_id": run_id,
        "fake_upstream_variant": variant,
        "exact_tool_choice_shape": _shape(kwargs.get("tool_choice")),
        "multi_tool_schema_present": isinstance(kwargs.get("tools"), list) and len(kwargs.get("tools") or []) > 1,
        "responses_to_chat_conversion_exercised": True,
        "forwarded_tool_choice_shape": forwarded_shape,
        "forwarded_tools_count_bucket": _bucket(len(chat_request.get("tools") or [])),
        "token_field_forwarded_shape": _token_forward_shape(kwargs, chat_request),
        "runtime_engine_exercised": True,
        "engine_final_has_tool_calls": final_has_tools,
        "engine_final_content_empty": final_empty,
        "engine_coerced_nonempty_text_to_empty": coerced,
        "chat_to_responses_conversion_exercised": True,
        "responses_output_has_function_call": has_function_call,
        "responses_output_has_message_text": has_message_text,
        "bfcl_or_openai_decode_exercised": decode_exercised,
        "bfcl_decode_execute_nonempty": decode_nonempty,
        "provider_request_executed": False,
        "live_telemetry_executed": False,
        "bfcl_smoke_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "suspected_replay_failure_stage": _suspected_stage(
            variant,
            forwarded_shape=forwarded_shape,
            final_has_tools=final_has_tools,
            final_empty=final_empty,
            coerced=coerced,
            has_function_call=has_function_call,
            has_message_text=has_message_text,
            decode_exercised=decode_exercised,
            decode_nonempty=decode_nonempty,
        ),
    }


def build_report() -> dict[str, Any]:
    exact_kwargs = _exact_kwargs_by_run_id()
    records = [_record(run_id, exact_kwargs[run_id], variant) for run_id in SIGNED_IDS for variant in FAKE_VARIANTS]
    tool_call_records = [record for record in records if record["fake_upstream_variant"] == "tool_call"]
    survives = all(
        record["forwarded_tool_choice_shape"] == "required_string"
        and record["engine_final_has_tool_calls"]
        and record["responses_output_has_function_call"]
        and record["bfcl_decode_execute_nonempty"]
        for record in tool_call_records
    )
    expected_non_failure = {
        "required_string_multi_tool_survives_local_conversion_runtime_decode",
        "non_tool_text_preserved_as_message_text",
        "true_empty_distinguished",
        "malformed_nonempty_response_shape_distinguished",
    }
    failure_stages = [record["suspected_replay_failure_stage"] for record in records if record["suspected_replay_failure_stage"] not in expected_non_failure]
    primary = failure_stages[0] if failure_stages else "required_string_multi_tool_survives_local_conversion_runtime_decode"
    return {
        "artifact_kind": "bfcl_exact_request_replay",
        "approval_status": "prepared",
        "route_model": "gpt-4.1",
        "active_profile": "novacode",
        "provider_request_executed": False,
        "live_telemetry_executed": False,
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
        "fake_upstream_variants": list(FAKE_VARIANTS),
        "records": records,
        "required_string_multi_tool_survives_local_conversion_runtime_decode": survives,
        "suspected_replay_failure_stage": primary,
        "minimal_tool_choice_patch_recommended_next": False,
        "not_measurement_evidence": True,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# BFCL Exact Request Replay",
        "",
        "Status: no-provider exact request replay with fake upstream. No provider request, live telemetry, BFCL smoke, scorer, full/default baseline, candidate activation, performance, +3pp, SOTA, or Huawei path was run.",
        "",
        f"- signed_run_ids: `{', '.join(report['signed_run_ids'])}`",
        f"- fake_upstream_variants: `{', '.join(report['fake_upstream_variants'])}`",
        f"- required_string_multi_tool_survives_local_conversion_runtime_decode: `{report['required_string_multi_tool_survives_local_conversion_runtime_decode']}`",
        f"- suspected_replay_failure_stage: `{report['suspected_replay_failure_stage']}`",
        f"- minimal_tool_choice_patch_recommended_next: `{report['minimal_tool_choice_patch_recommended_next']}`",
        "",
        "The artifact is shape-only and omits raw prompt/content text, tool arguments, raw case material, gold/reference/expected, scorer diffs, provider payloads, headers, logs, traces, endpoint/key values, and candidate output.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
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
