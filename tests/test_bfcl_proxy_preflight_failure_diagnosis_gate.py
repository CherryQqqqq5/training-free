from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_proxy_preflight_failure_diagnosis_gate import (
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
    assert summary["bfcl_proxy_preflight_failure_diagnosis_gate_passed"] is True
    assert summary["approval_status"] in {"prepared", "pending"}
    assert summary["authorized"] is False
    assert summary["prior_suspected_substage"] == "preflight_not_completed"
    assert summary["suspected_proxy_preflight_failure_class"] == "local_proxy_preflight_probe_or_env_check_failed_without_sanitized_detail"
    assert summary["next_gate_recommended"] == "prepare_sanitized_proxy_preflight_failure_telemetry_gate"


def test_packet_rejects_provider_live_preflight_bfcl_and_scorer_flags() -> None:
    base = _packet()
    for key in (
        "authorized",
        "provider_request_authorized",
        "proxy_live_preflight_authorized",
        "bfcl_generate_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
    ):
        data = copy.deepcopy(base)
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_packet_rejects_candidate_and_performance_flags() -> None:
    base = _packet()
    for key in (
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


def test_packet_requires_no_live_scope_and_exact_fields() -> None:
    data = _packet()
    data["no_live_preflight"] = False
    assert any("no_live_scope" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["route_model"] = "gpt-5.2"
    assert any("route" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["allowed_diagnosis_fields"] = REQUIRED_DIAGNOSIS_FIELDS[:-1]
    assert any("allowed_diagnosis_fields" in blocker for blocker in validate_packet(data))


def test_diagnosis_requires_prior_stage_provider_boundary_and_next_gate() -> None:
    data = _diagnosis()
    data["prior_suspected_substage"] = "other"
    assert any("prior_suspected_substage" in blocker for blocker in validate_diagnosis(data))
    data = _diagnosis()
    data["provider_not_observed_prior"] = False
    assert any("provider_not_observed_prior" in blocker for blocker in validate_diagnosis(data))
    data = _diagnosis()
    data["next_gate_recommended"] = ""
    assert any("next_gate_recommended" in blocker for blocker in validate_diagnosis(data))


def test_diagnosis_rejects_missing_required_fields_and_extra_fields() -> None:
    data = _diagnosis()
    data.pop("suspected_proxy_preflight_failure_class")
    assert any("diagnosis_missing_fields" in blocker for blocker in validate_diagnosis(data))
    data = _diagnosis()
    data["extra"] = "shape"
    assert any("diagnosis_extra_fields" in blocker for blocker in validate_diagnosis(data))


def test_diagnosis_requires_missing_observability_fields() -> None:
    data = _diagnosis()
    data["missing_proxy_preflight_observability_fields"] = []
    assert any("missing_proxy_preflight_observability_fields_empty" in blocker for blocker in validate_diagnosis(data))


def test_rejects_raw_secret_case_scorer_provider_material() -> None:
    data = _packet()
    data["raw_prompt_value"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_packet(data))
    data = _diagnosis()
    data["endpoint_value"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_diagnosis(data))
    data = _diagnosis()
    data["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_diagnosis(data))
    data = _diagnosis()
    data["note"] = "http" + "://example.invalid"
    assert any("forbidden_value" in blocker for blocker in validate_diagnosis(data))


def test_required_fields_are_compact_shape_labels_only() -> None:
    diagnosis = _diagnosis()
    for field in REQUIRED_DIAGNOSIS_FIELDS:
        assert field in diagnosis
    assert diagnosis["proxy_health_probe_target_label"] == "local_proxy_health_path"
    assert diagnosis["preflight_request_target_label"] == "local_proxy_openai_compatible_chat_and_responses_paths"
