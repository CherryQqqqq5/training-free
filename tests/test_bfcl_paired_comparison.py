from __future__ import annotations

import json
import hashlib
from pathlib import Path

from scripts.check_bfcl_paired_comparison import evaluate


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


def _run(root: Path, *, manifest: dict | None = None, acc: float = 0.9, kind: str = "baseline") -> None:
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
        (root / "active_rules_snapshot.yaml").parent.mkdir(parents=True, exist_ok=True)
        (root / "active_rules_snapshot.yaml").write_text(rule_text, encoding="utf-8")
        manifest.setdefault("active_rules_snapshot_path", "active_rules_snapshot.yaml")
        manifest.setdefault("rule_path", "active_rules_snapshot.yaml")
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
    _write(root / "run_manifest.json", manifest or _manifest())
    _write(root / "metrics.json", _metrics(acc))
    _write(root / "sanitized_trace_summary.json", {"trace_count": 20, "contains_raw_payloads": False})


def _provider(path: Path, *, green: bool = True) -> None:
    _write(
        path,
        {
            "source_collection_rerun_ready": green,
            "candidate_evaluation_ready": green,
            "upstream_auth_passed": green,
            "model_route_available": green,
            "bfcl_compatible_response": green,
        },
    )


def test_paired_comparison_blocks_provider_red(tmp_path: Path) -> None:
    baseline = tmp_path / "runs/baseline"
    candidate = tmp_path / "runs/candidate"
    _run(baseline, acc=0.90)
    _run(candidate, acc=0.94, kind="candidate")
    _provider(tmp_path / "provider.json", green=False)
    _write(tmp_path / "acceptance/paired_comparison.json", {"baseline_run_root": str(baseline), "candidate_run_root": str(candidate), "absolute_delta_pp": 4.0})
    _write(tmp_path / "acceptance/acceptance_decision.json", {"required_3pp_target_passed": True, "performance_claim_allowed": True})
    _write(tmp_path / "acceptance/regression_report.json", {"unacceptable_regression_present": False})
    _write(tmp_path / "acceptance/cost_latency_report.json", {"cost_delta_pct": 0, "latency_delta_pct": 0, "cost_latency_within_bounds": True})

    report = evaluate(tmp_path / "acceptance", provider_status=tmp_path / "provider.json")

    assert report["paired_comparison_ready"] is False
    assert "provider_green_preflight_not_passed" in report["blockers"]


def test_paired_comparison_blocks_manifest_drift(tmp_path: Path) -> None:
    baseline = tmp_path / "runs/baseline"
    candidate = tmp_path / "runs/candidate"
    _run(baseline, acc=0.90)
    candidate_manifest = _manifest()
    candidate_manifest.update({"kind": "candidate", "comparison_line": "compiler_patch_candidate"})
    candidate_manifest["test_category"] = "simple_python"
    _run(candidate, manifest=candidate_manifest, acc=0.94)
    _write(tmp_path / "acceptance/paired_comparison.json", {"baseline_run_root": str(baseline), "candidate_run_root": str(candidate), "absolute_delta_pp": 4.0})
    _write(tmp_path / "acceptance/acceptance_decision.json", {"required_3pp_target_passed": True, "performance_claim_allowed": True})
    _write(tmp_path / "acceptance/regression_report.json", {"unacceptable_regression_present": False})
    _write(tmp_path / "acceptance/cost_latency_report.json", {"cost_delta_pct": 0, "latency_delta_pct": 0, "cost_latency_within_bounds": True})

    report = evaluate(tmp_path / "acceptance")

    assert report["paired_comparison_ready"] is False
    assert "baseline_candidate_manifest_alignment_not_passed" in report["blockers"]


def test_paired_comparison_passes_green_chain(tmp_path: Path) -> None:
    baseline = tmp_path / "runs/baseline"
    candidate = tmp_path / "runs/candidate"
    _run(baseline, acc=0.90)
    _run(candidate, acc=0.94, kind="candidate")
    _provider(tmp_path / "provider.json", green=True)
    _write(tmp_path / "acceptance/paired_comparison.json", {"baseline_run_root": str(baseline), "candidate_run_root": str(candidate), "absolute_delta_pp": 4.0})
    _write(tmp_path / "acceptance/acceptance_decision.json", {"required_3pp_target_passed": True, "performance_claim_allowed": True})
    _write(tmp_path / "acceptance/regression_report.json", {"unacceptable_regression_present": False, "case_fixed_count": 2, "case_regressed_count": 0})
    _write(tmp_path / "acceptance/cost_latency_report.json", {"cost_delta_pct": 0, "latency_delta_pct": 0, "cost_latency_within_bounds": True})

    report = evaluate(tmp_path / "acceptance", provider_status=tmp_path / "provider.json")

    assert report["paired_comparison_ready"] is True
    assert report["blockers"] == []
