from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_pregenerate_failure_diagnosis_gate import (
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


def test_committed_packet_and_diagnosis_pass_fail_closed() -> None:
    summary = check(DEFAULT_PACKET, DEFAULT_DIAGNOSIS)
    assert summary["bfcl_pregenerate_failure_diagnosis_gate_passed"] is True
    assert summary["approval_status"] in {"prepared", "pending"}
    assert summary["authorized"] is False
    assert summary["prior_suspected_stage"] == "pre_generate_failure"
    assert summary["pre_generate_failure_candidate_class"] == "post_preflight_or_preamble_before_bfcl_generate_marker_needs_substage_observability"
    assert summary["next_gate_recommended"] == "no_provider_pregenerate_substage_observability_patch_gate"


def test_packet_rejects_execution_flags() -> None:
    base = _packet()
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
        data = copy.deepcopy(base)
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_packet_rejects_wrong_route_and_non_offline_scope() -> None:
    data = _packet()
    data["route_model"] = "gpt-5.2"
    assert any("route" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["no_provider"] = False
    assert any("no_provider" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["no_bfcl_execution"] = False
    assert any("no_bfcl_execution" in blocker for blocker in validate_packet(data))


def test_rejects_raw_secret_case_scorer_material() -> None:
    data = _packet()
    data["raw_prompt_value"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_packet(data))
    data = _diagnosis()
    data["endpoint_value"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_diagnosis(data))
    data = _diagnosis()
    data["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_diagnosis(data))


def test_rejects_missing_required_diagnosis_fields() -> None:
    data = _diagnosis()
    data.pop("next_gate_recommended")
    blockers = validate_diagnosis(data)
    assert any("diagnosis_missing_fields" in blocker for blocker in blockers)
    assert any("next_gate_recommended" in blocker for blocker in blockers)


def test_requires_observability_gap_and_candidate_class() -> None:
    data = _diagnosis()
    data["missing_observability_fields"] = []
    assert any("missing_observability_fields_empty" in blocker for blocker in validate_diagnosis(data))
    data = _diagnosis()
    data["pre_generate_failure_candidate_class"] = ""
    assert any("pre_generate_failure_candidate_class_missing" in blocker for blocker in validate_diagnosis(data))


def test_allowed_fields_exact() -> None:
    packet = _packet()
    assert packet["allowed_diagnosis_fields"] == REQUIRED_DIAGNOSIS_FIELDS
    diagnosis = _diagnosis()
    for field in REQUIRED_DIAGNOSIS_FIELDS:
        assert field in diagnosis
