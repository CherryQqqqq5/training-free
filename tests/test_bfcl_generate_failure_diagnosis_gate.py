from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_generate_failure_diagnosis_gate import (
    DEFAULT_DIAGNOSIS,
    DEFAULT_PACKET,
    REQUIRED_DIAGNOSIS_FIELDS,
    check,
    validate_diagnosis,
    validate_packet,
)


def _packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _diagnosis() -> dict:
    return json.loads(DEFAULT_DIAGNOSIS.read_text(encoding="utf-8"))


def test_committed_packet_and_diagnosis_pass_fail_closed_gate() -> None:
    summary = check(DEFAULT_PACKET, DEFAULT_DIAGNOSIS)
    assert summary["bfcl_generate_failure_diagnosis_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["authorized"] is False
    assert summary["prior_failed_stage"] == "bfcl_generate"
    assert summary["suspected_generate_failure_plan_stage"] == "bfcl_generate_failure_without_generate_error_class"
    assert summary["next_gate_recommended"] == "sanitized_bfcl_generate_failure_telemetry_gate"


def test_rejects_execution_authorization_flags() -> None:
    for key in (
        "authorized",
        "provider_request_authorized",
        "bfcl_generate_authorized",
        "bfcl_smoke_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        data = _packet()
        data[key] = True
        blockers = validate_packet(data)
        assert any(key in blocker for blocker in blockers)


def test_rejects_route_drift_and_missing_no_provider_scope() -> None:
    data = _packet()
    data["route_profile"] = "openrouter"
    assert any("route_drift" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["no_provider"] = False
    assert any("no_provider" in blocker for blocker in validate_packet(data))


def test_rejects_raw_secret_case_scorer_material() -> None:
    data = _packet()
    data["endpoint_value"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))
    diagnosis = _diagnosis()
    diagnosis["raw_log_content"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_diagnosis(diagnosis))


def test_requires_exact_diagnosis_fields_and_stage_recommendation() -> None:
    diagnosis = _diagnosis()
    for field in REQUIRED_DIAGNOSIS_FIELDS:
        modified = copy.deepcopy(diagnosis)
        modified.pop(field, None)
        blockers = validate_diagnosis(modified)
        assert any("diagnosis_missing_fields" in blocker for blocker in blockers)
    diagnosis = _diagnosis()
    diagnosis["suspected_generate_failure_plan_stage"] = ""
    assert any("suspected_generate_failure_plan_stage_missing" in blocker for blocker in validate_diagnosis(diagnosis))
    diagnosis = _diagnosis()
    diagnosis["next_gate_recommended"] = ""
    assert any("next_gate_recommended_missing" in blocker for blocker in validate_diagnosis(diagnosis))


def test_diagnosis_records_missing_generate_observability() -> None:
    diagnosis = _diagnosis()
    assert diagnosis["prior_failed_stage"] == "bfcl_generate"
    assert diagnosis["prior_stage_failure_class"] == "nonzero_1"
    assert diagnosis["generate_result_count_observable"] is False
    assert diagnosis["generate_error_class_observable"] is False
    assert diagnosis["missing_generate_stage_observability_fields"]
    assert diagnosis["next_gate_recommended"] == "sanitized_bfcl_generate_failure_telemetry_gate"
