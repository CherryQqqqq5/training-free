#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_PRIORITY_CATEGORIES = [
    "multi_turn_miss_func",
    "multi_turn_long_context",
    "multi_turn_base",
    "parallel_multiple",
    "multiple",
]
FORBIDDEN_FIELD_FRAGMENTS = (
    "gold",
    "answer",
    "expected",
    "ground_truth",
    "oracle",
    "checker",
    "reference",
    "possible_answer",
    "score",
    "candidate",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        rows = payload.get("records") or payload.get("data") or payload.get("rows")
        if rows is None:
            rows = list(payload.values())
    else:
        rows = payload
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _parse_categories(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_PRIORITY_CATEGORIES)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _has_question_or_messages(row: dict[str, Any]) -> bool:
    return any(key in row and row.get(key) for key in ("question", "messages"))


def _functions(row: dict[str, Any]) -> list[dict[str, Any]]:
    raw = row.get("function") or row.get("functions") or []
    if isinstance(raw, dict):
        raw = [raw]
    return [fn for fn in raw if isinstance(fn, dict)]


def _function_errors(row: dict[str, Any]) -> list[str]:
    fns = _functions(row)
    if not fns:
        return ["function_schema_missing"]
    errors: list[str] = []
    has_required_arg = False
    for fn in fns:
        if not isinstance(fn.get("name"), str) or not fn.get("name"):
            errors.append("function_name_missing")
        params = fn.get("parameters")
        if not isinstance(params, dict):
            errors.append("function_parameters_missing")
            continue
        props = params.get("properties")
        if not isinstance(props, dict):
            errors.append("function_properties_missing")
            props = {}
        required = params.get("required")
        if not isinstance(required, list) or not all(isinstance(item, str) and item for item in required):
            errors.append("required_args_missing")
            continue
        if required:
            has_required_arg = True
        for arg in required:
            if arg not in props or not isinstance(props.get(arg), dict):
                errors.append("required_arg_property_schema_missing")
    return sorted(set(errors))


def _category(row: dict[str, Any], categories: list[str]) -> str | None:
    raw = row.get("category") or row.get("test_category")
    if isinstance(raw, str) and raw:
        return raw
    case_id = str(row.get("id") or row.get("case_id") or "")
    for category in categories:
        if case_id.startswith(category) or f"_{category}_" in case_id or category in case_id:
            return category
    return None


def _forbidden_fields(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for key in row:
        lowered = str(key).lower()
        if any(fragment in lowered for fragment in FORBIDDEN_FIELD_FRAGMENTS):
            found.append(str(key))
    return sorted(found)


def evaluate(dataset_json: Path, categories: list[str] | None = None) -> dict[str, Any]:
    categories = list(categories or DEFAULT_PRIORITY_CATEGORIES)
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    malformed_records: list[dict[str, Any]] = []
    forbidden_records: list[dict[str, Any]] = []
    category_counts = {category: 0 for category in categories}

    if not dataset_json.exists():
        blockers.append("dataset_json_missing")
    else:
        try:
            rows = _records(_read_json(dataset_json))
        except Exception:
            blockers.append("dataset_json_invalid")

    if not rows and "dataset_json_missing" not in blockers and "dataset_json_invalid" not in blockers:
        blockers.append("dataset_records_missing")

    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for index, row in enumerate(rows):
        errors: list[str] = []
        case_id = row.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append("id_missing")
            case_id_text = f"<row:{index}>"
        else:
            case_id_text = case_id
            if case_id in seen_ids:
                duplicate_ids.add(case_id)
            seen_ids.add(case_id)
        if not _has_question_or_messages(row):
            errors.append("question_or_messages_missing")
        errors.extend(_function_errors(row))
        forbidden = _forbidden_fields(row)
        if forbidden:
            forbidden_records.append({"case_id": case_id_text, "fields": forbidden})
        category = _category(row, categories)
        if category in category_counts and not errors and not forbidden:
            category_counts[category] += 1
        if errors:
            malformed_records.append({"case_id": case_id_text, "errors": sorted(set(errors))})

    if malformed_records:
        blockers.append("dataset_records_malformed")
    if forbidden_records:
        blockers.append("dataset_forbidden_fields_present")
    if duplicate_ids:
        blockers.append("dataset_duplicate_ids_present")
    missing_categories = [category for category, count in category_counts.items() if count == 0]
    if missing_categories:
        blockers.append("priority_category_coverage_missing")

    return {
        "report_scope": "explicit_literal_dataset_schema_gate",
        "offline_only": True,
        "does_not_call_provider": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "dataset_json": str(dataset_json),
        "dataset_present": dataset_json.exists(),
        "record_count": len(rows),
        "requested_categories": categories,
        "category_counts": category_counts,
        "missing_categories": missing_categories,
        "malformed_record_count": len(malformed_records),
        "malformed_records": malformed_records[:50],
        "forbidden_record_count": len(forbidden_records),
        "forbidden_records": forbidden_records[:50],
        "duplicate_ids": sorted(duplicate_ids),
        "blockers": blockers,
        "explicit_literal_dataset_gate_passed": not blockers,
        "gold_score_candidate_fields_required_or_read": False,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Explicit Literal Dataset Schema Gate",
        "",
        f"- Passed: `{report['explicit_literal_dataset_gate_passed']}`",
        f"- Dataset: `{report['dataset_json']}`",
        f"- Records: `{report['record_count']}`",
        f"- Blockers: `{', '.join(report['blockers']) if report['blockers'] else 'none'}`",
        "",
        "| Category | Valid Records |",
        "| --- | ---: |",
    ]
    for category, count in report["category_counts"].items():
        lines.append(f"| `{category}` | `{count}` |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate offline dataset JSON before explicit-literal candidate extraction.")
    parser.add_argument("--dataset-json", type=Path, required=True)
    parser.add_argument("--categories", default=",".join(DEFAULT_PRIORITY_CATEGORIES))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    report = evaluate(args.dataset_json, _parse_categories(args.categories))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "explicit_literal_dataset_gate_passed": report["explicit_literal_dataset_gate_passed"],
            "record_count": report["record_count"],
            "missing_categories": report["missing_categories"],
            "blockers": report["blockers"],
        }, indent=2, sort_keys=True))
    if args.strict and not report["explicit_literal_dataset_gate_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
