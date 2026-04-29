#!/usr/bin/env python3
"""Baseline-only dry audit for materialized explicit-obligation smoke cases.

This reads only existing source traces and the materialized review manifest. It
does not run BFCL/model/scorer. The goal is to detect baseline ceiling and
control false-positive risk before spending a controlled smoke run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_PROTOCOL = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_executable_smoke_protocol.json")
DEFAULT_SOURCE_ROOT = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
DEFAULT_OUT = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_baseline_dry_audit.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_baseline_dry_audit.md")
MEMORY_TOOL_HINTS = ("memory", "archival_", "core_memory")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_outputs(trace: dict[str, Any]) -> list[dict[str, Any]]:
    final_response = trace.get("final_response") or {}
    outputs = final_response.get("output") if isinstance(final_response, dict) else None
    if isinstance(outputs, list):
        return [item for item in outputs if isinstance(item, dict)]
    raw = trace.get("raw_response") or {}
    choices = raw.get("choices") if isinstance(raw, dict) else None
    if not isinstance(choices, list):
        return []
    out: list[dict[str, Any]] = []
    for choice in choices:
        message = (choice or {}).get("message") or {}
        for call in message.get("tool_calls") or []:
            fn = (call or {}).get("function") or {}
            out.append({"type": "function_call", "name": fn.get("name"), "arguments": fn.get("arguments")})
        if message.get("content"):
            out.append({"type": "message", "content": message.get("content")})
    return out


def _is_memory_tool(name: Any) -> bool:
    value = str(name or "").lower()
    return any(hint in value for hint in MEMORY_TOOL_HINTS)


def _audit_record(item: dict[str, Any], source_root: Path, record_type: str) -> dict[str, Any]:
    trace_relative = str(item.get("trace_relative_path") or "")
    trace_path = source_root / trace_relative if trace_relative else None
    trace = _load_json(trace_path) if trace_path else None
    trace = trace if isinstance(trace, dict) else {}
    outputs = _extract_outputs(trace)
    function_calls = [out for out in outputs if out.get("type") == "function_call"]
    memory_calls = [str(out.get("name")) for out in function_calls if _is_memory_tool(out.get("name"))]
    message_outputs = [out for out in outputs if out.get("type") in {"message", "text"} or out.get("content")]
    memory_observed = bool(memory_calls)
    final_without_memory = bool(message_outputs and not memory_observed)
    if record_type == "positive":
        if memory_observed:
            bucket = "baseline_process_already_uses_memory"
        elif final_without_memory:
            bucket = "baseline_capability_miss_candidate"
        else:
            bucket = "baseline_process_unknown"
    else:
        bucket = "control_memory_activation_present" if memory_observed else "control_no_memory_activation"
    return {
        "record_type": record_type,
        "audit_case_id": item.get("audit_case_id"),
        "bfcl_case_id": item.get("bfcl_case_id"),
        "category": item.get("category"),
        "trace_relative_path": trace_relative,
        "trace_exists": bool(trace_path and trace_path.exists()),
        "baseline_first_response_function_call_count": len(function_calls),
        "baseline_first_response_memory_call_count": len(memory_calls),
        "baseline_first_response_memory_tools": memory_calls,
        "baseline_first_response_message_count": len(message_outputs),
        "required_capability_before_final": memory_observed,
        "final_answer_without_memory_call": final_without_memory,
        "baseline_dry_bucket": bucket,
    }


def evaluate(protocol_path: Path = DEFAULT_PROTOCOL, source_root: Path = DEFAULT_SOURCE_ROOT) -> dict[str, Any]:
    protocol = _load_json(protocol_path)
    protocol = protocol if isinstance(protocol, dict) else {}
    positives = [_audit_record(item, source_root, "positive") for item in protocol.get("selected_positive_cases") or [] if isinstance(item, dict)]
    controls = [_audit_record(item, source_root, "control") for item in protocol.get("selected_control_cases") or [] if isinstance(item, dict)]
    pos_bucket_counts: dict[str, int] = {}
    control_bucket_counts: dict[str, int] = {}
    for item in positives:
        pos_bucket_counts[item["baseline_dry_bucket"]] = pos_bucket_counts.get(item["baseline_dry_bucket"], 0) + 1
    for item in controls:
        control_bucket_counts[item["baseline_dry_bucket"]] = control_bucket_counts.get(item["baseline_dry_bucket"], 0) + 1
    selected = positives + controls
    unique_bfcl_case_id_count = len({str(item.get("bfcl_case_id") or "") for item in selected if item.get("bfcl_case_id")})
    unique_trace_relative_path_count = len({str(item.get("trace_relative_path") or "") for item in selected if item.get("trace_relative_path")})
    unique_audit_case_id_count = len({str(item.get("audit_case_id") or "") for item in selected if item.get("audit_case_id")})
    duplicate_selected_case_or_trace = bool(selected) and (
        unique_bfcl_case_id_count != len(selected)
        or unique_trace_relative_path_count != len(selected)
        or unique_audit_case_id_count != len(selected)
    )
    primary_positive_count = pos_bucket_counts.get("baseline_capability_miss_candidate", 0)
    ceiling_count = pos_bucket_counts.get("baseline_process_already_uses_memory", 0)
    unknown_count = pos_bucket_counts.get("baseline_process_unknown", 0)
    control_activation_count = control_bucket_counts.get("control_memory_activation_present", 0)
    baseline_ceiling_risk = ceiling_count > 2 or primary_positive_count < 6
    smoke_selection_ready = bool(len(positives) == 12 and len(controls) == 8 and not baseline_ceiling_risk and control_activation_count == 0 and not duplicate_selected_case_or_trace)
    blockers: list[str] = []
    if len(positives) < 12:
        blockers.append("positive_case_count_below_12")
    if len(controls) < 8:
        blockers.append("control_case_count_below_8")
    if primary_positive_count < 6:
        blockers.append("primary_positive_capability_miss_below_6")
    if ceiling_count > 2:
        blockers.append("baseline_ceiling_positive_count_above_2")
    if control_activation_count:
        blockers.append("control_memory_activation_present")
    if unique_bfcl_case_id_count != len(positives) + len(controls):
        blockers.append("duplicate_bfcl_case_id_present")
    if unique_trace_relative_path_count != len(positives) + len(controls):
        blockers.append("duplicate_trace_path_present")
    if unique_audit_case_id_count != len(positives) + len(controls):
        blockers.append("duplicate_audit_case_id_present")
    return {
        "report_scope": "explicit_obligation_baseline_dry_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "protocol_path": str(protocol_path),
        "source_root": str(source_root),
        "baseline_dry_audit_ready": bool(positives or controls),
        "smoke_selection_ready_after_baseline_dry_audit": smoke_selection_ready,
        "baseline_ceiling_risk": baseline_ceiling_risk,
        "positive_case_count": len(positives),
        "control_case_count": len(controls),
        "primary_positive_capability_miss_count": primary_positive_count,
        "baseline_process_already_uses_memory_count": ceiling_count,
        "baseline_process_unknown_count": unknown_count,
        "control_memory_activation_count": control_activation_count,
        "selected_smoke_baseline_control_activation_count": control_activation_count,
        "unique_bfcl_case_id_count": unique_bfcl_case_id_count,
        "unique_trace_relative_path_count": unique_trace_relative_path_count,
        "unique_audit_case_id_count": unique_audit_case_id_count,
        "duplicate_selected_case_or_trace": duplicate_selected_case_or_trace,
        "positive_bucket_counts": pos_bucket_counts,
        "control_bucket_counts": control_bucket_counts,
        "records": positives + controls,
        "blockers": blockers,
        "next_required_action": "request_controlled_smoke_approval" if smoke_selection_ready else "replace_ceiling_or_false_positive_cases_before_smoke",
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Explicit Obligation Baseline Dry Audit",
        "",
        f"- Baseline dry audit ready: `{report['baseline_dry_audit_ready']}`",
        f"- Smoke selection ready after dry audit: `{report['smoke_selection_ready_after_baseline_dry_audit']}`",
        f"- Baseline ceiling risk: `{report['baseline_ceiling_risk']}`",
        f"- Positive / control cases: `{report['positive_case_count']}` / `{report['control_case_count']}`",
        f"- Primary positive capability-miss count: `{report['primary_positive_capability_miss_count']}`",
        f"- Baseline already uses memory count: `{report['baseline_process_already_uses_memory_count']}`",
        f"- Control memory activation count: `{report['control_memory_activation_count']}`",
        f"- Unique BFCL case ids: `{report['unique_bfcl_case_id_count']}` / `{report['positive_case_count'] + report['control_case_count']}`",
        f"- Unique trace paths: `{report['unique_trace_relative_path_count']}` / `{report['positive_case_count'] + report['control_case_count']}`",
        f"- Unique audit ids: `{report['unique_audit_case_id_count']}` / `{report['positive_case_count'] + report['control_case_count']}`",
        f"- Positive buckets: `{report['positive_bucket_counts']}`",
        f"- Control buckets: `{report['control_bucket_counts']}`",
        f"- Candidate commands: `{report['candidate_commands']}`",
        f"- Planned commands: `{report['planned_commands']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "This audit is offline only and reads existing source traces. It does not authorize execution.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.protocol, args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        keys = [
            "baseline_dry_audit_ready",
            "smoke_selection_ready_after_baseline_dry_audit",
            "baseline_ceiling_risk",
            "positive_case_count",
            "control_case_count",
            "primary_positive_capability_miss_count",
            "baseline_process_already_uses_memory_count",
            "control_memory_activation_count",
            "selected_smoke_baseline_control_activation_count",
            "unique_bfcl_case_id_count",
            "unique_trace_relative_path_count",
            "unique_audit_case_id_count",
            "duplicate_selected_case_or_trace",
            "positive_bucket_counts",
            "control_bucket_counts",
            "candidate_commands",
            "planned_commands",
            "blockers",
            "next_required_action",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    return 0 if report["smoke_selection_ready_after_baseline_dry_audit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
