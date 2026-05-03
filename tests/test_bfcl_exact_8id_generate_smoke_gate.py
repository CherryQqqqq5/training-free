from __future__ import annotations

import copy
import json
import subprocess
from contextlib import nullcontext
from pathlib import Path

from scripts.check_bfcl_exact_8id_generate_smoke_gate import (
    REQUIRED_COMPACT_FIELDS,
    REQUIRED_STOP_GATES,
    SIGNED_IDS,
    check,
    validate_packet,
)
from scripts.run_bfcl_exact_8id_generate_smoke import (
    SIGNED_RUN_IDS_BY_CATEGORY,
    _temporary_8id_manifest,
    build_plan,
    execute_exact_8id_generate_smoke,
)

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_8id_generate_smoke_gate_packet.json")


def _packet() -> dict:
    return json.loads(PACKET.read_text(encoding="utf-8"))


def test_committed_pending_packet_passes_fail_closed_gate() -> None:
    summary = check(PACKET)
    assert summary["bfcl_exact_8id_generate_smoke_gate_passed"] is True
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
    variants = [
        SIGNED_IDS[:7],
        ["web_search_base_0"] + SIGNED_IDS[2:],
        list(SIGNED_IDS) + ["extra_0"],
    ]
    for ids in variants:
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
    summary = execute_exact_8id_generate_smoke(PACKET, tmp_path / "artifact.json")
    assert "exact_8id_generate_smoke_packet_not_approved" in summary["blockers"]
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["provider_request_executed"] is False
    assert summary["bfcl_generate_executed"] is False
    assert not (tmp_path / "artifact.json").exists()


def test_approved_execute_path_with_mocks_reaches_pre_execution_without_real_provider(tmp_path: Path) -> None:
    data = _packet()
    data["approval_status"] = "approved"
    data["authorized"] = True
    data["provider_request_authorized"] = True
    data["bfcl_generate_authorized"] = True
    data["bfcl_smoke_authorized"] = True
    packet_path = tmp_path / "approved_packet.json"
    packet_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    calls: dict[str, object] = {}

    class FakeProc:
        def terminate(self) -> None:
            calls["terminated"] = True

        def wait(self, timeout: int) -> None:
            calls["wait_timeout"] = timeout

        def kill(self) -> None:
            calls["killed"] = True

    def fake_start_proxy(port, trace_dir, runtime_config, rules_dir, log_path):
        calls["start_proxy"] = {"port": port, "trace_dir_name": trace_dir.name, "log_name": log_path.name}
        return FakeProc()

    def fake_run_generate(command):
        calls["generate_command"] = command
        assert "generate" in command
        assert "evaluate" not in command
        assert ",".join([
            "web_search_base",
            "memory_kv",
            "multi_turn_base",
            "multi_turn_long_context",
            "multi_turn_miss_param",
            "multi_turn_miss_func",
            "irrelevance",
            "live_irrelevance",
        ]) in command
        return subprocess.CompletedProcess(command, 0)

    def fake_classify(run_id: str, result_root: Path) -> dict:
        return {
            "run_id": run_id,
            "status": "generated",
            "empty_model_response_detected": False,
            "no_tool_text_recorded": False,
            "tool_call_detected": True,
            "protocol_error_detected": False,
        }

    output = tmp_path / "eight.json"
    summary = execute_exact_8id_generate_smoke(
        packet_path,
        output,
        tmp_path / "run_root",
        8138,
        start_proxy=fake_start_proxy,
        run_generate=fake_run_generate,
        classify_result=fake_classify,
        sync_fixture_env=lambda run_root, port: calls.setdefault("sync_fixture_env", port),
        manifest_context=nullcontext,
    )
    assert summary["blockers"] == []
    assert summary["provider_request_executed"] is True
    assert summary["bfcl_generate_executed"] is True
    assert summary["bfcl_evaluate_executed"] is False
    assert summary["scorer_executed"] is False
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["signed_run_ids"] == list(SIGNED_IDS)
    assert artifact["stop_gate_triggered"] == "none"
    assert artifact["smoke_passed"] is True
    assert not (tmp_path / "run_root").exists()


def test_temporary_8id_manifest_uses_signed_category_schema_and_cleans_up(tmp_path: Path) -> None:
    manifest = tmp_path / "test_case_ids_to_generate.json"
    with _temporary_8id_manifest(manifest):
        assert json.loads(manifest.read_text(encoding="utf-8")) == SIGNED_RUN_IDS_BY_CATEGORY
    assert not manifest.exists()


def test_required_stop_gates_present() -> None:
    data = _packet()
    assert data["stop_gates"] == REQUIRED_STOP_GATES
    assert data["allowed_future_compact_fields"] == REQUIRED_COMPACT_FIELDS
    for gate in REQUIRED_STOP_GATES:
        mutated = _packet()
        mutated["stop_gates"] = [item for item in mutated["stop_gates"] if item != gate]
        assert any(f"stop_gate_missing:{gate}" in blocker for blocker in validate_packet(mutated))
