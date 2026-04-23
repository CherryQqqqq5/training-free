from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from grc.compiler.failure_taxonomy import classify_error_type

COMPATIBILITY_REPAIRS = {
    "resolve_contextual_string_arg",
    "repair_json",
    "coerce_types",
    "drop_unknown_key",
    "fill_default",
    "arguments_changed",
}
DECISION_ADJACENT_REPAIRS = {
    "coerce_no_tool_text_to_empty",
    "termination_to_tool_retry",
    "strip_assistant_content_with_tool_calls",
}


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _collect_user_texts(value: Any) -> list[str]:
    texts: list[str] = []

    def add_text(item: Any) -> None:
        if isinstance(item, str) and item.strip():
            texts.append(item.strip())
            return
        if isinstance(item, list):
            for child in item:
                add_text(child)
            return
        if not isinstance(item, dict):
            return
        for key in ("text", "content", "input_text"):
            if key in item:
                add_text(item.get(key))

    def visit(item: Any) -> None:
        if isinstance(item, list):
            for child in item:
                visit(child)
            return
        if not isinstance(item, dict):
            return
        if item.get("role") == "user":
            add_text(item.get("content"))
            return
        for key, child in item.items():
            if key in {"id", "call_id", "name"}:
                continue
            visit(child)

    visit(value)
    return texts


def _request_fingerprint(value: Any) -> str | None:
    normalized = [_normalize_text(text) for text in _collect_user_texts(value)]
    normalized = [text for text in normalized if text]
    if not normalized:
        return None
    return "fp:" + hashlib.sha1(" || ".join(normalized).encode("utf-8")).hexdigest()


def _load_success_map(path: Path | None) -> dict[str, bool]:
    if path is None or not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except Exception:
        data = None
    mapping: dict[str, bool] = {}
    if isinstance(data, dict):
        record_like = any(key in data for key in ("id", "case_id", "test_id", "prompt", "valid", "correct"))
        if record_like:
            case_id = None
            for key in ("id", "case_id", "test_id"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    case_id = value
                    break
            if not case_id:
                case_id = _request_fingerprint((data.get("prompt") or {}).get("question"))
            success_value = None
            if isinstance(data.get("valid"), bool):
                success_value = bool(data["valid"])
            elif isinstance(data.get("correct"), bool):
                success_value = bool(data["correct"])
            fingerprint = _request_fingerprint((data.get("prompt") or {}).get("question"))
            if case_id and success_value is not None:
                mapping[case_id] = success_value
            if fingerprint and success_value is not None:
                mapping[fingerprint] = success_value
            return mapping
        for key, value in data.items():
            if isinstance(value, bool):
                mapping[str(key)] = value
            elif isinstance(value, (int, float)):
                mapping[str(key)] = bool(value)
            elif isinstance(value, dict):
                if isinstance(value.get("valid"), bool):
                    mapping[str(key)] = bool(value["valid"])
                elif isinstance(value.get("correct"), bool):
                    mapping[str(key)] = bool(value["correct"])
        return mapping

    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if not isinstance(item, dict):
            continue
        case_id = None
        for key in ("id", "case_id", "test_id"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                case_id = value
                break
        if not case_id:
            case_id = _request_fingerprint((item.get("prompt") or {}).get("question"))
        if not case_id:
            continue
        success_value = None
        if isinstance(item.get("valid"), bool):
            success_value = bool(item["valid"])
        elif isinstance(item.get("correct"), bool):
            success_value = bool(item["correct"])
        fingerprint = _request_fingerprint((item.get("prompt") or {}).get("question"))
        if success_value is None:
            continue
        mapping[case_id] = success_value
        if fingerprint:
            mapping[fingerprint] = success_value
    return mapping


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
    request_fingerprint = _request_fingerprint(
        request.get("input") if isinstance(request, dict) else None
    ) or _request_fingerprint(
        request.get("messages") if isinstance(request, dict) else None
    )
    if request_fingerprint:
        return request_fingerprint
    return trace_id


def classify_repair(repair: str) -> str:
    if repair in COMPATIBILITY_REPAIRS:
        return "compatibility"
    if repair in DECISION_ADJACENT_REPAIRS or repair.startswith("termination") or "no_tool" in repair:
        return "decision_adjacent"
    return "unknown"


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


def _has_prior_tool_output(payload: dict[str, Any]) -> bool:
    def visit(item: Any) -> bool:
        if isinstance(item, list):
            return any(visit(child) for child in item)
        if not isinstance(item, dict):
            return False
        if item.get("role") == "tool" or item.get("type") == "function_call_output":
            return True
        return any(visit(value) for key, value in item.items() if key not in {"id", "call_id", "name"})

    return any(
        visit(candidate)
        for candidate in (
            payload.get("request", {}).get("messages") if isinstance(payload.get("request"), dict) else None,
            payload.get("request_original", {}).get("messages") if isinstance(payload.get("request_original"), dict) else None,
            payload.get("request_original", {}).get("input") if isinstance(payload.get("request_original"), dict) else None,
        )
    )


def _issue_request_predicates(issue: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    predicates: list[str] = []
    issue_predicates = issue.get("request_predicates")
    if isinstance(issue_predicates, list):
        predicates.extend(str(item) for item in issue_predicates if str(item).strip())
    evidence = issue.get("predicate_evidence")
    if isinstance(evidence, dict):
        if evidence.get("has_sufficient_literals") and "prior_explicit_literals_present" not in predicates:
            predicates.append("prior_explicit_literals_present")
        if evidence.get("tool_output_sufficient") and "prior_tool_outputs_present" not in predicates:
            predicates.append("prior_tool_outputs_present")
    if _has_prior_tool_output(payload) and "prior_tool_outputs_present" not in predicates:
        predicates.append("prior_tool_outputs_present")
    return predicates


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
            request_predicates = _issue_request_predicates(issue, payload)
            classification = classify_error_type(
                str(issue.get("kind") or "validation_issue"),
                request_predicates=request_predicates,
                has_prior_tool_output="prior_tool_outputs_present" in request_predicates,
            )
            failure_stage = str(issue.get("stage") or classification.stage.value)
            failure_type = str(issue.get("failure_type") or classification.failure_type.value)
            failure_label = str(issue.get("failure_label") or f"({failure_stage},{failure_type})")
            records.append(
                {
                    "case_id": case_id,
                    "run_id": run_id,
                    "trace_id": trace_id,
                    "failure_stage": failure_stage,
                    "failure_type": failure_type,
                    "failure_label": failure_label,
                    "legacy_error_type": str(issue.get("kind") or "validation_issue"),
                    "request_predicates": request_predicates,
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
    family_applied_counts: dict[tuple[str, str], int] = defaultdict(int)
    family_known_success: dict[tuple[str, str], int] = defaultdict(int)
    family_success_counts: dict[tuple[str, str], int] = defaultdict(int)

    for record in records:
        for repair in record.get("repairs_applied") or []:
            repair_failure_counts[repair][record["failure_label"]] += 1
            family_applied_counts[(record["failure_label"], repair)] += 1
            if record.get("final_success") is not None:
                repair_known_success[repair] += 1
                family_known_success[(record["failure_label"], repair)] += 1
                if bool(record["final_success"]):
                    repair_success_counts[repair] += 1
                    family_success_counts[(record["failure_label"], repair)] += 1

    for repair, by_failure in sorted(repair_failure_counts.items()):
        applied = sum(by_failure.values())
        target_failure_count = sum(failure_totals[label] for label in by_failure)
        repair_stats[repair] = {
            "applied": applied,
            "repair_class": classify_repair(repair),
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

    repair_by_family: list[dict[str, Any]] = []
    family_summary_index: dict[str, dict[str, Any]] = {}
    for (failure_label, repair), applied in sorted(family_applied_counts.items()):
        repair_class = classify_repair(repair)
        failure_total = failure_totals[failure_label]
        success_known = family_known_success[(failure_label, repair)]
        success_count = family_success_counts[(failure_label, repair)]
        row = {
            "failure_label": failure_label,
            "repair": repair,
            "repair_class": repair_class,
            "coverage": (applied / failure_total if failure_total else 0.0),
            "success": (success_count / success_known if success_known else None),
            "attribution_gain": repair_stats.get(repair, {}).get("attribution_gain"),
            "applied": applied,
        }
        repair_by_family.append(row)
        family_summary = family_summary_index.setdefault(
            failure_label,
            {
                "failure_label": failure_label,
                "total_failures": failure_total,
                "compatibility_repair_coverage": 0.0,
                "decision_adjacent_repair_coverage": 0.0,
                "unknown_repair_coverage": 0.0,
            },
        )
        key = f"{repair_class}_repair_coverage"
        family_summary[key] += row["coverage"]

    return {
        "record_count": len(records),
        "failure_totals": dict(sorted(failure_totals.items())),
        "repairs": repair_stats,
        "repair_by_family": repair_by_family,
        "family_summary": list(family_summary_index.values()),
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
    parser.add_argument("--score-json", help="Optional score JSON with per-case success information.")
    parser.add_argument("--result-json", help="Optional result JSON fallback with per-case success information.")
    parser.add_argument("--ablation", action="append", type=_parse_ablation, help="NAME=ACC, use full=ACC for full run.")
    parser.add_argument("--records-out", help="Optional JSONL records path.")
    parser.add_argument("--summary-out", help="Optional JSON summary path.")
    parser.add_argument("--out-md", help="Optional markdown summary path.")
    args = parser.parse_args()

    success_map = _load_success_map(Path(args.success_map) if args.success_map else None)
    success_map.update(_load_success_map(Path(args.score_json) if args.score_json else None))
    success_map.update(_load_success_map(Path(args.result_json) if args.result_json else None))
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
    if args.out_md:
        md_path = Path(args.out_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Repair Contribution Report", "", "## Repair By Family", "", "| Failure Label | Repair | Class | Applied | Coverage | Success | Gain |", "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
        for row in summary["repair_by_family"]:
            success = "-" if row["success"] is None else f"{row['success']:.4f}"
            gain = "-" if row["attribution_gain"] is None else f"{row['attribution_gain']:.4f}"
            lines.append(f"| {row['failure_label']} | {row['repair']} | {row['repair_class']} | {row['applied']} | {row['coverage']:.4f} | {success} | {gain} |")
        lines.extend(["", "## Family Summary", "", "| Failure Label | Total Failures | Compatibility Coverage | Decision-Adjacent Coverage | Unknown Coverage |", "| --- | ---: | ---: | ---: | ---: |"])
        for row in summary["family_summary"]:
            lines.append(
                f"| {row['failure_label']} | {row['total_failures']} | {row['compatibility_repair_coverage']:.4f} | {row['decision_adjacent_repair_coverage']:.4f} | {row['unknown_repair_coverage']:.4f} |"
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not args.summary_out:
        print(rendered)


if __name__ == "__main__":
    main()
