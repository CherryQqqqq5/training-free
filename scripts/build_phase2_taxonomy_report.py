from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from grc.compiler.failure_groups import group_failure_label
from grc.compiler.failure_signature import top_k_signatures
from grc.compiler.mine import mine_failures


def _parse_mapping(value: str, *, label_name: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"{label_name} must be formatted as LABEL=PATH")
    label, raw_path = value.split("=", 1)
    label = label.strip()
    if not label:
        raise argparse.ArgumentTypeError(f"{label_name} label is empty")
    return label, Path(raw_path)


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _metrics_summary(path: Path | None) -> dict[str, Any]:
    metrics = _load_json(path)
    subsets = metrics.get("subsets")
    category = metrics.get("test_category")
    accuracy = None
    accuracy_source = None
    if isinstance(subsets, dict) and category in subsets:
        accuracy = subsets.get(category)
        accuracy_source = f"subsets.{category}"
    if accuracy is None:
        accuracy = metrics.get("acc")
        if accuracy is not None:
            accuracy_source = "acc"
    correct_count = metrics.get("correct_count")
    if correct_count is None and isinstance(subsets, dict):
        correct_count = subsets.get("correct_count")
    return {
        "accuracy": accuracy,
        "accuracy_source": accuracy_source,
        "correct_count": correct_count,
        "metrics_path": str(path) if path else None,
    }


def _failure_row(label: str, count: int, total: int, group: str) -> dict[str, Any]:
    return {
        "failure_label": label,
        "count": int(count),
        "share": (int(count) / total if total else 0.0),
        "failure_group": group,
    }


def summarize_run(label: str, trace_dir: Path, metrics_path: Path | None = None) -> dict[str, Any]:
    failures = mine_failures(str(trace_dir))
    distribution = Counter()
    group_totals = Counter()
    evidence_by_label: dict[str, dict[str, Any]] = {}
    for failure in failures:
        failure_label = failure.failure_label or f"({failure.stage or 'UNKNOWN'},{failure.failure_type or failure.error_type})"
        evidence = dict(failure.predicate_evidence or {})
        if "prior_explicit_literals_present" in (failure.request_predicates or []):
            evidence["prior_explicit_literals_present"] = True
        group = group_failure_label(failure_label, evidence)
        distribution[failure_label] += 1
        group_totals[group] += 1
        evidence_by_label.setdefault(failure_label, evidence)

    total = sum(distribution.values())
    metrics = _metrics_summary(metrics_path)
    rows = [
        {
            "run": label,
            **_failure_row(failure_label, count, total, group_failure_label(failure_label, evidence_by_label.get(failure_label))),
            "accuracy": metrics["accuracy"],
            "correct_count": metrics["correct_count"],
        }
        for failure_label, count in sorted(distribution.items())
    ]
    return {
        "run": label,
        "trace_dir": str(trace_dir),
        "failure_count": total,
        "accuracy": metrics["accuracy"],
        "accuracy_source": metrics["accuracy_source"],
        "correct_count": metrics["correct_count"],
        "taxonomy_distribution": rows,
        "top_failure_families": rows[:0] + [
            {
                **_failure_row(failure_label, count, total, group_failure_label(failure_label, evidence_by_label.get(failure_label))),
            }
            for failure_label, count in distribution.most_common(3)
        ],
        "group_totals": dict(sorted(group_totals.items())),
        "top_failure_signatures": [item.model_dump(mode="json") for item in top_k_signatures(failures, k=5)],
    }


def build_comparison(run_summaries: list[dict[str, Any]], baseline_label: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    label_order = [summary["run"] for summary in run_summaries]
    by_run = {summary["run"]: summary for summary in run_summaries}
    all_labels = sorted(
        {
            row["failure_label"]
            for summary in run_summaries
            for row in (summary.get("taxonomy_distribution") or [])
        }
    )
    merged_rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []
    baseline_rows = {
        row["failure_label"]: row
        for row in by_run.get(baseline_label, {}).get("taxonomy_distribution", [])
    }
    for failure_label in all_labels:
        merged: dict[str, Any] = {"failure_label": failure_label}
        for run_label in label_order:
            row = next(
                (item for item in by_run[run_label].get("taxonomy_distribution", []) if item["failure_label"] == failure_label),
                None,
            )
            merged[f"{run_label}_count"] = row["count"] if row else 0
            merged[f"{run_label}_share"] = row["share"] if row else 0.0
        merged_rows.append(merged)
        baseline = baseline_rows.get(failure_label, {"count": 0, "share": 0.0})
        for run_label in label_order:
            if run_label == baseline_label:
                continue
            row = next(
                (item for item in by_run[run_label].get("taxonomy_distribution", []) if item["failure_label"] == failure_label),
                None,
            )
            delta_rows.append(
                {
                    "run": run_label,
                    "failure_label": failure_label,
                    "count_delta_vs_baseline": (row["count"] if row else 0) - baseline["count"],
                    "share_delta_vs_baseline": (row["share"] if row else 0.0) - baseline["share"],
                }
            )
    return merged_rows, delta_rows


def _render_markdown(run_summaries: list[dict[str, Any]], merged_rows: list[dict[str, Any]], delta_rows: list[dict[str, Any]]) -> str:
    lines = ["# Phase-2 Taxonomy Report", ""]
    lines.append("## Runs")
    lines.append("")
    lines.append("| Run | Accuracy | Accuracy Source | Correct Count | Failure Count | Top-3 Families |")
    lines.append("| --- | ---: | --- | ---: | ---: | --- |")
    for summary in run_summaries:
        top = ", ".join(item["failure_label"] for item in summary.get("top_failure_families") or []) or "-"
        lines.append(
            f"| {summary['run']} | {summary.get('accuracy', '-') if summary.get('accuracy') is not None else '-'} | "
            f"{summary.get('accuracy_source', '-') if summary.get('accuracy_source') is not None else '-'} | "
            f"{summary.get('correct_count', '-') if summary.get('correct_count') is not None else '-'} | "
            f"{summary.get('failure_count', 0)} | {top} |"
        )
    lines.append("")
    lines.append("## Table A")
    lines.append("")
    lines.append("| Run | Failure Label | Group | Count | Share |")
    lines.append("| --- | --- | --- | ---: | ---: |")
    for summary in run_summaries:
        for row in summary.get("taxonomy_distribution", []):
            lines.append(
                f"| {summary['run']} | {row['failure_label']} | {row['failure_group']} | {row['count']} | {row['share']:.4f} |"
            )
    lines.append("")
    lines.append("## Merged Comparison")
    lines.append("")
    if merged_rows:
        headers = list(merged_rows[0].keys())
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in merged_rows:
            lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    lines.append("")
    lines.append("## Delta Vs Baseline")
    lines.append("")
    lines.append("| Run | Failure Label | Count Delta | Share Delta |")
    lines.append("| --- | --- | ---: | ---: |")
    for row in delta_rows:
        lines.append(
            f"| {row['run']} | {row['failure_label']} | {row['count_delta_vs_baseline']} | {row['share_delta_vs_baseline']:.4f} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase-2 taxonomy report across benchmark runs.")
    parser.add_argument("--run", action="append", default=[], help="LABEL=TRACE_DIR")
    parser.add_argument("--optional-run", action="append", default=[], help="LABEL=TRACE_DIR")
    parser.add_argument("--metrics", action="append", default=[], help="LABEL=METRICS_JSON")
    parser.add_argument("--require-runs", default="baseline,primary_v4")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    runs = dict(_parse_mapping(item, label_name="run") for item in args.run)
    optional_runs = dict(_parse_mapping(item, label_name="optional-run") for item in args.optional_run)
    metrics = dict(_parse_mapping(item, label_name="metrics") for item in args.metrics)
    required = [item.strip() for item in str(args.require_runs).split(",") if item.strip()]

    missing_required = [label for label in required if label not in runs and label not in optional_runs]
    if missing_required:
        raise SystemExit(f"missing required run declarations: {', '.join(missing_required)}")

    summaries: list[dict[str, Any]] = []
    skipped_optional: list[dict[str, Any]] = []
    for label in required:
        trace_dir = runs.get(label) or optional_runs.get(label)
        if trace_dir is None or not trace_dir.exists():
            raise SystemExit(f"required run missing on disk: {label} -> {trace_dir}")
        summaries.append(summarize_run(label, trace_dir, metrics.get(label)))
    for label, trace_dir in optional_runs.items():
        if label in required:
            continue
        if not trace_dir.exists():
            skipped_optional.append({"run": label, "status": "skipped_missing", "trace_dir": str(trace_dir)})
            continue
        summaries.append(summarize_run(label, trace_dir, metrics.get(label)))

    merged_rows, delta_rows = build_comparison(summaries, baseline_label=required[0])
    result = {
        "runs": summaries,
        "skipped_optional_runs": skipped_optional,
        "merged_comparison": merged_rows,
        "delta_vs_baseline": delta_rows,
    }
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_render_markdown(summaries, merged_rows, delta_rows), encoding="utf-8")


if __name__ == "__main__":
    main()
