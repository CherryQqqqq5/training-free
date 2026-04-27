#!/usr/bin/env python3
"""Audit raw BFCL prompt coverage for M2.8-pre explicit literal priors.

This diagnostic compares legacy source_result_tool_args literals against raw BFCL
prompts and function schemas. Source-result tool args are used only as the value
to audit; they are not treated as observable retain-prior evidence.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from grc.compiler.literal_grounding import ground_literal
from scripts.build_m28pre_explicit_required_arg_literal import (
    _arg_schema,
    _function_map,
    _iter_tool_calls,
    _load_dataset_records,
    _load_result_records,
    _normalize_tool_name,
    _required_args,
)

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1")
DEFAULT_SOURCE_MANIFEST = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1/source_collection_manifest.json")
OUT = DEFAULT_ROOT / "raw_bfcl_literal_coverage_audit.json"
MD = DEFAULT_ROOT / "raw_bfcl_literal_coverage_audit.md"

FAILURE_NO_PROMPT_LITERAL = "no_prompt_literal"
FAILURE_SOURCE_RESULT_ONLY = "source_result_only"
FAILURE_AMBIGUOUS = "ambiguous"
FAILURE_SCHEMA_MISMATCH = "schema_mismatch"
FAILURE_SCANNER_MISSED = "scanner_missed"


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_result_diagnostic_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _read_jsonl(root / "candidate_rules.jsonl"):
        if row.get("candidate_rules_type") != "explicit_required_arg_literal_completion":
            continue
        if row.get("literal_source") == "source_result_tool_args" or row.get("literal_source_before_grounding") == "source_result_tool_args":
            rows.append(row)
    return rows


def _walk_prompt(value: Any, request: list[str], observation: list[str]) -> None:
    if isinstance(value, list):
        for item in value:
            _walk_prompt(item, request, observation)
    elif isinstance(value, dict):
        role = str(value.get("role") or "").lower()
        content = value.get("content")
        if isinstance(content, str):
            if role in {"user", "system"}:
                request.append(content)
            elif role in {"tool", "function", "observation"}:
                observation.append(content)
        for key, nested in value.items():
            if key not in {"role", "content"}:
                _walk_prompt(nested, request, observation)
    elif isinstance(value, str):
        request.append(value)


def _prompt_texts(entry: dict[str, Any]) -> tuple[str, str]:
    request: list[str] = []
    observation: list[str] = []
    _walk_prompt(entry.get("question") or [], request, observation)
    return "\n".join(request), "\n".join(observation)


def _scalar(value: Any) -> str | None:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        text = str(value).strip()
        return text if text else None
    return None


def _schema_type(schema: dict[str, Any]) -> str:
    return str(schema.get("type") or "string").lower()


def _schema_type_match(value: Any, schema: dict[str, Any]) -> bool:
    text = _scalar(value)
    if text is None:
        return False
    typ = _schema_type(schema)
    if typ == "integer":
        return re.fullmatch(r"-?\d+", text) is not None
    if typ == "number":
        return re.fullmatch(r"-?\d+(?:\.\d+)?", text) is not None
    if typ == "boolean":
        return text.lower() in {"true", "false", "yes", "no"}
    if typ in {"array", "object"}:
        return False
    return True


def _number_literals(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z0-9_])-?\d+(?:\.\d+)?(?![A-Za-z0-9_])", text)


def _quoted_literals(text: str) -> list[str]:
    return [m.group(1) or m.group(2) for m in re.finditer(r"'([^']+)'|\"([^\"]+)\"", text)]


def _file_like_literals(text: str) -> list[str]:
    return re.findall(r"\b[\w.-]+\.(?:txt|pdf|csv|json|py|java|js|md|log|xml|ya?ml)\b", text, flags=re.IGNORECASE)


def _contains_literal(text: str, literal: str) -> bool:
    if not literal:
        return False
    if re.fullmatch(r"-?\d+(?:\.\d+)?", literal) or not any(ch in literal for ch in ".-/"):
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(literal) + r"(?![A-Za-z0-9_])"
    else:
        pattern = r"(?<![\w.-])" + re.escape(literal) + r"(?![\w.-])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _typed_literals(text: str, schema: dict[str, Any], literal_value: str | None = None) -> list[str]:
    typ = _schema_type(schema)
    if typ in {"integer", "number"}:
        candidates = _number_literals(text)
    elif typ == "boolean":
        raw = re.findall(r"\b(?:true|false|yes|no)\b", text, flags=re.IGNORECASE)
        candidates = ["true" if item.lower() in {"true", "yes"} else "false" for item in raw]
    else:
        candidates = _quoted_literals(text) + _file_like_literals(text)
    if literal_value and _contains_literal(text, literal_value):
        candidates.append(literal_value)
    unique: list[str] = []
    for value in candidates:
        text_value = str(value).strip()
        if text_value and text_value not in unique:
            unique.append(text_value)
    return unique


def _matching_tool_args(result: dict[str, Any] | None, tool: str) -> dict[str, Any]:
    if not result:
        return {}
    target = _normalize_tool_name(tool)
    for emitted_tool, args in _iter_tool_calls(result.get("result")):
        if _normalize_tool_name(emitted_tool) == target:
            return args
    return {}


def _entry_tool_schema(entry: dict[str, Any], tool: str, required_arg: str) -> tuple[list[str], dict[str, Any]]:
    functions = _function_map(entry)
    fn = functions.get(_normalize_tool_name(tool)) or {}
    required = _required_args(fn)
    return required, _arg_schema(fn, required_arg)


def _failure_reason(*, schema_type_match: bool, literal_value: str | None, in_request: bool, in_observation: bool, uniqueness: bool, retain_prior_candidate: bool) -> str | None:
    if not schema_type_match:
        return FAILURE_SCHEMA_MISMATCH
    if retain_prior_candidate:
        return FAILURE_SCANNER_MISSED
    if in_request or in_observation:
        return FAILURE_AMBIGUOUS if not uniqueness else FAILURE_SCANNER_MISSED
    if literal_value:
        return FAILURE_SOURCE_RESULT_ONLY
    return FAILURE_NO_PROMPT_LITERAL


def _audit_row(row: dict[str, Any], entry: dict[str, Any] | None, result: dict[str, Any] | None) -> dict[str, Any]:
    case_id = str(row.get("case_id") or "")
    category = str(row.get("category") or "")
    tool = str(row.get("tool") or "")
    required_arg = str(row.get("required_arg") or row.get("schema_arg_name") or "")
    literal_value = _scalar(row.get("literal_value"))
    entry = entry or {}
    request_text, observation_text = _prompt_texts(entry)
    schema_required_args, arg_schema = _entry_tool_schema(entry, tool, required_arg)
    gold_or_source_tool_args = _matching_tool_args(result, tool)
    if not literal_value and required_arg in gold_or_source_tool_args:
        literal_value = _scalar(gold_or_source_tool_args.get(required_arg))
    grounding = ground_literal(request_text, observation_text, arg_schema, required_arg, tool, literal_value)
    user_literals = _typed_literals(request_text, arg_schema, literal_value)
    observation_literals = _typed_literals(observation_text, arg_schema, literal_value)
    literal_in_request = bool(literal_value and _contains_literal(request_text, literal_value))
    literal_in_observation = bool(literal_value and _contains_literal(observation_text, literal_value))
    schema_match = grounding.schema_type_match
    literal_uniqueness = grounding.literal_uniqueness
    retain_candidate = grounding.retain_prior_candidate
    prior = row.get("retention_prior") if isinstance(row.get("retention_prior"), dict) else {}
    already_compiled = prior.get("retain_eligibility") == "demote_candidate" and retain_candidate
    failure = None if already_compiled else _failure_reason(
        schema_type_match=schema_match,
        literal_value=literal_value,
        in_request=literal_in_request,
        in_observation=literal_in_observation,
        uniqueness=literal_uniqueness,
        retain_prior_candidate=retain_candidate,
    )
    return {
        "case_id": case_id,
        "category": category,
        "tool": tool,
        "required_arg": required_arg,
        "user_prompt_literals": user_literals,
        "tool_observation_literals": observation_literals,
        "schema_required_args": schema_required_args,
        "gold_or_source_tool_args": gold_or_source_tool_args,
        "literal_value": literal_value,
        "literal_in_current_request": literal_in_request,
        "literal_in_current_observation": literal_in_observation,
        "literal_only_in_source_result": bool(literal_value and not literal_in_request and not literal_in_observation),
        "schema_type_match": schema_match,
        "literal_uniqueness": literal_uniqueness,
        "retain_prior_candidate": retain_candidate,
        "selected_literal": grounding.selected_literal,
        "disambiguation_cue": grounding.disambiguation_cue,
        "failure_reason": failure,
        "candidate_origin": row.get("candidate_origin"),
        "literal_source": row.get("literal_source"),
    }


def _ready_source_roots(source_manifest: dict[str, Any]) -> dict[str, list[Path]]:
    roots: dict[str, list[Path]] = {}
    for row in source_manifest.get("category_status") or []:
        if not isinstance(row, dict) or not row.get("source_artifacts_available"):
            continue
        category = str(row.get("category") or "")
        if not category:
            continue
        roots[category] = [Path(str(root)) for root in row.get("existing_source_roots") or []]
    return roots


def evaluate(root: Path = DEFAULT_ROOT, source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST) -> dict[str, Any]:
    source_manifest = _read_json(source_manifest_path, {}) or {}
    ready_roots = _ready_source_roots(source_manifest)
    rows = _source_result_diagnostic_rows(root)
    dataset_cache: dict[str, dict[str, dict[str, Any]]] = {}
    result_cache: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    records: list[dict[str, Any]] = []
    for row in rows:
        category = str(row.get("category") or "")
        case_id = str(row.get("case_id") or "")
        if category not in dataset_cache:
            dataset_cache[category] = _load_dataset_records(category)
        source_root = Path(str(row.get("source_run_root") or ""))
        if not source_root and ready_roots.get(category):
            source_root = ready_roots[category][0]
        key = (str(source_root), category)
        if key not in result_cache:
            result_cache[key] = _load_result_records(source_root, category) if str(source_root) else {}
        records.append(_audit_row(row, dataset_cache[category].get(case_id), result_cache[key].get(case_id)))
    reason_counts = Counter(str(record.get("failure_reason")) for record in records if record.get("failure_reason"))
    prompt_anchored = sum(1 for record in records if record["literal_in_current_request"] or record["literal_in_current_observation"])
    retain_candidates = sum(1 for record in records if record["retain_prior_candidate"])
    scanner_missed_count = reason_counts.get(FAILURE_SCANNER_MISSED, 0)
    route = "pivot_to_next_theory_family=wrong_arg_key_alias_repair" if prompt_anchored == 0 else "fix_current_context_literal_extractor"
    return {
        "report_scope": "m2_8pre_raw_bfcl_literal_coverage_audit",
        "m28pre_raw_bfcl_literal_coverage_audit_ready": True,
        "offline_only": True,
        "no_bfcl_or_model_call": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "source_result_diagnostic_literal_count": len(records),
        "source_result_literals_prompt_anchored_count": prompt_anchored,
        "source_result_literals_retain_prior_candidate_count": retain_candidates,
        "source_result_literals_prompt_coverage_zero": prompt_anchored == 0,
        "scanner_missed_count": scanner_missed_count,
        "failure_reason_counts": dict(sorted(reason_counts.items())),
        "route_recommendation": route,
        "pivot_to_next_theory_family": "wrong_arg_key_alias_repair" if prompt_anchored == 0 else None,
        "candidate_family_to_debug": "explicit_required_arg_literal_completion",
        "ready_categories": sorted(ready_roots),
        "records": records,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.8-pre Raw BFCL Literal Coverage Audit",
        "",
        "Offline diagnostic only. Source-result tool args are audited against raw BFCL prompts; they are not treated as retain-prior evidence.",
        "",
        f"- Audit ready: `{report['m28pre_raw_bfcl_literal_coverage_audit_ready']}`",
        f"- Source-result diagnostic literals: `{report['source_result_diagnostic_literal_count']}`",
        f"- Prompt/observation anchored literals: `{report['source_result_literals_prompt_anchored_count']}`",
        f"- Retain-prior candidates under raw prompt audit: `{report['source_result_literals_retain_prior_candidate_count']}`",
        f"- Route recommendation: `{report['route_recommendation']}`",
        "",
        "| Failure reason | Count |",
        "| --- | ---: |",
    ]
    for reason, count in report["failure_reason_counts"].items():
        lines.append(f"| `{reason}` | `{count}` |")
    lines.extend(["", "No scorer commands are emitted.", ""])
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], output: Path = OUT, markdown_output: Path = MD) -> None:
    _write_json(output, report)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.root, args.source_manifest)
    write_outputs(report, args.output, args.markdown_output)
    if args.compact:
        print(json.dumps({
            "m28pre_raw_bfcl_literal_coverage_audit_ready": report["m28pre_raw_bfcl_literal_coverage_audit_ready"],
            "source_result_diagnostic_literal_count": report["source_result_diagnostic_literal_count"],
            "source_result_literals_prompt_anchored_count": report["source_result_literals_prompt_anchored_count"],
            "source_result_literals_retain_prior_candidate_count": report["source_result_literals_retain_prior_candidate_count"],
            "source_result_literals_prompt_coverage_zero": report["source_result_literals_prompt_coverage_zero"],
            "scanner_missed_count": report["scanner_missed_count"],
            "route_recommendation": report["route_recommendation"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
