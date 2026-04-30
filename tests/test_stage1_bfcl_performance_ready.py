from __future__ import annotations

import json
import hashlib
from pathlib import Path

import scripts.check_stage1_bfcl_performance_ready as perf


def _write_json(path: Path, data: dict) -> None:
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


def _write_run(root: Path, *, manifest: dict | None = None, acc: float = 0.9, kind: str = "baseline") -> Path:
    if manifest is None:
        manifest = _manifest()
        if kind == "candidate":
            manifest.update({
                "kind": "candidate",
                "comparison_line": "compiler_patch_candidate",
                "rule_path": "active_rules_snapshot.yaml",
                "active_rules_snapshot_path": "active_rules_snapshot.yaml",
                "candidate_record_manifest_path": "candidate_records.jsonl",
            })
    if manifest.get("kind") == "candidate":
        rule_text = "rules: []\n"
        rule_path = root / "active_rules_snapshot.yaml"
        rule_path.parent.mkdir(parents=True, exist_ok=True)
        rule_path.write_text(rule_text, encoding="utf-8")
        manifest.setdefault("rule_path", "active_rules_snapshot.yaml")
        manifest.setdefault("active_rules_snapshot_path", "active_rules_snapshot.yaml")
        manifest["active_rules_snapshot_hash"] = hashlib.sha256(rule_text.encode("utf-8")).hexdigest()
        manifest.setdefault("candidate_record_manifest_path", "candidate_records.jsonl")
        (root / "candidate_records.jsonl").write_text(
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
    _write_json(root / "run_manifest.json", manifest or _manifest())
    _write_json(root / "metrics.json", _metrics(acc))
    _write_json(root / "sanitized_trace_summary.json", {"trace_count": 20, "contains_raw_payloads": False})
    return root


def test_performance_ready_fails_closed_without_scores(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_json(
        tmp_path / "provider.json",
        {
            "source_collection_rerun_ready": False,
            "candidate_evaluation_ready": False,
            "blocking_condition": "valid_provider_credential_required",
        },
    )

    report = perf.evaluate(provider_path=tmp_path / "provider.json", acceptance_root=tmp_path / "acceptance")

    assert report["ready_for_formal_bfcl_performance_acceptance"] is False
    assert "provider_green_preflight_not_passed" in report["blockers"]
    assert "paired_bfcl_score_chain_not_ready" in report["blockers"]
    assert "required_3pp_target_not_passed" in report["blockers"]


def test_performance_ready_requires_manifest_alignment(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/stage1_sota_comparison.md").write_text("x", encoding="utf-8")
    (tmp_path / "docs/stage1_bfcl_performance_sprint.md").write_text("x", encoding="utf-8")
    _write_json(
        tmp_path / "provider.json",
        {
            "source_collection_rerun_ready": True,
            "candidate_evaluation_ready": True,
            "upstream_auth_passed": True,
            "model_route_available": True,
            "bfcl_compatible_response": True,
        },
    )
    baseline_manifest = tmp_path / "runs/baseline/run_manifest.json"
    candidate_manifest = tmp_path / "runs/candidate/run_manifest.json"
    _write_run(baseline_manifest.parent, acc=0.90)
    mismatched = _manifest()
    mismatched.update({"kind": "candidate", "comparison_line": "compiler_patch_candidate"})
    mismatched["upstream_model_route"] = "other-model"
    _write_run(candidate_manifest.parent, manifest=mismatched, acc=0.94)
    _write_json(
        tmp_path / "acceptance/paired_comparison.json",
        {
            "baseline_run_root": str(baseline_manifest.parent),
            "candidate_run_root": str(candidate_manifest.parent),
            "baseline_run_manifest_path": str(baseline_manifest),
            "candidate_run_manifest_path": str(candidate_manifest),
            "absolute_delta_pp": 3.1,
            "target_absolute_delta_pp": 3.0,
        },
    )
    _write_json(tmp_path / "acceptance/acceptance_decision.json", {"required_3pp_target_passed": True, "performance_claim_allowed": True})
    _write_json(tmp_path / "acceptance/regression_report.json", {"unacceptable_regression_present": False, "case_fixed_count": 2, "case_regressed_count": 0})
    _write_json(tmp_path / "acceptance/cost_latency_report.json", {"cost_delta_pct": 0, "latency_delta_pct": 0, "cost_latency_within_bounds": True})

    report = perf.evaluate(provider_path=tmp_path / "provider.json", acceptance_root=tmp_path / "acceptance")

    assert report["ready_for_formal_bfcl_performance_acceptance"] is False
    assert "baseline_candidate_manifest_alignment_not_passed" in report["blockers"]


def test_performance_ready_passes_with_green_provider_and_paired_scores(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/stage1_sota_comparison.md").write_text("x", encoding="utf-8")
    (tmp_path / "docs/stage1_bfcl_performance_sprint.md").write_text("x", encoding="utf-8")
    _write_json(
        tmp_path / "provider.json",
        {
            "source_collection_rerun_ready": True,
            "candidate_evaluation_ready": True,
            "upstream_auth_passed": True,
            "model_route_available": True,
            "bfcl_compatible_response": True,
        },
    )
    baseline_manifest = tmp_path / "runs/baseline/run_manifest.json"
    candidate_manifest = tmp_path / "runs/candidate/run_manifest.json"
    _write_run(baseline_manifest.parent, acc=0.90)
    _write_run(candidate_manifest.parent, acc=0.94, kind="candidate")
    _write_json(
        tmp_path / "acceptance/paired_comparison.json",
        {
            "baseline_run_root": str(baseline_manifest.parent),
            "candidate_run_root": str(candidate_manifest.parent),
            "baseline_run_manifest_path": str(baseline_manifest),
            "candidate_run_manifest_path": str(candidate_manifest),
            "absolute_delta_pp": 3.1,
            "target_absolute_delta_pp": 3.0,
        },
    )
    _write_json(tmp_path / "acceptance/acceptance_decision.json", {"required_3pp_target_passed": True, "performance_claim_allowed": True})
    _write_json(tmp_path / "acceptance/regression_report.json", {"unacceptable_regression_present": False, "case_fixed_count": 2, "case_regressed_count": 0})
    _write_json(tmp_path / "acceptance/cost_latency_report.json", {"cost_delta_pct": 0, "latency_delta_pct": 0, "cost_latency_within_bounds": True})

    report = perf.evaluate(provider_path=tmp_path / "provider.json", acceptance_root=tmp_path / "acceptance")

    assert report["ready_for_formal_bfcl_performance_acceptance"] is True
    assert report["blockers"] == []
