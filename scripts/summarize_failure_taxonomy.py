from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from grc.compiler.mine import mine_failures


def _parse_run(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("run must be formatted as LABEL=TRACE_DIR")
    label, trace_dir = value.split("=", 1)
    label = label.strip()
    if not label:
        raise argparse.ArgumentTypeError("run label is empty")
    return label, Path(trace_dir)


def summarize_trace_dir(label: str, trace_dir: Path) -> dict[str, Any]:
    failures = mine_failures(str(trace_dir))
    distribution = Counter(
        failure.failure_label or f"({failure.stage or 'UNKNOWN'},{failure.failure_type or failure.error_type})"
        for failure in failures
    )
    total = sum(distribution.values())
    return {
        "run": label,
        "trace_dir": str(trace_dir),
        "failure_count": total,
        "taxonomy_distribution": dict(sorted(distribution.items())),
        "top_failure_families": [
            {
                "failure_label": failure_label,
                "count": count,
                "share": (count / total if total else 0.0),
            }
            for failure_label, count in distribution.most_common(3)
        ],
    }


def build_table_a(run_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary in run_summaries:
        total = int(summary.get("failure_count") or 0)
        distribution = summary.get("taxonomy_distribution") or {}
        for failure_label, count in sorted(distribution.items()):
            rows.append(
                {
                    "run": summary["run"],
                    "failure_label": failure_label,
                    "count": int(count),
                    "share": (int(count) / total if total else 0.0),
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize GRC failures by Phase-2 (stage,type) taxonomy.")
    parser.add_argument("--run", action="append", type=_parse_run, required=True, help="LABEL=TRACE_DIR")
    parser.add_argument("--out", help="Optional JSON output path.")
    args = parser.parse_args()

    summaries = [summarize_trace_dir(label, trace_dir) for label, trace_dir in args.run]
    result = {
        "runs": summaries,
        "table_a": build_table_a(summaries),
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
