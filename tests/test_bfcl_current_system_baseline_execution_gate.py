from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.build_bfcl_current_system_baseline_execution_plan import build
from scripts.check_bfcl_current_system_baseline_execution_gate import DEFAULT_PACKET, validate, check


def _packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _pending_packet() -> dict:
    data = copy.deepcopy(_packet())
    data["approval_status"] = "pending"
    for key in (
        "authorized",
        "provider_call_authorized",
        "bfcl_generate_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
    ):
        data[key] = False
    return data


def test_committed_approved_packet_passes_baseline_only_gate() -> None:
    summary = check(DEFAULT_PACKET)
    assert summary["bfcl_current_system_baseline_execution_gate_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["authorized"] is True
    assert summary["measurement_kind"] == "current_system_baseline_only"
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
        data = _pending_packet()
        data[key] = True
        blockers = validate(data, current_head=data["target_commit_for_measurement"])
        assert any(key in blocker for blocker in blockers)


def test_rejects_candidate_and_performance_flags() -> None:
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "candidate_specs_activated",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        data = _pending_packet()
        data[key] = True
        blockers = validate(data, current_head=data["target_commit_for_measurement"])
        assert any(key in blocker for blocker in blockers)


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


def test_rejects_wrong_measurement_kind_or_broader_claim() -> None:
    data = copy.deepcopy(_packet())
    data["measurement_kind"] = "candidate_comparison"
    assert any("measurement_kind_invalid" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))
    data = copy.deepcopy(_packet())
    data["claim_policy"]["not_3pp_claim"] = False
    assert any("claim_policy_not_3pp_claim_not_true" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))


def test_requires_case_scope_categories_and_runner_command() -> None:
    data = copy.deepcopy(_packet())
    data["case_scope_protocol"]["categories"] = ["simple"]
    assert any("case_scope_categories_missing" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))
    data = copy.deepcopy(_packet())
    data["runner_command_template"] = []
    blockers = validate(data, current_head=data["target_commit_for_measurement"])
    assert any("baseline_runner_missing" in blocker for blocker in blockers)
    assert any("runner_route_not_frozen" in blocker for blocker in blockers)


def test_requires_output_roots_and_compact_schema() -> None:
    data = copy.deepcopy(_packet())
    data["output_roots"].pop("compact_metrics")
    assert any("output_root_missing:compact_metrics" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))
    data = copy.deepcopy(_packet())
    data["compact_manifest_schema"]["raw_outputs_committed"] = True
    assert any("compact_manifest_schema_invalid" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))
    data = copy.deepcopy(_packet())
    data["compact_metrics_schema"]["performance_evidence"] = True
    assert any("compact_metrics_schema_invalid" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))


def test_rejects_output_boundary_broadening() -> None:
    data = copy.deepcopy(_packet())
    data["output_boundary_policy"]["commit_traces"] = True
    assert any("boundary_commit_traces_not_false" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))
    data = copy.deepcopy(_packet())
    data["output_boundary_policy"]["commit_compact_metrics"] = False
    assert any("boundary_commit_compact_metrics_not_true" in blocker for blocker in validate(data, current_head=data["target_commit_for_measurement"]))


def test_rejects_raw_secret_fields_and_values() -> None:
    data = copy.deepcopy(_packet())
    data["endpoint_value"] = "shape"
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
    data.pop("target_commit_current_head_mismatch_justification", None)
    assert any("target_commit_not_current_head" in blocker for blocker in validate(data, current_head="1" * 40))


def test_target_commit_mismatch_allowed_with_gate_only_justification() -> None:
    data = copy.deepcopy(_packet())
    data["target_commit_for_measurement"] = "0" * 40
    blockers = validate(data, current_head="1" * 40)
    assert not any("target_commit_not_current_head" in blocker for blocker in blockers)


def test_plan_builder_is_no_execution_and_freezes_outputs() -> None:
    plan = build(DEFAULT_PACKET)
    assert plan["gate_passed"] is True
    assert plan["authorized"] is True
    assert plan["provider_call_authorized"] is True
    assert plan["bfcl_generate_authorized"] is True
    assert plan["bfcl_evaluate_authorized"] is True
    assert plan["scorer_authorized"] is True
    assert plan["full_baseline_authorized"] is True
    assert plan["candidate_runtime_activation_authorized"] is False
    assert plan["performance_evidence"] is False
    assert plan["sota_3pp_claim_ready"] is False
    assert plan["huawei_acceptance_ready"] is False
    assert plan["output_roots"]["compact_metrics"].endswith("bfcl_current_system_baseline_compact_metrics.json")
    assert "scripts/run_bfcl_v4_baseline.sh" in plan["runner_command_template"]
