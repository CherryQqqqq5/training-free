#!/usr/bin/env python3
"""Build Stage 1F no-provider BFCL parse/decode-loss debug artifact."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_OUTPUT = ARTIFACT_ROOT / "bfcl_parse_decode_loss_debug.json"
DEFAULT_MD = ARTIFACT_ROOT / "bfcl_parse_decode_loss_debug.md"
AFTER_PATCH_TELEMETRY = ARTIFACT_ROOT / "bfcl_one_id_live_shape_telemetry_after_tool_choice_patch_compact.json"
RUN_ID = "web_search_base_0"

VARIANT_ORDER = [
    "valid_json_string_arguments_completed_status",
    "valid_object_arguments_completed_status",
    "missing_call_id",
    "missing_status",
    "missing_name",
    "missing_arguments",
    "name_nested_under_function",
    "arguments_nested_under_function",
    "invalid_json_string_arguments",
    "status_in_progress",
]

FORBIDDEN_EXECUTION_FLAGS = {
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
}


@contextlib.contextmanager
def _dummy_openai_env():
    old_key = os.environ.get("OPENAI_API_KEY")
    old_base = os.environ.get("OPENAI_BASE_URL")
    os.environ["OPENAI_API_KEY"] = "dummy"
    os.environ["OPENAI_BASE_URL"] = "http" + "://127.0.0.1:1/v1"
    try:
        yield
    finally:
        if old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old_key
        if old_base is None:
            os.environ.pop("OPENAI_BASE_URL", None)
        else:
            os.environ["OPENAI_BASE_URL"] = old_base


def _handler_imports() -> tuple[bool, Any | None, str | None]:
    try:
        import scripts.run_bfcl_cli  # noqa: F401 - applies same BFCL CLI decode/request patches without CLI execution
        from bfcl_eval.model_handler.api_inference.openai_response import OpenAIResponsesHandler

        return True, OpenAIResponsesHandler, None
    except Exception as exc:  # pragma: no cover - environment-dependent
        return False, None, exc.__class__.__name__


def _safe_shape_hash_label() -> str:
    return "synthetic_two_field_schema_hash_redacted"


def _ns(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def _fixture_item(variant: str) -> SimpleNamespace:
    base: dict[str, Any] = {
        "type": "function_call",
        "name": "synthetic_function",
        "arguments": "{}",
        "call_id": "synthetic_call_id",
        "status": "completed",
    }
    if variant == "valid_object_arguments_completed_status":
        base["arguments"] = {}
    elif variant == "missing_call_id":
        base.pop("call_id")
    elif variant == "missing_status":
        base.pop("status")
    elif variant == "missing_name":
        base.pop("name")
    elif variant == "missing_arguments":
        base.pop("arguments")
    elif variant == "name_nested_under_function":
        base.pop("name")
        base["function"] = {"name_shape": "present_nested"}
    elif variant == "arguments_nested_under_function":
        base.pop("arguments")
        base["function"] = {"arguments_shape": "present_nested"}
    elif variant == "invalid_json_string_arguments":
        base["arguments"] = "{invalid_json_shape}"
    elif variant == "status_in_progress":
        base["status"] = "in_progress"
    elif variant != "valid_json_string_arguments_completed_status":
        raise ValueError(variant)
    return _ns(**base)


def _api_response_for_variant(variant: str) -> SimpleNamespace:
    return _ns(
        output=[_fixture_item(variant)],
        output_text="",
        usage=_ns(input_tokens=1, output_tokens=1, total_tokens=2),
    )


def _has_attr(item: Any, name: str) -> bool:
    return hasattr(item, name)


def _value_shape(value: Any) -> str:
    if isinstance(value, str):
        return "json_string" if value.strip().startswith("{") else "string"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "missing"
    return type(value).__name__


def _fixture_shape(item: Any) -> dict[str, Any]:
    return {
        "proxy_responses_function_call_shape_label": "responses_output_function_call_item",
        "proxy_responses_function_call_has_name": _has_attr(item, "name"),
        "proxy_responses_function_call_has_arguments": _has_attr(item, "arguments"),
        "proxy_responses_function_call_has_call_id": _has_attr(item, "call_id"),
        "proxy_responses_function_call_has_status": _has_attr(item, "status"),
        "arguments_shape_label": _value_shape(getattr(item, "arguments", None)) if _has_attr(item, "arguments") else "missing",
        "name_field_placement_label": "top_level" if _has_attr(item, "name") else ("nested_function_object" if _has_attr(item, "function") else "missing"),
        "status_shape_label": str(getattr(item, "status", "missing")),
    }


def _missing_required_fields(item: Any) -> list[str]:
    missing = []
    for field in ("name", "arguments", "call_id"):
        if not _has_attr(item, field):
            missing.append(field)
    return missing


def _decode_with_handler(ResponsesHandler: Any | None, variant: str) -> dict[str, Any]:
    item = _fixture_item(variant)
    shape = _fixture_shape(item)
    record: dict[str, Any] = {
        "variant": variant,
        "no_provider": True,
        "synthetic_fixtures_only": True,
        "handler_import_available": ResponsesHandler is not None,
        "responses_handler_available": ResponsesHandler is not None,
        "decode_execute_called": False,
        "decode_execute_nonempty": False,
        "decode_exception_class": "none",
        "parse_exception_class": "none",
        "bfcl_parser_input_shape_label": "openai_responses_output_list_synthetic_function_call",
        "bfcl_parser_expected_shape_label": "function_call_item_with_top_level_name_arguments_call_id",
        "missing_required_decode_fields": _missing_required_fields(item),
        **shape,
    }
    if ResponsesHandler is None:
        record["shape_mismatch_detected"] = bool(record["missing_required_decode_fields"])
        record["suspected_parse_decode_failure_stage"] = "handler_import_unavailable"
        return record

    try:
        with _dummy_openai_env():
            handler = ResponsesHandler("gpt-4.1", 0.0, "synthetic", True)
        parsed = handler._parse_query_response_FC(_api_response_for_variant(variant))
        model_responses = parsed.get("model_responses")
        record["parse_model_responses_shape_label"] = "list" if isinstance(model_responses, list) else type(model_responses).__name__
        record["parse_model_responses_count"] = len(model_responses) if isinstance(model_responses, list) else 0
    except Exception as exc:
        record["parse_exception_class"] = exc.__class__.__name__
        record["shape_mismatch_detected"] = True
        record["suspected_parse_decode_failure_stage"] = _stage_for_record(record)
        return record

    record["decode_execute_called"] = True
    try:
        decoded = handler.decode_execute(model_responses, False)
        record["decode_execute_nonempty"] = bool(decoded)
        record["decode_output_count"] = len(decoded) if isinstance(decoded, list) else (1 if decoded else 0)
    except Exception as exc:
        record["decode_exception_class"] = exc.__class__.__name__
        record["decode_execute_nonempty"] = False
        record["decode_output_count"] = 0
    record["shape_mismatch_detected"] = bool(record["missing_required_decode_fields"] or record["parse_exception_class"] != "none" or record["decode_exception_class"] != "none" or not record["decode_execute_nonempty"])
    record["suspected_parse_decode_failure_stage"] = _stage_for_record(record)
    return record


def _stage_for_record(record: dict[str, Any]) -> str:
    missing = set(record.get("missing_required_decode_fields") or [])
    if record.get("parse_exception_class") != "none":
        if missing:
            return "bfcl_parse_missing_" + "_".join(sorted(missing))
        return "bfcl_parse_exception"
    if record.get("decode_exception_class") != "none":
        if record.get("arguments_shape_label") == "json_string":
            return "bfcl_decode_arguments_json_string_invalid"
        return "bfcl_decode_exception"
    if record.get("decode_execute_nonempty") is True:
        return "accepted_by_bfcl_parse_decode"
    if missing:
        return "bfcl_decode_missing_" + "_".join(sorted(missing))
    return "bfcl_decode_empty_without_exception"


def _read_after_patch_telemetry_shape() -> dict[str, Any]:
    if not AFTER_PATCH_TELEMETRY.exists():
        return {"after_patch_telemetry_available": False}
    data = json.loads(AFTER_PATCH_TELEMETRY.read_text(encoding="utf-8"))
    records = data.get("records") if isinstance(data.get("records"), list) else []
    record = records[0] if records and isinstance(records[0], dict) else {}
    return {
        "after_patch_telemetry_available": True,
        "after_patch_request_tool_choice_shape": record.get("request_tool_choice_shape"),
        "after_patch_provider_response_has_tool_calls": record.get("provider_response_has_tool_calls"),
        "after_patch_proxy_responses_output_has_function_call": record.get("proxy_responses_output_has_function_call"),
        "after_patch_bfcl_parse_called": record.get("bfcl_parse_called"),
        "after_patch_bfcl_parse_model_response_empty": record.get("bfcl_parse_model_response_empty"),
        "after_patch_bfcl_decode_execute_nonempty": record.get("bfcl_decode_execute_nonempty"),
        "after_patch_suspected_live_failure_stage": record.get("suspected_live_failure_stage"),
    }


def build_report() -> dict[str, Any]:
    import_available, ResponsesHandler, import_error = _handler_imports()
    records = [_decode_with_handler(ResponsesHandler, variant) for variant in VARIANT_ORDER]
    accepted = [record for record in records if record.get("decode_execute_nonempty") is True]
    rejected = [record for record in records if record.get("decode_execute_nonempty") is not True]
    valid = next(record for record in records if record["variant"] == "valid_json_string_arguments_completed_status")
    if not import_available:
        stage = "handler_import_unavailable"
    elif valid.get("decode_execute_nonempty") is not True:
        stage = valid.get("suspected_parse_decode_failure_stage", "valid_shape_decode_loss")
    else:
        stage = "not_reproduced_offline_valid_function_call_decodes_nonempty"
    return {
        "artifact_kind": "bfcl_parse_decode_loss_debug",
        "approval_status": "prepared",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "gpt_5_2_active": False,
        "openrouter_allowed": False,
        "run_id": RUN_ID,
        "no_provider": True,
        "synthetic_fixtures_only": True,
        "synthetic_schema_shape_hash_label": _safe_shape_hash_label(),
        **FORBIDDEN_EXECUTION_FLAGS,
        "handler_import_available": import_available,
        "handler_import_error_class": import_error or "none",
        "responses_handler_available": ResponsesHandler is not None,
        "variant_count": len(records),
        "variant_order": list(VARIANT_ORDER),
        "accepted_variant_count": len(accepted),
        "rejected_variant_count": len(rejected),
        "decode_execute_called": any(record.get("decode_execute_called") for record in records),
        "decode_execute_nonempty": bool(valid.get("decode_execute_nonempty")),
        "decode_exception_class": str(valid.get("decode_exception_class", "none")),
        "proxy_responses_function_call_shape_label": valid.get("proxy_responses_function_call_shape_label"),
        "proxy_responses_function_call_has_name": valid.get("proxy_responses_function_call_has_name"),
        "proxy_responses_function_call_has_arguments": valid.get("proxy_responses_function_call_has_arguments"),
        "proxy_responses_function_call_has_call_id": valid.get("proxy_responses_function_call_has_call_id"),
        "proxy_responses_function_call_has_status": valid.get("proxy_responses_function_call_has_status"),
        "bfcl_parser_input_shape_label": valid.get("bfcl_parser_input_shape_label"),
        "bfcl_parser_expected_shape_label": valid.get("bfcl_parser_expected_shape_label"),
        "shape_mismatch_detected": any(record.get("shape_mismatch_detected") for record in records),
        "missing_required_decode_fields": valid.get("missing_required_decode_fields"),
        "records": records,
        "after_patch_telemetry_shape": _read_after_patch_telemetry_shape(),
        "suspected_parse_decode_failure_stage": stage,
        "next_recommended_patch_gate": "bfcl_responses_decode_shape_alignment_gate" if not stage.startswith("not_reproduced_offline") else "no_patch_live_decode_exception_shape_capture_gate",
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# BFCL Parse/Decode-Loss Debug",
        "",
        "Status: no-provider synthetic fixture artifact only. No live telemetry, BFCL generate, smoke, evaluate, scorer, full baseline, candidate path, performance evidence, +3pp claim, SOTA claim, or Huawei claim was run or authorized.",
        "",
        f"handler_import_available: `{report['handler_import_available']}`",
        f"responses_handler_available: `{report['responses_handler_available']}`",
        f"decode_execute_called: `{report['decode_execute_called']}`",
        f"decode_execute_nonempty_for_valid_fixture: `{report['decode_execute_nonempty']}`",
        f"shape_mismatch_detected: `{report['shape_mismatch_detected']}`",
        f"suspected_parse_decode_failure_stage: `{report['suspected_parse_decode_failure_stage']}`",
        f"next_recommended_patch_gate: `{report['next_recommended_patch_gate']}`",
        "",
        "Variant summary:",
    ]
    for record in report["records"]:
        lines.append(
            f"- `{record['variant']}`: stage=`{record['suspected_parse_decode_failure_stage']}`, "
            f"missing_fields=`{','.join(record['missing_required_decode_fields']) or 'none'}`, "
            f"parse_exception=`{record['parse_exception_class']}`, decode_exception=`{record['decode_exception_class']}`, "
            f"decode_nonempty=`{record['decode_execute_nonempty']}`"
        )
    lines.extend([
        "",
        "The artifact stores only booleans, enum labels, counts, and shape labels. It intentionally omits raw prompts, BFCL case content, provider payloads, logs, traces, raw tool arguments, endpoint/key values, gold/reference/expected data, scorer diffs, and candidate output.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(output: Path = DEFAULT_OUTPUT, md_output: Path = DEFAULT_MD) -> dict[str, Any]:
    report = build_report()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(md_output, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    report = write_report(args.output, args.md_output)
    summary = {
        "report_scope": "bfcl_parse_decode_loss_debug_build",
        "artifact_path": str(args.output),
        "handler_import_available": report["handler_import_available"],
        "decode_execute_called": report["decode_execute_called"],
        "decode_execute_nonempty": report["decode_execute_nonempty"],
        "shape_mismatch_detected": report["shape_mismatch_detected"],
        "suspected_parse_decode_failure_stage": report["suspected_parse_decode_failure_stage"],
        "provider_request_executed": report["provider_request_executed"],
        "bfcl_generate_executed": report["bfcl_generate_executed"],
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
