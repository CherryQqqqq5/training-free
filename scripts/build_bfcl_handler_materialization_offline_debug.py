#!/usr/bin/env python3
"""Build Stage 1C no-provider BFCL handler/materialization offline debug artifact."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_handler_materialization_offline_debug.json")
DEFAULT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_handler_materialization_offline_debug.md")
SIGNED_IDS = ["web_search_base_0", "multi_turn_base_0"]
VARIANTS = ["responses_function_call", "chat_tool_call", "text_only", "true_empty", "malformed_nonempty", "handler_exception"]


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


def _handler_imports() -> tuple[bool, Any, Any]:
    try:
        import scripts.run_bfcl_cli  # noqa: F401 - applies decode/request patches without CLI execution
        from bfcl_eval.model_handler.api_inference.openai_completion import OpenAICompletionsHandler
        from bfcl_eval.model_handler.api_inference.openai_response import OpenAIResponsesHandler
        return True, OpenAIResponsesHandler, OpenAICompletionsHandler
    except Exception:
        return False, None, None


def _response_function_call_payload() -> Any:
    return SimpleNamespace(
        output=[SimpleNamespace(type="function_call", name="synthetic_function", arguments="{}", call_id="synthetic_call")],
        output_text="",
        usage=SimpleNamespace(input_tokens=1, output_tokens=1, total_tokens=2),
    )


def _chat_tool_call_payload() -> Any:
    fn = SimpleNamespace(name="synthetic_function", arguments="{}")
    call = SimpleNamespace(id="synthetic_call", function=fn)
    message = SimpleNamespace(tool_calls=[call], content=None)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    return SimpleNamespace(choices=[choice], usage=usage)


def _exercise_decode() -> dict[str, Any]:
    available, ResponsesHandler, CompletionsHandler = _handler_imports()
    result = {
        "handler_import_available": available,
        "responses_decode_execute_exercised": False,
        "chat_decode_execute_exercised": False,
        "responses_function_call_decodes_nonempty": False,
        "chat_tool_call_decodes_nonempty": False,
    }
    if not available:
        return result
    with _dummy_openai_env():
        responses_handler = ResponsesHandler("gpt-4.1", 0.0, "synthetic", True)
        completions_handler = CompletionsHandler("gpt-4.1", 0.0, "synthetic", True)
    parsed_responses = responses_handler._parse_query_response_FC(_response_function_call_payload())
    result["responses_decode_execute_exercised"] = True
    result["responses_function_call_decodes_nonempty"] = bool(responses_handler.decode_execute(parsed_responses["model_responses"], False))
    parsed_chat = completions_handler._parse_query_response_FC(_chat_tool_call_payload())
    result["chat_decode_execute_exercised"] = True
    result["chat_tool_call_decodes_nonempty"] = bool(completions_handler.decode_execute(parsed_chat["model_responses"], False))
    return result


def _write_synthetic_result(root: Path, run_id: str, variant: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if variant in {"responses_function_call", "chat_tool_call"}:
        payload = {"id": run_id, "shape_label": "function_call", "function_call": True}
    elif variant == "text_only":
        payload = {"id": run_id, "shape_label": "record_only_no_tool_text", "record_only_no_tool_text": True}
    elif variant == "true_empty":
        payload = {"id": run_id, "shape_label": "empty_model_response", "status": "Empty response from the model"}
    elif variant == "malformed_nonempty":
        payload = {"id": run_id, "shape_label": "malformed_nonempty", "error": "synthetic_malformed_nonempty"}
    elif variant == "handler_exception":
        payload = {"id": run_id, "shape_label": "handler_exception", "exception_classification": "synthetic_protocol_exception"}
    else:
        raise ValueError(variant)
    (root / f"{run_id}_{variant}.json").write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _classify(run_id: str, root: Path) -> dict[str, Any]:
    from scripts.run_bfcl_exact_2id_generate_smoke import _classify_result_for_run_id

    compact = _classify_result_for_run_id(run_id, root)
    return {
        "status": compact["status"],
        "empty_model_response_detected": compact["empty_model_response_detected"],
        "no_tool_text_recorded": compact["no_tool_text_recorded"],
        "tool_call_detected": compact["tool_call_detected"],
        "protocol_error_detected": compact["protocol_error_detected"],
    }


def _materialization_record(run_id: str, variant: str, decode: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="bfcl_stage1c_materialization_") as tmp:
        root = Path(tmp)
        _write_synthetic_result(root, run_id, variant)
        classification = _classify(run_id, root)
    nonempty_variant = variant in {"responses_function_call", "chat_tool_call", "text_only", "malformed_nonempty", "handler_exception"}
    true_empty = variant == "true_empty"
    exception_variant = variant == "handler_exception"
    return {
        "run_id": run_id,
        "variant": variant,
        "synthetic_fake_upstream_only": True,
        "provider_request_executed": False,
        "bfcl_generate_executed": False,
        "bfcl_smoke_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "performance_evidence": False,
        "proxy_output_shape_label": variant,
        "handler_decode_exercised": bool(decode["responses_decode_execute_exercised"] or decode["chat_decode_execute_exercised"]),
        "synthetic_result_tempfile_written": True,
        "synthetic_result_tempfile_persisted": False,
        "bfcl_result_file_contains_nonempty_shape": nonempty_variant,
        "true_empty_shape": true_empty,
        "classifier_status": classification["status"],
        "classifier_empty_model_response": classification["empty_model_response_detected"],
        "classifier_detected_tool_call": classification["tool_call_detected"],
        "classifier_detected_no_tool_text": classification["no_tool_text_recorded"],
        "classifier_protocol_error": classification["protocol_error_detected"],
        "classifier_false_empty_for_nonempty": nonempty_variant and classification["empty_model_response_detected"],
        "exception_simulated": exception_variant,
        "exception_preserved_as_protocol_debug": exception_variant and classification["protocol_error_detected"],
        "exception_swallowed_as_empty": exception_variant and classification["empty_model_response_detected"],
        "suspected_failure_stage": _stage_for_variant(variant, classification),
    }


def _stage_for_variant(variant: str, classification: dict[str, Any]) -> str:
    if variant in {"responses_function_call", "chat_tool_call"}:
        return "nonempty_tool_call_materializes_nonempty" if classification["tool_call_detected"] else "tool_call_materialization_or_classifier_loss"
    if variant == "text_only":
        return "nonempty_text_distinguished_from_true_empty" if classification["no_tool_text_recorded"] and not classification["empty_model_response_detected"] else "text_materialization_or_classifier_loss"
    if variant == "true_empty":
        return "true_empty_classified_as_empty_model_response" if classification["empty_model_response_detected"] else "true_empty_not_classified_as_empty"
    if variant == "malformed_nonempty":
        return "malformed_nonempty_classified_as_protocol_error" if classification["protocol_error_detected"] else "malformed_nonempty_classification_loss"
    if variant == "handler_exception":
        return "exception_preserved_as_protocol_debug" if classification["protocol_error_detected"] else "exception_swallowed_or_lost"
    return "unknown_variant"


def build_report() -> dict[str, Any]:
    decode = _exercise_decode()
    records = [_materialization_record(run_id, variant, decode) for run_id in SIGNED_IDS for variant in VARIANTS]
    classifier_false_empty = any(record["classifier_false_empty_for_nonempty"] for record in records)
    exception_swallowed = any(record["exception_swallowed_as_empty"] for record in records)
    nonempty_tool_materialized = all(
        record["classifier_detected_tool_call"] and not record["classifier_empty_model_response"]
        for record in records
        if record["variant"] in {"responses_function_call", "chat_tool_call"}
    )
    nonempty_text_distinguished = all(
        record["classifier_detected_no_tool_text"] and not record["classifier_empty_model_response"]
        for record in records
        if record["variant"] == "text_only"
    )
    true_empty_distinguished = all(
        record["classifier_empty_model_response"]
        for record in records
        if record["variant"] == "true_empty"
    )
    if classifier_false_empty:
        suspected = "compact_result_classifier_false_empty"
    elif exception_swallowed:
        suspected = "exception_path_swallowed_as_empty"
    elif nonempty_tool_materialized and nonempty_text_distinguished and true_empty_distinguished:
        suspected = "not_reproduced_offline_handler_materialization"
    else:
        suspected = "handler_or_materialization_offline_mismatch"
    return {
        "artifact_kind": "bfcl_handler_materialization_offline_debug",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "signed_run_ids": list(SIGNED_IDS),
        "variants": list(VARIANTS),
        "no_provider": True,
        "synthetic_fake_upstream_only": True,
        "provider_request_executed": False,
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
        "raw_prompt_persisted": False,
        "raw_case_content_persisted": False,
        "raw_provider_payload_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "endpoint_or_key_committed": False,
        **decode,
        "nonempty_tool_call_materialized_nonempty": nonempty_tool_materialized,
        "nonempty_text_distinguished_from_true_empty": nonempty_text_distinguished and true_empty_distinguished,
        "result_classifier_false_empty_for_nonempty": classifier_false_empty,
        "exception_path_swallowed_as_empty": exception_swallowed,
        "decode_execute_exercised": bool(decode["responses_decode_execute_exercised"] or decode["chat_decode_execute_exercised"]),
        "records": records,
        "suspected_failure_stage": suspected,
    }


def write_report(output: Path = DEFAULT_OUTPUT, md_output: Path = DEFAULT_MD) -> dict[str, Any]:
    report = build_report()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_output.write_text(
        "# BFCL Handler Materialization Offline Debug\n\n"
        "No provider, BFCL generate, BFCL smoke, evaluate, scorer, full baseline, candidate, performance, +3pp, or Huawei path was executed.\n\n"
        f"handler_import_available: `{report['handler_import_available']}`\n\n"
        f"decode_execute_exercised: `{report['decode_execute_exercised']}`\n\n"
        f"nonempty_tool_call_materialized_nonempty: `{report['nonempty_tool_call_materialized_nonempty']}`\n\n"
        f"nonempty_text_distinguished_from_true_empty: `{report['nonempty_text_distinguished_from_true_empty']}`\n\n"
        f"result_classifier_false_empty_for_nonempty: `{report['result_classifier_false_empty_for_nonempty']}`\n\n"
        f"exception_path_swallowed_as_empty: `{report['exception_path_swallowed_as_empty']}`\n\n"
        f"suspected_failure_stage: `{report['suspected_failure_stage']}`\n",
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
        "report_scope": "bfcl_handler_materialization_offline_debug_build",
        "artifact_path": str(args.output),
        "handler_import_available": report["handler_import_available"],
        "decode_execute_exercised": report["decode_execute_exercised"],
        "suspected_failure_stage": report["suspected_failure_stage"],
        "provider_request_executed": report["provider_request_executed"],
        "bfcl_generate_executed": report["bfcl_generate_executed"],
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
