#!/usr/bin/env python3
"""Build M2.8-pre explicit-required-arg-literal offline candidates.

This low-risk compiler is theory-prior first. It can still report legacy
CTSPC/file-path candidates for diagnostics, but scorer authorization is driven
only by explicit required-argument literal completions whose literal is anchored
in the current request/observation and whose retention prior is demote-eligible.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from grc.compiler.literal_grounding import ground_literal
from grc.compiler.retention_priors import (
    DEMOTE_CANDIDATE,
    BFCL_FAILURE_REASONS,
    deterministic_schema_local_non_live_prior,
    explicit_required_arg_literal_prior,
    summarize_retention_priors,
    wrong_arg_key_alias_prior,
)

DEFAULT_LOW_RISK = Path("outputs/artifacts/bfcl_ctspc_low_risk_slices_v1/low_risk_slice_manifest.json")
DEFAULT_STATUS = Path("outputs/artifacts/bfcl_ctspc_subset30_v1/m27ae_ctspc_v0_status.json")
DEFAULT_SOURCE_MANIFEST = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1/source_collection_manifest.json")
DEFAULT_OUT_ROOT = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1")

TRAJECTORY_SENSITIVE_TOOLS = {"cat", "touch", "mkdir", "cp", "mv", "cd"}
STRATIFIED_SLICES = ["explicit_required_arg_literal", "wrong_arg_key_alias_repair", "deterministic_schema_local_non_live_repair"]
PRIOR_AWARE_EXCLUDED_CATEGORIES = {"memory", "memory_kv", "memory_rec_sum", "memory_vector"}


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


def _result_path(source_root: Path, category: str) -> Path | None:
    matches = sorted((source_root / "bfcl" / "result").glob(f"**/BFCL_v4_{category}_result.json"))
    return matches[0] if matches else None


def _load_result_record_stats(source_root: Path, category: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    path = _result_path(source_root, category)
    stats: dict[str, Any] = {
        "source_root": str(source_root),
        "category": category,
        "result_file_path": str(path) if path else None,
        "result_file_exists": bool(path),
        "raw_line_count": 0,
        "parsed_line_count": 0,
        "parse_error_count": 0,
        "missing_case_id_count": 0,
        "result_record_count": 0,
        "result_layout_unrecognized": False,
    }
    if not path:
        return {}, stats
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        stats["raw_line_count"] += 1
        try:
            item = json.loads(line)
        except Exception:
            stats["parse_error_count"] += 1
            continue
        case_id = str(item.get("id") or item.get("case_id") or "")
        if case_id:
            records[case_id] = item
            stats["parsed_line_count"] += 1
        else:
            stats["missing_case_id_count"] += 1
    stats["result_record_count"] = len(records)
    stats["result_layout_unrecognized"] = bool(stats["raw_line_count"] and not records)
    return records, stats


def _load_result_records(source_root: Path, category: str) -> dict[str, dict[str, Any]]:
    records, _stats = _load_result_record_stats(source_root, category)
    return records


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _iter_tool_calls(value: Any) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, list):
        for item in value:
            calls.extend(_iter_tool_calls(item))
    elif isinstance(value, dict):
        for tool, raw_args in value.items():
            calls.append((str(tool), _parse_args(raw_args)))
    return calls


def _normalize_tool_name(name: Any) -> str:
    return str(name or "").replace(".", "_").strip()


def _question_text(entry: dict[str, Any]) -> str:
    texts: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            role = str(value.get("role") or "")
            content = value.get("content")
            if role in {"user", "system"} and isinstance(content, str):
                texts.append(content)
            elif not role:
                walk(list(value.values()))
        elif isinstance(value, str):
            texts.append(value)

    walk(entry.get("question") or [])
    return "\n".join(texts)


def _load_dataset_records(category: str) -> dict[str, dict[str, Any]]:
    try:
        from bfcl_eval.utils import load_dataset_entry
    except Exception:
        return {}
    try:
        rows = load_dataset_entry(category, include_prereq=False)
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and row.get("id"):
            out[str(row["id"])] = row
    return out


def _function_map(entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    funcs = entry.get("function") or []
    if isinstance(funcs, dict):
        funcs = [funcs]
    out: dict[str, dict[str, Any]] = {}
    for fn in funcs if isinstance(funcs, list) else []:
        if isinstance(fn, dict) and fn.get("name"):
            out[_normalize_tool_name(fn.get("name"))] = fn
    return out


def _required_args(fn: dict[str, Any]) -> list[str]:
    params = fn.get("parameters") or {}
    required = params.get("required") or []
    return [str(arg) for arg in required if isinstance(arg, str)]


def _arg_schema(fn: dict[str, Any], arg: str) -> dict[str, Any]:
    params = fn.get("parameters") or {}
    props = params.get("properties") or {}
    schema = props.get(arg) if isinstance(props, dict) else None
    return schema if isinstance(schema, dict) else {}


def _scalar(value: Any) -> str | None:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value).strip()
    return None


def _number_literals(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z0-9_])-?\d+(?:\.\d+)?(?![A-Za-z0-9_])", text)


def _quoted_literals(text: str) -> list[str]:
    return [m.group(1) or m.group(2) for m in re.finditer(r"'([^']+)'|\"([^\"]+)\"", text)]


def _literal_candidates_for_arg(text: str, schema: dict[str, Any], emitted_args: dict[str, Any], required_arg: str = "") -> list[str]:
    emitted = {_scalar(value) for value in emitted_args.values()}
    emitted.discard(None)
    grounding = ground_literal(text, "", schema, required_arg, "", None, exclude_values={str(value) for value in emitted if value is not None})
    return [grounding.selected_literal] if grounding.selected_literal else grounding.candidate_literals



ALIAS_GROUPS: dict[str, set[str]] = {
    "file_name": {"filename", "file", "file_path", "filepath", "path_name"},
    "filename": {"file_name", "file", "file_path", "filepath", "path_name"},
    "path": {"file_path", "filepath", "path_name", "dir", "directory", "folder"},
    "dir_name": {"dir", "directory", "folder", "dirname", "folder_name"},
    "directory": {"dir", "dir_name", "folder", "folder_name"},
    "source": {"src", "from", "source_file", "source_path", "input", "input_file"},
    "destination": {"dest", "dst", "to", "target", "target_file", "target_path", "output", "output_file"},
    "pattern": {"query", "term", "search_term", "search_pattern", "regex"},
    "query": {"pattern", "term", "search_term", "search_pattern"},
    "content": {"text", "message", "body", "value"},
    "message": {"text", "content", "body"},
}


def _normalize_arg_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _canonical_alias_candidates(arg_key: str, canonical_keys: list[str]) -> list[tuple[str, str]]:
    norm_key = _normalize_arg_key(arg_key)
    candidates: list[tuple[str, str]] = []
    for canonical in canonical_keys:
        if arg_key == canonical:
            continue
        norm_canonical = _normalize_arg_key(canonical)
        aliases = ALIAS_GROUPS.get(canonical, set()) | {canonical}
        normalized_aliases = {_normalize_arg_key(alias) for alias in aliases}
        if norm_key == norm_canonical or norm_key in normalized_aliases:
            evidence = "normalized_key_match" if norm_key == norm_canonical else "deterministic_alias_group"
            candidates.append((canonical, evidence))
    # A few safe suffix/prefix aliases are common in BFCL tool args.
    if not candidates:
        for canonical in canonical_keys:
            norm_canonical = _normalize_arg_key(canonical)
            if norm_key.endswith(norm_canonical) or norm_canonical.endswith(norm_key):
                if len(norm_key) >= 4 and len(norm_canonical) >= 4:
                    candidates.append((canonical, "deterministic_schema_local_substring"))
    deduped: list[tuple[str, str]] = []
    for item in candidates:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _alias_rejection(base: dict[str, Any], reason: str, **extra: Any) -> dict[str, Any]:
    row = {**base, **extra, "candidate_generatable": False, "rejection_reason": reason}
    row.setdefault("rule_type", "wrong_arg_key_alias_repair")
    row.setdefault("candidate_rules_type", "wrong_arg_key_alias_repair")
    row.setdefault("no_next_tool_intervention", True)
    row.setdefault("exact_tool_choice", False)
    row.setdefault("guidance_only", True)
    row.setdefault("ctspc_v0_action_rule", False)
    row.setdefault("tool_choice_mutation", False)
    row.setdefault("trajectory_mutation", False)
    row.setdefault("value_mutation", False)
    row["retention_prior"] = wrong_arg_key_alias_prior(row)
    return row


def _prior_rejection(base: dict[str, Any], reason: str, **extra: Any) -> dict[str, Any]:
    row = {**base, **extra, "candidate_generatable": False, "rejection_reason": reason}
    row.setdefault("rule_type", "explicit_required_arg_literal_completion")
    row.setdefault("candidate_rules_type", "explicit_required_arg_literal_completion")
    row.setdefault("no_next_tool_intervention", True)
    row.setdefault("exact_tool_choice", False)
    row.setdefault("guidance_only", True)
    row.setdefault("ctspc_v0_action_rule", False)
    row["retention_prior"] = explicit_required_arg_literal_prior(row)
    return row



def _compile_wrong_arg_key_alias_records(entry: dict[str, Any], result: dict[str, Any] | None, source_root: Path, category: str) -> list[dict[str, Any]]:
    case_id = str(entry.get("id") or "")
    base = {
        "case_id": case_id,
        "category": category,
        "source_run_root": str(source_root),
        "slice_name": "wrong_arg_key_alias_repair",
        "low_risk_slices": ["wrong_arg_key_alias_repair"],
        "candidate_origin": "theory_prior_wrong_arg_key_alias",
        "ctspc_legacy_file_path_candidate": False,
        "theory_prior_explicit_literal_candidate": False,
        "theory_prior_wrong_arg_key_alias_candidate": True,
    }
    if not case_id:
        return []
    if category in PRIOR_AWARE_EXCLUDED_CATEGORIES:
        return [_alias_rejection(base, "memory_or_hidden_state_category_excluded")]
    if not result:
        return [_alias_rejection(base, "missing_source_result")]
    calls = _iter_tool_calls(result.get("result"))
    if not calls:
        return [_alias_rejection(base, "missing_emitted_tool_call")]
    calls_by_tool: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for tool, args in calls:
        calls_by_tool[_normalize_tool_name(tool)].append((tool, args))
    functions = _function_map(entry)
    rows: list[dict[str, Any]] = []
    saw_matching_tool = False
    for norm_tool, fn in functions.items():
        if norm_tool not in calls_by_tool:
            continue
        saw_matching_tool = True
        if len(calls_by_tool[norm_tool]) != 1:
            rows.append(_alias_rejection(base, "parallel_call_mapping_not_unique", tool=norm_tool))
            continue
        emitted_tool, emitted_args = calls_by_tool[norm_tool][0]
        props = (fn.get("parameters") or {}).get("properties") or {}
        canonical_keys = [str(key) for key in props.keys()] if isinstance(props, dict) else []
        if not canonical_keys:
            rows.append(_alias_rejection(base, "missing_schema_properties", tool=norm_tool))
            continue
        emitted_any_alias = False
        for original_key, value in emitted_args.items():
            original_key = str(original_key)
            if original_key in canonical_keys:
                continue
            scalar_value = _scalar(value)
            common = {
                **base,
                "tool": norm_tool,
                "emitted_tool_name": emitted_tool,
                "original_arg_key": original_key,
                "arg_value": scalar_value,
                "value_source": "model_emitted_args",
                "source_value_key": original_key,
                "no_next_tool_intervention": True,
                "exact_tool_choice": False,
                "guidance_only": True,
                "ctspc_v0_action_rule": False,
                "tool_choice_mutation": False,
                "trajectory_mutation": False,
                "value_mutation": False,
                "rule_type": "wrong_arg_key_alias_repair",
                "candidate_rules_type": "wrong_arg_key_alias_repair",
            }
            if scalar_value is None or str(scalar_value).strip() == "" or len(str(scalar_value)) > 240:
                rows.append(_alias_rejection(common, "missing_or_non_scalar_arg_value"))
                emitted_any_alias = True
                continue
            candidates = _canonical_alias_candidates(original_key, canonical_keys)
            if len(candidates) != 1:
                rows.append(_alias_rejection(common, "ambiguous_alias" if candidates else "no_schema_alias_match", alias_candidates=[c[0] for c in candidates], alias_ambiguous=len(candidates) != 1))
                emitted_any_alias = True
                continue
            canonical_key, evidence = candidates[0]
            if canonical_key in emitted_args:
                rows.append(_alias_rejection(common, "canonical_key_already_present", canonical_arg_key=canonical_key, alias_evidence=evidence))
                emitted_any_alias = True
                continue
            row = {
                **common,
                "canonical_arg_key": canonical_key,
                "schema_arg_name": canonical_key,
                "alias_evidence": evidence,
                "alias_ambiguous": False,
                "candidate_generatable": True,
                "rejection_reason": None,
                "confidence": 0.78,
            }
            row["retention_prior"] = wrong_arg_key_alias_prior(row)
            rows.append(row)
            emitted_any_alias = True
        if not emitted_any_alias:
            rows.append(_alias_rejection({**base, "tool": norm_tool}, "no_wrong_arg_key_alias_detected"))
    if rows:
        return rows
    if not saw_matching_tool:
        return [_alias_rejection(base, "no_matching_emitted_tool")]
    return [_alias_rejection(base, "no_wrong_arg_key_alias_detected")]


def _load_wrong_arg_key_alias_candidates(source_manifest_path: Path, existing_case_ids: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    manifest = _read_json(source_manifest_path, {}) or {}
    rows = manifest.get("category_status") or []
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    scanned_categories: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        if not row.get("source_artifacts_available"):
            continue
        category = str(row.get("category") or "")
        roots = [Path(str(root)) for root in row.get("existing_source_roots") or []]
        if not category or not roots:
            continue
        entries = _load_dataset_records(category)
        if not entries:
            continue
        scanned_categories.append(category)
        for root in roots:
            results = _load_result_records(root, category)
            for case_id, entry in entries.items():
                if case_id in existing_case_ids:
                    continue
                compiled_rows = _compile_wrong_arg_key_alias_records(entry, results.get(case_id), root, category)
                for compiled in compiled_rows:
                    if compiled.get("candidate_generatable"):
                        candidates.append(compiled)
                        existing_case_ids.add(case_id)
                    else:
                        rejected.append(compiled)
    diagnostic = {
        "wrong_arg_key_alias_scan_enabled": True,
        "wrong_arg_key_alias_scanned_categories": sorted(set(scanned_categories)),
        "wrong_arg_key_alias_candidate_count": len(candidates),
        "wrong_arg_key_alias_rejected_count": len(rejected),
        "wrong_arg_key_alias_rejection_distribution": dict(Counter(str(row.get("rejection_reason")) for row in rejected)),
    }
    return candidates, rejected, diagnostic



def _json_safe_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _json_safe_value(v) for k, v in value.items()}
    return str(value)


def _schema_type_for_repair(schema: dict[str, Any]) -> str:
    typ = schema.get("type")
    if isinstance(typ, list):
        for item in typ:
            if item != "null":
                return str(item).lower()
        return "string"
    return str(typ or "string").lower()


def _normalize_enum_value(value: Any, schema: dict[str, Any]) -> tuple[Any | None, str | None, str | None]:
    enum = schema.get("enum")
    if not isinstance(enum, list) or not enum or not isinstance(value, str):
        return None, None, None
    norm = re.sub(r"[^a-z0-9]", "", value.lower())
    matches = [candidate for candidate in enum if re.sub(r"[^a-z0-9]", "", str(candidate).lower()) == norm]
    if len(matches) == 1 and matches[0] != value:
        return matches[0], "enum_canonicalization", None
    if len(matches) > 1:
        return None, None, "ambiguous_enum_canonicalization"
    return None, None, None


def _normalize_scalar_for_schema(value: Any, schema: dict[str, Any]) -> tuple[Any | None, str | None, str | None]:
    enum_value, enum_kind, enum_error = _normalize_enum_value(value, schema)
    if enum_kind or enum_error:
        return enum_value, enum_kind, enum_error
    typ = _schema_type_for_repair(schema)
    if typ == "boolean" and isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"true", "yes"}:
            return True, "boolean_string_normalization", None
        if raw in {"false", "no"}:
            return False, "boolean_string_normalization", None
    if typ == "integer" and isinstance(value, str):
        raw = value.strip()
        if re.fullmatch(r"-?\d+", raw):
            return int(raw), "numeric_string_to_integer", None
    if typ == "number" and isinstance(value, str):
        raw = value.strip()
        if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
            return (float(raw) if "." in raw else int(raw)), "numeric_string_to_number", None
    if typ in {"array", "object"} and isinstance(value, str):
        raw = value.strip()
        if raw and raw[0] in "[{":
            try:
                parsed = json.loads(raw)
            except Exception:
                return None, None, "json_string_parse_failed"
            if typ == "array" and isinstance(parsed, list):
                return parsed, "json_string_to_array", None
            if typ == "object" and isinstance(parsed, dict):
                return parsed, "json_string_to_object", None
            return None, None, "json_string_schema_mismatch"
    if typ == "array" and not isinstance(value, list):
        item_schema = schema.get("items") if isinstance(schema.get("items"), dict) else {}
        if item_schema:
            normalized_item, item_kind, item_error = _normalize_scalar_for_schema(value, item_schema)
            if item_kind and item_error is None:
                return [normalized_item], "scalar_to_singleton_array", None
            if item_error:
                return None, None, item_error
        if isinstance(value, (str, int, float, bool)):
            return [value], "scalar_to_singleton_array", None
    return None, None, None


def _deterministic_rejection(base: dict[str, Any], reason: str, **extra: Any) -> dict[str, Any]:
    row = {**base, **extra, "candidate_generatable": False, "rejection_reason": reason}
    row.setdefault("rule_type", "deterministic_schema_local_non_live_repair")
    row.setdefault("candidate_rules_type", "deterministic_schema_local_non_live_repair")
    row.setdefault("no_next_tool_intervention", True)
    row.setdefault("exact_tool_choice", False)
    row.setdefault("guidance_only", True)
    row.setdefault("ctspc_v0_action_rule", False)
    row.setdefault("tool_choice_mutation", False)
    row.setdefault("trajectory_mutation", False)
    row.setdefault("value_creation", False)
    row.setdefault("gold_value_mutation", False)
    row.setdefault("schema_local_deterministic", False)
    row.setdefault("tool_call_mapping_unique", True)
    row["retention_prior"] = deterministic_schema_local_non_live_prior(row)
    return row


def _compile_deterministic_schema_local_records(entry: dict[str, Any], result: dict[str, Any] | None, source_root: Path, category: str) -> list[dict[str, Any]]:
    case_id = str(entry.get("id") or "")
    base = {
        "case_id": case_id,
        "category": category,
        "source_run_root": str(source_root),
        "slice_name": "deterministic_schema_local_non_live_repair",
        "low_risk_slices": ["deterministic_schema_local_non_live_repair"],
        "candidate_origin": "theory_prior_deterministic_schema_local_non_live",
        "ctspc_legacy_file_path_candidate": False,
        "theory_prior_explicit_literal_candidate": False,
        "theory_prior_wrong_arg_key_alias_candidate": False,
        "theory_prior_deterministic_schema_local_candidate": True,
    }
    if not case_id:
        return []
    if category in PRIOR_AWARE_EXCLUDED_CATEGORIES:
        return [_deterministic_rejection(base, "memory_or_hidden_state_category_excluded", hidden_state_category=True)]
    if not result:
        return [_deterministic_rejection(base, "missing_source_result")]
    calls = _iter_tool_calls(result.get("result"))
    if not calls:
        return [_deterministic_rejection(base, "missing_emitted_tool_call")]
    calls_by_tool: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for tool, args in calls:
        calls_by_tool[_normalize_tool_name(tool)].append((tool, args))
    functions = _function_map(entry)
    rows: list[dict[str, Any]] = []
    saw_matching_tool = False
    for norm_tool, fn in functions.items():
        if norm_tool not in calls_by_tool:
            continue
        saw_matching_tool = True
        props = (fn.get("parameters") or {}).get("properties") or {}
        if not isinstance(props, dict) or not props:
            rows.append(_deterministic_rejection(base, "missing_schema_properties", tool=norm_tool))
            continue
        if len(calls_by_tool[norm_tool]) != 1:
            rows.append(_deterministic_rejection(base, "parallel_call_mapping_not_unique", tool=norm_tool, tool_call_mapping_unique=False))
            continue
        emitted_tool, emitted_args = calls_by_tool[norm_tool][0]
        emitted_any_repair = False
        for arg_key, value in emitted_args.items():
            arg_key = str(arg_key)
            schema = props.get(arg_key)
            common = {
                **base,
                "tool": norm_tool,
                "emitted_tool_name": emitted_tool,
                "arg_key": arg_key,
                "schema_arg_name": arg_key,
                "original_value": _json_safe_value(value),
                "schema_type": _schema_type_for_repair(schema if isinstance(schema, dict) else {}),
                "tool_call_mapping_unique": True,
                "no_next_tool_intervention": True,
                "exact_tool_choice": False,
                "guidance_only": True,
                "ctspc_v0_action_rule": False,
                "tool_choice_mutation": False,
                "trajectory_mutation": False,
                "value_creation": False,
                "gold_value_mutation": False,
                "rule_type": "deterministic_schema_local_non_live_repair",
                "candidate_rules_type": "deterministic_schema_local_non_live_repair",
            }
            if not isinstance(schema, dict):
                rows.append(_deterministic_rejection(common, "arg_key_not_in_schema_properties"))
                emitted_any_repair = True
                continue
            normalized, repair_kind, error = _normalize_scalar_for_schema(value, schema)
            if error:
                rows.append(_deterministic_rejection(common, error))
                emitted_any_repair = True
                continue
            if repair_kind is None:
                continue
            if normalized == value:
                rows.append(_deterministic_rejection(common, "already_schema_local_canonical", normalized_value=_json_safe_value(normalized), repair_kind=repair_kind))
                emitted_any_repair = True
                continue
            row = {
                **common,
                "normalized_value": _json_safe_value(normalized),
                "repair_kind": repair_kind,
                "schema_local_deterministic": True,
                "retain_prior_candidate": True,
                "candidate_generatable": True,
                "rejection_reason": None,
                "confidence": 0.8,
            }
            row["retention_prior"] = deterministic_schema_local_non_live_prior(row)
            rows.append(row)
            emitted_any_repair = True
        if not emitted_any_repair:
            rows.append(_deterministic_rejection({**base, "tool": norm_tool}, "no_deterministic_schema_local_repair_detected"))
    if rows:
        return rows
    if not saw_matching_tool:
        return [_deterministic_rejection(base, "no_matching_emitted_tool")]
    return [_deterministic_rejection(base, "no_deterministic_schema_local_repair_detected")]


def _load_deterministic_schema_local_candidates(source_manifest_path: Path, existing_case_ids: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    manifest = _read_json(source_manifest_path, {}) or {}
    rows = manifest.get("category_status") or []
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    scanned_categories: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        if not row.get("source_artifacts_available"):
            continue
        category = str(row.get("category") or "")
        roots = [Path(str(root)) for root in row.get("existing_source_roots") or []]
        if not category or not roots:
            continue
        entries = _load_dataset_records(category)
        if not entries:
            continue
        scanned_categories.append(category)
        for root in roots:
            results = _load_result_records(root, category)
            for case_id, entry in entries.items():
                if case_id in existing_case_ids:
                    continue
                compiled_rows = _compile_deterministic_schema_local_records(entry, results.get(case_id), root, category)
                accepted_for_case = False
                for compiled in compiled_rows:
                    if compiled.get("candidate_generatable") and not accepted_for_case:
                        candidates.append(compiled)
                        existing_case_ids.add(case_id)
                        accepted_for_case = True
                    else:
                        rejected.append(compiled)
    diagnostic = {
        "deterministic_schema_local_scan_enabled": True,
        "deterministic_schema_local_scanned_categories": sorted(set(scanned_categories)),
        "deterministic_schema_local_candidate_count": len(candidates),
        "deterministic_schema_local_rejected_count": len(rejected),
        "deterministic_schema_local_rejection_distribution": dict(Counter(str(row.get("rejection_reason")) for row in rejected)),
    }
    return candidates, rejected, diagnostic

def _compile_prior_aware_record(entry: dict[str, Any], result: dict[str, Any] | None, source_root: Path, category: str) -> dict[str, Any] | None:
    case_id = str(entry.get("id") or "")
    base = {
        "case_id": case_id,
        "category": category,
        "source_run_root": str(source_root),
        "slice_name": "explicit_required_arg_literal",
        "low_risk_slices": ["explicit_required_arg_literal"],
        "candidate_origin": "theory_prior_explicit_literal",
        "ctspc_legacy_file_path_candidate": False,
        "theory_prior_explicit_literal_candidate": True,
    }
    if not case_id:
        return None
    if category in PRIOR_AWARE_EXCLUDED_CATEGORIES:
        return _prior_rejection(base, "memory_or_hidden_state_category_excluded")
    if not result:
        return _prior_rejection(base, "missing_source_result")
    text = _question_text(entry)
    if not text.strip():
        return _prior_rejection(base, "missing_current_request_or_observation")
    calls = _iter_tool_calls(result.get("result"))
    if not calls:
        return _prior_rejection(base, "missing_emitted_tool_call")
    calls_by_tool: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for tool, args in calls:
        calls_by_tool[_normalize_tool_name(tool)].append((tool, args))
    functions = _function_map(entry)
    for norm_tool, fn in functions.items():
        required = _required_args(fn)
        if not required or norm_tool not in calls_by_tool:
            continue
        if len(calls_by_tool[norm_tool]) != 1:
            return _prior_rejection(base, "parallel_call_mapping_not_unique", tool=norm_tool, required_args=required)
        emitted_tool, emitted_args = calls_by_tool[norm_tool][0]
        missing = [arg for arg in required if arg not in emitted_args]
        if not missing:
            continue
        if len(missing) != 1:
            return _prior_rejection(base, "multiple_missing_required_args", tool=norm_tool, required_args=required, missing_required_args=missing, emitted_tool_args=emitted_args)
        required_arg = missing[0]
        candidates = _literal_candidates_for_arg(text, _arg_schema(fn, required_arg), emitted_args, required_arg)
        common = {
            **base,
            "tool": norm_tool,
            "emitted_tool_name": emitted_tool,
            "required_arg": required_arg,
            "schema_arg_name": required_arg,
            "required_args": required,
            "missing_required_args": missing,
            "emitted_tool_args": emitted_args,
            "literal_candidate_count": len(candidates),
            "literal_source_rank": 1 if len(candidates) == 1 else None,
            "literal_type_match": len(candidates) == 1,
            "no_next_tool_intervention": True,
            "exact_tool_choice": False,
            "guidance_only": True,
            "ctspc_v0_action_rule": False,
            "rule_type": "explicit_required_arg_literal_completion",
            "candidate_rules_type": "explicit_required_arg_literal_completion",
        }
        if len(candidates) != 1:
            return _prior_rejection(common, "ambiguous_or_missing_observable_literal", literal_candidates=candidates)
        row = {
            **common,
            "literal_value": candidates[0],
            "unique_literal_value": candidates[0],
            "literal_source": "current_request",
            "literal_source_observed_as": "current_request",
            "literal_source_anchor": "current_request",
            "confidence": 0.75,
            "candidate_generatable": True,
            "rejection_reason": None,
            "trajectory_sensitive_tool": False,
        }
        row["retention_prior"] = explicit_required_arg_literal_prior(row)
        return row
    return _prior_rejection(base, "required_args_already_present_or_no_matching_emitted_tool")



def _classify_source_result_case(entry: dict[str, Any], result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        return {"availability_reason": "source_result_case_not_collected", "tool": None, "required_arg": None}
    calls = _iter_tool_calls(result.get("result"))
    if not calls:
        return {"availability_reason": "baseline_no_tool_call", "tool": None, "required_arg": None}
    calls_by_tool: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for tool, args in calls:
        calls_by_tool[_normalize_tool_name(tool)].append((tool, args))
    functions = _function_map(entry)
    any_required = False
    matched_tool = False
    complete_tool_count = 0
    for norm_tool, fn in functions.items():
        required = _required_args(fn)
        if not required:
            continue
        any_required = True
        if norm_tool not in calls_by_tool:
            continue
        matched_tool = True
        if len(calls_by_tool[norm_tool]) != 1:
            return {"availability_reason": "parallel_call_mapping_not_unique", "tool": norm_tool, "required_arg": None}
        _emitted_tool, emitted_args = calls_by_tool[norm_tool][0]
        missing = [arg for arg in required if arg not in emitted_args]
        if not missing:
            complete_tool_count += 1
            continue
        if len(missing) == 1:
            return {"availability_reason": "missing_required_arg_candidate", "tool": norm_tool, "required_arg": missing[0]}
        return {"availability_reason": "multiple_missing_required_args", "tool": norm_tool, "required_arg": ",".join(missing)}
    if not any_required:
        return {"availability_reason": "no_required_args_in_schema", "tool": None, "required_arg": None}
    if matched_tool and complete_tool_count:
        return {"availability_reason": "emitted_args_complete", "tool": None, "required_arg": None}
    return {"availability_reason": "no_matching_emitted_tool", "tool": None, "required_arg": None}


def _source_result_availability_audit(source_manifest_path: Path) -> dict[str, Any]:
    manifest = _read_json(source_manifest_path, {}) or {}
    category_rows = manifest.get("category_status") or []
    category_reports: list[dict[str, Any]] = []
    total_issue_counts: Counter[str] = Counter()
    hard_issue_counts: Counter[str] = Counter()
    for row in category_rows if isinstance(category_rows, list) else []:
        category = str(row.get("category") or "")
        roots = [Path(str(root)) for root in row.get("existing_source_roots") or []]
        entries = _load_dataset_records(category) if category else {}
        category_report: dict[str, Any] = {
            "category": category,
            "source_artifacts_available": bool(row.get("source_artifacts_available")),
            "source_roots": [str(root) for root in roots],
            "dataset_case_count": len(entries),
            "root_reports": [],
            "issue_counts": {},
        }
        if not category_report["source_artifacts_available"] or not roots:
            count = len(entries) or int(row.get("selected_case_count") or 0) or 1
            category_report["issue_counts"] = {"category_source_artifacts_missing": count}
            total_issue_counts["category_source_artifacts_missing"] += count
            hard_issue_counts["category_source_artifacts_missing"] += count
            category_reports.append(category_report)
            continue
        for root in roots:
            records, stats = _load_result_record_stats(root, category)
            issue_counts: Counter[str] = Counter()
            if not stats["result_file_exists"]:
                issue_counts["result_file_missing"] += len(entries) or 1
                hard_issue_counts["result_file_missing"] += len(entries) or 1
            elif stats["result_layout_unrecognized"]:
                issue_counts["result_layout_unrecognized"] += len(entries) or 1
                hard_issue_counts["result_layout_unrecognized"] += len(entries) or 1
            else:
                collected_ids = [case_id for case_id in records if case_id in entries]
                for case_id in collected_ids:
                    classified = _classify_source_result_case(entries[case_id], records.get(case_id))
                    issue_counts[str(classified["availability_reason"])] += 1
                uncollected_count = max(len(entries) - len(collected_ids), 0)
                if uncollected_count:
                    issue_counts["source_result_case_not_collected"] += uncollected_count
            total_issue_counts.update(issue_counts)
            collected_ids_count = len([case_id for case_id in records if case_id in entries]) if records else 0
            category_report["root_reports"].append({**stats, "source_result_case_count_scanned": collected_ids_count, "issue_counts": dict(sorted(issue_counts.items()))})
        combined: Counter[str] = Counter()
        for root_report in category_report["root_reports"]:
            combined.update(root_report.get("issue_counts") or {})
        category_report["issue_counts"] = dict(sorted(combined.items()))
        category_reports.append(category_report)
    ready = not hard_issue_counts
    return {
        "report_scope": "m28pre_source_result_availability_audit",
        "offline_only": True,
        "candidate_commands": [],
        "planned_commands": [],
        "source_result_availability_audit_ready": True,
        "source_result_availability_ready": ready,
        "hard_issue_counts": dict(sorted(hard_issue_counts.items())),
        "issue_counts": dict(sorted(total_issue_counts.items())),
        "category_reports": category_reports,
    }


def _prior_scan_category_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    categories: dict[str, dict[str, Any]] = {}
    for row in rows:
        category = str(row.get("category") or "unknown")
        item = categories.setdefault(category, {
            "accepted_count": 0,
            "rejected_count": 0,
            "rejection_reason_counts": Counter(),
            "accepted_by_tool_required_arg": Counter(),
            "rejected_by_tool_required_arg": Counter(),
        })
        key = f"{row.get('tool') or 'unknown'}::{row.get('required_arg') or 'unknown'}"
        if row.get("candidate_generatable") and row.get("retention_prior", {}).get("retain_eligibility") == DEMOTE_CANDIDATE:
            item["accepted_count"] += 1
            item["accepted_by_tool_required_arg"][key] += 1
        else:
            item["rejected_count"] += 1
            item["rejection_reason_counts"][str(row.get("rejection_reason") or "not_demote_candidate")] += 1
            item["rejected_by_tool_required_arg"][key] += 1
    normalized: dict[str, Any] = {}
    for category, item in sorted(categories.items()):
        normalized[category] = {
            "accepted_count": item["accepted_count"],
            "rejected_count": item["rejected_count"],
            "rejection_reason_counts": dict(sorted(item["rejection_reason_counts"].items())),
            "accepted_by_tool_required_arg": dict(sorted(item["accepted_by_tool_required_arg"].items())),
            "rejected_by_tool_required_arg": dict(sorted(item["rejected_by_tool_required_arg"].items())),
        }
    return normalized


def _load_prior_aware_candidates(source_manifest_path: Path, existing_case_ids: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    manifest = _read_json(source_manifest_path, {}) or {}
    rows = manifest.get("category_status") or []
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    scanned_categories: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        if not row.get("source_artifacts_available"):
            continue
        category = str(row.get("category") or "")
        roots = [Path(str(root)) for root in row.get("existing_source_roots") or []]
        if not category or not roots:
            continue
        entries = _load_dataset_records(category)
        if not entries:
            continue
        scanned_categories.append(category)
        for root in roots:
            results = _load_result_records(root, category)
            for case_id, entry in entries.items():
                if case_id in existing_case_ids:
                    continue
                compiled = _compile_prior_aware_record(entry, results.get(case_id), root, category)
                if not compiled:
                    continue
                if compiled.get("candidate_generatable"):
                    candidates.append(compiled)
                    existing_case_ids.add(case_id)
                else:
                    rejected.append(compiled)
    diagnostic = {
        "prior_aware_scan_enabled": True,
        "prior_aware_scanned_categories": sorted(set(scanned_categories)),
        "prior_aware_candidate_count": len(candidates),
        "prior_aware_rejected_count": len(rejected),
        "prior_aware_rejection_distribution": dict(Counter(str(row.get("rejection_reason")) for row in rejected)),
    }
    return candidates, rejected, diagnostic


def _pick_arg(_tool: str, args: dict[str, Any]) -> tuple[str | None, Any | None]:
    for name, value in args.items():
        if isinstance(value, (str, int, float, bool)):
            return str(name), value
    return None, None


def _compile_legacy_record(record: dict[str, Any], result: dict[str, Any] | None, slice_name: str, entry: dict[str, Any] | None = None) -> dict[str, Any]:
    case_id = str(record.get("case_id") or "")
    target_tools = [str(t) for t in (record.get("target_action_tools_present") or [])]
    base = {
        "case_id": case_id,
        "category": record.get("category"),
        "slice_name": slice_name,
        "low_risk_slices": sorted(set(str(s) for s in (record.get("low_risk_slices") or [slice_name]))),
        "source_run_root": record.get("source_run_root"),
        "candidate_origin": "ctspc_legacy_file_path",
        "ctspc_legacy_file_path_candidate": True,
        "theory_prior_explicit_literal_candidate": False,
    }
    if not result:
        return {**base, "candidate_generatable": False, "rejection_reason": "missing_source_result"}
    for tool, args in _iter_tool_calls(result.get("result")):
        if target_tools and tool not in target_tools:
            continue
        arg_name, value = _pick_arg(tool, args)
        if arg_name is None or value is None:
            continue
        literal = str(value)
        common = {
            **base,
            "tool": tool,
            "required_arg": arg_name,
            "literal_value": literal,
            "literal_source": "source_result_tool_args",
            "schema_arg_name": arg_name,
            "rule_type": "explicit_required_arg_literal_completion",
            "candidate_rules_type": "explicit_required_arg_literal_completion",
            "no_next_tool_intervention": True,
            "exact_tool_choice": False,
            "guidance_only": True,
            "ctspc_v0_action_rule": False,
            "literal_candidate_count": 0,
            "literal_source_rank": None,
            "literal_type_match": False,
        }
        if literal.strip() == "" or len(literal) > 240:
            return {**common, "candidate_generatable": False, "rejection_reason": "ambiguous_literal"}
        if entry:
            functions = _function_map(entry)
            fn = functions.get(_normalize_tool_name(tool)) or {}
            schema = _arg_schema(fn, arg_name)
            grounding = ground_literal(_question_text(entry), "", schema, arg_name, tool, literal)
            grounded_common = {
                **common,
                "literal_candidate_count": len(grounding.candidate_literals),
                "literal_candidates": grounding.candidate_literals,
                "selected_literal": grounding.selected_literal,
                "disambiguation_cue": grounding.disambiguation_cue,
                "grounding_rejection_reason": grounding.why_rejected,
                "literal_type_match": grounding.schema_type_match,
                "literal_source_before_grounding": "source_result_tool_args",
            }
            if grounding.retain_prior_candidate and grounding.selected_literal:
                row = {
                    **grounded_common,
                    "candidate_origin": "theory_prior_explicit_literal_from_source_result_context",
                    "ctspc_legacy_file_path_candidate": True,
                    "theory_prior_explicit_literal_candidate": True,
                    "literal_value": grounding.selected_literal,
                    "unique_literal_value": grounding.selected_literal,
                    "literal_source": grounding.literal_source,
                    "literal_source_observed_as": grounding.literal_source,
                    "literal_source_anchor": grounding.source_span,
                    "literal_source_rank": 1,
                    "confidence": 0.72,
                    "candidate_generatable": True,
                    "rejection_reason": None,
                    "trajectory_sensitive_tool": False,
                }
                row["retention_prior"] = explicit_required_arg_literal_prior(row)
                return row
            common = grounded_common
        return {**common, "confidence": 0.6, "candidate_generatable": True, "rejection_reason": None, "trajectory_sensitive_tool": tool in TRAJECTORY_SENSITIVE_TOOLS}
    return {**base, "candidate_generatable": False, "rejection_reason": "no_matching_scalar_required_arg"}


def _source_cache_loader() -> Any:
    cache: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}

    def load(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
        source_root = Path(str(record.get("source_run_root") or ""))
        category = str(record.get("category") or "")
        key = (str(source_root), category)
        if key not in cache:
            cache[key] = _load_result_records(source_root, category)
        return cache[key]

    return load


def _dataset_cache_loader() -> Any:
    cache: dict[str, dict[str, dict[str, Any]]] = {}

    def load(record: dict[str, Any]) -> dict[str, Any] | None:
        category = str(record.get("category") or "")
        if not category:
            return None
        if category not in cache:
            cache[category] = _load_dataset_records(category)
        return cache[category].get(str(record.get("case_id") or ""))

    return load


def _compile_legacy_records(records: list[dict[str, Any]], slice_name: str, load_result: Any, load_entry: Any | None = None) -> list[dict[str, Any]]:
    compiled: list[dict[str, Any]] = []
    for record in records:
        results = load_result(record)
        entry = load_entry(record) if load_entry else None
        item = _compile_legacy_record(record, results.get(str(record.get("case_id") or "")), slice_name, entry)
        item["retention_prior"] = explicit_required_arg_literal_prior(item)
        compiled.append(item)
    return compiled


def _manifest(
    name: str,
    rows: list[dict[str, Any]],
    *,
    ready: bool,
    slice_name: str | None = None,
    candidate_rules_type: str = "explicit_required_arg_literal_completion",
    selection_criteria: str | None = None,
) -> dict[str, Any]:
    return {
        "manifest_name": name,
        "selected_case_count": len(rows),
        "selected_case_ids": [str(row.get("case_id")) for row in rows],
        "selection_criteria": selection_criteria or "theory-prior explicit required-arg literal completion; no CTSPC-v0 next-tool intervention",
        "slice_name": slice_name,
        "planned_commands": [],
        "candidate_commands": [],
        "ctspc_v0_frozen": True,
        "repair_stack_default": "disabled",
        "candidate_rules_type": candidate_rules_type,
        "authorized_theory_prior_families": sorted({str(row.get("candidate_rules_type") or row.get("rule_type") or candidate_rules_type) for row in rows}),
        "no_next_tool_intervention": True,
        "exact_tool_choice": False,
        "ready": ready,
        "cases": rows,
    }


def _unique_records_by_case(slice_cases: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for slice_name in STRATIFIED_SLICES:
        for row in slice_cases.get(slice_name) or []:
            case_id = str(row.get("case_id") or "")
            if not case_id:
                continue
            item = dict(row)
            labels = set(str(s) for s in item.get("low_risk_slices") or [])
            labels.add(slice_name)
            if case_id in merged:
                labels.update(str(s) for s in merged[case_id].get("low_risk_slices") or [])
            item["low_risk_slices"] = sorted(labels)
            merged[case_id] = item
    return list(merged.values())


def build(low_risk_path: Path = DEFAULT_LOW_RISK, status_path: Path = DEFAULT_STATUS, dev_size: int = 20, holdout_size: int = 20, source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST) -> dict[str, Any]:
    low = _read_json(low_risk_path, {}) or {}
    status = _read_json(status_path, {}) or {}
    slice_cases = low.get("slice_cases") or {}
    load_result = _source_cache_loader()
    load_entry = _dataset_cache_loader()

    legacy_explicit_records = list(slice_cases.get("explicit_required_arg_literal") or [])
    legacy_explicit_compiled = _compile_legacy_records(legacy_explicit_records, "explicit_required_arg_literal", load_result, load_entry)
    existing_case_ids = {str(row.get("case_id") or "") for row in legacy_explicit_records if row.get("case_id")}
    if source_manifest_path == DEFAULT_SOURCE_MANIFEST and low_risk_path != DEFAULT_LOW_RISK:
        prior_candidates, prior_rejected, prior_diag = [], [], {
            "prior_aware_scan_enabled": False,
            "prior_aware_skip_reason": "non_default_low_risk_manifest_without_explicit_source_manifest",
            "prior_aware_candidate_count": 0,
            "prior_aware_rejected_count": 0,
            "prior_aware_rejection_distribution": {},
        }
        alias_candidates, alias_rejected, alias_diag = [], [], {
            "wrong_arg_key_alias_scan_enabled": False,
            "wrong_arg_key_alias_skip_reason": "non_default_low_risk_manifest_without_explicit_source_manifest",
            "wrong_arg_key_alias_candidate_count": 0,
            "wrong_arg_key_alias_rejected_count": 0,
            "wrong_arg_key_alias_rejection_distribution": {},
        }
        deterministic_candidates, deterministic_rejected, deterministic_diag = [], [], {
            "deterministic_schema_local_scan_enabled": False,
            "deterministic_schema_local_skip_reason": "non_default_low_risk_manifest_without_explicit_source_manifest",
            "deterministic_schema_local_candidate_count": 0,
            "deterministic_schema_local_rejected_count": 0,
            "deterministic_schema_local_rejection_distribution": {},
        }
    else:
        prior_candidates, prior_rejected, prior_diag = _load_prior_aware_candidates(source_manifest_path, existing_case_ids)
        alias_candidates, alias_rejected, alias_diag = _load_wrong_arg_key_alias_candidates(source_manifest_path, set(existing_case_ids))
        deterministic_candidates, deterministic_rejected, deterministic_diag = _load_deterministic_schema_local_candidates(source_manifest_path, set(existing_case_ids))

    source_result_availability_audit = _source_result_availability_audit(source_manifest_path)
    prior_scan_category_coverage = _prior_scan_category_coverage(prior_candidates + prior_rejected)
    alias_scan_category_coverage = _prior_scan_category_coverage(alias_candidates + alias_rejected)
    deterministic_scan_category_coverage = _prior_scan_category_coverage(deterministic_candidates + deterministic_rejected)

    explicit_compiled = legacy_explicit_compiled + prior_candidates + prior_rejected
    alias_compiled = alias_candidates + alias_rejected
    deterministic_compiled = deterministic_candidates + deterministic_rejected
    compiler_category_coverage = _prior_scan_category_coverage(explicit_compiled + alias_compiled + deterministic_compiled)
    explicit_generatable = [item for item in explicit_compiled if item.get("candidate_generatable")]
    alias_generatable = [item for item in alias_compiled if item.get("candidate_generatable")]
    deterministic_generatable = [item for item in deterministic_compiled if item.get("candidate_generatable")]
    theory_prior_generatable = [item for item in explicit_generatable if item.get("theory_prior_explicit_literal_candidate")]
    explicit_ambiguous = sum(1 for item in explicit_compiled if item.get("rejection_reason") in {"ambiguous_literal", "ambiguous_or_missing_observable_literal"})
    alias_ambiguous_count = sum(1 for item in alias_compiled if item.get("rejection_reason") == "ambiguous_alias")
    alias_value_mutation_count = sum(1 for item in alias_compiled if item.get("value_mutation") is True)
    deterministic_ambiguous_count = sum(1 for item in deterministic_compiled if item.get("rejection_reason") in {"ambiguous_enum_canonicalization", "ambiguous_or_non_deterministic_schema_repair"})
    deterministic_value_creation_count = sum(1 for item in deterministic_compiled if item.get("value_creation") is True or item.get("gold_value_mutation") is True)

    stratified_records = _unique_records_by_case(slice_cases)
    stratified_compiled = _compile_legacy_records(stratified_records, "stratified_low_risk", load_result, load_entry)
    stratified_generatable = [item for item in stratified_compiled if item.get("candidate_generatable")]
    stratified_ambiguous = sum(1 for item in stratified_compiled if item.get("rejection_reason") == "ambiguous_literal")
    stratified_counts: dict[str, int] = defaultdict(int)
    for item in stratified_generatable:
        for slice_name in item.get("low_risk_slices") or []:
            if slice_name in STRATIFIED_SLICES:
                stratified_counts[slice_name] += 1

    explicit_prior_distribution = summarize_retention_priors(explicit_generatable)
    stratified_prior_distribution = summarize_retention_priors(stratified_generatable)
    retain_eligible = [row for row in explicit_generatable if row.get("retention_prior", {}).get("retain_eligibility") == DEMOTE_CANDIDATE]
    alias_retain_eligible = [row for row in alias_generatable if row.get("retention_prior", {}).get("retain_eligibility") == DEMOTE_CANDIDATE]
    deterministic_retain_eligible = [row for row in deterministic_generatable if row.get("retention_prior", {}).get("retain_eligibility") == DEMOTE_CANDIDATE]
    combined_retain_eligible = retain_eligible + deterministic_retain_eligible
    stratified_retain_eligible = [row for row in stratified_generatable if row.get("retention_prior", {}).get("retain_eligibility") == DEMOTE_CANDIDATE]
    disambiguation_records = [
        {
            "case_id": row.get("case_id"),
            "category": row.get("category"),
            "tool": row.get("tool"),
            "required_arg": row.get("required_arg"),
            "candidate_literals": row.get("literal_candidates") or [],
            "selected_literal": row.get("selected_literal"),
            "disambiguation_cue": row.get("disambiguation_cue"),
            "why_rejected": row.get("grounding_rejection_reason") or row.get("rejection_reason"),
            "retain_prior_candidate": row.get("retention_prior", {}).get("retain_eligibility") == DEMOTE_CANDIDATE,
        }
        for row in explicit_generatable
        if row.get("literal_source_before_grounding") == "source_result_tool_args"
    ]
    disambiguated_current_context_count = sum(1 for row in disambiguation_records if row["retain_prior_candidate"])
    source_result_only_diagnostic_count = sum(1 for row in explicit_generatable if row.get("literal_source") == "source_result_tool_args")

    ctspc_off = bool(status.get("ctspc_v0_frozen") and status.get("scorer_default") == "off" and status.get("retain") == 0 and status.get("dev_rerun_authorized") is False and status.get("holdout_authorized") is False)
    required_total = dev_size + holdout_size
    explicit_compiler_ready = len(explicit_generatable) >= dev_size and explicit_ambiguous == 0 and ctspc_off
    alias_compiler_ready = len(alias_retain_eligible) >= dev_size and alias_ambiguous_count == 0 and alias_value_mutation_count == 0 and ctspc_off
    deterministic_compiler_ready = len(deterministic_retain_eligible) >= dev_size and deterministic_ambiguous_count == 0 and deterministic_value_creation_count == 0 and ctspc_off
    combined_compiler_ready = len(combined_retain_eligible) >= dev_size and explicit_ambiguous == 0 and deterministic_ambiguous_count == 0 and deterministic_value_creation_count == 0 and ctspc_off
    stratified_compiler_ready = len(stratified_generatable) >= dev_size and stratified_ambiguous == 0 and ctspc_off
    compiler_ready = explicit_compiler_ready or combined_compiler_ready or stratified_compiler_ready
    explicit_holdout_ready = len(retain_eligible) >= required_total and explicit_ambiguous == 0
    alias_holdout_ready = len(alias_retain_eligible) >= required_total and alias_ambiguous_count == 0 and alias_value_mutation_count == 0
    deterministic_holdout_ready = len(deterministic_retain_eligible) >= required_total and deterministic_ambiguous_count == 0 and deterministic_value_creation_count == 0
    combined_holdout_ready = len(combined_retain_eligible) >= required_total and explicit_ambiguous == 0 and deterministic_ambiguous_count == 0 and deterministic_value_creation_count == 0
    stratified_holdout_ready = False
    explicit_dev = retain_eligible[:dev_size]
    explicit_holdout = retain_eligible[dev_size : dev_size + holdout_size]
    alias_dev = alias_retain_eligible[:dev_size]
    alias_holdout = alias_retain_eligible[dev_size : dev_size + holdout_size]
    deterministic_dev = deterministic_retain_eligible[:dev_size]
    deterministic_holdout = deterministic_retain_eligible[dev_size : dev_size + holdout_size]
    combined_dev = combined_retain_eligible[:dev_size]
    combined_holdout = combined_retain_eligible[dev_size : dev_size + holdout_size]
    stratified_dev = stratified_retain_eligible[:dev_size]
    stratified_holdout = stratified_retain_eligible[dev_size : dev_size + holdout_size]
    scorer_ready = compiler_ready and combined_holdout_ready
    if combined_holdout_ready:
        route_recommendation = "theory_prior_low_risk_pool_ready_for_scorer_request"
    elif deterministic_retain_eligible:
        route_recommendation = "deterministic_schema_local_non_live_repair_coverage_insufficient"
    else:
        route_recommendation = "define_next_theory_family_after_deterministic_schema_local_non_live_repair"

    blockers = []
    if len(explicit_generatable) < required_total:
        blockers.append("explicit_total_below_40")
    if len(retain_eligible) < 35:
        blockers.append("explicit_demote_candidate_below_35")
    if len(alias_retain_eligible) < 20:
        blockers.append("wrong_arg_key_alias_demote_below_20")
    if len(deterministic_retain_eligible) < 20:
        blockers.append("deterministic_schema_local_demote_below_20")
    if len(combined_retain_eligible) < 35:
        blockers.append("combined_demote_candidate_below_35")
    if explicit_ambiguous:
        blockers.append("explicit_ambiguous_literal_present")
    if alias_ambiguous_count:
        blockers.append("wrong_arg_key_alias_ambiguous_present")
    if alias_value_mutation_count:
        blockers.append("wrong_arg_key_alias_value_mutation_present")
    if deterministic_ambiguous_count:
        blockers.append("deterministic_schema_local_ambiguous_present")
    if deterministic_value_creation_count:
        blockers.append("deterministic_schema_local_value_creation_present")
    if not explicit_holdout_ready:
        blockers.append("explicit_holdout_below_20")
    if not combined_holdout_ready:
        blockers.append("combined_theory_prior_holdout_below_20")
    if stratified_generatable and not stratified_holdout_ready:
        blockers.append("stratified_without_complete_theory_priors_not_authorized")
    if not ctspc_off:
        blockers.append("ctspc_v0_not_frozen")


    return {
        "report_scope": "m2_8pre_explicit_required_arg_literal_compiler",
        "offline_only": True,
        "source_pool_expansion_required": not scorer_ready,
        "explicit_source_pool_expansion_required": not explicit_holdout_ready,
        "stratified_source_pool_expansion_required": True,
        "required_explicit_total": required_total,
        "required_explicit_candidate_generatable": 35,
        "required_stratified_total": required_total,
        "required_stratified_candidate_generatable": 35,
        "no_bfcl_or_model_call": True,
        "planned_commands": [],
        "candidate_commands": [],
        "ctspc_v0_file_path_multi_turn_enabled": False,
        "ctspc_v0_action_rules_enabled": False,
        "ctspc_v0_frozen": ctspc_off,
        "repair_stack_default": "disabled",
        "candidate_rules_type": "theory_prior_low_risk_combined",
        "authorized_theory_prior_families": ["explicit_required_arg_literal_completion", "deterministic_schema_local_non_live_repair"],
        "no_next_tool_intervention": True,
        "exact_tool_choice": False,
        "retention_prior_required": True,
        "retention_prior_rule_family": "explicit_required_arg_literal_completion",
        "retention_prior_rule_families": ["explicit_required_arg_literal_completion", "deterministic_schema_local_non_live_repair", "wrong_arg_key_alias_repair"],
        "bfcl_score_cannot_create_retain_rule": True,
        "stratified_pool_diagnostic_only_until_family_priors_exist": True,
        "ctspc_legacy_file_path_candidate_count": len([row for row in explicit_generatable if row.get("ctspc_legacy_file_path_candidate")]),
        "theory_prior_explicit_literal_candidate_count": len(theory_prior_generatable),
        "prior_aware_scan": prior_diag,
        "source_result_availability_audit": source_result_availability_audit,
        "source_result_availability_ready": source_result_availability_audit.get("source_result_availability_ready"),
        "prior_scan_category_coverage": prior_scan_category_coverage,
        "alias_prior_scan": alias_diag,
        "alias_scan_category_coverage": alias_scan_category_coverage,
        "deterministic_schema_local_prior_scan": deterministic_diag,
        "deterministic_schema_local_scan_category_coverage": deterministic_scan_category_coverage,
        "compiler_category_coverage": compiler_category_coverage,
        "explicit_remaining_gap_to_35_demote_candidates": max(0, 35 - len(retain_eligible)),
        "remaining_gap_to_35_demote_candidates": max(0, 35 - len(combined_retain_eligible)),
        "route_recommendation": route_recommendation,
        "retention_prior_distribution": explicit_prior_distribution,
        "wrong_arg_key_alias_retention_prior_distribution": summarize_retention_priors(alias_generatable),
        "deterministic_schema_local_retention_prior_distribution": summarize_retention_priors(deterministic_generatable),
        "combined_retention_prior_distribution": summarize_retention_priors(explicit_generatable + deterministic_generatable),
        "stratified_retention_prior_distribution": stratified_prior_distribution,
        "retain_eligible_candidate_count": len(retain_eligible),
        "wrong_arg_key_alias_candidate_count": len(alias_generatable),
        "wrong_arg_key_alias_demote_candidate_count": len(alias_retain_eligible),
        "wrong_arg_key_alias_ambiguous_count": alias_ambiguous_count,
        "wrong_arg_key_alias_value_mutation_count": alias_value_mutation_count,
        "deterministic_schema_local_candidate_count": len(deterministic_generatable),
        "deterministic_schema_local_demote_candidate_count": len(deterministic_retain_eligible),
        "deterministic_schema_local_ambiguous_count": deterministic_ambiguous_count,
        "deterministic_schema_local_value_creation_count": deterministic_value_creation_count,
        "combined_retain_eligible_candidate_count": len(combined_retain_eligible),
        "stratified_retain_eligible_candidate_count": len(stratified_retain_eligible),
        "scanner_missed_count": 0,
        "disambiguated_current_context_candidate_count": disambiguated_current_context_count,
        "source_result_only_diagnostic_count": source_result_only_diagnostic_count,
        "literal_disambiguation_records": disambiguation_records,
        "selected_case_count": len(explicit_generatable),
        "candidate_generatable_count": len(explicit_generatable),
        "ambiguous_literal_count": explicit_ambiguous,
        "candidate_rules": explicit_generatable,
        "wrong_arg_key_alias_candidate_rules": alias_generatable,
        "deterministic_schema_local_candidate_rules": deterministic_generatable,
        "combined_candidate_rules": explicit_generatable + deterministic_generatable,
        "rejected_candidates": [item for item in explicit_compiled if not item.get("candidate_generatable")],
        "wrong_arg_key_alias_rejected_candidates": [item for item in alias_compiled if not item.get("candidate_generatable")],
        "deterministic_schema_local_rejected_candidates": [item for item in deterministic_compiled if not item.get("candidate_generatable")],
        "dev_manifest": _manifest("explicit_required_arg_literal_dev20", explicit_dev, ready=len(explicit_dev) >= dev_size, slice_name="explicit_required_arg_literal"),
        "holdout_manifest": _manifest("explicit_required_arg_literal_holdout20", explicit_holdout, ready=explicit_holdout_ready, slice_name="explicit_required_arg_literal"),
        "wrong_arg_key_alias_dev_manifest": _manifest("wrong_arg_key_alias_dev20", alias_dev, ready=len(alias_dev) >= dev_size, slice_name="wrong_arg_key_alias_repair", candidate_rules_type="wrong_arg_key_alias_repair", selection_criteria="theory-prior schema-local wrong-arg-key alias repair; value/tool/trajectory unchanged"),
        "wrong_arg_key_alias_holdout_manifest": _manifest("wrong_arg_key_alias_holdout20", alias_holdout, ready=alias_holdout_ready, slice_name="wrong_arg_key_alias_repair", candidate_rules_type="wrong_arg_key_alias_repair", selection_criteria="theory-prior schema-local wrong-arg-key alias repair; value/tool/trajectory unchanged"),
        "deterministic_schema_local_dev_manifest": _manifest("deterministic_schema_local_dev20", deterministic_dev, ready=len(deterministic_dev) >= dev_size, slice_name="deterministic_schema_local_non_live_repair", candidate_rules_type="deterministic_schema_local_non_live_repair", selection_criteria="theory-prior deterministic schema-local non-live repair; value is normalized from emitted args only"),
        "deterministic_schema_local_holdout_manifest": _manifest("deterministic_schema_local_holdout20", deterministic_holdout, ready=deterministic_holdout_ready, slice_name="deterministic_schema_local_non_live_repair", candidate_rules_type="deterministic_schema_local_non_live_repair", selection_criteria="theory-prior deterministic schema-local non-live repair; value is normalized from emitted args only"),
        "combined_dev_manifest": _manifest("theory_prior_low_risk_dev20", combined_dev, ready=len(combined_dev) >= dev_size, slice_name="theory_prior_low_risk_combined", candidate_rules_type="theory_prior_low_risk_combined", selection_criteria="combined theory-prior pool: explicit required-arg literal completion plus deterministic schema-local non-live repair"),
        "combined_holdout_manifest": _manifest("theory_prior_low_risk_holdout20", combined_holdout, ready=combined_holdout_ready, slice_name="theory_prior_low_risk_combined", candidate_rules_type="theory_prior_low_risk_combined", selection_criteria="combined theory-prior pool: explicit required-arg literal completion plus deterministic schema-local non-live repair"),
        "stratified_candidate_rules": stratified_generatable,
        "stratified_counts": dict(sorted(stratified_counts.items())),
        "stratified_selected_case_count": len(stratified_generatable),
        "stratified_candidate_generatable_count": len(stratified_generatable),
        "stratified_ambiguous_literal_count": stratified_ambiguous,
        "stratified_dev_manifest": _manifest("stratified_low_risk_dev20", stratified_dev, ready=False, slice_name="stratified_low_risk"),
        "stratified_holdout_manifest": _manifest("stratified_low_risk_holdout20", stratified_holdout, ready=False, slice_name="stratified_low_risk"),
        "compiler_ready": compiler_ready,
        "explicit_compiler_ready": explicit_compiler_ready,
        "wrong_arg_key_alias_compiler_ready": alias_compiler_ready,
        "deterministic_schema_local_compiler_ready": deterministic_compiler_ready,
        "combined_compiler_ready": combined_compiler_ready,
        "stratified_compiler_ready": stratified_compiler_ready,
        "explicit_holdout_ready": explicit_holdout_ready,
        "wrong_arg_key_alias_holdout_ready": alias_holdout_ready,
        "deterministic_schema_local_holdout_ready": deterministic_holdout_ready,
        "combined_theory_prior_holdout_ready": combined_holdout_ready,
        "stratified_holdout_ready": stratified_holdout_ready,
        "scorer_authorization_ready": scorer_ready,
        "m28pre_explicit_required_arg_literal_compiler_passed": compiler_ready,
        "m28pre_explicit_required_arg_literal_holdout_ready": explicit_holdout_ready,
        "m28pre_low_risk_slice_ready": scorer_ready,
        "blockers": blockers,
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# M2.8-pre Explicit Required Arg Literal Compiler",
        "",
        f"- Compiler ready: `{report['compiler_ready']}`",
        f"- Explicit holdout ready: `{report['explicit_holdout_ready']}`",
        f"- Stratified holdout ready: `{report['stratified_holdout_ready']}`",
        f"- Scorer authorization ready: `{report['scorer_authorization_ready']}`",
        f"- Explicit selected/generatable: `{report['selected_case_count']}` / `{report['candidate_generatable_count']}`",
        f"- Retain-eligible explicit candidates: `{report['retain_eligible_candidate_count']}`",
        f"- Retain-eligible wrong-key alias candidates: `{report['wrong_arg_key_alias_demote_candidate_count']}`",
        f"- Retain-eligible deterministic schema-local candidates: `{report['deterministic_schema_local_demote_candidate_count']}`",
        f"- Combined retain-eligible candidates: `{report['combined_retain_eligible_candidate_count']}`",
        f"- Theory-prior explicit candidates: `{report['theory_prior_explicit_literal_candidate_count']}`",
        f"- Remaining combined gap to 35 demote candidates: `{report['remaining_gap_to_35_demote_candidates']}`",
        f"- Source/result availability ready: `{report['source_result_availability_ready']}`",
        f"- Route recommendation: `{report['route_recommendation']}`",
        f"- Stratified selected/generatable: `{report['stratified_selected_case_count']}` / `{report['stratified_candidate_generatable_count']}`",
        f"- Source pool expansion required: `{report['source_pool_expansion_required']}`",
        f"- Blockers: `{report['blockers']}`",
        "",
        "No BFCL scorer commands are emitted.",
        "",
    ])


def _render_manifest(manifest: dict[str, Any]) -> str:
    return "\n".join([f"# {manifest['manifest_name']}", "", f"- Ready: `{manifest['ready']}`", f"- Slice: `{manifest['slice_name']}`", f"- Selected cases: `{manifest['selected_case_count']}`", "- Planned commands: `[]`", ""])


def _mismatch_schema() -> dict[str, Any]:
    return {
        "report_scope": "m2_8pre_retain_prior_mismatch_schema",
        "offline_schema_only": True,
        "bfcl_score_cannot_create_retain_rule": True,
        "failure_reasons": sorted(BFCL_FAILURE_REASONS),
        "required_join_keys": ["case_id", "rule_id", "candidate_id", "retention_prior.rule_family", "selected_tool", "required_arg"],
        "future_scorer_fields": ["retain_prior_match", "bfcl_failure_reason", "literal_candidate_count", "unique_literal_value", "literal_source_rank", "literal_type_match", "emitted_tool_args", "scorer_emitted_args", "dev_fixed_or_regressed"],
        "candidate_commands": [],
        "planned_commands": [],
    }




def _render_disambiguation_report(report: dict[str, Any]) -> str:
    lines = [
        "# M2.8-pre Literal Disambiguation Report",
        "",
        f"- Scanner missed count: `{report.get('scanner_missed_count')}`",
        f"- Disambiguated current-context candidates: `{report.get('disambiguated_current_context_candidate_count')}`",
        f"- Source-result-only diagnostics: `{report.get('source_result_only_diagnostic_count')}`",
        "",
        "| Case | Tool | Arg | Selected | Cue | Rejected | Retain prior candidate |",
        "| --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for row in report.get("records") or []:
        lines.append(
            f"| `{row.get('case_id')}` | `{row.get('tool')}` | `{row.get('required_arg')}` | "
            f"`{row.get('selected_literal')}` | `{row.get('disambiguation_cue')}` | "
            f"`{row.get('why_rejected')}` | `{row.get('retain_prior_candidate')}` |"
        )
    lines.append("")
    return "\n".join(lines)

def _render_mismatch_schema(schema: dict[str, Any]) -> str:
    lines = ["# Retain Prior Mismatch Schema", "", "Offline schema only. BFCL failures diagnose prior mismatch; they do not create retain rules.", "", "## Failure Reasons"]
    for reason in schema["failure_reasons"]:
        lines.append(f"- `{reason}`")
    lines.extend(["", "## Required Join Keys"])
    for key in schema["required_join_keys"]:
        lines.append(f"- `{key}`")
    lines.append("")
    return "\n".join(lines)



def _render_source_result_availability_audit(report: dict[str, Any]) -> str:
    lines = [
        "# M2.8-pre Source/Result Availability Audit",
        "",
        f"- Audit ready: `{report.get('source_result_availability_audit_ready')}`",
        f"- Source/result availability ready: `{report.get('source_result_availability_ready')}`",
        f"- Hard issue counts: `{report.get('hard_issue_counts')}`",
        f"- Issue counts: `{report.get('issue_counts')}`",
        "",
        "| Category | Dataset cases | Result records | Top issues |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in report.get("category_reports") or []:
        result_records = sum(int(root.get("result_record_count") or 0) for root in row.get("root_reports") or [])
        issues = row.get("issue_counts") or {}
        top = dict(list(issues.items())[:5])
        lines.append(f"| `{row.get('category')}` | `{row.get('dataset_case_count')}` | `{result_records}` | `{top}` |")
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], out_root: Path = DEFAULT_OUT_ROOT) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    _write_json(out_root / "compiler_summary.json", {key: value for key, value in report.items() if key not in {"candidate_rules", "rejected_candidates", "wrong_arg_key_alias_candidate_rules", "wrong_arg_key_alias_rejected_candidates", "deterministic_schema_local_candidate_rules", "deterministic_schema_local_rejected_candidates", "combined_candidate_rules", "stratified_candidate_rules", "literal_disambiguation_records"}})
    (out_root / "compiler_summary.md").write_text(render_markdown(report), encoding="utf-8")
    with (out_root / "candidate_rules.jsonl").open("w", encoding="utf-8") as handle:
        for row in report["candidate_rules"]:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with (out_root / "wrong_arg_key_alias_candidate_rules.jsonl").open("w", encoding="utf-8") as handle:
        for row in report["wrong_arg_key_alias_candidate_rules"]:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with (out_root / "deterministic_schema_local_candidate_rules.jsonl").open("w", encoding="utf-8") as handle:
        for row in report["deterministic_schema_local_candidate_rules"]:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with (out_root / "combined_theory_prior_candidate_rules.jsonl").open("w", encoding="utf-8") as handle:
        for row in report["combined_candidate_rules"]:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with (out_root / "stratified_candidate_rules.jsonl").open("w", encoding="utf-8") as handle:
        for row in report["stratified_candidate_rules"]:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with (out_root / "rejected_candidates.jsonl").open("w", encoding="utf-8") as handle:
        for row in report["rejected_candidates"]:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    for path, md_path, manifest in [
        (out_root / "explicit_required_arg_literal_dev20_manifest.json", out_root / "explicit_required_arg_literal_dev20_manifest.md", report["dev_manifest"]),
        (out_root / "explicit_required_arg_literal_holdout20_manifest.json", out_root / "explicit_required_arg_literal_holdout20_manifest.md", report["holdout_manifest"]),
        (out_root / "wrong_arg_key_alias_dev20_manifest.json", out_root / "wrong_arg_key_alias_dev20_manifest.md", report["wrong_arg_key_alias_dev_manifest"]),
        (out_root / "wrong_arg_key_alias_holdout20_manifest.json", out_root / "wrong_arg_key_alias_holdout20_manifest.md", report["wrong_arg_key_alias_holdout_manifest"]),
        (out_root / "deterministic_schema_local_dev20_manifest.json", out_root / "deterministic_schema_local_dev20_manifest.md", report["deterministic_schema_local_dev_manifest"]),
        (out_root / "deterministic_schema_local_holdout20_manifest.json", out_root / "deterministic_schema_local_holdout20_manifest.md", report["deterministic_schema_local_holdout_manifest"]),
        (out_root / "theory_prior_low_risk_dev20_manifest.json", out_root / "theory_prior_low_risk_dev20_manifest.md", report["combined_dev_manifest"]),
        (out_root / "theory_prior_low_risk_holdout20_manifest.json", out_root / "theory_prior_low_risk_holdout20_manifest.md", report["combined_holdout_manifest"]),
        (out_root / "stratified_low_risk_dev20_manifest.json", out_root / "stratified_low_risk_dev20_manifest.md", report["stratified_dev_manifest"]),
        (out_root / "stratified_low_risk_holdout20_manifest.json", out_root / "stratified_low_risk_holdout20_manifest.md", report["stratified_holdout_manifest"]),
    ]:
        _write_json(path, manifest)
        md_path.write_text(_render_manifest(manifest), encoding="utf-8")
    availability = report.get("source_result_availability_audit") or {}
    _write_json(out_root / "m28pre_source_result_availability_audit.json", availability)
    (out_root / "m28pre_source_result_availability_audit.md").write_text(_render_source_result_availability_audit(availability), encoding="utf-8")

    disamb = {
        "report_scope": "m2_8pre_literal_disambiguation_report",
        "offline_only": True,
        "candidate_commands": [],
        "planned_commands": [],
        "scanner_missed_count": report.get("scanner_missed_count"),
        "disambiguated_current_context_candidate_count": report.get("disambiguated_current_context_candidate_count"),
        "source_result_only_diagnostic_count": report.get("source_result_only_diagnostic_count"),
        "records": report.get("literal_disambiguation_records") or [],
    }
    _write_json(out_root / "m28pre_literal_disambiguation_report.json", disamb)
    (out_root / "m28pre_literal_disambiguation_report.md").write_text(_render_disambiguation_report(disamb), encoding="utf-8")
    schema = _mismatch_schema()
    _write_json(out_root / "retain_prior_mismatch_schema.json", schema)
    (out_root / "retain_prior_mismatch_schema.md").write_text(_render_mismatch_schema(schema), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--low-risk-manifest", type=Path, default=DEFAULT_LOW_RISK)
    parser.add_argument("--ctspc-status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = build(args.low_risk_manifest, args.ctspc_status, source_manifest_path=args.source_manifest)
    write_outputs(report, args.out_root)
    if args.compact:
        print(json.dumps({
            "compiler_ready": report["compiler_ready"],
            "explicit_holdout_ready": report["explicit_holdout_ready"],
            "stratified_holdout_ready": report["stratified_holdout_ready"],
            "scorer_authorization_ready": report["scorer_authorization_ready"],
            "selected_case_count": report["selected_case_count"],
            "candidate_generatable_count": report["candidate_generatable_count"],
            "retain_eligible_candidate_count": report["retain_eligible_candidate_count"],
            "wrong_arg_key_alias_demote_candidate_count": report["wrong_arg_key_alias_demote_candidate_count"],
            "deterministic_schema_local_demote_candidate_count": report["deterministic_schema_local_demote_candidate_count"],
            "combined_retain_eligible_candidate_count": report["combined_retain_eligible_candidate_count"],
            "theory_prior_explicit_literal_candidate_count": report["theory_prior_explicit_literal_candidate_count"],
            "stratified_selected_case_count": report["stratified_selected_case_count"],
            "stratified_candidate_generatable_count": report["stratified_candidate_generatable_count"],
            "source_result_availability_ready": report["source_result_availability_ready"],
            "remaining_gap_to_35_demote_candidates": report["remaining_gap_to_35_demote_candidates"],
            "route_recommendation": report["route_recommendation"],
            "retention_prior_distribution": report["retention_prior_distribution"],
            "wrong_arg_key_alias_retention_prior_distribution": report["wrong_arg_key_alias_retention_prior_distribution"],
            "deterministic_schema_local_retention_prior_distribution": report["deterministic_schema_local_retention_prior_distribution"],
            "combined_retention_prior_distribution": report["combined_retention_prior_distribution"],
            "stratified_retention_prior_distribution": report["stratified_retention_prior_distribution"],
            "blockers": report["blockers"],
            "planned_commands": report["planned_commands"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
