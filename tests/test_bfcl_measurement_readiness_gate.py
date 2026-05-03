from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.build_bfcl_measurement_readiness_summary import build
from scripts.check_bfcl_measurement_readiness_gate import DEFAULT_PACKET, check, validate


def _packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def test_committed_pending_packet_passes_fail_closed_gate() -> None:
    summary = check(DEFAULT_PACKET)
    assert summary["bfcl_measurement_readiness_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["authorized"] is False
    assert summary["route_profile"] == "novacode"
    assert summary["route_model"] == "gpt-4.1"
    assert summary["performance_evidence"] is False


def test_rejects_execution_authorization_while_pending() -> None:
    for key in (
        "authorized",
        "provider_call_authorized",
        "bfcl_generate_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
    ):
        data = copy.deepcopy(_packet())
        data[key] = True
        assert any(key in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))


def test_rejects_candidate_and_performance_flags() -> None:
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
        "candidate_specs_activated",
        "scorer_feedback_enabled",
    ):
        data = copy.deepcopy(_packet())
        data[key] = True
        assert any(key in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))


def test_rejects_route_fallback_openrouter_active_gpt52() -> None:
    variants = (
        ("route_profile", "openrouter"),
        ("route_model", "gpt-5.2"),
        ("fallback_allowed", True),
        ("gpt_4o_fallback_allowed", True),
        ("openrouter_allowed", True),
        ("gpt_5_2_active", True),
    )
    for key, value in variants:
        data = copy.deepcopy(_packet())
        data[key] = value
        assert validate(data, current_head=data["target_commit_for_measurement"])


def test_requires_candidates_inert() -> None:
    data = copy.deepcopy(_packet())
    data["candidates_inert"] = False
    assert any("candidates_inert_not_true" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))


def test_rejects_raw_secret_fields_and_values() -> None:
    data = copy.deepcopy(_packet())
    data["raw_prompt_value"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))
    data = copy.deepcopy(_packet())
    data["note"] = "https" + "://example.invalid"
    assert any("forbidden_value" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))
    data = copy.deepcopy(_packet())
    data["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))


def test_target_commit_mismatch_requires_explicit_justification() -> None:
    data = copy.deepcopy(_packet())
    data["target_commit_for_measurement"] = "0" * 40
    data["reproducibility"]["commit"] = "0" * 40
    data.pop("target_commit_current_head_mismatch_justification", None)
    assert any("target_commit_not_current_head" in blocker for blocker in validate(data, current_head="1" * 40))


def test_target_commit_mismatch_allowed_with_gate_only_justification() -> None:
    data = copy.deepcopy(_packet())
    data["target_commit_for_measurement"] = "0" * 40
    data["reproducibility"]["commit"] = "0" * 40
    blockers = validate(data, current_head="1" * 40)
    assert not any("target_commit_not_current_head" in blocker for blocker in blockers)


def test_requires_reproducibility_fields() -> None:
    data = copy.deepcopy(_packet())
    data["reproducibility"]["config_files"] = []
    assert any("reproducibility_config_files_missing" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))
    data = copy.deepcopy(_packet())
    data["reproducibility"]["env_values_committed"] = True
    assert any("env_values_committed_not_false" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))


def test_rejects_raw_output_policy() -> None:
    data = copy.deepcopy(_packet())
    data["output_policy"]["commit_raw_traces"] = True
    assert any("commit_raw_traces" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))


def test_summary_builder_is_compact_and_no_execution() -> None:
    summary = build(DEFAULT_PACKET)
    assert summary["readiness_gate_passed"] is True
    assert summary["authorized"] is False
    assert summary["provider_call_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False
    assert summary["bfcl_evaluate_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["full_baseline_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["sota_3pp_claim_ready"] is False
    assert summary["huawei_acceptance_ready"] is False
