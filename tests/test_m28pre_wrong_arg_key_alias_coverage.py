from __future__ import annotations

import json
from pathlib import Path

import scripts.diagnose_m28pre_wrong_arg_key_alias_coverage as alias_audit


def _wj(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _source_manifest(path: Path, category: str, source_root: Path) -> None:
    _wj(path, {
        "category_status": [{
            "category": category,
            "source_artifacts_available": True,
            "existing_source_roots": [str(source_root)],
        }],
        "candidate_commands": [],
        "planned_commands": [],
        "source_collection_only": True,
        "no_candidate_rules": True,
    })


def _result(root: Path, category: str, rows: list[dict]) -> None:
    path = root / "bfcl" / "result" / "model" / "simple" / f"BFCL_v4_{category}_result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _entry(case_id: str, tool: str = "cat", *canonical_keys: str) -> dict:
    keys = canonical_keys or ("file_name",)
    return {
        "id": case_id,
        "question": [[{"role": "user", "content": "Use the emitted tool call."}]],
        "function": [{
            "name": tool,
            "parameters": {
                "type": "dict",
                "properties": {key: {"type": "string"} for key in keys},
                "required": [keys[0]],
            },
        }],
    }


def test_alias_coverage_classifies_canonical_unknown_alias_candidate_and_parallel(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "simple_python"
    entries = {
        "canonical": _entry("canonical", "cat", "file_name"),
        "unknown_alias": _entry("unknown_alias", "cat", "file_name"),
        "candidate": _entry("candidate", "cat", "file_name"),
        "parallel": _entry("parallel", "cat", "file_name"),
    }
    monkeypatch.setattr(alias_audit, "_load_dataset_records", lambda cat: entries if cat == category else {})
    source_manifest = tmp_path / "source_manifest.json"
    _source_manifest(source_manifest, category, source)
    _result(source, category, [
        {"id": "canonical", "result": [{"cat": json.dumps({"file_name": "report.txt"})}]},
        {"id": "unknown_alias", "result": [{"cat": json.dumps({"fname": "report.txt"})}]},
        {"id": "candidate", "result": [{"cat": json.dumps({"filename": "report.txt"})}]},
        {"id": "parallel", "result": [{"cat": json.dumps({"filename": "a.txt"})}, {"cat": json.dumps({"filename": "b.txt"})}]},
    ])

    report = alias_audit.evaluate(source_manifest)
    reasons = report["rejection_reason_counts"]

    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["wrong_arg_key_alias_demote_candidate_count"] == 1
    assert reasons["no_wrong_arg_key_alias_detected"] == 1
    assert reasons["no_schema_alias_match"] == 1
    assert reasons["parallel_call_mapping_not_unique"] == 1
    candidate = next(row for row in report["records"] if row["case_id"] == "candidate")
    assert candidate["retain_prior_candidate"] is True
    assert candidate["original_arg_key"] == "filename"
    assert candidate["selected_canonical_key"] == "file_name"


def test_alias_coverage_routes_zero_coverage_to_next_theory_family(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "simple_python"
    entries = {f"canonical_{i}": _entry(f"canonical_{i}", "cat", "file_name") for i in range(3)}
    monkeypatch.setattr(alias_audit, "_load_dataset_records", lambda cat: entries if cat == category else {})
    source_manifest = tmp_path / "source_manifest.json"
    _source_manifest(source_manifest, category, source)
    _result(source, category, [
        {"id": case_id, "result": [{"cat": json.dumps({"file_name": f"report_{i}.txt"})}]}
        for i, case_id in enumerate(entries)
    ])

    report = alias_audit.evaluate(source_manifest)

    assert report["wrong_arg_key_alias_family_coverage_zero"] is True
    assert "wrong_arg_key_alias_family_coverage_zero" in report["blockers"]
    assert report["route_recommendation"] == "pivot_to_next_theory_family=deterministic_schema_local_non_live_repair"
