#!/usr/bin/env python3
"""Build an explicit-literal candidate pool from offline source artifacts.

This first extractor increment supports a narrow offline fixture path: dataset
JSON plus simple BFCL result JSONL. It emits candidates only when the current
request contains a unique literal for a missing required argument. All other
cases are rejected in the audit. It does not call a provider, BFCL, a model, or
a scorer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_MANIFEST = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1/source_collection_manifest.json")
DEFAULT_SOURCE_ROOT = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
DEFAULT_OUT_ROOT = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1")
DEFAULT_CANDIDATES = DEFAULT_OUT_ROOT / "candidate_rules.jsonl"
DEFAULT_DEV = DEFAULT_OUT_ROOT / "explicit_required_arg_literal_dev20_manifest.json"
DEFAULT_HOLDOUT = DEFAULT_OUT_ROOT / "explicit_required_arg_literal_holdout20_manifest.json"
DEFAULT_AUDIT = DEFAULT_OUT_ROOT / "explicit_literal_extractor_audit.json"
DEFAULT_SUMMARY = DEFAULT_OUT_ROOT / "explicit_literal_candidate_pool_build_summary.json"
DEFAULT_MD = DEFAULT_OUT_ROOT / "explicit_literal_candidate_pool_build_summary.md"
DEFAULT_DATASET_JSON = DEFAULT_OUT_ROOT / "explicit_literal_dataset_fixture.json"


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _parse_categories(raw: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        values = raw.split(",")
    else:
        values = list(raw)
    return [str(item).strip() for item in values if str(item).strip()]


def _manifest(path: Path, *, name: str, selected_case_ids: list[str], candidate_jsonl: Path) -> dict[str, Any]:
    return {
        "manifest_name": name,
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_rules_type": "explicit_required_arg_literal_completion",
        "candidate_jsonl": str(candidate_jsonl),
        "selected_case_count": len(selected_case_ids),
        "selected_case_ids": selected_case_ids,
        "unique_selected_case_count": len(set(selected_case_ids)),
        "duplicate_selected_case_ids": [],
        "planned_commands": [],
        "candidate_commands": [],
        "no_next_tool_intervention": True,
        "exact_tool_choice": False,
    }


def _dataset_records(path: Path) -> dict[str, dict[str, Any]]:
    data = _read_json(path, []) or []
    if isinstance(data, dict):
        rows = data.get("records") or data.get("data") or data.get("rows")
        if rows is None:
            rows = list(data.values())
    else:
        rows = data
    out: dict[str, dict[str, Any]] = {}
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and row.get("id"):
            out[str(row["id"])] = row
    return out


def _source_roots(source: dict[str, Any], source_root: Path, categories: list[str]) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    wanted = set(categories)
    for item in source.get("category_status") or []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "")
        if not category or (wanted and category not in wanted):
            continue
        existing = item.get("existing_source_roots") or []
        if not existing and item.get("source_artifacts_available"):
            existing = [source_root / category / "baseline"]
        for raw in existing:
            roots.append((category, Path(str(raw))))
    return roots


def _result_file(root: Path, category: str) -> Path | None:
    matches = sorted((root / "bfcl" / "result").glob(f"**/BFCL_v4_{category}_result.json")) if (root / "bfcl" / "result").exists() else []
    if not matches:
        matches = sorted(root.glob(f"**/BFCL_v4_{category}_result.json"))
    return matches[0] if matches else None


def _result_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _question_text(entry: dict[str, Any]) -> str:
    chunks: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            content = value.get("content")
            if isinstance(content, str):
                chunks.append(content)
            else:
                for nested in value.values():
                    walk(nested)

    walk(entry.get("question") or entry.get("prompt") or entry.get("messages") or [])
    return "\n".join(chunks)


def _function_map(entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = entry.get("function") or entry.get("functions") or []
    if isinstance(raw, dict):
        raw = [raw]
    return {str(fn["name"]): fn for fn in raw if isinstance(fn, dict) and fn.get("name")}


def _required_args(fn: dict[str, Any]) -> list[str]:
    params = fn.get("parameters") or {}
    required = params.get("required") or []
    return [str(item) for item in required if isinstance(item, str)]


def _parse_call_args(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _tool_calls(value: Any) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, list):
        for item in value:
            calls.extend(_tool_calls(item))
    elif isinstance(value, dict):
        if value.get("name") and ("arguments" in value or "args" in value):
            calls.append((str(value["name"]), _parse_call_args(value.get("arguments", value.get("args")))))
        else:
            for key, raw_args in value.items():
                if isinstance(raw_args, (dict, str)):
                    calls.append((str(key), _parse_call_args(raw_args)))
    return calls


def _literal_spans(text: str) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    for pattern in (r"'([^']+)'", r'"([^"]+)"', r"\b[A-Za-z0-9_.-]+\.(?:txt|csv|json|pdf|md|log)\b"):
        for match in re.finditer(pattern, text):
            literal = next((group for group in match.groups() if group), match.group(0))
            start = text.find(literal, match.start(), match.end())
            spans.append((literal, start, start + len(literal)))
    by_literal: dict[str, tuple[str, int, int]] = {}
    for literal, start, end in spans:
        by_literal.setdefault(literal, (literal, start, end))
    return list(by_literal.values())


def _arg_schema(fn: dict[str, Any], arg: str) -> dict[str, Any]:
    params = fn.get("parameters") or {}
    props = params.get("properties") or {}
    schema = props.get(arg) if isinstance(props, dict) else None
    return schema if isinstance(schema, dict) else {}


def _literal_matches_schema(literal: str, schema: dict[str, Any]) -> bool:
    expected = str(schema.get("type") or "string").lower()
    if expected in {"", "string"}:
        return True
    if expected in {"integer", "number"}:
        try:
            float(literal)
        except ValueError:
            return False
        if expected == "integer" and not re.fullmatch(r"-?\d+", literal):
            return False
        return True
    if expected == "boolean":
        return literal.lower() in {"true", "false"}
    return False


def _extract_candidates(
    *,
    source_root: Path,
    source_manifest: Path,
    dataset_json: Path,
    categories: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int], list[str]]:
    source = _read_json(source_manifest, {}) or {}
    dataset = _dataset_records(dataset_json)
    blockers: list[str] = []
    if not source_manifest.exists():
        blockers.append("source_collection_manifest_missing")
    if not dataset_json.exists():
        blockers.append("dataset_json_missing")
    if not dataset:
        blockers.append("dataset_records_missing")
    candidates: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    reject_counts: dict[str, int] = {}

    def reject(reason: str, **payload: Any) -> None:
        reject_counts[reason] = reject_counts.get(reason, 0) + 1
        rejections.append({"reason": reason, **payload})

    for category, root in _source_roots(source, source_root, categories):
        result_path = _result_file(root, category)
        rows = _result_rows(result_path)
        if result_path is None:
            reject("missing_source_result", category=category, source_run_root=str(root))
            continue
        if not rows:
            reject("result_jsonl_empty", category=category, source_run_root=str(root), result_path=str(result_path))
            continue
        for row in rows:
            case_id = str(row.get("id") or row.get("case_id") or "")
            entry = dataset.get(case_id)
            if not case_id or not entry:
                reject("dataset_record_missing", case_id=case_id, category=category)
                continue
            spans = _literal_spans(_question_text(entry))
            if len(spans) != 1:
                reject("ambiguous_literal", case_id=case_id, category=category, literal_count=len(spans))
                continue
            fns = _function_map(entry)
            emitted = False
            for tool, args in _tool_calls(row.get("result")):
                fn = fns.get(tool)
                if not fn:
                    continue
                missing = [arg for arg in _required_args(fn) if arg not in args]
                if len(missing) != 1:
                    continue
                literal, start, end = spans[0]
                required_arg = missing[0]
                if not _literal_matches_schema(literal, _arg_schema(fn, required_arg)):
                    reject("schema_type_mismatch", case_id=case_id, category=category, required_arg=required_arg, literal=literal)
                    emitted = True
                    break
                span_hash = hashlib.sha256(literal.encode("utf-8")).hexdigest()
                candidates.append({
                    "case_id": case_id,
                    "category": category,
                    "candidate_generatable": True,
                    "candidate_origin": "current_request_explicit_literal_fixture_extractor",
                    "candidate_rules_type": "explicit_required_arg_literal_completion",
                    "rule_type": "explicit_required_arg_literal_completion",
                    "source_run_root": str(root),
                    "tool": tool,
                    "schema_arg_name": required_arg,
                    "required_arg": required_arg,
                    "selected_literal": literal,
                    "literal_source": "current_request",
                    "literal_source_span": {"source": "current_request", "start": start, "end": end, "text": literal},
                    "literal_source_text_hash": span_hash,
                    "used_gold_fields": False,
                    "used_score_fields": False,
                    "used_candidate_output": False,
                    "no_next_tool_intervention": True,
                    "exact_tool_choice": False,
                    "retention_prior": {
                        "rule_family": "explicit_required_arg_literal_completion",
                        "theory_class": "schema_constraint_completion",
                        "retain_eligibility": "demote_candidate",
                        "intervention_scope": "argument_only",
                        "tool_choice_mutation": False,
                        "trajectory_mutation": False,
                    },
                })
                emitted = True
                break
            if not emitted:
                reject("no_single_missing_required_arg", case_id=case_id, category=category)
    return candidates, rejections, reject_counts, blockers


def build(
    *,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    source_manifest: Path = DEFAULT_SOURCE_MANIFEST,
    dataset_json: Path = DEFAULT_DATASET_JSON,
    categories: str | list[str] | tuple[str, ...] | None = None,
    output_root: Path = DEFAULT_OUT_ROOT,
    candidate_jsonl: Path | None = None,
    audit_json: Path | None = None,
    out_candidates: Path | None = None,
    dev_manifest: Path = DEFAULT_DEV,
    holdout_manifest: Path = DEFAULT_HOLDOUT,
    summary_output: Path = DEFAULT_SUMMARY,
    markdown_output: Path = DEFAULT_MD,
    min_pool_size: int = 35,
    min_eligible: int | None = None,
    dev_count: int = 20,
    holdout_count: int = 20,
    dry_run: bool = False,
) -> dict[str, Any]:
    if min_eligible is not None:
        min_pool_size = min_eligible
    if candidate_jsonl is None:
        candidate_jsonl = out_candidates or output_root / "candidate_rules.jsonl"
    if audit_json is None:
        audit_json = candidate_jsonl.parent / "explicit_literal_extractor_audit.json"
    source = _read_json(source_manifest, {}) or {}
    source_present = source_manifest.exists()
    manifest_categories = [
        str(item.get("category"))
        for item in source.get("category_status") or []
        if isinstance(item, dict) and item.get("category")
    ]
    requested_categories = _parse_categories(categories) or manifest_categories
    candidates, rejections, reject_reason_counts, blockers = _extract_candidates(
        source_root=source_root,
        source_manifest=source_manifest,
        dataset_json=dataset_json,
        categories=requested_categories,
    )
    if not requested_categories:
        blockers.append("source_collection_categories_missing")
    if len(candidates) < min_pool_size:
        blockers.append("eligible_explicit_literal_candidates_below_minimum")
    candidate_ids = [row["case_id"] for row in candidates]
    dev_ids = candidate_ids[:dev_count]
    holdout_ids = candidate_ids[dev_count : dev_count + holdout_count]
    if len(dev_ids) < dev_count:
        blockers.append("dev_count_not_met")
    if len(holdout_ids) < holdout_count:
        blockers.append("holdout_count_not_met")

    audit = {
        "report_scope": "explicit_literal_extractor_audit",
        "offline_only": True,
        "extractor_skeleton_only": False,
        "source_root": str(source_root),
        "source_manifest": str(source_manifest),
        "dataset_json": str(dataset_json),
        "source_manifest_present": source_present,
        "requested_categories": requested_categories,
        "source_manifest_categories": manifest_categories,
        "candidate_jsonl": str(candidate_jsonl),
        "accepted_record_count": len(candidates),
        "rejected_record_count": len(rejections),
        "reject_reason_counts": reject_reason_counts,
        "rejections": rejections,
        "planned_commands": [],
        "candidate_commands": [],
        "blockers": list(dict.fromkeys(blockers)),
    }

    if not dry_run:
        _write_jsonl(candidate_jsonl, candidates)
        _write_json(dev_manifest, _manifest(dev_manifest, name="explicit_required_arg_literal_dev20", selected_case_ids=dev_ids, candidate_jsonl=candidate_jsonl))
        _write_json(holdout_manifest, _manifest(holdout_manifest, name="explicit_required_arg_literal_holdout20", selected_case_ids=holdout_ids, candidate_jsonl=candidate_jsonl))
        _write_json(audit_json, audit)

    report = {
        "report_scope": "explicit_literal_candidate_pool_build",
        "offline_only": True,
        "does_not_call_provider": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "extractor_skeleton_only": False,
        "dry_run": dry_run,
        "source_root": str(source_root),
        "source_manifest": str(source_manifest),
        "dataset_json": str(dataset_json),
        "source_manifest_present": source_present,
        "source_manifest_categories": manifest_categories,
        "requested_categories": requested_categories,
        "output_root": str(output_root),
        "candidate_jsonl": str(candidate_jsonl),
        "out_candidates": str(candidate_jsonl),
        "audit_json": str(audit_json),
        "dev_manifest": str(dev_manifest),
        "holdout_manifest": str(holdout_manifest),
        "candidate_record_count": len(candidates),
        "eligible_count": len(candidates),
        "min_pool_size": min_pool_size,
        "min_eligible": min_pool_size,
        "dev_required_count": dev_count,
        "holdout_required_count": holdout_count,
        "dev_selected_case_count": len(dev_ids),
        "holdout_selected_case_count": len(holdout_ids),
        "accepted_record_count": len(candidates),
        "rejected_record_count": len(rejections),
        "reject_reason_counts": reject_reason_counts,
        "candidate_jsonl_written": not dry_run,
        "audit_json_written": not dry_run,
        "manifests_written": not dry_run,
        "candidate_pool_build_passed": not blockers,
        "blockers": list(dict.fromkeys(blockers)),
        "next_required_action": "run_candidate_pool_gate" if not blockers else "repair_offline_extractor_inputs_or_expand_source_pool",
    }
    _write_json(summary_output, report)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Explicit Literal Candidate Pool Build",
        "",
        f"- Passed: `{report['candidate_pool_build_passed']}`",
        f"- Skeleton only: `{report['extractor_skeleton_only']}`",
        f"- Candidate records: `{report['candidate_record_count']}`",
        f"- Eligible count: `{report['eligible_count']}` / `{report['min_eligible']}`",
        f"- Dev selected: `{report['dev_selected_case_count']}` / `{report['dev_required_count']}`",
        f"- Holdout selected: `{report['holdout_selected_case_count']}` / `{report['holdout_required_count']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "Offline-only skeleton. This command does not call a provider, BFCL, a model, or a scorer.",
        "",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the explicit-literal candidate pool from offline source artifacts.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--dataset-json", type=Path, default=DEFAULT_DATASET_JSON)
    parser.add_argument("--categories", default=None, help="Comma-separated BFCL categories to scan.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--candidate-jsonl", type=Path, default=None)
    parser.add_argument("--audit-json", type=Path, default=None)
    parser.add_argument("--out-candidates", type=Path, default=None, help="Backward-compatible alias for --candidate-jsonl.")
    parser.add_argument("--dev-manifest", type=Path, default=DEFAULT_DEV)
    parser.add_argument("--holdout-manifest", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--min-pool-size", type=int, default=35)
    parser.add_argument("--min-eligible", type=int, default=None, help="Backward-compatible alias for --min-pool-size.")
    parser.add_argument("--dev-count", type=int, default=20)
    parser.add_argument("--holdout-count", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = build(
        source_root=args.source_root,
        source_manifest=args.source_manifest,
        dataset_json=args.dataset_json,
        categories=args.categories,
        output_root=args.output_root,
        candidate_jsonl=args.candidate_jsonl,
        audit_json=args.audit_json,
        out_candidates=args.out_candidates,
        dev_manifest=args.dev_manifest,
        holdout_manifest=args.holdout_manifest,
        summary_output=args.summary_output,
        markdown_output=args.markdown_output,
        min_pool_size=args.min_pool_size,
        min_eligible=args.min_eligible,
        dev_count=args.dev_count,
        holdout_count=args.holdout_count,
        dry_run=args.dry_run,
    )
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "candidate_pool_build_passed",
            "extractor_skeleton_only",
            "candidate_record_count",
            "eligible_count",
            "blockers",
            "next_required_action",
        ]}, indent=2, sort_keys=True))
    if args.strict and not report["candidate_pool_build_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
