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

from grc.compiler.retention_priors import (
    DEMOTE_CANDIDATE,
    BFCL_FAILURE_REASONS,
    explicit_required_arg_literal_prior,
    summarize_retention_priors,
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


def _load_result_records(source_root: Path, category: str) -> dict[str, dict[str, Any]]:
    path = _result_path(source_root, category)
    if not path:
        return {}
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        case_id = str(item.get("id") or item.get("case_id") or "")
        if case_id:
            records[case_id] = item
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


def _literal_candidates_for_arg(text: str, schema: dict[str, Any], emitted_args: dict[str, Any]) -> list[str]:
    emitted = {_scalar(value) for value in emitted_args.values()}
    emitted.discard(None)
    typ = str(schema.get("type") or "string").lower()
    if typ in {"integer", "number"}:
        candidates = _number_literals(text)
    elif typ == "boolean":
        raw = re.findall(r"\b(?:true|false|yes|no)\b", text, flags=re.IGNORECASE)
        candidates = ["true" if item.lower() in {"true", "yes"} else "false" for item in raw]
    else:
        candidates = _quoted_literals(text)
    unique: list[str] = []
    for value in candidates:
        if str(value) in emitted:
            continue
        if value not in unique:
            unique.append(str(value))
    return unique


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
        candidates = _literal_candidates_for_arg(text, _arg_schema(fn, required_arg), emitted_args)
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


def _compile_legacy_record(record: dict[str, Any], result: dict[str, Any] | None, slice_name: str) -> dict[str, Any]:
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


def _compile_legacy_records(records: list[dict[str, Any]], slice_name: str, load_result: Any) -> list[dict[str, Any]]:
    compiled: list[dict[str, Any]] = []
    for record in records:
        results = load_result(record)
        item = _compile_legacy_record(record, results.get(str(record.get("case_id") or "")), slice_name)
        item["retention_prior"] = explicit_required_arg_literal_prior(item)
        compiled.append(item)
    return compiled


def _manifest(name: str, rows: list[dict[str, Any]], *, ready: bool, slice_name: str | None = None) -> dict[str, Any]:
    return {
        "manifest_name": name,
        "selected_case_count": len(rows),
        "selected_case_ids": [str(row.get("case_id")) for row in rows],
        "selection_criteria": "theory-prior explicit required-arg literal completion; no CTSPC-v0 next-tool intervention",
        "slice_name": slice_name,
        "planned_commands": [],
        "candidate_commands": [],
        "ctspc_v0_frozen": True,
        "repair_stack_default": "disabled",
        "candidate_rules_type": "explicit_required_arg_literal_completion",
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

    legacy_explicit_records = list(slice_cases.get("explicit_required_arg_literal") or [])
    legacy_explicit_compiled = _compile_legacy_records(legacy_explicit_records, "explicit_required_arg_literal", load_result)
    existing_case_ids = {str(row.get("case_id") or "") for row in legacy_explicit_records if row.get("case_id")}
    if source_manifest_path == DEFAULT_SOURCE_MANIFEST and low_risk_path != DEFAULT_LOW_RISK:
        prior_candidates, prior_rejected, prior_diag = [], [], {
            "prior_aware_scan_enabled": False,
            "prior_aware_skip_reason": "non_default_low_risk_manifest_without_explicit_source_manifest",
            "prior_aware_candidate_count": 0,
            "prior_aware_rejected_count": 0,
            "prior_aware_rejection_distribution": {},
        }
    else:
        prior_candidates, prior_rejected, prior_diag = _load_prior_aware_candidates(source_manifest_path, existing_case_ids)

    explicit_compiled = legacy_explicit_compiled + prior_candidates + prior_rejected
    explicit_generatable = [item for item in explicit_compiled if item.get("candidate_generatable")]
    theory_prior_generatable = [item for item in explicit_generatable if item.get("theory_prior_explicit_literal_candidate")]
    explicit_ambiguous = sum(1 for item in explicit_compiled if item.get("rejection_reason") in {"ambiguous_literal", "ambiguous_or_missing_observable_literal"})

    stratified_records = _unique_records_by_case(slice_cases)
    stratified_compiled = _compile_legacy_records(stratified_records, "stratified_low_risk", load_result)
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
    stratified_retain_eligible = [row for row in stratified_generatable if row.get("retention_prior", {}).get("retain_eligibility") == DEMOTE_CANDIDATE]

    ctspc_off = bool(status.get("ctspc_v0_frozen") and status.get("scorer_default") == "off" and status.get("retain") == 0 and status.get("dev_rerun_authorized") is False and status.get("holdout_authorized") is False)
    required_total = dev_size + holdout_size
    explicit_compiler_ready = len(explicit_generatable) >= dev_size and explicit_ambiguous == 0 and ctspc_off
    stratified_compiler_ready = len(stratified_generatable) >= dev_size and stratified_ambiguous == 0 and ctspc_off
    compiler_ready = explicit_compiler_ready or stratified_compiler_ready
    explicit_holdout_ready = len(retain_eligible) >= required_total and explicit_ambiguous == 0
    stratified_holdout_ready = False
    explicit_dev = retain_eligible[:dev_size]
    explicit_holdout = retain_eligible[dev_size : dev_size + holdout_size]
    stratified_dev = stratified_retain_eligible[:dev_size]
    stratified_holdout = stratified_retain_eligible[dev_size : dev_size + holdout_size]
    scorer_ready = compiler_ready and explicit_holdout_ready

    blockers = []
    if len(explicit_generatable) < required_total:
        blockers.append("explicit_total_below_40")
    if len(retain_eligible) < 35:
        blockers.append("explicit_demote_candidate_below_35")
    if explicit_ambiguous:
        blockers.append("explicit_ambiguous_literal_present")
    if not explicit_holdout_ready:
        blockers.append("explicit_holdout_below_20")
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
        "candidate_rules_type": "explicit_required_arg_literal_completion",
        "no_next_tool_intervention": True,
        "exact_tool_choice": False,
        "retention_prior_required": True,
        "retention_prior_rule_family": "explicit_required_arg_literal_completion",
        "bfcl_score_cannot_create_retain_rule": True,
        "stratified_pool_diagnostic_only_until_family_priors_exist": True,
        "ctspc_legacy_file_path_candidate_count": len([row for row in explicit_generatable if row.get("ctspc_legacy_file_path_candidate")]),
        "theory_prior_explicit_literal_candidate_count": len(theory_prior_generatable),
        "prior_aware_scan": prior_diag,
        "retention_prior_distribution": explicit_prior_distribution,
        "stratified_retention_prior_distribution": stratified_prior_distribution,
        "retain_eligible_candidate_count": len(retain_eligible),
        "stratified_retain_eligible_candidate_count": len(stratified_retain_eligible),
        "selected_case_count": len(explicit_generatable),
        "candidate_generatable_count": len(explicit_generatable),
        "ambiguous_literal_count": explicit_ambiguous,
        "candidate_rules": explicit_generatable,
        "rejected_candidates": [item for item in explicit_compiled if not item.get("candidate_generatable")],
        "dev_manifest": _manifest("explicit_required_arg_literal_dev20", explicit_dev, ready=len(explicit_dev) >= dev_size, slice_name="explicit_required_arg_literal"),
        "holdout_manifest": _manifest("explicit_required_arg_literal_holdout20", explicit_holdout, ready=explicit_holdout_ready, slice_name="explicit_required_arg_literal"),
        "stratified_candidate_rules": stratified_generatable,
        "stratified_counts": dict(sorted(stratified_counts.items())),
        "stratified_selected_case_count": len(stratified_generatable),
        "stratified_candidate_generatable_count": len(stratified_generatable),
        "stratified_ambiguous_literal_count": stratified_ambiguous,
        "stratified_dev_manifest": _manifest("stratified_low_risk_dev20", stratified_dev, ready=False, slice_name="stratified_low_risk"),
        "stratified_holdout_manifest": _manifest("stratified_low_risk_holdout20", stratified_holdout, ready=False, slice_name="stratified_low_risk"),
        "compiler_ready": compiler_ready,
        "explicit_compiler_ready": explicit_compiler_ready,
        "stratified_compiler_ready": stratified_compiler_ready,
        "explicit_holdout_ready": explicit_holdout_ready,
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
        f"- Theory-prior explicit candidates: `{report['theory_prior_explicit_literal_candidate_count']}`",
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


def _render_mismatch_schema(schema: dict[str, Any]) -> str:
    lines = ["# Retain Prior Mismatch Schema", "", "Offline schema only. BFCL failures diagnose prior mismatch; they do not create retain rules.", "", "## Failure Reasons"]
    for reason in schema["failure_reasons"]:
        lines.append(f"- `{reason}`")
    lines.extend(["", "## Required Join Keys"])
    for key in schema["required_join_keys"]:
        lines.append(f"- `{key}`")
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], out_root: Path = DEFAULT_OUT_ROOT) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    _write_json(out_root / "compiler_summary.json", {key: value for key, value in report.items() if key not in {"candidate_rules", "rejected_candidates", "stratified_candidate_rules"}})
    (out_root / "compiler_summary.md").write_text(render_markdown(report), encoding="utf-8")
    with (out_root / "candidate_rules.jsonl").open("w", encoding="utf-8") as handle:
        for row in report["candidate_rules"]:
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
        (out_root / "stratified_low_risk_dev20_manifest.json", out_root / "stratified_low_risk_dev20_manifest.md", report["stratified_dev_manifest"]),
        (out_root / "stratified_low_risk_holdout20_manifest.json", out_root / "stratified_low_risk_holdout20_manifest.md", report["stratified_holdout_manifest"]),
    ]:
        _write_json(path, manifest)
        md_path.write_text(_render_manifest(manifest), encoding="utf-8")
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
            "theory_prior_explicit_literal_candidate_count": report["theory_prior_explicit_literal_candidate_count"],
            "stratified_selected_case_count": report["stratified_selected_case_count"],
            "stratified_candidate_generatable_count": report["stratified_candidate_generatable_count"],
            "retention_prior_distribution": report["retention_prior_distribution"],
            "stratified_retention_prior_distribution": report["stratified_retention_prior_distribution"],
            "blockers": report["blockers"],
            "planned_commands": report["planned_commands"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
