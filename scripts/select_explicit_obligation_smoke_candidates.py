#!/usr/bin/env python3
"""Select explicit-obligation smoke candidates from the full materialized pool.

This is an offline selector. It never runs BFCL/model/scorer and never emits
execution commands. It keeps the explicit-obligation smoke fail-closed unless it
can find non-ceiling positives and true no-activation controls.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.diagnose_explicit_obligation_baseline_dry_audit import _audit_record

DEFAULT_PROTOCOL = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_executable_smoke_protocol.json")
DEFAULT_SOURCE_ROOT = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
DEFAULT_OUT = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_smoke_selection_audit.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_smoke_selection_audit.md")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _all_records(protocol: dict[str, Any], selected_key: str, rejected_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in (selected_key, rejected_key):
        for item in protocol.get(key) or []:
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _unique_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item.get("audit_case_id") or ""), str(item.get("bfcl_case_id") or ""), str(item.get("trace_relative_path") or ""))


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for item in records:
        key = _unique_key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _classify_positive(item: dict[str, Any], source_root: Path) -> dict[str, Any]:
    audited = _audit_record(item, source_root, "positive")
    semantic_requires_memory = bool(item.get("operation") == "retrieve" or item.get("expected_policy") == "soft_guidance_only_memory_retrieve")
    baseline_gap = audited.get("baseline_dry_bucket") == "baseline_capability_miss_candidate"
    exact_mapping = bool(item.get("bfcl_case_id") and item.get("prompt_match_count") == 1 and item.get("dependency_closure_ready"))
    direct_final = bool(audited.get("baseline_first_response_message_count") and audited.get("baseline_first_response_function_call_count") == 0)
    eligible = bool(exact_mapping and semantic_requires_memory and baseline_gap and direct_final)
    reasons: list[str] = []
    if not exact_mapping:
        reasons.append("not_exact_mapped_or_dependency_not_ready")
    if not semantic_requires_memory:
        reasons.append("semantic_requires_memory_missing")
    if not baseline_gap:
        reasons.append("positive_baseline_not_capability_miss")
    if not direct_final:
        reasons.append("positive_baseline_not_direct_final")
    return {
        **item,
        **audited,
        "semantic_requires_memory": semantic_requires_memory,
        "baseline_gap_type": "activation_gap" if baseline_gap else audited.get("baseline_dry_bucket"),
        "selection_role": "positive_candidate" if eligible else "ceiling_diagnostic_or_reject",
        "selection_eligible": eligible,
        "selection_rejection_reasons": reasons,
        "selection_score": 10 if eligible else 0,
    }


def _classify_control(item: dict[str, Any], source_root: Path) -> dict[str, Any]:
    audited = _audit_record(item, source_root, "control")
    negative_type = str(item.get("negative_control_type") or "")
    semantic_requires_memory = False if negative_type == "no_memory_operation_intent" else None
    exact_mapping = bool(item.get("bfcl_case_id") and item.get("prompt_match_count") == 1 and item.get("dependency_closure_ready"))
    baseline_no_activation = audited.get("baseline_dry_bucket") == "control_no_memory_activation"
    semantic_known_clean = semantic_requires_memory is False
    eligible = bool(exact_mapping and baseline_no_activation and semantic_known_clean)
    reasons: list[str] = []
    if not exact_mapping:
        reasons.append("not_exact_mapped_or_dependency_not_ready")
    if not baseline_no_activation:
        reasons.append("control_baseline_memory_activation_present")
    if not semantic_known_clean:
        reasons.append("control_semantic_requires_memory_unknown_or_true")
    return {
        **item,
        **audited,
        "semantic_requires_memory": semantic_requires_memory,
        "selection_role": "control_candidate" if eligible else "invalid_control_or_reject",
        "selection_eligible": eligible,
        "selection_rejection_reasons": reasons,
        "selection_score": 10 if eligible else 0,
    }


def _reason_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in records:
        reasons = item.get("selection_rejection_reasons") or []
        if not reasons and item.get("selection_eligible"):
            counts["selected_or_eligible"] = counts.get("selected_or_eligible", 0) + 1
        for reason in reasons:
            counts[str(reason)] = counts.get(str(reason), 0) + 1
    return counts


def _select(records: list[dict[str, Any]], limit: int, excluded_case_ids: set[str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    excluded = set(excluded_case_ids or set())
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    seen_traces: set[str] = set()
    seen_audit_ids: set[str] = set()
    for item in sorted(records, key=lambda row: (-int(row.get("selection_score") or 0), str(row.get("audit_case_id") or ""))):
        if not item.get("selection_eligible"):
            rejected.append(item)
            continue
        case_id = str(item.get("bfcl_case_id") or "")
        trace = str(item.get("trace_relative_path") or "")
        audit_id = str(item.get("audit_case_id") or "")
        reject_reason = None
        if case_id in excluded:
            reject_reason = "positive_control_overlap"
        elif case_id in seen_case_ids:
            reject_reason = "duplicate_bfcl_case_id_present"
        elif trace in seen_traces:
            reject_reason = "duplicate_trace_path_present"
        elif audit_id in seen_audit_ids:
            reject_reason = "duplicate_audit_case_id_present"
        elif len(selected) >= limit:
            reject_reason = "selection_limit_reached"
        if reject_reason:
            rejected.append({**item, "selection_eligible": False, "selection_rejection_reasons": [reject_reason]})
            continue
        seen_case_ids.add(case_id)
        seen_traces.add(trace)
        seen_audit_ids.add(audit_id)
        selected.append(item)
    return selected, rejected


def _unique_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "unique_bfcl_case_id_count": len({str(item.get("bfcl_case_id") or "") for item in records if item.get("bfcl_case_id")}),
        "unique_trace_relative_path_count": len({str(item.get("trace_relative_path") or "") for item in records if item.get("trace_relative_path")}),
        "unique_audit_case_id_count": len({str(item.get("audit_case_id") or "") for item in records if item.get("audit_case_id")}),
    }


def evaluate(protocol_path: Path = DEFAULT_PROTOCOL, source_root: Path = DEFAULT_SOURCE_ROOT, positive_limit: int = 12, control_limit: int = 8) -> dict[str, Any]:
    protocol = _load_json(protocol_path)
    protocol = protocol if isinstance(protocol, dict) else {}
    positive_records = _dedupe_records(_all_records(protocol, "selected_positive_cases", "positive_selection_rejections"))
    control_records = _dedupe_records(_all_records(protocol, "selected_control_cases", "control_selection_rejections"))
    classified_positives = [_classify_positive(item, source_root) for item in positive_records]
    preliminary_controls = [_classify_control(item, source_root) for item in control_records]
    selected_positives, rejected_positives = _select(classified_positives, positive_limit)
    positive_case_ids = {str(item.get("bfcl_case_id")) for item in selected_positives}
    selected_controls, rejected_controls = _select(preliminary_controls, control_limit, excluded_case_ids=positive_case_ids)
    selected = selected_positives + selected_controls
    unique = _unique_counts(selected)
    duplicate_selected = any(count != len(selected) for count in unique.values()) if selected else False
    positive_control_overlap_count = len({str(item.get("bfcl_case_id")) for item in selected_positives} & {str(item.get("bfcl_case_id")) for item in selected_controls})
    selected_control_activation_count = sum(1 for item in selected_controls if item.get("baseline_first_response_memory_call_count"))
    source_pool_negative_control_activation_count = int(protocol.get("source_pool_negative_control_activation_count") or 0)
    materialized_protocol_negative_control_activation_count = sum(1 for item in preliminary_controls if item.get("baseline_first_response_memory_call_count"))
    selection_gate_passed = bool(
        len(selected_positives) == positive_limit
        and len(selected_controls) == control_limit
        and not duplicate_selected
        and positive_control_overlap_count == 0
        and selected_control_activation_count == 0
    )
    blockers: list[str] = []
    if len(selected_positives) < positive_limit:
        blockers.append("blocked_insufficient_non_ceiling_positives")
    if len(selected_controls) < control_limit:
        blockers.append("blocked_insufficient_true_controls")
    if duplicate_selected:
        blockers.append("duplicate_selected_case_or_trace_present")
    if positive_control_overlap_count:
        blockers.append("positive_control_overlap_present")
    if selected_control_activation_count:
        blockers.append("selected_smoke_baseline_control_activation_present")
    return {
        "report_scope": "explicit_obligation_smoke_candidate_selection",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "protocol_path": str(protocol_path),
        "source_root": str(source_root),
        "selection_gate_passed": selection_gate_passed,
        "positive_target_count": positive_limit,
        "control_target_count": control_limit,
        "positive_pool_count": len(classified_positives),
        "control_pool_count": len(preliminary_controls),
        "non_ceiling_positive_available_count": sum(1 for item in classified_positives if item.get("selection_eligible")),
        "true_control_available_count": sum(1 for item in preliminary_controls if item.get("selection_eligible")),
        "selected_positive_count": len(selected_positives),
        "selected_control_count": len(selected_controls),
        "selected_case_count": len(selected),
        **unique,
        "positive_control_overlap_count": positive_control_overlap_count,
        "source_pool_negative_control_activation_count": source_pool_negative_control_activation_count,
        "materialized_protocol_negative_control_activation_count": materialized_protocol_negative_control_activation_count,
        "selected_smoke_baseline_control_activation_count": selected_control_activation_count,
        "positive_rejection_reason_counts": _reason_counts(classified_positives + rejected_positives),
        "control_rejection_reason_counts": _reason_counts(preliminary_controls + rejected_controls),
        "selected_positive_cases": selected_positives,
        "selected_control_cases": selected_controls,
        "positive_selection_audit_records": classified_positives,
        "control_selection_audit_records": preliminary_controls,
        "blockers": blockers,
        "next_required_action": "request_explicit_obligation_smoke_ready_check" if selection_gate_passed else "rebuild_candidate_pool_or_upgrade_theory_prior_before_smoke",
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Explicit Obligation Smoke Candidate Selection",
        "",
        f"- Selection gate passed: `{report['selection_gate_passed']}`",
        f"- Positive pool / selected: `{report['positive_pool_count']}` / `{report['selected_positive_count']}`",
        f"- Control pool / selected: `{report['control_pool_count']}` / `{report['selected_control_count']}`",
        f"- Non-ceiling positives available: `{report['non_ceiling_positive_available_count']}`",
        f"- True controls available: `{report['true_control_available_count']}`",
        f"- Unique BFCL case ids: `{report['unique_bfcl_case_id_count']}` / `{report['selected_case_count']}`",
        f"- Unique trace paths: `{report['unique_trace_relative_path_count']}` / `{report['selected_case_count']}`",
        f"- Unique audit ids: `{report['unique_audit_case_id_count']}` / `{report['selected_case_count']}`",
        f"- Source-pool negative-control activations: `{report['source_pool_negative_control_activation_count']}`",
        f"- Materialized protocol negative-control activations: `{report['materialized_protocol_negative_control_activation_count']}`",
        f"- Selected smoke baseline control activations: `{report['selected_smoke_baseline_control_activation_count']}`",
        f"- Candidate commands: `{report['candidate_commands']}`",
        f"- Planned commands: `{report['planned_commands']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "This selector is offline-only. It does not authorize scorer execution.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--positive-limit", type=int, default=12)
    parser.add_argument("--control-limit", type=int, default=8)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.protocol, args.source_root, args.positive_limit, args.control_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        keys = [
            "selection_gate_passed",
            "positive_pool_count",
            "control_pool_count",
            "non_ceiling_positive_available_count",
            "true_control_available_count",
            "selected_positive_count",
            "selected_control_count",
            "selected_smoke_baseline_control_activation_count",
            "source_pool_negative_control_activation_count",
            "materialized_protocol_negative_control_activation_count",
            "candidate_commands",
            "planned_commands",
            "blockers",
            "next_required_action",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    return 0 if report["selection_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
