#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.run_phase2_target_subset import (
    _metric_acc,
    _render_summary,
    build_case_report,
    candidate_policy_tool_distribution,
    summarize_case_report,
)

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")


def _j(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _mtime(path: Path | None) -> float | None:
    return path.stat().st_mtime if path and path.exists() else None


def _first_glob(root: Path, pattern: str) -> Path | None:
    matches = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return matches[0] if matches else None


def _run_metadata(root: Path, run: str, category: str) -> dict[str, Any]:
    run_root = root / run
    manifest_path = run_root / "artifacts" / "run_manifest.json"
    metrics_path = run_root / "artifacts" / "metrics.json"
    score_path = _first_glob(run_root / "bfcl", f"**/BFCL_v4_{category}_score.json")
    result_path = _first_glob(run_root / "bfcl", f"**/BFCL_v4_{category}_result.json")
    manifest = _j(manifest_path, {}) or {}
    source_paths = [path for path in [manifest_path, metrics_path, score_path, result_path] if path and path.exists()]
    return {
        "run_id": manifest.get("run_id"),
        "run_manifest_timestamp": manifest.get("timestamp"),
        "run_manifest_path": str(manifest_path),
        "metrics_path": str(metrics_path),
        "score_path": str(score_path) if score_path else None,
        "result_path": str(result_path) if result_path else None,
        "run_manifest_mtime": _mtime(manifest_path),
        "metrics_mtime": _mtime(metrics_path),
        "score_mtime": _mtime(score_path),
        "result_mtime": _mtime(result_path),
        "freshest_source_mtime": max((_mtime(path) or 0.0) for path in source_paths) if source_paths else None,
    }


def rebuild(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    manifest_path = root / "paired_subset_manifest.json"
    if not manifest_path.exists():
        manifest_path = root / "subset_manifest.json"
    manifest = _j(manifest_path, {}) or {}
    selected_ids = list(manifest.get("selected_case_ids") or [])
    if not selected_ids:
        raise RuntimeError(f"selected_case_ids missing from {manifest_path}")
    category = str(manifest.get("category") or "multi_turn_miss_param")
    baseline_run = root / "baseline"
    candidate_run = root / "candidate"
    rules_dir = Path(manifest.get("candidate_rules_dir") or "outputs/phase2_subset/bfcl_ctspc_subset30_v1/candidate_rules")

    rows = build_case_report(
        baseline_run=baseline_run,
        candidate_run=candidate_run,
        category=category,
        selected_ids=selected_ids,
    )
    case_report_path = root / "subset_case_report.jsonl"
    with case_report_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = summarize_case_report(
        rows,
        baseline_acc=_metric_acc(baseline_run, category),
        candidate_acc=_metric_acc(candidate_run, category),
    )
    summary["candidate_policy_tool_distribution"] = candidate_policy_tool_distribution(rules_dir / "rule.yaml")
    summary["manifest"] = manifest
    summary["report_build_metadata"] = {
        "case_report_build_time_utc": datetime.now(timezone.utc).isoformat(),
        "case_report_path": str(case_report_path),
        "summary_path": str(root / "subset_summary.json"),
        "baseline": _run_metadata(root, "baseline", category),
        "candidate": _run_metadata(root, "candidate", category),
    }
    (root / "subset_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "subset_summary.md").write_text(_render_summary(summary, rows), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild M2.7f case report and summary from existing BFCL artifacts without running BFCL.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    summary = rebuild(args.root)
    out = {
        "baseline_accuracy": summary.get("baseline_accuracy"),
        "candidate_accuracy": summary.get("candidate_accuracy"),
        "case_report_trace_mapping": summary.get("case_report_trace_mapping"),
        "case_level_gate_allowed": summary.get("case_level_gate_allowed"),
        "case_fixed_count": summary.get("case_fixed_count"),
        "case_regressed_count": summary.get("case_regressed_count"),
        "net_case_gain": summary.get("net_case_gain"),
        "recommended_tool_match_rate_among_activated": summary.get("recommended_tool_match_rate_among_activated"),
        "raw_normalized_arg_match_rate_among_activated": summary.get("raw_normalized_arg_match_rate_among_activated"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

