#!/usr/bin/env python3
"""Build compact BFCL current-system baseline artifacts from local run outputs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_current_system_baseline_execution_gate import DEFAULT_PACKET, check as check_gate  # noqa: E402

DEFAULT_RUN_ARTIFACT_DIR = Path("outputs/bfcl_v4/current_system_baseline/artifacts")
DEFAULT_METRICS_SOURCE = DEFAULT_RUN_ARTIFACT_DIR / "metrics.json"
DEFAULT_FAILURE_SOURCE = DEFAULT_RUN_ARTIFACT_DIR / "failure_summary.json"
DEFAULT_RUN_MANIFEST_SOURCE = DEFAULT_RUN_ARTIFACT_DIR / "run_manifest.json"
DEFAULT_COMPACT_DIR = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_COMPACT_MANIFEST = DEFAULT_COMPACT_DIR / "bfcl_current_system_baseline_compact_manifest.json"
DEFAULT_COMPACT_METRICS = DEFAULT_COMPACT_DIR / "bfcl_current_system_baseline_compact_metrics.json"
DEFAULT_COMPACT_FAILURE = DEFAULT_COMPACT_DIR / "bfcl_current_system_baseline_compact_failure_summary.json"
DEFAULT_COMPACT_RUN_MANIFEST = DEFAULT_COMPACT_DIR / "bfcl_current_system_baseline_compact_run_manifest.json"


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _path_class(value: str) -> str:
    if "/result" in value:
        return "bfcl_result_json"
    if "/score" in value or value.endswith(".csv") or value.endswith(".tsv"):
        return "bfcl_score_or_metric_file"
    if "/trace" in value:
        return "trace_file_not_committed"
    return "compact_or_internal_metric_file"


def _count_from_sources(metrics: dict[str, Any]) -> int | None:
    subsets = metrics.get("subsets")
    if isinstance(subsets, dict) and subsets:
        return len(subsets)
    return None


def build(
    *,
    packet_path: Path,
    metrics_source: Path,
    failure_source: Path,
    run_manifest_source: Path,
    compact_manifest_path: Path,
    compact_metrics_path: Path,
    compact_failure_path: Path,
    compact_run_manifest_path: Path,
) -> dict[str, Any]:
    gate = check_gate(packet_path)
    if not gate.get("bfcl_current_system_baseline_execution_gate_passed"):
        raise ValueError(f"baseline gate failed:{gate.get('blockers')}")
    packet = _load(packet_path)
    metrics = _load(metrics_source)
    failure = _load(failure_source)
    run_manifest = _load(run_manifest_source)

    route_profile = packet.get("route_profile")
    route_model = packet.get("route_model")
    categories = (packet.get("case_scope_protocol") or {}).get("categories")
    metric_sources = metrics.get("metric_sources") if isinstance(metrics.get("metric_sources"), list) else []

    compact_metrics = {
        "artifact_kind": "bfcl_current_system_baseline_compact_metrics",
        "measurement_kind": "current_system_baseline_only",
        "measurement_evidence": True,
        "performance_evidence": False,
        "route_profile": route_profile,
        "route_model": route_model,
        "overall_accuracy": metrics.get("acc"),
        "overall_cost": metrics.get("cost"),
        "overall_latency_ms": metrics.get("latency"),
        "evaluation_status": metrics.get("evaluation_status"),
        "artifact_validity_issues": metrics.get("artifact_validity_issues", []),
        "subset_metrics": metrics.get("subsets", {}),
        "case_scope_categories": categories,
        "case_count": _count_from_sources(metrics),
        "repair_count": metrics.get("repair_count"),
        "validation_issue_count": metrics.get("validation_issue_count"),
        "fallback_count": metrics.get("fallback_count"),
        "scorer_feedback_used": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_specs_activated": False,
        "metric_source_count": len(metric_sources),
        "metric_source_path_classes": sorted({_path_class(str(item)) for item in metric_sources}),
        "raw_outputs_committed": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
    }

    compact_failure = {
        "artifact_kind": "bfcl_current_system_baseline_compact_failure_summary",
        "measurement_kind": "current_system_baseline_only",
        "route_profile": route_profile,
        "route_model": route_model,
        "trace_count": failure.get("trace_count"),
        "repair_count": failure.get("repair_count"),
        "validation_issue_count": failure.get("validation_issue_count"),
        "fallback_count": failure.get("fallback_count"),
        "status_code_classes": sorted({str(code)[0] + "xx" if str(code) and str(code)[0].isdigit() else "unknown" for code in (failure.get("status_codes") or {})}),
        "raw_outputs_committed": False,
        "performance_evidence": False,
    }

    compact_run_manifest = {
        "artifact_kind": "bfcl_current_system_baseline_compact_run_manifest",
        "measurement_kind": "current_system_baseline_only",
        "kind": run_manifest.get("kind"),
        "comparison_line": run_manifest.get("comparison_line"),
        "target_commit": packet.get("target_commit_for_measurement"),
        "execution_commit": _git_head(),
        "manifest_git_sha": run_manifest.get("git_sha"),
        "manifest_git_dirty": run_manifest.get("git_dirty"),
        "route_profile": route_profile,
        "route_model": route_model,
        "upstream_profile": run_manifest.get("upstream_profile"),
        "upstream_model_route": run_manifest.get("upstream_model_route"),
        "bfcl_model_alias": run_manifest.get("bfcl_model_alias"),
        "protocol_id": run_manifest.get("protocol_id"),
        "test_category": run_manifest.get("test_category"),
        "run_id_label": "baseline_run_id_present" if run_manifest.get("run_id") else "missing",
        "runtime_config_label": Path(str(run_manifest.get("runtime_config_path", ""))).name,
        "rules_dir_label": Path(str(run_manifest.get("rules_dir", ""))).name,
        "candidate_specs_activated": False,
        "scorer_feedback_used": False,
        "raw_outputs_committed": False,
    }

    compact_manifest = {
        "artifact_kind": "bfcl_current_system_baseline_compact_manifest",
        "measurement_kind": "current_system_baseline_only",
        "target_commit": packet.get("target_commit_for_measurement"),
        "execution_commit": _git_head(),
        "route_profile": route_profile,
        "route_model": route_model,
        "evaluator_package": packet.get("evaluator_package"),
        "bfcl_version": packet.get("bfcl_version"),
        "bfcl_evaluator_checkout": packet.get("bfcl_evaluator_checkout"),
        "case_scope_protocol": packet.get("case_scope_protocol"),
        "metrics_artifact": str(compact_metrics_path),
        "failure_summary_artifact": str(compact_failure_path),
        "run_manifest_artifact": str(compact_run_manifest_path),
        "raw_outputs_committed": False,
        "candidate_specs_activated": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "scorer_feedback_used": False,
        "performance_claim_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "provider_call_executed": True,
        "bfcl_generate_executed": True,
        "bfcl_evaluate_executed": True,
        "scorer_executed": True,
        "full_baseline_executed": True,
        "baseline_vs_treatment_comparison": False,
    }

    for path, payload in (
        (compact_metrics_path, compact_metrics),
        (compact_failure_path, compact_failure),
        (compact_run_manifest_path, compact_run_manifest),
        (compact_manifest_path, compact_manifest),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "artifact_kind": "bfcl_current_system_baseline_compact_artifact_build_summary",
        "compact_manifest": str(compact_manifest_path),
        "compact_metrics": str(compact_metrics_path),
        "compact_failure_summary": str(compact_failure_path),
        "compact_run_manifest": str(compact_run_manifest_path),
        "overall_accuracy": compact_metrics.get("overall_accuracy"),
        "evaluation_status": compact_metrics.get("evaluation_status"),
        "performance_evidence": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--metrics-source", type=Path, default=DEFAULT_METRICS_SOURCE)
    parser.add_argument("--failure-source", type=Path, default=DEFAULT_FAILURE_SOURCE)
    parser.add_argument("--run-manifest-source", type=Path, default=DEFAULT_RUN_MANIFEST_SOURCE)
    parser.add_argument("--compact-manifest", type=Path, default=DEFAULT_COMPACT_MANIFEST)
    parser.add_argument("--compact-metrics", type=Path, default=DEFAULT_COMPACT_METRICS)
    parser.add_argument("--compact-failure", type=Path, default=DEFAULT_COMPACT_FAILURE)
    parser.add_argument("--compact-run-manifest", type=Path, default=DEFAULT_COMPACT_RUN_MANIFEST)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    summary = build(
        packet_path=args.packet,
        metrics_source=args.metrics_source,
        failure_source=args.failure_source,
        run_manifest_source=args.run_manifest_source,
        compact_manifest_path=args.compact_manifest,
        compact_metrics_path=args.compact_metrics,
        compact_failure_path=args.compact_failure,
        compact_run_manifest_path=args.compact_run_manifest,
    )
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
