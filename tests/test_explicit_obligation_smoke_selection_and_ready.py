from __future__ import annotations

import json
from pathlib import Path

from scripts.select_explicit_obligation_smoke_candidates import evaluate as evaluate_selection
from scripts.diagnose_explicit_obligation_baseline_dry_audit import evaluate as evaluate_dry
import scripts.check_explicit_obligation_smoke_ready as ready


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _trace(root: Path, rel: str, outputs: list[dict]) -> None:
    _write(root / rel, {"final_response": {"output": outputs}})


def _record(audit_id: str, bfcl_id: str, trace: str, *, record_type: str = "positive", negative_type: str | None = None) -> dict:
    return {
        "audit_case_id": audit_id,
        "source_audit_record_id": audit_id,
        "bfcl_case_id": bfcl_id,
        "category": "memory_kv",
        "trace_relative_path": trace,
        "prompt_match_count": 1,
        "dependency_closure_ready": True,
        "operation": "retrieve" if record_type == "positive" else None,
        "expected_policy": "soft_guidance_only_memory_retrieve" if record_type == "positive" else "no_activation_expected",
        "negative_control_type": negative_type,
    }


def test_selection_fails_closed_for_all_ceiling_positives_and_active_controls(tmp_path: Path) -> None:
    source = tmp_path / "source"
    positives = []
    controls = []
    for i in range(12):
        rel = f"memory_kv/baseline/traces/p{i}.json"
        _trace(source, rel, [{"type": "function_call", "name": "core_memory_retrieve", "arguments": "{}"}])
        positives.append(_record(f"p{i}", f"memory_kv_{i}", rel))
    for i in range(8):
        rel = f"memory_kv/baseline/traces/c{i}.json"
        _trace(source, rel, [{"type": "function_call", "name": "archival_memory_key_search", "arguments": "{}"}])
        controls.append(_record(f"c{i}", f"memory_kv_c{i}", rel, record_type="control", negative_type="no_memory_operation_intent"))
    protocol = tmp_path / "protocol.json"
    _write(protocol, {"selected_positive_cases": positives, "selected_control_cases": controls})

    report = evaluate_selection(protocol, source)

    assert report["selection_gate_passed"] is False
    assert report["non_ceiling_positive_available_count"] == 0
    assert report["true_control_available_count"] == 0
    assert "blocked_insufficient_non_ceiling_positives" in report["blockers"]
    assert "blocked_insufficient_true_controls" in report["blockers"]
    assert report["materialized_protocol_negative_control_activation_count"] == 8


def test_selection_passes_with_unique_non_ceiling_positives_and_clean_controls(tmp_path: Path) -> None:
    source = tmp_path / "source"
    positives = []
    controls = []
    for i in range(12):
        rel = f"memory_kv/baseline/traces/p{i}.json"
        _trace(source, rel, [{"type": "message", "content": "answer"}])
        positives.append(_record(f"p{i}", f"memory_kv_{i}", rel))
    for i in range(8):
        rel = f"memory_kv/baseline/traces/c{i}.json"
        _trace(source, rel, [{"type": "message", "content": "answer"}])
        controls.append(_record(f"c{i}", f"memory_kv_c{i}", rel, record_type="control", negative_type="no_memory_operation_intent"))
    protocol = tmp_path / "protocol.json"
    _write(protocol, {"selected_positive_cases": positives, "selected_control_cases": controls})

    report = evaluate_selection(protocol, source)

    assert report["selection_gate_passed"] is True
    assert report["selected_positive_count"] == 12
    assert report["selected_control_count"] == 8
    assert report["selected_smoke_baseline_control_activation_count"] == 0


def test_dry_audit_duplicate_positive_blocks_ready(tmp_path: Path) -> None:
    source = tmp_path / "source"
    rel = "memory_kv/baseline/traces/p.json"
    _trace(source, rel, [{"type": "message", "content": "answer"}])
    positives = [_record(f"p{i}", "memory_kv_same", rel) for i in range(12)]
    controls = []
    for i in range(8):
        crel = f"memory_kv/baseline/traces/c{i}.json"
        _trace(source, crel, [{"type": "message", "content": "answer"}])
        controls.append(_record(f"c{i}", f"memory_kv_c{i}", crel, record_type="control", negative_type="no_memory_operation_intent"))
    protocol = tmp_path / "protocol.json"
    _write(protocol, {"selected_positive_cases": positives, "selected_control_cases": controls})

    report = evaluate_dry(protocol, source)

    assert report["smoke_selection_ready_after_baseline_dry_audit"] is False
    assert "duplicate_bfcl_case_id_present" in report["blockers"]
    assert "duplicate_trace_path_present" in report["blockers"]


def test_ready_checker_requires_all_gates(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "exec.json"
    dry = tmp_path / "dry.json"
    selection = tmp_path / "selection.json"
    _write(executable, {"bfcl_executable_manifest_ready": True, "candidate_commands": [], "planned_commands": []})
    _write(dry, {"smoke_selection_ready_after_baseline_dry_audit": False, "blockers": ["baseline_ceiling_positive_count_above_2"]})
    _write(selection, {"selection_gate_passed": False, "blockers": ["blocked_insufficient_non_ceiling_positives"]})
    monkeypatch.setattr(ready, "_artifact_boundary_status", lambda: {"artifact_boundary_passed": True, "forbidden_artifact_count": 0, "forbidden_artifact_samples": []})
    monkeypatch.setattr(ready, "evaluate_m28pre", lambda: {"scorer_authorization_ready": True})

    report = ready.evaluate(executable, dry, selection)

    assert report["ready"] is False
    assert report["gates"]["bfcl_executable_manifest_ready"] is True
    assert "smoke_selection_not_ready_after_baseline_dry_audit" in report["blockers"]
    assert report["next_required_action"] == "rebuild_candidate_pool_or_upgrade_theory_prior_before_smoke"
    assert report["next_required_actions"][0] == "rebuild_candidate_pool_or_upgrade_theory_prior_before_smoke"


def test_ready_checker_passes_only_when_all_gates_pass(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "exec.json"
    dry = tmp_path / "dry.json"
    selection = tmp_path / "selection.json"
    _write(executable, {"bfcl_executable_manifest_ready": True, "candidate_commands": [], "planned_commands": []})
    _write(dry, {"smoke_selection_ready_after_baseline_dry_audit": True, "blockers": []})
    _write(selection, {"selection_gate_passed": True, "blockers": []})
    monkeypatch.setattr(ready, "_artifact_boundary_status", lambda: {"artifact_boundary_passed": True, "forbidden_artifact_count": 0, "forbidden_artifact_samples": []})
    monkeypatch.setattr(ready, "evaluate_m28pre", lambda: {"scorer_authorization_ready": True})

    report = ready.evaluate(executable, dry, selection)

    assert report["ready"] is True
    assert report["execution_allowed"] is False
    assert report["planned_commands"] == []
    assert report["next_required_action"] == "request_explicit_smoke_execution_approval"
    assert report["next_required_actions"] == ["request_explicit_smoke_execution_approval"]



def test_ready_checker_prefers_zero_selection_activation(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "exec.json"
    dry = tmp_path / "dry.json"
    selection = tmp_path / "selection.json"
    _write(executable, {"bfcl_executable_manifest_ready": True, "candidate_commands": [], "planned_commands": []})
    _write(dry, {"smoke_selection_ready_after_baseline_dry_audit": False, "selected_smoke_baseline_control_activation_count": 8, "blockers": []})
    _write(selection, {"selection_gate_passed": False, "selected_smoke_baseline_control_activation_count": 0, "blockers": ["blocked_insufficient_true_controls"]})
    monkeypatch.setattr(ready, "_artifact_boundary_status", lambda: {"artifact_boundary_passed": True, "forbidden_artifact_count": 0, "forbidden_artifact_samples": []})
    monkeypatch.setattr(ready, "evaluate_m28pre", lambda: {"scorer_authorization_ready": True})

    report = ready.evaluate(executable, dry, selection)

    assert report["selected_smoke_baseline_control_activation_count"] == 0
    assert report["ready"] is False
