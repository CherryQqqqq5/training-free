from __future__ import annotations

import json
from pathlib import Path

import scripts.check_memory_operation_smoke_snapshot_preflight as preflight


def _write_protocol(path: Path, *, include_deps: bool = True) -> None:
    generation = ["memory_kv_prereq_0-customer-0", "memory_kv_prereq_1-customer-1", "memory_kv_0-customer-0"] if include_deps else ["memory_kv_0-customer-0"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "candidate_commands": [],
            "planned_commands": [],
            "target_ids_by_category": {"memory_kv": ["memory_kv_0-customer-0"]},
            "generation_ids_by_category": {"memory_kv": generation},
        }),
        encoding="utf-8",
    )


def _fake_entries(category: str, include_prereq: bool = True):
    return [
        {"id": "memory_kv_prereq_0-customer-0", "depends_on": []},
        {"id": "memory_kv_prereq_1-customer-1", "depends_on": ["memory_kv_prereq_0-customer-0"]},
        {"id": "memory_kv_0-customer-0", "depends_on": ["memory_kv_prereq_0-customer-0", "memory_kv_prereq_1-customer-1"]},
    ]


def test_snapshot_preflight_passes_when_dependency_closure_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(preflight, "load_dataset_entry", _fake_entries)
    protocol_path = tmp_path / "protocol.json"
    _write_protocol(protocol_path, include_deps=True)

    report = preflight.evaluate(protocol_path)

    assert report["memory_snapshot_preflight_passed"] is True
    assert report["target_case_count"] == 1
    assert report["generation_case_count"] == 3
    assert report["prereq_case_count"] == 2
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []


def test_snapshot_preflight_fails_for_target_only_memory_subset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(preflight, "load_dataset_entry", _fake_entries)
    protocol_path = tmp_path / "protocol.json"
    _write_protocol(protocol_path, include_deps=False)

    report = preflight.evaluate(protocol_path)

    assert report["memory_snapshot_preflight_passed"] is False
    assert report["first_failure"]["check"] == "memory_snapshot_dependency_closure"
    assert report["first_failure"]["missing_dependency_ids"] == ["memory_kv_prereq_0-customer-0", "memory_kv_prereq_1-customer-1"]


def test_snapshot_preflight_fails_when_protocol_embeds_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(preflight, "load_dataset_entry", _fake_entries)
    protocol_path = tmp_path / "protocol.json"
    _write_protocol(protocol_path, include_deps=True)
    data = json.loads(protocol_path.read_text(encoding="utf-8"))
    data["planned_commands"] = ["bash run_bfcl.sh"]
    protocol_path.write_text(json.dumps(data), encoding="utf-8")

    report = preflight.evaluate(protocol_path)

    assert report["memory_snapshot_preflight_passed"] is False
    assert report["first_failure"]["check"] == "protocol_has_no_commands"



def test_snapshot_preflight_fails_when_run_root_ids_are_target_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(preflight, "load_dataset_entry", _fake_entries)
    protocol_path = tmp_path / "protocol.json"
    _write_protocol(protocol_path, include_deps=True)
    run_root = tmp_path / "baseline"
    ids_path = run_root / "bfcl" / "test_case_ids_to_generate.json"
    ids_path.parent.mkdir(parents=True, exist_ok=True)
    ids_path.write_text(json.dumps({"memory_kv": ["memory_kv_0-customer-0"]}), encoding="utf-8")

    report = preflight.evaluate(protocol_path, baseline_run_root=run_root)

    assert report["memory_snapshot_preflight_passed"] is False
    assert report["first_failure"]["check"] == "run_ids_match_protocol_generation_ids"
    assert report["first_failure"]["actual_generation_case_count"] == 1
    assert report["first_failure"]["expected_generation_case_count"] == 3


def test_snapshot_preflight_passes_when_run_root_ids_match_protocol(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(preflight, "load_dataset_entry", _fake_entries)
    protocol_path = tmp_path / "protocol.json"
    _write_protocol(protocol_path, include_deps=True)
    for label in ("baseline", "candidate"):
        run_root = tmp_path / label
        ids_path = run_root / "bfcl" / "test_case_ids_to_generate.json"
        ids_path.parent.mkdir(parents=True, exist_ok=True)
        ids_path.write_text(json.dumps({"memory_kv": ["memory_kv_prereq_0-customer-0", "memory_kv_prereq_1-customer-1", "memory_kv_0-customer-0"]}), encoding="utf-8")

    report = preflight.evaluate(protocol_path, baseline_run_root=tmp_path / "baseline", candidate_run_root=tmp_path / "candidate")

    assert report["memory_snapshot_preflight_passed"] is True
    assert len(report["run_id_checks"]) == 2
    assert all(check["matches_protocol_generation_ids"] for check in report["run_id_checks"])
