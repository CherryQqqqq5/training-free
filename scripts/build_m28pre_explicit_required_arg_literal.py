#!/usr/bin/env python3
"""Build M2.8-pre explicit-required-arg-literal offline candidates.

This is a low-risk slice compiler. It does not change the next-tool policy and
does not emit BFCL scorer commands. Candidates are argument-completion records
grounded in source artifacts for future offline review.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_LOW_RISK = Path("outputs/artifacts/bfcl_ctspc_low_risk_slices_v1/low_risk_slice_manifest.json")
DEFAULT_STATUS = Path("outputs/artifacts/bfcl_ctspc_subset30_v1/m27ae_ctspc_v0_status.json")
DEFAULT_OUT_ROOT = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1")

TRAJECTORY_SENSITIVE_TOOLS = {"cat", "touch", "mkdir", "cp", "mv", "cd"}
PREFERRED_ARG_BY_TOOL = {
    "echo": ["content", "text", "message"],
    "grep": ["pattern", "query", "file_name", "path"],
    "find": ["query", "name", "pattern", "path"],
    "diff": ["file_name1", "source", "file_name", "path"],
    "cp": ["source", "src", "from", "destination", "dest", "to", "target"],
    "mv": ["source", "src", "from", "destination", "dest", "to", "target"],
    "touch": ["file_name", "filename", "path"],
    "mkdir": ["dir_name", "directory", "path"],
    "cat": ["file_name", "filename", "path"],
}
STRATIFIED_SLICES = [
    "explicit_required_arg_literal",
    "wrong_arg_key_alias_repair",
    "deterministic_schema_local_non_live_repair",
]


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
    matches = sorted((source_root / "bfcl" / "result").glob(f"*/multi_turn/BFCL_v4_{category}_result.json"))
    if not matches:
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


def _pick_arg(tool: str, args: dict[str, Any]) -> tuple[str | None, Any | None]:
    for name in PREFERRED_ARG_BY_TOOL.get(tool, []):
        if name in args and isinstance(args[name], (str, int, float, bool)):
            return name, args[name]
    for name, value in args.items():
        if isinstance(value, (str, int, float, bool)):
            return str(name), value
    return None, None


def _compile_record(record: dict[str, Any], result: dict[str, Any] | None, slice_name: str) -> dict[str, Any]:
    case_id = str(record.get("case_id") or "")
    target_tools = [str(t) for t in (record.get("target_action_tools_present") or [])]
    base = {
        "case_id": case_id,
        "category": record.get("category"),
        "slice_name": slice_name,
        "low_risk_slices": sorted(set(str(s) for s in (record.get("low_risk_slices") or [slice_name]))),
        "source_run_root": record.get("source_run_root"),
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
        ambiguous = literal.strip() == "" or len(literal) > 240
        if ambiguous:
            return {**base, "candidate_generatable": False, "rejection_reason": "ambiguous_literal"}
        return {
            **base,
            "tool": tool,
            "required_arg": arg_name,
            "literal_value": literal,
            "literal_source": "source_result_tool_args",
            "schema_arg_name": arg_name,
            "confidence": 0.7 if tool not in TRAJECTORY_SENSITIVE_TOOLS else 0.6,
            "candidate_generatable": True,
            "rejection_reason": None,
            "rule_type": "explicit_required_arg_literal_completion",
            "candidate_rules_type": "explicit_required_arg_literal_completion",
            "no_next_tool_intervention": True,
            "exact_tool_choice": False,
            "guidance_only": True,
            "trajectory_sensitive_tool": tool in TRAJECTORY_SENSITIVE_TOOLS,
            "ctspc_v0_action_rule": False,
        }
    return {**base, "candidate_generatable": False, "rejection_reason": "no_matching_scalar_required_arg"}


def _source_cache_loader() -> tuple[dict[tuple[str, str], dict[str, dict[str, Any]]], Any]:
    cache: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}

    def load(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
        source_root = Path(str(record.get("source_run_root") or ""))
        category = str(record.get("category") or "")
        key = (str(source_root), category)
        if key not in cache:
            cache[key] = _load_result_records(source_root, category)
        return cache[key]

    return cache, load


def _compile_records(records: list[dict[str, Any]], slice_name: str, load_result: Any) -> list[dict[str, Any]]:
    compiled: list[dict[str, Any]] = []
    for record in records:
        results = load_result(record)
        compiled.append(_compile_record(record, results.get(str(record.get("case_id") or "")), slice_name))
    return compiled


def _manifest(name: str, rows: list[dict[str, Any]], *, ready: bool, slice_name: str | None = None) -> dict[str, Any]:
    return {
        "manifest_name": name,
        "selected_case_count": len(rows),
        "selected_case_ids": [str(row.get("case_id")) for row in rows],
        "selection_criteria": "low-risk argument completion; schema-local; no CTSPC-v0 next-tool intervention",
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


def build(low_risk_path: Path = DEFAULT_LOW_RISK, status_path: Path = DEFAULT_STATUS, dev_size: int = 20, holdout_size: int = 20) -> dict[str, Any]:
    low = _read_json(low_risk_path, {}) or {}
    status = _read_json(status_path, {}) or {}
    slice_cases = low.get("slice_cases") or {}
    _, load_result = _source_cache_loader()

    explicit_records = list(slice_cases.get("explicit_required_arg_literal") or [])
    explicit_compiled = _compile_records(explicit_records, "explicit_required_arg_literal", load_result)
    explicit_generatable = [item for item in explicit_compiled if item.get("candidate_generatable")]
    explicit_ambiguous = sum(1 for item in explicit_compiled if item.get("rejection_reason") == "ambiguous_literal")

    stratified_records = _unique_records_by_case(slice_cases)
    stratified_compiled = _compile_records(stratified_records, "stratified_low_risk", load_result)
    stratified_generatable = [item for item in stratified_compiled if item.get("candidate_generatable")]
    stratified_ambiguous = sum(1 for item in stratified_compiled if item.get("rejection_reason") == "ambiguous_literal")
    stratified_counts: dict[str, int] = defaultdict(int)
    for item in stratified_generatable:
        for slice_name in item.get("low_risk_slices") or []:
            if slice_name in STRATIFIED_SLICES:
                stratified_counts[slice_name] += 1

    ctspc_off = bool(
        status.get("ctspc_v0_frozen")
        and status.get("scorer_default") == "off"
        and status.get("retain") == 0
        and status.get("dev_rerun_authorized") is False
        and status.get("holdout_authorized") is False
    )
    explicit_compiler_ready = len(explicit_records) >= dev_size and len(explicit_generatable) >= 15 and explicit_ambiguous == 0 and ctspc_off
    stratified_compiler_ready = len(stratified_records) >= dev_size and len(stratified_generatable) >= 15 and stratified_ambiguous == 0 and ctspc_off
    compiler_ready = explicit_compiler_ready or stratified_compiler_ready
    explicit_holdout_ready = len(explicit_records) >= dev_size + holdout_size and len(explicit_generatable) >= dev_size + holdout_size and explicit_ambiguous == 0
    stratified_holdout_ready = len(stratified_records) >= dev_size + holdout_size and len(stratified_generatable) >= dev_size + holdout_size and stratified_ambiguous == 0
    explicit_dev = explicit_generatable[:dev_size]
    explicit_holdout = explicit_generatable[dev_size : dev_size + holdout_size]
    stratified_dev = stratified_generatable[:dev_size]
    stratified_holdout = stratified_generatable[dev_size : dev_size + holdout_size]
    scorer_ready = compiler_ready and (explicit_holdout_ready or stratified_holdout_ready)
    blockers = []
    if len(explicit_records) < dev_size + holdout_size:
        blockers.append("explicit_total_below_40")
    if len(explicit_generatable) < 35:
        blockers.append("explicit_candidate_generatable_below_35")
    if explicit_ambiguous:
        blockers.append("explicit_ambiguous_literal_present")
    if not explicit_holdout_ready:
        blockers.append("explicit_holdout_below_20")
    if not stratified_holdout_ready:
        blockers.append("stratified_holdout_below_20")
    if not ctspc_off:
        blockers.append("ctspc_v0_not_frozen")
    return {
        "report_scope": "m2_8pre_explicit_required_arg_literal_compiler",
        "offline_only": True,
        "source_pool_expansion_required": not scorer_ready,
        "explicit_source_pool_expansion_required": not explicit_holdout_ready,
        "stratified_source_pool_expansion_required": not stratified_holdout_ready,
        "required_explicit_total": dev_size + holdout_size,
        "required_explicit_candidate_generatable": 35,
        "required_stratified_total": dev_size + holdout_size,
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
        "selected_case_count": len(explicit_records),
        "candidate_generatable_count": len(explicit_generatable),
        "ambiguous_literal_count": explicit_ambiguous,
        "candidate_rules": explicit_generatable,
        "rejected_candidates": [item for item in explicit_compiled if not item.get("candidate_generatable")],
        "dev_manifest": _manifest("explicit_required_arg_literal_dev20", explicit_dev, ready=len(explicit_dev) >= dev_size, slice_name="explicit_required_arg_literal"),
        "holdout_manifest": _manifest("explicit_required_arg_literal_holdout20", explicit_holdout, ready=explicit_holdout_ready, slice_name="explicit_required_arg_literal"),
        "stratified_candidate_rules": stratified_generatable,
        "stratified_counts": dict(sorted(stratified_counts.items())),
        "stratified_selected_case_count": len(stratified_records),
        "stratified_candidate_generatable_count": len(stratified_generatable),
        "stratified_ambiguous_literal_count": stratified_ambiguous,
        "stratified_dev_manifest": _manifest("stratified_low_risk_dev20", stratified_dev, ready=len(stratified_dev) >= dev_size, slice_name="stratified_low_risk"),
        "stratified_holdout_manifest": _manifest("stratified_low_risk_holdout20", stratified_holdout, ready=stratified_holdout_ready, slice_name="stratified_low_risk"),
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
        f"- Stratified selected/generatable: `{report['stratified_selected_case_count']}` / `{report['stratified_candidate_generatable_count']}`",
        f"- Source pool expansion required: `{report['source_pool_expansion_required']}`",
        f"- Blockers: `{report['blockers']}`",
        "",
        "No BFCL scorer commands are emitted.",
        "",
    ])


def _render_manifest(manifest: dict[str, Any]) -> str:
    return "\n".join([
        f"# {manifest['manifest_name']}",
        "",
        f"- Ready: `{manifest['ready']}`",
        f"- Slice: `{manifest['slice_name']}`",
        f"- Selected cases: `{manifest['selected_case_count']}`",
        "- Planned commands: `[]`",
        "",
    ])


def write_outputs(report: dict[str, Any], out_root: Path = DEFAULT_OUT_ROOT) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    summary_path = out_root / "compiler_summary.json"
    summary_md = out_root / "compiler_summary.md"
    rules_out = out_root / "candidate_rules.jsonl"
    stratified_rules_out = out_root / "stratified_candidate_rules.jsonl"
    dev_out = out_root / "explicit_required_arg_literal_dev20_manifest.json"
    dev_md = out_root / "explicit_required_arg_literal_dev20_manifest.md"
    hold_out = out_root / "explicit_required_arg_literal_holdout20_manifest.json"
    hold_md = out_root / "explicit_required_arg_literal_holdout20_manifest.md"
    strat_dev_out = out_root / "stratified_low_risk_dev20_manifest.json"
    strat_dev_md = out_root / "stratified_low_risk_dev20_manifest.md"
    strat_hold_out = out_root / "stratified_low_risk_holdout20_manifest.json"
    strat_hold_md = out_root / "stratified_low_risk_holdout20_manifest.md"
    _write_json(summary_path, {key: value for key, value in report.items() if key not in {"candidate_rules", "rejected_candidates", "stratified_candidate_rules"}})
    summary_md.write_text(render_markdown(report), encoding="utf-8")
    with rules_out.open("w", encoding="utf-8") as handle:
        for row in report["candidate_rules"]:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with stratified_rules_out.open("w", encoding="utf-8") as handle:
        for row in report["stratified_candidate_rules"]:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    for path, md_path, manifest in [
        (dev_out, dev_md, report["dev_manifest"]),
        (hold_out, hold_md, report["holdout_manifest"]),
        (strat_dev_out, strat_dev_md, report["stratified_dev_manifest"]),
        (strat_hold_out, strat_hold_md, report["stratified_holdout_manifest"]),
    ]:
        _write_json(path, manifest)
        md_path.write_text(_render_manifest(manifest), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--low-risk-manifest", type=Path, default=DEFAULT_LOW_RISK)
    parser.add_argument("--ctspc-status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = build(args.low_risk_manifest, args.ctspc_status)
    write_outputs(report, args.out_root)
    if args.compact:
        print(json.dumps({
            "compiler_ready": report["compiler_ready"],
            "explicit_holdout_ready": report["explicit_holdout_ready"],
            "stratified_holdout_ready": report["stratified_holdout_ready"],
            "scorer_authorization_ready": report["scorer_authorization_ready"],
            "selected_case_count": report["selected_case_count"],
            "candidate_generatable_count": report["candidate_generatable_count"],
            "stratified_selected_case_count": report["stratified_selected_case_count"],
            "stratified_candidate_generatable_count": report["stratified_candidate_generatable_count"],
            "blockers": report["blockers"],
            "planned_commands": report["planned_commands"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
