#!/usr/bin/env python3
"""Validate BFCL->GRC workflow run quality gates.

Usage:
  python scripts/validate_run.py --root outputs/bfcl_v4
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_SUBSETS = [
    "simple_python",
    "multiple",
    "parallel_multiple",
    "multi_turn_miss_param",
]


def read_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def csv_has_data_rows(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
        return len(rows) >= 2 and any(any(cell.strip() for cell in row) for row in rows[1:])
    except Exception:
        return False


def scan_trace_patch_evidence(trace_dir: Path, sample_limit: int = 200) -> Tuple[bool, Dict[str, int]]:
    counters = {
        "rule_hits": 0,
        "repairs": 0,
        "request_patches": 0,
        "fallback_applied": 0,
    }
    if not trace_dir.exists():
        return False, counters

    scanned = 0
    for p in sorted(trace_dir.glob("*.json")):
        if scanned >= sample_limit:
            break
        scanned += 1
        payload = read_json(p)
        validation = payload.get("validation") or {}
        if validation.get("rule_hits"):
            counters["rule_hits"] += 1
        if validation.get("repairs"):
            counters["repairs"] += 1
        if validation.get("request_patches"):
            counters["request_patches"] += 1
        if validation.get("fallback_applied") is True:
            counters["fallback_applied"] += 1

    has_evidence = any(v > 0 for v in counters.values())
    return has_evidence, counters


def pick_key_score_csv(score_dir: Path, subset: str) -> Path:
    if subset == "multi_turn_miss_param":
        return score_dir / "data_multi_turn.csv"
    return score_dir / "data_non_live.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate workflow gates for BFCL/GRC runs.")
    parser.add_argument("--root", default="outputs/bfcl_v4", help="Run root containing baseline/ and patch/")
    parser.add_argument(
        "--reports-dir",
        default="outputs/reports",
        help="Directory containing <subset>_failures.jsonl files",
    )
    parser.add_argument(
        "--subsets",
        nargs="*",
        default=DEFAULT_SUBSETS,
        help="Subsets to validate",
    )
    args = parser.parse_args()

    root = Path(args.root)
    reports_dir = Path(args.reports_dir)
    subsets: List[str] = args.subsets

    all_pass = True
    global_failure_nonzero = False

    for subset in subsets:
        print(f"\n=== {subset} ===")
        subset_failures: List[str] = []

        # Gate 1: score CSV has model rows
        base_score_dir = root / "baseline" / subset / "bfcl" / "score"
        patch_score_dir = root / "patch" / subset / "bfcl" / "score"
        key_base_csv = pick_key_score_csv(base_score_dir, subset)
        key_patch_csv = pick_key_score_csv(patch_score_dir, subset)

        base_has_rows = csv_has_data_rows(key_base_csv)
        patch_has_rows = csv_has_data_rows(key_patch_csv)
        if not base_has_rows:
            subset_failures.append(f"baseline score empty/missing: {key_base_csv}")
        if not patch_has_rows:
            subset_failures.append(f"patch score empty/missing: {key_patch_csv}")

        # Gate 2: metrics sources/subsets/acc are valid
        base_metrics = read_json(root / "baseline" / subset / "artifacts" / "metrics.json")
        patch_metrics = read_json(root / "patch" / subset / "artifacts" / "metrics.json")
        for label, m in [("baseline", base_metrics), ("patch", patch_metrics)]:
            if not m:
                subset_failures.append(f"{label} metrics missing/invalid JSON")
                continue
            metric_sources = m.get("metric_sources")
            subsets_obj = m.get("subsets")
            acc = m.get("acc")
            if not metric_sources:
                subset_failures.append(f"{label} metrics metric_sources empty")
            if not subsets_obj:
                subset_failures.append(f"{label} metrics subsets empty")
            if acc is None:
                subset_failures.append(f"{label} metrics acc is None")

        # Gate 3: failure miner output exists and is non-zero (global requirement)
        failures_path = reports_dir / f"{subset}_failures.jsonl"
        if failures_path.exists():
            line_count = sum(1 for _ in failures_path.open("r", encoding="utf-8"))
        else:
            line_count = 0
        print(f"failure lines: {line_count} ({failures_path})")
        if line_count > 0:
            global_failure_nonzero = True

        # Gate 4: patch trace has evidence
        patch_trace_dir = root / "patch" / subset / "traces"
        has_evidence, counters = scan_trace_patch_evidence(patch_trace_dir)
        if not has_evidence:
            subset_failures.append(
                f"no patch evidence in traces: rule_hits={counters['rule_hits']}, "
                f"repairs={counters['repairs']}, request_patches={counters['request_patches']}, "
                f"fallback_applied={counters['fallback_applied']}"
            )
        print(
            "trace evidence counts:",
            counters,
        )

        if subset_failures:
            all_pass = False
            print("status: FAIL")
            for item in subset_failures:
                print(f"- {item}")
        else:
            print("status: PASS")

    # Global mining gate: at least one subset must produce failures
    if not global_failure_nonzero:
        all_pass = False
        print("\nGLOBAL FAIL: all *_failures.jsonl are zero or missing")
    else:
        print("\nGLOBAL PASS: at least one subset produced failures")

    if all_pass:
        print("\nWORKFLOW GATE: PASS")
        return 0
    print("\nWORKFLOW GATE: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
