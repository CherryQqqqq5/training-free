from __future__ import annotations

import json
from pathlib import Path

import scripts.diagnose_m28pre_deterministic_schema_local_coverage as det_audit


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


def _entry(case_id: str, tool: str, props: dict, required: list[str] | None = None) -> dict:
    return {
        "id": case_id,
        "question": [[{"role": "user", "content": "Use the emitted tool call."}]],
        "function": [{
            "name": tool,
            "parameters": {"type": "dict", "properties": props, "required": required or list(props)},
        }],
    }


def test_deterministic_schema_local_audit_classifies_repairs_and_noops(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "simple_python"
    entries = {
        "bool_case": _entry("bool_case", "set_flag", {"enabled": {"type": "boolean"}}),
        "int_case": _entry("int_case", "set_count", {"count": {"type": "integer"}}),
        "enum_case": _entry("enum_case", "set_mode", {"mode": {"type": "string", "enum": ["FAST", "SLOW"]}}),
        "array_case": _entry("array_case", "tag", {"tags": {"type": "array", "items": {"type": "string"}}}),
        "noop_case": _entry("noop_case", "set_flag", {"enabled": {"type": "boolean"}}),
        "parallel_case": _entry("parallel_case", "set_count", {"count": {"type": "integer"}}),
    }
    monkeypatch.setattr(det_audit, "_load_dataset_records", lambda cat: entries if cat == category else {})
    source_manifest = tmp_path / "source_manifest.json"
    _source_manifest(source_manifest, category, source)
    _result(source, category, [
        {"id": "bool_case", "result": [{"set_flag": json.dumps({"enabled": "true"})}]},
        {"id": "int_case", "result": [{"set_count": json.dumps({"count": "7"})}]},
        {"id": "enum_case", "result": [{"set_mode": json.dumps({"mode": "fast"})}]},
        {"id": "array_case", "result": [{"tag": json.dumps({"tags": "alpha"})}]},
        {"id": "noop_case", "result": [{"set_flag": json.dumps({"enabled": True})}]},
        {"id": "parallel_case", "result": [{"set_count": json.dumps({"count": "1"})}, {"set_count": json.dumps({"count": "2"})}]},
    ])

    report = det_audit.evaluate(source_manifest)

    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["deterministic_schema_local_demote_candidate_count"] == 4
    reasons = report["rejection_reason_counts"]
    assert reasons["no_deterministic_schema_local_repair_detected"] == 1
    assert reasons["parallel_call_mapping_not_unique"] == 1
    kinds = {row.get("repair_kind") for row in report["records"] if row.get("retain_prior_candidate")}
    assert {"boolean_string_normalization", "numeric_string_to_integer", "enum_canonicalization", "scalar_to_singleton_array"} <= kinds


def test_deterministic_schema_local_zero_coverage_routes_fail_closed(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "simple_python"
    entries = {"noop": _entry("noop", "set_flag", {"enabled": {"type": "boolean"}})}
    monkeypatch.setattr(det_audit, "_load_dataset_records", lambda cat: entries if cat == category else {})
    source_manifest = tmp_path / "source_manifest.json"
    _source_manifest(source_manifest, category, source)
    _result(source, category, [{"id": "noop", "result": [{"set_flag": json.dumps({"enabled": True})}]}])

    report = det_audit.evaluate(source_manifest)

    assert report["deterministic_schema_local_family_coverage_zero"] is True
    assert "deterministic_schema_local_family_coverage_zero" in report["blockers"]
    assert report["route_recommendation"] == "define_next_theory_family_after_deterministic_schema_local_non_live_repair"
