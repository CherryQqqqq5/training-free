from __future__ import annotations

import json
from pathlib import Path

import scripts.check_explicit_obligation_smoke_executability as checker


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_protocol(path: Path, *, case_id: str = "memory_operation_obligation_0001", trace: str = "memory_kv/baseline/traces/t1.json") -> None:
    _write(path, {
        "protocol_id": "explicit_obligation_memory_heavy_smoke_v1",
        "protocol_ready_for_review": True,
        "approval_status": "pending",
        "positive_cases": [{"case_id": case_id, "category": "memory_kv", "trace_relative_path": trace}],
        "control_cases": [],
    })


def test_audit_candidate_ids_fail_closed_without_bfcl_mapping(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(checker, "load_dataset_entry", lambda category, include_prereq=True: [
        {"id": "memory_kv_0-customer-0", "depends_on": []},
    ])
    source = tmp_path / "source"
    protocol = tmp_path / "protocol.json"
    _write_protocol(protocol)
    _write(source / "memory_kv/baseline/bfcl/test_case_ids_to_generate.json", {"memory_kv": ["memory_kv_0-customer-0"]})
    _write(source / "memory_kv/baseline/traces/t1.json", {"trace_id": "trace-only"})

    report = checker.evaluate(protocol, source)

    assert report["bfcl_executable_manifest_ready"] is False
    assert report["missing_bfcl_case_id_count"] == 1
    assert report["protocol_id_is_audit_id_count"] == 1
    assert "explicit_protocol_not_bfcl_executable" in report["blockers"]
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["next_required_action"] == "materialize_explicit_obligation_candidates_to_bfcl_case_ids_before_smoke"


def test_protocol_case_id_can_be_executable_with_dependency_closure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(checker, "load_dataset_entry", lambda category, include_prereq=True: [
        {"id": "memory_kv_prereq_0-customer-0", "depends_on": []},
        {"id": "memory_kv_0-customer-0", "depends_on": ["memory_kv_prereq_0-customer-0"]},
    ])
    source = tmp_path / "source"
    protocol = tmp_path / "protocol.json"
    _write_protocol(protocol, case_id="memory_kv_0-customer-0")
    _write(source / "memory_kv/baseline/bfcl/test_case_ids_to_generate.json", {"memory_kv": ["memory_kv_0-customer-0"]})
    _write(source / "memory_kv/baseline/traces/t1.json", {"trace_id": "trace-only"})

    report = checker.evaluate(protocol, source)

    assert report["bfcl_executable_manifest_ready"] is True
    assert report["executable_case_id_count"] == 1
    assert report["dependency_ready_record_count"] == 1
    assert report["records"][0]["generation_case_ids"] == ["memory_kv_prereq_0-customer-0", "memory_kv_0-customer-0"]


def test_trace_explicit_case_id_can_map_when_protocol_id_is_audit_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(checker, "load_dataset_entry", lambda category, include_prereq=True: [
        {"id": "memory_kv_0-customer-0", "depends_on": []},
    ])
    source = tmp_path / "source"
    protocol = tmp_path / "protocol.json"
    _write_protocol(protocol)
    _write(source / "memory_kv/baseline/bfcl/test_case_ids_to_generate.json", {"memory_kv": ["memory_kv_0-customer-0"]})
    _write(source / "memory_kv/baseline/traces/t1.json", {"bfcl_case_id": "memory_kv_0-customer-0"})

    report = checker.evaluate(protocol, source)

    assert report["bfcl_executable_manifest_ready"] is True
    assert report["records"][0]["bfcl_case_id"] == "memory_kv_0-customer-0"
    assert report["records"][0]["bfcl_case_id_mapping_source"] == "trace_case_id_field"
    assert report["protocol_id_is_audit_id_count"] == 1


def test_missing_dependency_metadata_keeps_fail_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(checker, "load_dataset_entry", lambda category, include_prereq=True: [])
    source = tmp_path / "source"
    protocol = tmp_path / "protocol.json"
    _write_protocol(protocol, case_id="memory_kv_0-customer-0")
    _write(source / "memory_kv/baseline/bfcl/test_case_ids_to_generate.json", {"memory_kv": ["memory_kv_0-customer-0"]})

    report = checker.evaluate(protocol, source)

    assert report["bfcl_executable_manifest_ready"] is False
    assert report["dependency_not_ready_count"] == 1
    assert "dependency_closure_not_ready" in report["blockers"]
