from __future__ import annotations

import json
from pathlib import Path

import scripts.build_explicit_obligation_executable_smoke_protocol as builder


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _trace(root: Path, category: str, trace_name: str, prompt: str) -> str:
    rel = f"{category}/baseline/traces/{trace_name}.json"
    _write(root / rel, {"request_original": {"input": [{"role": "user", "content": prompt}]}})
    return rel


def _entries(category: str, include_prereq: bool = True):
    return [
        {"id": f"{category}_prereq_0", "depends_on": [], "question": [[{"role": "user", "content": "setup"}]]},
        {"id": f"{category}_0", "depends_on": [f"{category}_prereq_0"], "question": [[{"role": "user", "content": "What did I buy?"}]]},
        {"id": f"{category}_1", "depends_on": [f"{category}_prereq_0"], "question": [[{"role": "user", "content": "What brand do I trust?"}]]},
        {"id": f"{category}_2", "depends_on": [], "question": [[{"role": "user", "content": "Control prompt one"}]]},
        {"id": f"{category}_3", "depends_on": [], "question": [[{"role": "user", "content": "Control prompt two"}]]},
    ]


def test_materializer_selects_disjoint_executable_positive_and_controls(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(builder, "load_dataset_entry", _entries)
    source = tmp_path / "source"
    memory = tmp_path / "memory.json"
    _write(memory, {
        "candidate_records": [
            {"candidate_id": "p0", "candidate_ready": True, "risk_level": "low", "operation": "retrieve", "category": "memory_kv", "trace_relative_path": _trace(source, "memory_kv", "p0", "What did I buy?")},
            {"candidate_id": "p1", "candidate_ready": True, "risk_level": "low", "operation": "retrieve", "category": "memory_kv", "trace_relative_path": _trace(source, "memory_kv", "p1", "What brand do I trust?")},
        ],
        "sample_rejections": [
            {"source_audit_record_id": "c-overlap", "rejection_reason": "overlap", "category": "memory_kv", "trace_relative_path": _trace(source, "memory_kv", "c0", "What did I buy?")},
            {"source_audit_record_id": "c1", "rejection_reason": "control", "category": "memory_kv", "trace_relative_path": _trace(source, "memory_kv", "c1", "Control prompt one")},
            {"source_audit_record_id": "c2", "rejection_reason": "control", "category": "memory_kv", "trace_relative_path": _trace(source, "memory_kv", "c2", "Control prompt two")},
        ],
    })

    report = builder.evaluate(memory, source, positive_limit=2, control_limit=2)

    assert report["bfcl_executable_manifest_ready"] is True
    assert report["positive_case_count"] == 2
    assert report["control_case_count"] == 2
    assert {item["bfcl_case_id"] for item in report["selected_positive_cases"]} == {"memory_kv_0", "memory_kv_1"}
    assert {item["bfcl_case_id"] for item in report["selected_control_cases"]} == {"memory_kv_2", "memory_kv_3"}
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["execution_allowed"] is False
    assert report["selected_positive_cases"][0]["generation_case_ids"] == ["memory_kv_prereq_0", "memory_kv_0"]


def test_materializer_fails_closed_when_prompt_mapping_is_ambiguous(tmp_path: Path, monkeypatch) -> None:
    def ambiguous_entries(category: str, include_prereq: bool = True):
        return [
            {"id": f"{category}_0", "depends_on": [], "question": [[{"role": "user", "content": "same prompt"}]]},
            {"id": f"{category}_1", "depends_on": [], "question": [[{"role": "user", "content": "same prompt"}]]},
        ]
    monkeypatch.setattr(builder, "load_dataset_entry", ambiguous_entries)
    source = tmp_path / "source"
    memory = tmp_path / "memory.json"
    _write(memory, {
        "candidate_records": [
            {"candidate_id": "p0", "candidate_ready": True, "risk_level": "low", "operation": "retrieve", "category": "memory_kv", "trace_relative_path": _trace(source, "memory_kv", "p0", "same prompt")},
        ],
        "sample_rejections": [],
    })

    report = builder.evaluate(memory, source, positive_limit=1, control_limit=0)

    assert report["bfcl_executable_manifest_ready"] is False
    assert report["positive_case_count"] == 0
    assert report["positive_selection_rejections"][0]["mapping_status"] == "ambiguous_current_user_prompt_match"
    assert "positive_executable_cases_below_target" in report["blockers"]


def test_materializer_requires_dependency_metadata(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(builder, "load_dataset_entry", lambda category, include_prereq=True: [])
    source = tmp_path / "source"
    memory = tmp_path / "memory.json"
    _write(memory, {
        "candidate_records": [
            {"candidate_id": "p0", "candidate_ready": True, "risk_level": "low", "operation": "retrieve", "category": "memory_kv", "trace_relative_path": _trace(source, "memory_kv", "p0", "What did I buy?")},
        ],
        "sample_rejections": [],
    })

    report = builder.evaluate(memory, source, positive_limit=1, control_limit=0)

    assert report["bfcl_executable_manifest_ready"] is False
    assert report["positive_case_count"] == 0
    assert report["positive_selection_rejections"][0]["selection_rejection_reason"] == "not_mapped_or_dependency_not_ready"
