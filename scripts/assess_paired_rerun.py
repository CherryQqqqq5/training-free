#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _metric_value(metrics: Dict[str, Any], key: str, default: float = 0.0) -> float:
    value = metrics.get(key, default)
    if value is None:
        return default
    return float(value)


def _target_metric(metrics: Dict[str, Any]) -> float:
    test_category = str(metrics.get("test_category") or "").strip()
    subsets = metrics.get("subsets")
    if test_category and isinstance(subsets, dict) and test_category in subsets:
        return _metric_value(subsets, test_category)
    return _metric_value(metrics, "acc")


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--primary", required=True)
    parser.add_argument("--rerun", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    baseline = _load_json(Path(args.baseline))
    primary = _load_json(Path(args.primary))
    rerun = _load_json(Path(args.rerun))

    baseline_target = _target_metric(baseline)
    primary_target = _target_metric(primary)
    rerun_target = _target_metric(rerun)
    primary_delta = primary_target - baseline_target
    rerun_delta = rerun_target - baseline_target

    primary_complete = str(primary.get("evaluation_status") or "").strip().lower() == "complete"
    rerun_complete = str(rerun.get("evaluation_status") or "").strip().lower() == "complete"
    paired_rerun_consistent = primary_complete and rerun_complete and _sign(primary_delta) == _sign(rerun_delta)

    if not primary_complete or not rerun_complete:
        reason = "primary or rerun evaluation_status is not complete"
    elif paired_rerun_consistent:
        reason = "primary and rerun target deltas have consistent direction"
    else:
        reason = "primary and rerun target deltas disagree in direction"

    payload = {
        "baseline_target": baseline_target,
        "primary_target": primary_target,
        "rerun_target": rerun_target,
        "primary_delta": primary_delta,
        "rerun_delta": rerun_delta,
        "paired_rerun_consistent": paired_rerun_consistent,
        "reason": reason,
        "primary_metrics": args.primary,
        "rerun_metrics": args.rerun,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
