import json
from pathlib import Path

from scripts.build_explicit_obligation_smoke_protocol import evaluate


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_protocol_requires_separate_approval_and_no_commands(tmp_path: Path):
    audit = tmp_path / "audit.json"
    memory = tmp_path / "memory.json"
    _write(audit, {"smoke_ready": True, "eligible_by_capability": {"memory_retrieve": 12, "read_content": 1}})
    _write(memory, {
        "candidate_records": [
            {"candidate_id": f"c{i}", "candidate_ready": True, "risk_level": "low", "operation": "retrieve", "category": "memory_kv", "trace_relative_path": f"t{i}.json"}
            for i in range(12)
        ],
        "sample_rejections": [
            {"source_audit_record_id": f"r{i}", "rejection_reason": f"reason{i}", "category": "memory_kv", "trace_relative_path": f"r{i}.json"}
            for i in range(6)
        ],
    })
    report = evaluate(audit, memory)
    assert report["protocol_ready_for_review"] is True
    assert report["separate_approval_required_before_execution"] is True
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["execution_allowed"] is False
    assert report["approval_status"] == "pending"
    assert report["allowed_provider_profiles"] == ["novacode"]
    assert report["candidate_set_frozen"] is True
    assert len(report["frozen_candidate_hash"]) == 64
    assert report["hard_constraints"]["exact_tool_choice"] is False


def test_protocol_fails_without_controls(tmp_path: Path):
    audit = tmp_path / "audit.json"
    memory = tmp_path / "memory.json"
    _write(audit, {"smoke_ready": True, "eligible_by_capability": {"memory_retrieve": 12}})
    _write(memory, {
        "candidate_records": [
            {"candidate_id": f"c{i}", "candidate_ready": True, "risk_level": "low", "operation": "retrieve"}
            for i in range(12)
        ],
        "sample_rejections": [],
    })
    report = evaluate(audit, memory)
    assert report["protocol_ready_for_review"] is False
    assert "control_cases_below_6" in report["blockers"]
