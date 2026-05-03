#!/usr/bin/env python3
"""Build Stage 1G no-provider materialization/classifier-after-decode replay."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_bfcl_exact_2id_generate_smoke import _classify_result_for_run_id  # noqa: E402

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_OUTPUT = ARTIFACT_ROOT / "bfcl_materialization_classifier_after_decode_debug.json"
DEFAULT_MD = ARTIFACT_ROOT / "bfcl_materialization_classifier_after_decode_debug.md"
LIVE_CAPTURE = ARTIFACT_ROOT / "bfcl_live_decode_exception_shape_capture_compact.json"
RUN_ID = "web_search_base_0"
SOURCE_COMMIT = "d95feaba15d85f804b061360bfe70862318ab46e"
VARIANTS = [
    "valid_nonempty_decoded_tool_call_shape",
    "nonempty_decoded_alternate_layout",
    "true_empty_decoded_output",
    "malformed_decoded_output_shape",
    "post_decode_exception_after_nonempty_decode",
    "missing_materialized_file_path",
    "nonempty_materialized_result_with_classifier_path",
]
FALSE_FLAGS = {
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


def _source_shape() -> dict[str, Any]:
    if not LIVE_CAPTURE.exists():
        return {"source_available": False}
    data = json.loads(LIVE_CAPTURE.read_text(encoding="utf-8"))
    record = data.get("records", [{}])[0] if isinstance(data.get("records"), list) else {}
    return {
        "source_available": True,
        "decoded_output_count": int(record.get("bfcl_decode_output_count") or 0),
        "decoded_output_nonempty": record.get("bfcl_decode_execute_nonempty") is True,
        "arguments_shape_label": record.get("proxy_arguments_shape_label"),
        "arguments_json_parseable": record.get("proxy_arguments_json_parseable_bool"),
        "function_call_shape_present": record.get("proxy_responses_output_has_function_call") is True,
        "source_suspected_stage": record.get("suspected_live_decode_failure_stage"),
    }


def _payload_for(variant: str) -> dict[str, Any] | None:
    if variant == "missing_materialized_file_path":
        return None
    base = {"id": RUN_ID, "decoded_output_shape_label": "function_call", "function_call": True, "shape_only": True}
    if variant == "valid_nonempty_decoded_tool_call_shape":
        return base
    if variant == "nonempty_decoded_alternate_layout":
        return {"run_id": RUN_ID, "model_response_decoded": [{"shape_label": "function_call"}], "shape_only": True}
    if variant == "true_empty_decoded_output":
        return {"id": RUN_ID, "status": "empty_model_response", "shape_only": True}
    if variant == "malformed_decoded_output_shape":
        return {"id": RUN_ID, "error": "synthetic_malformed_decoded_shape", "shape_only": True}
    if variant == "post_decode_exception_after_nonempty_decode":
        return {"id": RUN_ID, "function_call": True, "error": "synthetic_post_decode_exception", "shape_only": True}
    if variant == "nonempty_materialized_result_with_classifier_path":
        return {"id": RUN_ID, "tool_calls": [{"shape_label": "function_call"}], "shape_only": True}
    raise ValueError(variant)


def _layout_path(root: Path, variant: str) -> Path:
    if variant == "nonempty_decoded_alternate_layout":
        return root / "alternate_layout" / "result.json"
    return root / "bfcl" / "result" / f"{RUN_ID}_{variant}.json"


def _classify_status(classification: dict[str, Any]) -> str:
    return str(classification.get("status") or "missing_result")


def _protocol_label(variant: str, classification: dict[str, Any], nonempty: bool) -> str:
    if variant == "post_decode_exception_after_nonempty_decode":
        return "post_decode_exception_recorded_after_nonempty"
    if classification.get("protocol_error_detected"):
        return "protocol_error"
    if nonempty and classification.get("tool_call_detected"):
        return "nonempty_tool_call"
    if classification.get("empty_model_response_detected"):
        return "empty_model_response"
    return _classify_status(classification)


def _stage_for(variant: str, classification: dict[str, Any], *, layout_match: bool, materialized_nonempty: bool) -> str:
    if variant == "missing_materialized_file_path":
        return "result_layout_or_path_lookup_missing"
    if not layout_match:
        return "result_layout_path_mismatch"
    if materialized_nonempty and classification.get("protocol_error_detected"):
        return "classifier_false_protocol_error_on_nonempty"
    if materialized_nonempty and classification.get("tool_call_detected"):
        return "not_reproduced_nonempty_materializes_and_classifies"
    if variant == "true_empty_decoded_output" and classification.get("empty_model_response_detected"):
        return "true_empty_distinguished"
    if variant == "post_decode_exception_after_nonempty_decode":
        return "post_decode_exception_classified_distinctly"
    if variant == "malformed_decoded_output_shape":
        return "malformed_decoded_shape_classified_protocol_error"
    return "materialization_classifier_replay_mismatch"


def _record(variant: str, source: dict[str, Any]) -> dict[str, Any]:
    payload = _payload_for(variant)
    decoded_nonempty = variant not in {"true_empty_decoded_output", "missing_materialized_file_path"}
    with tempfile.TemporaryDirectory(prefix="bfcl_stage1g_materialization_") as tmp:
        root = Path(tmp)
        result_root = root / "bfcl" / "result"
        materialization_called = True
        materialized_written = payload is not None
        observed_layout = "missing"
        if payload is not None:
            path = _layout_path(root, variant)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
            observed_layout = "bfcl_result_tree" if path.parent == result_root else "alternate_layout_tree"
        classification = _classify_result_for_run_id(RUN_ID, result_root)
    expected_layout = "bfcl_result_tree"
    layout_match = observed_layout == expected_layout
    materialized_nonempty = bool(payload and ("function_call" in json.dumps(payload) or "tool_calls" in json.dumps(payload) or "model_response_decoded" in json.dumps(payload)))
    classifier_called = True
    classifier_nonempty = bool(classification.get("tool_call_detected") or classification.get("no_tool_text_recorded"))
    classifier_status = _classify_status(classification)
    false_protocol = materialized_nonempty and classifier_status == "protocol_error"
    protocol_label = _protocol_label(variant, classification, materialized_nonempty)
    false_protocol_status = decoded_nonempty and protocol_label == "protocol_error" and variant != "malformed_decoded_output_shape"
    return {
        "variant": variant,
        "no_provider": True,
        "synthetic_fixtures_only": True,
        "decoded_output_shape_label": "function_call_shape" if decoded_nonempty else "empty_shape",
        "decoded_output_count": int(source.get("decoded_output_count") or (1 if decoded_nonempty else 0)),
        "decoded_output_nonempty": decoded_nonempty,
        "materialization_called": materialization_called,
        "materialized_result_written": materialized_written,
        "materialized_result_shape_label": "shape_only_function_call" if materialized_nonempty else ("missing" if payload is None else "empty_shape"),
        "materialized_result_nonempty": materialized_nonempty,
        "result_layout_expected_label": expected_layout,
        "result_layout_observed_label": observed_layout,
        "result_layout_match": layout_match,
        "classifier_called": classifier_called,
        "classifier_detected_nonempty": classifier_nonempty,
        "classifier_status": classifier_status,
        "classifier_false_protocol_error_on_nonempty": false_protocol,
        "protocol_status_classifier_called": True,
        "protocol_status_classifier_label": protocol_label,
        "protocol_status_false_error_after_nonempty_decode": false_protocol_status,
        "post_decode_exception_simulated": variant == "post_decode_exception_after_nonempty_decode",
        "post_decode_exception_classification_label": protocol_label if variant == "post_decode_exception_after_nonempty_decode" else "not_simulated",
        "suspected_materialization_classifier_failure_stage": _stage_for(variant, classification, layout_match=layout_match, materialized_nonempty=materialized_nonempty),
    }


def build_report() -> dict[str, Any]:
    source = _source_shape()
    records = [_record(variant, source) for variant in VARIANTS]
    primary = next(record for record in records if record["variant"] == "valid_nonempty_decoded_tool_call_shape")
    if primary["classifier_false_protocol_error_on_nonempty"]:
        suspected = "classifier_false_protocol_error_on_nonempty"
    elif not primary["result_layout_match"]:
        suspected = "result_layout_path_mismatch"
    elif primary["materialized_result_nonempty"] and primary["classifier_detected_nonempty"]:
        suspected = "not_reproduced_offline_materialization_classifier"
    else:
        suspected = "materialization_classifier_after_decode_replay_mismatch"
    return {
        "artifact_kind": "bfcl_materialization_classifier_after_decode_debug",
        "approval_status": "prepared",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "no_provider": True,
        "synthetic_fixtures_only": True,
        "replay_source_capture_commit": SOURCE_COMMIT,
        "replay_source_capture_artifact_label": "bfcl_live_decode_exception_shape_capture_compact",
        **FALSE_FLAGS,
        "decoded_output_shape_label": primary["decoded_output_shape_label"],
        "decoded_output_count": primary["decoded_output_count"],
        "decoded_output_nonempty": primary["decoded_output_nonempty"],
        "materialization_called": primary["materialization_called"],
        "materialized_result_written": primary["materialized_result_written"],
        "materialized_result_shape_label": primary["materialized_result_shape_label"],
        "materialized_result_nonempty": primary["materialized_result_nonempty"],
        "result_layout_expected_label": primary["result_layout_expected_label"],
        "result_layout_observed_label": primary["result_layout_observed_label"],
        "result_layout_match": primary["result_layout_match"],
        "classifier_called": primary["classifier_called"],
        "classifier_detected_nonempty": primary["classifier_detected_nonempty"],
        "classifier_status": primary["classifier_status"],
        "classifier_false_protocol_error_on_nonempty": primary["classifier_false_protocol_error_on_nonempty"],
        "protocol_status_classifier_called": primary["protocol_status_classifier_called"],
        "protocol_status_classifier_label": primary["protocol_status_classifier_label"],
        "protocol_status_false_error_after_nonempty_decode": primary["protocol_status_false_error_after_nonempty_decode"],
        "post_decode_exception_simulated": primary["post_decode_exception_simulated"],
        "post_decode_exception_classification_label": primary["post_decode_exception_classification_label"],
        "variant_order": list(VARIANTS),
        "records": records,
        "suspected_materialization_classifier_failure_stage": suspected,
        "next_recommended_gate": "one_id_post_decode_materialization_telemetry_only" if suspected.startswith("not_reproduced") else "minimal_offline_materialization_classifier_patch_gate",
    }


def write_report(output: Path = DEFAULT_OUTPUT, md_output: Path = DEFAULT_MD) -> dict[str, Any]:
    report = build_report()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# BFCL Materialization/Classifier After Decode Debug",
        "",
        "No provider, live telemetry, BFCL generate, smoke, evaluate, scorer, full baseline, candidate path, performance evidence, +3pp, SOTA, or Huawei path was run or authorized.",
        "",
        f"decoded_output_nonempty: `{report['decoded_output_nonempty']}`",
        f"materialized_result_nonempty: `{report['materialized_result_nonempty']}`",
        f"result_layout_match: `{report['result_layout_match']}`",
        f"classifier_detected_nonempty: `{report['classifier_detected_nonempty']}`",
        f"classifier_false_protocol_error_on_nonempty: `{report['classifier_false_protocol_error_on_nonempty']}`",
        f"protocol_status_false_error_after_nonempty_decode: `{report['protocol_status_false_error_after_nonempty_decode']}`",
        f"suspected_materialization_classifier_failure_stage: `{report['suspected_materialization_classifier_failure_stage']}`",
        f"next_recommended_gate: `{report['next_recommended_gate']}`",
    ]
    md_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    report = write_report(args.output, args.md_output)
    summary = {
        "report_scope": "bfcl_materialization_classifier_after_decode_debug_build",
        "artifact_path": str(args.output),
        "decoded_output_nonempty": report["decoded_output_nonempty"],
        "materialized_result_nonempty": report["materialized_result_nonempty"],
        "result_layout_match": report["result_layout_match"],
        "classifier_false_protocol_error_on_nonempty": report["classifier_false_protocol_error_on_nonempty"],
        "protocol_status_false_error_after_nonempty_decode": report["protocol_status_false_error_after_nonempty_decode"],
        "suspected_materialization_classifier_failure_stage": report["suspected_materialization_classifier_failure_stage"],
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
