#!/usr/bin/env python3
"""Build M2.8-pre explicit-required-arg-literal offline candidates.

This is a low-risk slice compiler. It does not change the next-tool policy and
does not emit BFCL scorer commands. Candidates are argument-completion records
grounded in source artifacts for future offline review.
"""

from __future__ import annotations

import argparse
import json
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


def _compile_record(record: dict[str, Any], result: dict[str, Any] | None) -> dict[str, Any]:
    case_id = str(record.get("case_id") or "")
    target_tools = [str(t) for t in (record.get("target_action_tools_present") or [])]
    if not result:
        return {"case_id": case_id, "candidate_generatable": False, "rejection_reason": "missing_source_result"}
    for tool, args in _iter_tool_calls(result.get("result")):
        if target_tools and tool not in target_tools:
            continue
        arg_name, value = _pick_arg(tool, args)
        if arg_name is None or value is None:
            continue
        literal = str(value)
        ambiguous = literal.strip() == "" or len(literal) > 240
        if ambiguous:
            return {"case_id": case_id, "candidate_generatable": False, "rejection_reason": "ambiguous_literal"}
        return {
            "case_id": case_id,
            "category": record.get("category"),
            "tool": tool,
            "required_arg": arg_name,
            "literal_value": literal,
            "literal_source": "source_result_tool_args",
            "schema_arg_name": arg_name,
            "confidence": 0.7 if tool not in TRAJECTORY_SENSITIVE_TOOLS else 0.6,
            "candidate_generatable": True,
            "rejection_reason": None,
            "rule_type": "explicit_required_arg_literal_completion",
            "no_next_tool_intervention": True,
            "exact_tool_choice": False,
            "guidance_only": True,
            "trajectory_sensitive_tool": tool in TRAJECTORY_SENSITIVE_TOOLS,
            "ctspc_v0_action_rule": False,
            "source_run_root": record.get("source_run_root"),
        }
    return {"case_id": case_id, "candidate_generatable": False, "rejection_reason": "no_matching_scalar_required_arg"}


def _manifest(name: str, rows: list[dict[str, Any]], *, ready: bool) -> dict[str, Any]:
    return {
        "manifest_name": name,
        "selected_case_count": len(rows),
        "selected_case_ids": [str(row.get("case_id")) for row in rows],
        "selection_criteria": "explicit_required_arg_literal; schema-local; no CTSPC-v0 next-tool intervention",
        "planned_commands": [],
        "candidate_commands": [],
        "ready": ready,
        "cases": rows,
    }


def build(low_risk_path: Path = DEFAULT_LOW_RISK, status_path: Path = DEFAULT_STATUS, dev_size: int = 20, holdout_size: int = 20) -> dict[str, Any]:
    low = _read_json(low_risk_path, {}) or {}
    status = _read_json(status_path, {}) or {}
    source_cache: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    explicit_records = list((low.get("slice_cases") or {}).get("explicit_required_arg_literal") or [])
    compiled: list[dict[str, Any]] = []
    ambiguous = 0
    for record in explicit_records:
        source_root = Path(str(record.get("source_run_root") or ""))
        category = str(record.get("category") or "")
        key = (str(source_root), category)
        if key not in source_cache:
            source_cache[key] = _load_result_records(source_root, category)
        item = _compile_record(record, source_cache[key].get(str(record.get("case_id") or "")))
        compiled.append(item)
        if item.get("rejection_reason") == "ambiguous_literal":
            ambiguous += 1
    generatable = [item for item in compiled if item.get("candidate_generatable")]
    dev = generatable[:dev_size]
    holdout = generatable[dev_size : dev_size + holdout_size]
    ctspc_off = bool(
        status.get("ctspc_v0_frozen")
        and status.get("scorer_default") == "off"
        and status.get("retain") == 0
        and status.get("dev_rerun_authorized") is False
        and status.get("holdout_authorized") is False
    )
    compiler_passed = len(explicit_records) >= dev_size and len(generatable) >= 15 and ambiguous == 0 and ctspc_off
    holdout_ready = len(holdout) >= holdout_size
    return {
        "report_scope": "m2_8pre_explicit_required_arg_literal_compiler",
        "offline_only": True,
        "no_bfcl_or_model_call": True,
        "planned_commands": [],
        "candidate_commands": [],
        "ctspc_v0_file_path_multi_turn_enabled": False,
        "ctspc_v0_action_rules_enabled": False,
        "ctspc_v0_frozen": ctspc_off,
        "selected_case_count": len(explicit_records),
        "candidate_generatable_count": len(generatable),
        "ambiguous_literal_count": ambiguous,
        "candidate_rules": generatable,
        "rejected_candidates": [item for item in compiled if not item.get("candidate_generatable")],
        "dev_manifest": _manifest("explicit_required_arg_literal_dev20", dev, ready=len(dev) >= dev_size),
        "holdout_manifest": _manifest("explicit_required_arg_literal_holdout20", holdout, ready=holdout_ready),
        "m28pre_explicit_required_arg_literal_compiler_passed": compiler_passed,
        "m28pre_explicit_required_arg_literal_holdout_ready": holdout_ready,
        "m28pre_low_risk_slice_ready": compiler_passed and holdout_ready,
        "blockers": [
            reason
            for reason, blocked in [
                ("candidate_generatable_below_15", len(generatable) < 15),
                ("ambiguous_literal_present", ambiguous > 0),
                ("ctspc_v0_not_frozen", not ctspc_off),
                ("holdout_below_20", not holdout_ready),
            ]
            if blocked
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# M2.8-pre Explicit Required Arg Literal Compiler",
        "",
        f"- Compiler passed: `{report['m28pre_explicit_required_arg_literal_compiler_passed']}`",
        f"- Low-risk slice ready: `{report['m28pre_low_risk_slice_ready']}`",
        f"- Selected cases: `{report['selected_case_count']}`",
        f"- Candidate-generatable: `{report['candidate_generatable_count']}`",
        f"- Ambiguous literals: `{report['ambiguous_literal_count']}`",
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
        f"- Selected cases: `{manifest['selected_case_count']}`",
        "- Planned commands: `[]`",
        "",
    ])


def write_outputs(report: dict[str, Any], out_root: Path = DEFAULT_OUT_ROOT) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    summary_path = out_root / "compiler_summary.json"
    summary_md = out_root / "compiler_summary.md"
    rules_out = out_root / "candidate_rules.jsonl"
    dev_out = out_root / "explicit_required_arg_literal_dev20_manifest.json"
    dev_md = out_root / "explicit_required_arg_literal_dev20_manifest.md"
    hold_out = out_root / "explicit_required_arg_literal_holdout20_manifest.json"
    hold_md = out_root / "explicit_required_arg_literal_holdout20_manifest.md"
    _write_json(summary_path, {key: value for key, value in report.items() if key not in {"candidate_rules", "rejected_candidates"}})
    summary_md.write_text(render_markdown(report), encoding="utf-8")
    with rules_out.open("w", encoding="utf-8") as handle:
        for row in report["candidate_rules"]:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    _write_json(dev_out, report["dev_manifest"])
    dev_md.write_text(_render_manifest(report["dev_manifest"]), encoding="utf-8")
    _write_json(hold_out, report["holdout_manifest"])
    hold_md.write_text(_render_manifest(report["holdout_manifest"]), encoding="utf-8")


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
            "m28pre_low_risk_slice_ready": report["m28pre_low_risk_slice_ready"],
            "m28pre_explicit_required_arg_literal_compiler_passed": report["m28pre_explicit_required_arg_literal_compiler_passed"],
            "m28pre_explicit_required_arg_literal_holdout_ready": report["m28pre_explicit_required_arg_literal_holdout_ready"],
            "selected_case_count": report["selected_case_count"],
            "candidate_generatable_count": report["candidate_generatable_count"],
            "ambiguous_literal_count": report["ambiguous_literal_count"],
            "blockers": report["blockers"],
            "planned_commands": report["planned_commands"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
