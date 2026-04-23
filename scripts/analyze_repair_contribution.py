from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from grc.compiler.failure_taxonomy import classify_error_type


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _case_id(payload: dict[str, Any], trace_id: str) -> str:
    for key in ("case_id", "test_id", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    request = payload.get("request_original") or payload.get("request") or {}
    for key in ("case_id", "test_id", "id"):
        value = request.get(key) if isinstance(request, dict) else None
        if isinstance(value, str) and value.strip():
            return value
    return trace_id


def _repair_kinds(payload: dict[str, Any]) -> list[str]:
    validation = payload.get("validation") or {}
    if isinstance(validation, dict) and isinstance(validation.get("repair_kinds"), list):
        return [str(item) for item in validation["repair_kinds"] if str(item).strip()]
    repairs = payload.get("repairs") or []
    kinds: list[str] = []
    if isinstance(repairs, list):
        for repair in repairs:
            if isinstance(repair, dict) and str(repair.get("kind") or "").strip():
                kind = str(repair["kind"])
                if kind not in kinds:
                    kinds.append(kind)
    return kinds


def repair_records(trace_dir: Path, *, run_id: str, success_map: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    success_map = success_map or {}
    records: list[dict[str, Any]] = []
    for path in sorted(trace_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        trace_id = str(payload.get("trace_id") or path.stem)
        case_id = _case_id(payload, trace_id)
        repairs = _repair_kinds(payload)
        validation = payload.get("validation") or {}
        issues = validation.get("issues") if isinstance(validation, dict) else []
        if not isinstance(issues, list):
            issues = []
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            classification = classify_error_type(str(issue.get("kind") or "validation_issue"))
            records.append(
                {
                    "case_id": case_id,
                    "run_id": run_id,
                    "trace_id": trace_id,
                    "failure_stage": classification.stage.value,
                    "failure_type": classification.failure_type.value,
                    "failure_label": classification.label,
                    "legacy_error_type": str(issue.get("kind") or "validation_issue"),
                    "repairs_applied": repairs,
                    "final_success": success_map.get(case_id),
                }
            )
    return records


def summarize_repairs(records: list[dict[str, Any]], ablation_acc: dict[str, float] | None = None) -> dict[str, Any]:
    failure_totals = Counter(record["failure_label"] for record in records)
    repair_stats: dict[str, dict[str, Any]] = {}
    repair_failure_counts: dict[str, Counter[str]] = defaultdict(Counter)
    repair_success_counts: Counter[str] = Counter()
    repair_known_success: Counter[str] = Counter()

    for record in records:
        for repair in record.get("repairs_applied") or []:
            repair_failure_counts[repair][record["failure_label"]] += 1
            if record.get("final_success") is not None:
                repair_known_success[repair] += 1
                if bool(record["final_success"]):
                    repair_success_counts[repair] += 1

    for repair, by_failure in sorted(repair_failure_counts.items()):
        applied = sum(by_failure.values())
        target_failure_count = sum(failure_totals[label] for label in by_failure)
        repair_stats[repair] = {
            "applied": applied,
            "coverage": (applied / target_failure_count if target_failure_count else 0.0),
            "success": (
                repair_success_counts[repair] / repair_known_success[repair]
                if repair_known_success[repair]
                else None
            ),
            "by_failure_label": dict(sorted(by_failure.items())),
        }

    if ablation_acc:
        full_acc = ablation_acc.get("full")
        if full_acc is not None:
            for repair, stats in repair_stats.items():
                without = ablation_acc.get(repair)
                stats["attribution_gain"] = (full_acc - without) if without is not None else None

    return {
        "record_count": len(records),
        "failure_totals": dict(sorted(failure_totals.items())),
        "repairs": repair_stats,
    }


def _parse_ablation(value: str) -> tuple[str, float]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("ablation must be formatted as NAME=ACC")
    key, raw = value.split("=", 1)
    return key.strip(), float(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze repair coverage, success, and ablation gain.")
    parser.add_argument("--trace-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--success-map", help="Optional JSON map from case_id to boolean success.")
    parser.add_argument("--ablation", action="append", type=_parse_ablation, help="NAME=ACC, use full=ACC for full run.")
    parser.add_argument("--records-out", help="Optional JSONL records path.")
    parser.add_argument("--summary-out", help="Optional JSON summary path.")
    args = parser.parse_args()

    success_map = _load_json(Path(args.success_map) if args.success_map else None)
    records = repair_records(Path(args.trace_dir), run_id=args.run_id, success_map=success_map)
    ablation_acc = dict(args.ablation or [])
    summary = summarize_repairs(records, ablation_acc=ablation_acc)

    if args.records_out:
        records_path = Path(args.records_out)
        records_path.parent.mkdir(parents=True, exist_ok=True)
        with records_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.summary_out:
        summary_path = Path(args.summary_out)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
