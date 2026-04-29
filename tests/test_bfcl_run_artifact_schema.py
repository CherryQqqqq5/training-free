from __future__ import annotations

import json
import hashlib
from pathlib import Path

from scripts.check_bfcl_run_artifact_schema import evaluate


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _manifest() -> dict:
    return {
        "artifact_schema_version": "stage1_bfcl_run_v1",
        "protocol_id": "bfcl_v4_performance",
        "bfcl_model_alias": "model-FC",
        "upstream_profile": "approved",
        "upstream_model_route": "model",
        "test_category": "multi_turn_miss_param",
        "runtime_config_path": "configs/runtime_bfcl_structured.yaml",
        "rules_dir": "rules/baseline_empty",
        "run_id": "run-1",
        "kind": "baseline",
        "comparison_line": "compatibility_baseline",
        "selected_case_count": 20,
        "selected_case_ids_hash": "casehash",
        "provider_preflight_status_path": "provider.json",
        "provider_preflight_passed": True,
    }


def _metrics(acc: float = 0.9) -> dict:
    return {
        "evaluation_status": "complete",
        "acc": acc,
        "artifact_validity_issues": [],
        "resolved_score_sources": ["score_summary"],
        "resolved_result_sources": ["result_summary"],
        "metric_sources": ["score_summary"],
        "score_result_source_summary": {
            "score_source_count": 1,
            "result_source_count": 1,
            "metric_source_count": 1,
        },
    }


def _write_sanitized_trace(root: Path) -> None:
    _write(root / "sanitized_trace_summary.json", {"trace_count": 20, "contains_raw_payloads": False})


def test_run_artifact_schema_blocks_missing_manifest_fields(tmp_path: Path) -> None:
    _write(tmp_path / "run_manifest.json", {"run_id": "run-1"})
    _write(tmp_path / "metrics.json", _metrics())
    _write_sanitized_trace(tmp_path)

    report = evaluate(tmp_path)

    assert report["run_artifact_schema_passed"] is False
    assert "run_manifest_required_fields_missing" in report["blockers"]


def test_run_artifact_schema_accepts_complete_compact_run(tmp_path: Path) -> None:
    _write(tmp_path / "run_manifest.json", _manifest())
    _write(tmp_path / "metrics.json", _metrics())
    _write_sanitized_trace(tmp_path)

    report = evaluate(tmp_path)

    assert report["run_artifact_schema_passed"] is True
    assert report["blockers"] == []


def test_candidate_schema_requires_raman_candidate_records_and_rule_hash(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest.update({
        "kind": "candidate",
        "comparison_line": "compiler_patch_candidate",
        "rule_path": "active_rules_snapshot.yaml",
        "active_rules_snapshot_path": "active_rules_snapshot.yaml",
        "candidate_record_manifest_path": "candidate_records.jsonl",
    })
    rule_text = "rules: []\n"
    (tmp_path / "active_rules_snapshot.yaml").write_text(rule_text, encoding="utf-8")
    manifest["active_rules_snapshot_hash"] = hashlib.sha256(rule_text.encode("utf-8")).hexdigest()
    _write(tmp_path / "run_manifest.json", manifest)
    _write(tmp_path / "metrics.json", _metrics())
    _write_sanitized_trace(tmp_path)
    (tmp_path / "candidate_records.jsonl").write_text(
        json.dumps({
            "case_id": "case-1",
            "category": "multi_turn_miss_param",
            "candidate_generatable": True,
            "candidate_origin": "theory_prior_explicit_literal_from_source_result_context",
            "rule_type": "explicit_required_arg_literal_completion",
            "candidate_rules_type": "explicit_required_arg_literal_completion",
            "source_run_root": "source",
            "retention_prior": {"retain_eligibility": "demote_candidate"},
            "schema_arg_name": "file_name",
            "tool": "grep",
        }) + "\n",
        encoding="utf-8",
    )

    report = evaluate(tmp_path)

    assert report["run_artifact_schema_passed"] is True
    assert report["candidate_records"]["passed"] is True
