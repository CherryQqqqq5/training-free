from __future__ import annotations

import copy
import json

from scripts.build_bfcl_materialization_classifier_after_decode_debug import VARIANTS, build_report
from scripts.check_bfcl_materialization_classifier_after_decode_debug import validate_artifact, validate_packet


def _report() -> dict:
    return build_report()


def _record(report: dict, variant: str) -> dict:
    return next(record for record in report["records"] if record["variant"] == variant)


def test_nonempty_decoded_shape_materializes_nonempty_or_records_failure() -> None:
    report = _report()
    record = _record(report, "valid_nonempty_decoded_tool_call_shape")
    assert record["decoded_output_nonempty"] is True
    assert record["materialization_called"] is True
    assert record["materialized_result_written"] is True
    assert record["materialized_result_nonempty"] is True
    assert record["suspected_materialization_classifier_failure_stage"]


def test_result_layout_path_mismatch_detected_distinctly() -> None:
    report = _report()
    record = _record(report, "nonempty_decoded_alternate_layout")
    assert record["result_layout_match"] is False
    assert record["suspected_materialization_classifier_failure_stage"] == "result_layout_path_mismatch"


def test_classifier_detects_nonempty_or_records_false_protocol_error_distinctly() -> None:
    report = _report()
    record = _record(report, "nonempty_materialized_result_with_classifier_path")
    assert record["classifier_called"] is True
    assert record["classifier_detected_nonempty"] is True or record["classifier_false_protocol_error_on_nonempty"] is True
    assert record["suspected_materialization_classifier_failure_stage"]


def test_true_empty_decoded_output_remains_distinguishable() -> None:
    report = _report()
    record = _record(report, "true_empty_decoded_output")
    assert record["decoded_output_nonempty"] is False
    assert record["classifier_status"] == "empty_model_response"


def test_post_decode_exception_not_silent_empty() -> None:
    report = _report()
    record = _record(report, "post_decode_exception_after_nonempty_decode")
    assert record["post_decode_exception_simulated"] is True
    assert record["post_decode_exception_classification_label"] != "empty_model_response"


def test_missing_materialized_file_path_distinct() -> None:
    report = _report()
    record = _record(report, "missing_materialized_file_path")
    assert record["materialized_result_written"] is False
    assert record["result_layout_observed_label"] == "missing"
    assert record["suspected_materialization_classifier_failure_stage"] == "result_layout_or_path_lookup_missing"


def test_checker_rejects_execution_flags() -> None:
    report = _report()
    dirty = copy.deepcopy(report)
    dirty["provider_request_executed"] = True
    assert any("provider_request_executed" in blocker for blocker in validate_artifact(dirty))


def test_checker_rejects_raw_secret_case_material() -> None:
    report = _report()
    dirty = copy.deepcopy(report)
    dirty["raw_prompt_text"] = "redacted"
    assert any("forbidden_key" in blocker for blocker in validate_artifact(dirty))
    dirty = copy.deepcopy(report)
    dirty["notes"] = "api key value"
    assert any("forbidden_value" in blocker for blocker in validate_artifact(dirty))


def test_packet_fail_closed_shape() -> None:
    packet = {
        "artifact_kind": "bfcl_materialization_classifier_after_decode_debug_packet",
        "approval_status": "prepared",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "no_provider_required": True,
        "synthetic_fixtures_only": True,
        "authorized": False,
        "provider_request_authorized": False,
        "live_telemetry_authorized": False,
        "bfcl_generate_authorized": False,
        "bfcl_smoke_authorized": False,
        "bfcl_evaluate_authorized": False,
        "scorer_authorized": False,
        "full_baseline_authorized": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "gpt_5_2_active": False,
        "openrouter_allowed": False,
    }
    assert validate_packet(packet) == []


def test_artifact_matrix_and_boundary_pass() -> None:
    report = _report()
    assert report["variant_order"] == list(VARIANTS)
    assert len(report["records"]) == len(VARIANTS)
    assert validate_artifact(report) == []
    text = json.dumps(report, sort_keys=True).lower()
    for forbidden in ("provider payload", "raw prompt", "scorer diff", "candidate output"):
        assert forbidden not in text
