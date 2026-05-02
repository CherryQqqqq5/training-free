from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_exact_2id_generate_smoke_artifact import check as check_artifact, validate as validate_artifact
from scripts.check_bfcl_exact_2id_smoke_approval_packet import check as check_packet, validate_packet
from scripts.run_bfcl_exact_2id_generate_smoke import (
    SIGNED_IDS,
    _assert_generate_only_command,
    _generate_command,
    build_plan,
    execute_generate_smoke,
)

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_smoke_approval_packet.json")


def _valid_artifact() -> dict:
    return {
        "artifact_kind": "bfcl_exact_2id_generate_smoke_compact",
        "approval_status": "executed_generate_only",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "provider_profile": "Chuangzhi/Novacode",
        "run_ids": list(SIGNED_IDS),
        "case_count": 2,
        "provider_call_executed": True,
        "bfcl_generate_executed": True,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "gpt_5_2_active": False,
        "raw_prompt_persisted": False,
        "raw_case_persisted": False,
        "raw_provider_payload_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "endpoint_or_key_committed": False,
        "records": [
            {
                "run_id": "web_search_base_0",
                "status": "generated",
                "empty_model_response_detected": False,
                "no_tool_text_recorded": False,
                "tool_call_detected": True,
                "protocol_error_detected": False,
                "route_profile": "novacode",
                "route_model": "gpt-4.1",
                "candidate_runtime_activation_authorized": False,
                "candidate_jsonl_authorized": False,
                "candidate_pool_ready": False,
                "bfcl_evaluate_executed": False,
                "scorer_executed": False,
                "full_baseline_executed": False,
                "performance_evidence": False,
                "sota_3pp_claim_ready": False,
                "huawei_acceptance_ready": False,
            },
            {
                "run_id": "multi_turn_base_0",
                "status": "no_tool_text",
                "empty_model_response_detected": False,
                "no_tool_text_recorded": True,
                "tool_call_detected": False,
                "protocol_error_detected": False,
                "route_profile": "novacode",
                "route_model": "gpt-4.1",
                "candidate_runtime_activation_authorized": False,
                "candidate_jsonl_authorized": False,
                "candidate_pool_ready": False,
                "bfcl_evaluate_executed": False,
                "scorer_executed": False,
                "full_baseline_executed": False,
                "performance_evidence": False,
                "sota_3pp_claim_ready": False,
                "huawei_acceptance_ready": False,
            },
        ],
    }


def test_exact_smoke_packet_checker_includes_generate_only_paths() -> None:
    summary = check_packet(PACKET)
    assert summary["bfcl_exact_2id_smoke_approval_packet_passed"] is True
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    assert packet["generate_only_runner_path"] == "scripts/run_bfcl_exact_2id_generate_smoke.py"
    assert packet["compact_artifact_checker_path"] == "scripts/check_bfcl_exact_2id_generate_smoke_artifact.py"
    assert packet["bfcl_generate_authorized"] is False
    assert packet["bfcl_evaluate_authorized"] is False


def test_dry_run_plan_reads_no_endpoint_or_key_and_calls_no_provider() -> None:
    plan = build_plan(PACKET)
    assert plan["provider_call_executed"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["bfcl_evaluate_executed"] is False
    assert plan["scorer_executed"] is False
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["run_ids"] == list(SIGNED_IDS)


def test_execute_mode_fails_closed_while_packet_pending(tmp_path: Path) -> None:
    summary = execute_generate_smoke(output=tmp_path / "out.json", packet_path=PACKET, run_root=tmp_path / "run")
    assert summary["provider_call_executed"] is False
    assert summary["bfcl_generate_executed"] is False
    assert summary["bfcl_evaluate_executed"] is False
    assert summary["scorer_executed"] is False
    assert summary["blockers"]
    assert not (tmp_path / "out.json").exists()


def test_generate_only_runner_command_has_no_evaluate_or_scorer(tmp_path: Path) -> None:
    command = _generate_command(tmp_path / "run", 8131, Path("configs/runtime_bfcl_structured.yaml"), Path("rules/baseline_empty"))
    _assert_generate_only_command(command)
    joined = " ".join(command)
    assert " generate " in f" {joined} "
    assert " evaluate " not in f" {joined} "
    assert "aggregate_bfcl_metrics.py" not in joined
    assert "run_bfcl_v4_baseline.sh" not in joined


def test_generate_only_command_scan_rejects_evaluate() -> None:
    try:
        _assert_generate_only_command(["python", "scripts/run_bfcl_cli.py", "evaluate"])
    except RuntimeError as exc:
        assert "forbidden_evaluate_or_scorer_command" in str(exc)
    else:
        raise AssertionError("expected evaluate command rejection")


def test_signed_ids_exactly_enforced_in_packet() -> None:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    packet["signed_run_ids"] = ["web_search_base_0"]
    blockers = validate_packet(packet)
    assert any("signed_run_ids_invalid" in blocker for blocker in blockers)


def test_artifact_checker_accepts_compact_valid_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text(json.dumps(_valid_artifact(), indent=2), encoding="utf-8")
    assert check_artifact(artifact)["bfcl_exact_2id_generate_smoke_artifact_passed"] is True


def test_artifact_checker_rejects_extra_ids_and_missing_ids() -> None:
    data = _valid_artifact()
    data["run_ids"] = ["web_search_base_0", "multi_turn_base_0", "extra_0"]
    data["case_count"] = 3
    blockers = validate_artifact(data)
    assert any("run_ids_invalid" in blocker for blocker in blockers)
    assert any("case_count_invalid" in blocker for blocker in blockers)


def test_artifact_checker_rejects_scorer_evaluate_flags() -> None:
    data = _valid_artifact()
    data["bfcl_evaluate_executed"] = True
    data["scorer_executed"] = True
    data["records"][0]["bfcl_evaluate_executed"] = True
    blockers = validate_artifact(data)
    assert any("bfcl_evaluate_executed_not_false" in blocker for blocker in blockers)
    assert any("scorer_executed_not_false" in blocker for blocker in blockers)


def test_artifact_checker_rejects_raw_markers_route_drift_candidate_performance() -> None:
    data = _valid_artifact()
    data["route_model"] = "gpt-4o"
    data["candidate_pool_ready"] = True
    data["performance_evidence"] = True
    data["records"][0]["status"] = "raw prompt leaked"
    blockers = validate_artifact(data)
    assert "route_drift" in blockers
    assert any("candidate_pool_ready_not_false" in blocker for blocker in blockers)
    assert any("performance_evidence_not_false" in blocker for blocker in blockers)
    assert any("forbidden_value" in blocker for blocker in blockers)


def test_artifact_checker_rejects_endpoint_and_key_literals() -> None:
    data = _valid_artifact()
    data["records"][0]["status"] = "https" + "://example.invalid/raw"
    blockers = validate_artifact(data)
    assert any("forbidden_value" in blocker for blocker in blockers)
    data = _valid_artifact()
    data["records"][0]["status"] = "sk-" + "A" * 32
    blockers = validate_artifact(data)
    assert any("key_literal_forbidden" in blocker for blocker in blockers)
