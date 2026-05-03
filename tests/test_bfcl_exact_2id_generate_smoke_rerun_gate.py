from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_exact_2id_generate_smoke_rerun_gate import (
    REQUIRED_COMPACT_FIELDS,
    REQUIRED_STOP_GATES,
    SIGNED_IDS,
    check,
    validate_packet,
)
from scripts.run_bfcl_exact_2id_generate_smoke_rerun import build_plan, execute_exact_2id_generate_smoke_rerun

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_generate_smoke_rerun_gate_packet.json")


def _packet() -> dict:
    return json.loads(PACKET.read_text(encoding="utf-8"))


def test_committed_pending_packet_passes_fail_closed_gate() -> None:
    summary = check(PACKET)
    assert summary["bfcl_exact_2id_generate_smoke_rerun_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["provider_request_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False
    assert summary["bfcl_smoke_authorized"] is False
    assert summary["signed_run_ids"] == list(SIGNED_IDS)


def test_rejects_pending_authorized_true() -> None:
    data = _packet()
    data["authorized"] = True
    assert any("authorized_not_false" in blocker for blocker in validate_packet(data))


def test_rejects_wrong_missing_extra_ids() -> None:
    for ids in (["web_search_base_0"], ["multi_turn_base_0"], ["web_search_base_0", "multi_turn_base_0", "extra_0"]):
        data = _packet()
        data["signed_run_ids"] = list(ids)
        data["run_id_count"] = len(ids)
        blockers = validate_packet(data)
        assert any("signed_run_ids_invalid" in blocker for blocker in blockers)


def test_rejects_evaluate_scorer_full_baseline_flags() -> None:
    for key in ("bfcl_evaluate_authorized", "scorer_authorized", "full_baseline_authorized", "evaluate_command_allowed", "scorer_command_allowed"):
        data = _packet()
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_candidate_performance_flags() -> None:
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        data = _packet()
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_raw_fields_endpoints_secrets() -> None:
    data = _packet()
    data["raw_provider_response_body"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["note"] = "https" + "://example.invalid"
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))


def test_rejects_route_drift_fallback_openrouter() -> None:
    for key, value in (("route_model", "gpt-5.2"), ("gpt_4o_fallback_allowed", True), ("openrouter_allowed", True), ("gpt_5_2_active", True)):
        data = copy.deepcopy(_packet())
        data[key] = value
        blockers = validate_packet(data)
        assert blockers


def test_dry_run_does_not_read_endpoint_key_or_execute_provider_or_generate() -> None:
    plan = build_plan(PACKET)
    assert plan["blockers"] == []
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["provider_request_executed"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["bfcl_smoke_executed"] is False
    assert plan["bfcl_evaluate_executed"] is False
    assert plan["scorer_executed"] is False
    assert plan["planned_run_ids"] == list(SIGNED_IDS)


def test_execute_pending_fails_closed_without_endpoint_key_or_execution(tmp_path: Path) -> None:
    summary = execute_exact_2id_generate_smoke_rerun(PACKET, tmp_path / "artifact.json")
    assert "exact_2id_generate_smoke_rerun_packet_not_approved" in summary["blockers"]
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["provider_request_executed"] is False
    assert summary["bfcl_generate_executed"] is False
    assert not (tmp_path / "artifact.json").exists()


def test_required_stop_gates_present() -> None:
    data = _packet()
    assert data["stop_gates"] == REQUIRED_STOP_GATES
    assert data["allowed_future_compact_fields"] == REQUIRED_COMPACT_FIELDS
    for gate in REQUIRED_STOP_GATES:
        mutated = _packet()
        mutated["stop_gates"] = [item for item in mutated["stop_gates"] if item != gate]
        assert any(f"stop_gate_missing:{gate}" in blocker for blocker in validate_packet(mutated))
