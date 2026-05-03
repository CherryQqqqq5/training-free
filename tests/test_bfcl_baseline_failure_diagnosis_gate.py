from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.build_bfcl_baseline_failure_plan_diagnosis import build
from scripts.check_bfcl_baseline_failure_diagnosis_gate import DEFAULT_PACKET, validate_diagnosis, validate_packet, check


def _packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def test_committed_pending_packet_passes_fail_closed_gate_after_build() -> None:
    diagnosis = build(DEFAULT_PACKET)
    assert diagnosis["no_provider"] is True
    assert diagnosis["no_bfcl_execution"] is True
    assert diagnosis["baseline_failure_summary_present"] is True
    assert diagnosis["command_template_present"] is True
    assert diagnosis["runner_script_present"] is True
    assert diagnosis["env_name_handoff_complete"] is True
    assert diagnosis["postcondition_checker_present"] is True
    assert diagnosis["missing_stage_observability"] is True
    assert diagnosis["live_failure_telemetry_gate_recommended"] is True
    assert validate_diagnosis(diagnosis) == []


def test_checker_accepts_committed_packet_and_written_diagnosis() -> None:
    summary = check(DEFAULT_PACKET)
    assert summary["bfcl_baseline_failure_diagnosis_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["authorized"] is False
    assert summary["no_provider"] is True
    assert summary["no_bfcl_execution"] is True


def test_rejects_execution_flags() -> None:
    for key in (
        "authorized",
        "provider_call_authorized",
        "bfcl_generate_authorized",
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
        packet = copy.deepcopy(_packet())
        packet[key] = True
        blockers = validate_packet(packet)
        assert any(key in blocker for blocker in blockers)


def test_rejects_wrong_route_or_scope() -> None:
    packet = copy.deepcopy(_packet())
    packet["route_profile"] = "openrouter"
    assert any("route_drift" in blocker for blocker in validate_packet(packet))
    packet = copy.deepcopy(_packet())
    packet["measurement_kind"] = "baseline_execution"
    assert any("measurement_kind" in blocker for blocker in validate_packet(packet))
    packet = copy.deepcopy(_packet())
    packet["no_provider"] = False
    assert any("no_provider" in blocker for blocker in validate_packet(packet))


def test_rejects_raw_secret_material() -> None:
    packet = copy.deepcopy(_packet())
    packet["endpoint_value"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_packet(packet))
    packet = copy.deepcopy(_packet())
    packet["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(packet))
    diagnosis = build(DEFAULT_PACKET)
    diagnosis["raw_prompt_text"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_diagnosis(diagnosis))


def test_diagnosis_requires_postconditions_and_suspected_stage() -> None:
    diagnosis = build(DEFAULT_PACKET)
    diagnosis["compact_metrics_expected"] = False
    assert any("compact_metrics_expected" in blocker for blocker in validate_diagnosis(diagnosis))
    diagnosis = build(DEFAULT_PACKET)
    diagnosis["suspected_failure_diagnosis_stage"] = ""
    assert any("suspected_stage" in blocker for blocker in validate_diagnosis(diagnosis))


def test_no_provider_diagnosis_does_not_run_baseline(tmp_path: Path) -> None:
    runner = tmp_path / "run_bfcl_v4_baseline.sh"
    runner.write_text("\n".join([
        "validate_model_split",
        "ensure_upstream_auth",
        "clean_run_state",
        "sync_bfcl_fixture_env.py",
        "grc_wait_proxy_healthy",
        "run_bfcl_preflight.py",
        "GENERATE_ARGS",
        "bfcl_fix_result_layout",
        "EVAL_ARGS",
        "aggregate_bfcl_metrics.py metrics.json failure_summary.json",
        "write_run_manifest.py run_manifest.json",
    ]), encoding="utf-8")
    diagnosis = build(DEFAULT_PACKET, runner_path=runner)
    assert diagnosis["no_provider"] is True
    assert diagnosis["no_bfcl_execution"] is True
    assert diagnosis["runner_script_present"] is True
    assert diagnosis["runner_stage_markers_missing"] == []
