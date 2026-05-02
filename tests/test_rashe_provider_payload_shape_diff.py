import copy
import json
import subprocess
import sys
from pathlib import Path

from scripts.build_rashe_provider_payload_shape_diff import build_report, payload_shape
from scripts.check_rashe_provider_payload_shape_diff import validate
from scripts import rashe_source_provider_client as source_client

BUILD_SCRIPT = Path("scripts/build_rashe_provider_payload_shape_diff.py")
CHECK_SCRIPT = Path("scripts/check_rashe_provider_payload_shape_diff.py")
ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_payload_shape_diff.json")


def run_json(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.stdout, result.stderr
    return result, json.loads(result.stdout)


def signed_payload(**overrides):
    request = {
        "category": "agentic_web_search",
        "ordinal": 0,
        "provider_profile": "Chuangzhi/Novacode",
        "model": "gpt-4.1",
        "compact_sanitized_only": True,
        "raw_payload_capture_authorized": False,
        "raw_trace_capture_authorized": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
    }
    request.update(overrides)
    return source_client.build_source_diagnostic_chat_payload(request)


def test_shape_diff_builder_and_checker_pass_current_artifact():
    build_result, build_summary = run_json([sys.executable, str(BUILD_SCRIPT), "--compact", "--strict"])
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr
    assert build_summary["alignment_passed"] is True
    assert build_summary["source_input_read"] is False
    assert build_summary["diagnostic_written"] is False
    assert build_summary["candidate_generation_authorized"] is False
    assert build_summary["scorer_authorized"] is False
    assert build_summary["performance_evidence"] is False

    check_result, check_summary = run_json([sys.executable, str(CHECK_SCRIPT), "--compact", "--strict"])
    assert check_result.returncode == 0, check_result.stdout + check_result.stderr
    assert check_summary["provider_payload_shape_diff_passed"] is True


def test_shape_diff_contains_no_sensitive_payload_material():
    report = build_report()
    encoded = json.dumps(report, sort_keys=True).lower()
    for forbidden in ["case_id", "gold", "expected", "reference", "scorer_diff", "candidate_output", "gpt-4o"]:
        assert forbidden not in encoded
    assert "category=agentic_web_search" not in encoded
    assert "synthetic_preflight_ping" not in encoded


def test_phase_b_planned_payload_matches_minimal_chat_tools_shape():
    shape = payload_shape(signed_payload())
    assert shape["model"] == "gpt-4.1"
    assert shape["message_count"] == 1
    assert shape["messages_role_sequence"] == ["user"]
    assert shape["tools_count"] == 1
    assert shape["tool_choice_form"] == "function_object"
    assert shape["token_field_name"] == "max_tokens"
    assert shape["temperature_present"] is True
    flags = shape["tool_schema_feature_flags"]
    assert flags["function_tool"] is True
    assert flags["parameters_type_object"] is True
    assert flags["required_present"] is True
    assert flags["additional_properties_false"] is True
    assert flags["strict_present"] is False


def test_checker_rejects_variant_or_route_drift():
    report = build_report()
    report["phase_b_planned_payload_shape"]["model"] = "gpt-4o"
    report["gpt_4o_fallback_allowed"] = True
    blockers = validate(report)
    assert "shape_diff_phase_b_not_aligned:model" in blockers
    assert "shape_diff_gpt_4o_fallback_allowed_not_false:True" in blockers


def test_checker_rejects_source_input_diagnostics_and_downstream_flags():
    report = build_report()
    report["source_input_read"] = True
    report["diagnostic_written"] = True
    report["candidate_generation_authorized"] = True
    report["scorer_authorized"] = True
    report["performance_evidence"] = True
    blockers = validate(report)
    assert "shape_diff_source_input_read_not_false:True" in blockers
    assert "shape_diff_diagnostic_written_not_false:True" in blockers
    assert "shape_diff_candidate_generation_authorized_not_false:True" in blockers
    assert "shape_diff_scorer_authorized_not_false:True" in blockers
    assert "shape_diff_performance_evidence_not_false:True" in blockers


def test_checker_rejects_raw_schema_text_leakage():
    report = build_report()
    report["phase_b_planned_payload_shape"] = copy.deepcopy(report["phase_b_planned_payload_shape"])
    report["phase_b_planned_payload_shape"]["leaked_value"] = "case_id"
    blockers = validate(report)
    assert "shape_diff_phase_b_planned_payload_shape_drift" in blockers
    assert "shape_diff_forbidden_value_fragment:case_id" in blockers
