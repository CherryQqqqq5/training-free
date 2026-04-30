#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.check_explicit_literal_dataset import DEFAULT_PRIORITY_CATEGORIES, FORBIDDEN_FIELD_FRAGMENTS


ALLOWED_OUTPUT_FIELDS = ("id", "category", "question", "messages", "function")
MULTI_TURN_FUNCTION_ALIASES = {
    "MessageAPI.view_messages_received": "search_messages",
    "TradingBot.add_stock_to_watchlist": "add_to_watchlist",
    "TradingBot.make_transaction": "place_order",
    "TradingBot.update_market_status": "get_stock_info",
    "TravelAPI.authenticate": "authenticate_travel",
}



def _parse_categories(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_PRIORITY_CATEGORIES)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _read_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    return _rows_from_text(text)


def _rows_from_text(text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
        return rows
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("records") or payload.get("data") or payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        if payload.get("id"):
            return [payload]
    return []


def _category_from_file(path: Path, categories: list[str]) -> str | None:
    name = path.name
    if name.startswith("BFCL_v4_") and name.endswith(".json"):
        category = name[len("BFCL_v4_") : -len(".json")]
        return category if category in categories else None
    for category in categories:
        if category in name:
            return category
    return None


def _category_from_row(row: dict[str, Any], fallback: str | None, categories: list[str]) -> str | None:
    raw = row.get("category") or row.get("test_category")
    if isinstance(raw, str) and raw in categories:
        return raw
    case_id = str(row.get("id") or row.get("case_id") or "")
    for category in categories:
        if case_id.startswith(category) or category in case_id:
            return category
    return fallback


def _forbidden_fields(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for key in row:
        lowered = str(key).lower()
        if any(fragment in lowered for fragment in FORBIDDEN_FIELD_FRAGMENTS):
            found.append(str(key))
    return sorted(found)


def _load_function_docs(dataset_file: Path) -> dict[str, dict[str, Any]]:
    doc_root = dataset_file.parent / "multi_turn_func_doc"
    if not doc_root.exists():
        return {}
    docs: dict[str, dict[str, Any]] = {}
    for doc_path in sorted(doc_root.glob("*.json")):
        try:
            rows = _rows_from_text(doc_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in rows:
            name = row.get("name")
            if isinstance(name, str) and name:
                docs[name] = row
    return docs


def _function_doc_for_path(raw_name: str, docs: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    method = raw_name.rsplit(".", 1)[-1]
    source = docs.get(method)
    if source is None:
        alias = MULTI_TURN_FUNCTION_ALIASES.get(raw_name) or MULTI_TURN_FUNCTION_ALIASES.get(method)
        source = docs.get(alias) if alias else None
    if source is None:
        return None
    copied = json.loads(json.dumps(source))
    # Keep the BFCL path-qualified function name so source result tool calls can
    # map back to this schema deterministically during candidate extraction.
    copied["name"] = raw_name
    return copied


def _function_payload(row: dict[str, Any], docs: dict[str, dict[str, Any]] | None = None) -> Any:
    if "function" in row:
        return row["function"]
    if "functions" in row:
        return row["functions"]
    path = row.get("path")
    if isinstance(path, list) and docs:
        functions: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in path:
            if not isinstance(item, str) or not item or item in seen:
                continue
            seen.add(item)
            fn = _function_doc_for_path(item, docs)
            if fn is not None:
                functions.append(fn)
        if functions:
            return functions
    return None


def _sanitize(row: dict[str, Any], category: str, docs: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": row.get("id") or row.get("case_id"),
        "category": category,
    }
    if "question" in row:
        out["question"] = row["question"]
    if "messages" in row:
        out["messages"] = row["messages"]
    fn = _function_payload(row, docs)
    if fn is not None:
        out["function"] = fn
    return {key: out[key] for key in ALLOWED_OUTPUT_FIELDS if key in out}


def _input_files(dataset_root: Path | None, dataset_files: list[Path], categories: list[str]) -> tuple[list[tuple[Path, str | None]], list[str]]:
    files: list[tuple[Path, str | None]] = []
    blockers: list[str] = []
    if dataset_root is not None:
        if not dataset_root.exists():
            blockers.append("dataset_root_missing")
        else:
            for category in categories:
                matches = sorted(dataset_root.glob(f"**/BFCL_v4_{category}.json"))
                if matches:
                    files.append((matches[0], category))
                else:
                    blockers.append(f"dataset_file_missing:{category}")
    for path in dataset_files:
        if not path.exists():
            blockers.append(f"dataset_file_missing:{path}")
            continue
        files.append((path, _category_from_file(path, categories)))
    if dataset_root is None and not dataset_files:
        blockers.append("dataset_input_missing")
    return files, blockers


def export_dataset(
    *,
    output: Path,
    dataset_root: Path | None = None,
    dataset_files: list[Path] | None = None,
    categories: list[str] | None = None,
) -> dict[str, Any]:
    categories = list(categories or DEFAULT_PRIORITY_CATEGORIES)
    files, blockers = _input_files(dataset_root, list(dataset_files or []), categories)
    sanitized: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    category_counts = {category: 0 for category in categories}
    function_doc_cache: dict[Path, dict[str, dict[str, Any]]] = {}

    for path, fallback_category in files:
        try:
            rows = _read_rows(path)
        except Exception as exc:
            blockers.append(f"dataset_file_unreadable:{path}")
            rejected.append({"path": str(path), "reason": "dataset_file_unreadable", "error": str(exc)})
            continue
        for index, row in enumerate(rows):
            case_id = row.get("id") or row.get("case_id")
            category = _category_from_row(row, fallback_category, categories)
            forbidden = _forbidden_fields(row)
            errors: list[str] = []
            if not isinstance(case_id, str) or not case_id:
                errors.append("id_missing")
            if category not in category_counts:
                errors.append("category_missing_or_not_selected")
            if forbidden:
                errors.append("forbidden_fields_present")
            if errors:
                rejected.append({
                    "path": str(path),
                    "row_index": index,
                    "case_id": case_id if isinstance(case_id, str) else f"<row:{index}>",
                    "errors": sorted(set(errors)),
                    "forbidden_fields": forbidden,
                })
                continue
            if case_id in seen_ids:
                duplicate_ids.add(case_id)
                rejected.append({"path": str(path), "row_index": index, "case_id": case_id, "errors": ["duplicate_id"]})
                continue
            seen_ids.add(case_id)
            if path.parent not in function_doc_cache:
                function_doc_cache[path.parent] = _load_function_docs(path)
            record = _sanitize(row, category, function_doc_cache[path.parent])  # type: ignore[arg-type]
            sanitized.append(record)
            category_counts[category] += 1

    if rejected:
        blockers.append("dataset_export_rejected_records_present")
    if duplicate_ids:
        blockers.append("dataset_export_duplicate_ids_present")
    missing_categories = [category for category, count in category_counts.items() if count == 0]
    if missing_categories:
        blockers.append("dataset_export_category_coverage_missing")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "report_scope": "explicit_literal_bfcl_dataset_export",
        "offline_only": True,
        "does_not_call_provider": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "dataset_root": str(dataset_root) if dataset_root is not None else None,
        "dataset_files": [str(path) for path in dataset_files or []],
        "output": str(output),
        "requested_categories": categories,
        "input_file_count": len(files),
        "exported_record_count": len(sanitized),
        "category_counts": category_counts,
        "missing_categories": missing_categories,
        "rejected_record_count": len(rejected),
        "rejected_records": rejected[:50],
        "duplicate_ids": sorted(duplicate_ids),
        "blockers": sorted(set(blockers)),
        "dataset_export_passed": not blockers,
        "output_fields": list(ALLOWED_OUTPUT_FIELDS),
        "multi_turn_function_doc_dirs": sorted(str(root) for root in function_doc_cache if function_doc_cache[root]),
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Explicit Literal BFCL Dataset Export",
        "",
        f"- Passed: `{report['dataset_export_passed']}`",
        f"- Output: `{report['output']}`",
        f"- Exported records: `{report['exported_record_count']}`",
        f"- Blockers: `{', '.join(report['blockers']) if report['blockers'] else 'none'}`",
        "",
        "| Category | Exported Records |",
        "| --- | ---: |",
    ]
    for category, count in report["category_counts"].items():
        lines.append(f"| `{category}` | `{count}` |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export sanitized BFCL dataset rows for explicit-literal candidate extraction.")
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--dataset-file", type=Path, action="append", default=[])
    parser.add_argument("--categories", default=",".join(DEFAULT_PRIORITY_CATEGORIES))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    report = export_dataset(
        output=args.output,
        dataset_root=args.dataset_root,
        dataset_files=args.dataset_file,
        categories=_parse_categories(args.categories),
    )
    if args.report_output:
        args.report_output.parent.mkdir(parents=True, exist_ok=True)
        args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "dataset_export_passed": report["dataset_export_passed"],
            "exported_record_count": report["exported_record_count"],
            "missing_categories": report["missing_categories"],
            "blockers": report["blockers"],
        }, indent=2, sort_keys=True))
    if args.strict and not report["dataset_export_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
