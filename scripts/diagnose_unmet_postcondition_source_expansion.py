#!/usr/bin/env python3
"""Audit strong-unmet postcondition opportunities with typed evidence compatibility.

This is offline-only. It reads existing validation traces and classifies whether a
postcondition gap is truly unmet, already satisfied, weakly satisfied, or
ambiguous. It does not call BFCL, models, or scorers.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts import diagnose_policy_conversion_opportunities as base

DEFAULT_TRACE_ROOT = Path("outputs/phase2_validation/required_next_tool_choice_v1")
DEFAULT_OUT = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/unmet_postcondition_source_expansion_audit.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/unmet_postcondition_source_expansion_audit.md")
LOW_RISK_OBSERVATION_CAPABILITIES = {"read_content", "search_or_find", "memory_recall"}


def _required_evidence_type(capability: str | None, user_text: str) -> str | None:
    text = user_text.lower()
    if capability == "read_content":
        if any(token in text for token in ["list", "directory", "folder", "files in"]):
            return "directory_listing"
        if any(token in text for token in ["last line", "last lines", "tail", "recent line"]):
            return "tail_recent_lines"
        if any(token in text for token in ["sort", "sorted"]):
            return "sorted_or_transformed_content"
        return "full_content"
    if capability == "search_or_find":
        return "search_match"
    if capability == "compare":
        return "diff_or_change_summary"
    if capability == "directory_navigation":
        return "current_working_directory"
    if capability == "memory_recall":
        return "memory_value"
    if capability in {"create_file", "write_content", "copy", "move_or_rename"}:
        return "state_mutation_confirmation"
    return None


def _observed_evidence_types(request: dict[str, Any]) -> tuple[list[str], list[str]]:
    observed: set[str] = set()
    keys: set[str] = set()
    for payload in base._tool_output_payloads(request):
        flat = base._flatten_keys(payload)
        keys.update(flat)
        if {"file_content", "content", "result"} & flat:
            observed.add("full_content")
        if "matching_lines" in flat or "matches" in flat or "matching_results" in flat:
            observed.add("search_match")
        if "current_directory_content" in flat:
            observed.add("directory_listing")
        if "diff_lines" in flat or "diff" in flat or "comparison_result" in flat:
            observed.add("diff_or_change_summary")
        if "last_lines" in flat:
            observed.add("tail_recent_lines")
        if "sorted_content" in flat:
            observed.add("sorted_or_transformed_content")
        if "current_working_directory" in flat or "cwd" in flat:
            observed.add("current_working_directory")
        if "memory_records" in flat or "memories" in flat or "records" in flat:
            observed.add("memory_value")
        if "error" in flat:
            observed.add("error_observation")
        if {"file_exists", "created", "written", "updated", "target_path_changed"} & flat:
            observed.add("state_mutation_confirmation")
    return sorted(observed), sorted(keys)


def _satisfaction_label(required: str | None, observed: list[str]) -> tuple[str, str]:
    if required is None:
        return "ambiguous", "required_evidence_type_unknown"
    obs = set(observed)
    if required in obs:
        return "satisfied_strong", "required_evidence_observed"
    if not obs or obs == {"error_observation"}:
        return "unmet_strong", "required_evidence_absent"
    weak_relations = {
        "full_content": {"directory_listing", "search_match", "tail_recent_lines", "sorted_or_transformed_content"},
        "search_match": {"directory_listing", "full_content"},
        "diff_or_change_summary": {"directory_listing", "full_content"},
        "state_mutation_confirmation": {"directory_listing", "full_content", "current_working_directory"},
    }
    if obs & weak_relations.get(required, set()):
        return "satisfied_weak", "related_but_not_exact_evidence_observed"
    if "error_observation" in obs:
        return "unmet_strong", "tool_error_without_required_evidence"
    return "ambiguous", "observed_evidence_not_compatible_with_required_type"


def _record_from_trace(path: Path, root: Path) -> dict[str, Any] | None:
    payload = base._load_json(path)
    if not isinstance(payload, dict):
        return None
    request = base._request(payload)
    validation = base._validation(payload)
    user_text = base._user_text(request)
    available = base._available_tools(request)
    capability, recommended, witnesses, cue = base._infer_capability(user_text, available)
    labels = [str(item) for item in validation.get("failure_labels") or []]
    predicates = [str(item) for item in validation.get("request_predicates") or []]
    rule_hits = [str(item) for item in validation.get("rule_hits") or []]
    observed_types, observed_keys = _observed_evidence_types(request)
    required_type = _required_evidence_type(capability, user_text)
    label, reason = _satisfaction_label(required_type, observed_types)
    base_record = base._record_from_trace(path, root) or {}
    policy_failure = bool(set(labels) & base.NO_TOOL_POLICY_LABELS)
    strong_unmet_candidate = bool(
        policy_failure
        and recommended
        and rule_hits
        and ("prior_tool_outputs_present" in predicates or base._prior_tool_output_present(request))
        and label == "unmet_strong"
    )
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    risk_lane = "low_risk_observation" if capability in LOW_RISK_OBSERVATION_CAPABILITIES else "high_risk_mutation_or_trajectory"
    return {
        "trace_path": str(path),
        "trace_relative_path": rel,
        "trace_id": path.stem,
        "run_name": rel.split("/", 1)[0] if "/" in rel else None,
        "failure_labels": labels,
        "request_predicates": predicates,
        "rule_hits": rule_hits,
        "available_tools": available,
        "user_text_excerpt": user_text[:240],
        "postcondition_gap": capability,
        "disambiguation_cue": cue,
        "recommended_tools": recommended,
        "expected_observation_keys": witnesses,
        "required_evidence_type": required_type,
        "observed_evidence_types": observed_types,
        "observed_tool_output_keys": observed_keys,
        "typed_satisfaction_label": label,
        "typed_satisfaction_reason": reason,
        "strong_unmet_candidate": strong_unmet_candidate,
        "postcondition_risk_lane": risk_lane,
        "low_risk_observation_candidate": bool(strong_unmet_candidate and risk_lane == "low_risk_observation"),
        "base_candidate_ready": bool(base_record.get("candidate_ready")),
        "base_rejection_reason": base_record.get("rejection_reason"),
        "candidate_commands": [],
        "planned_commands": [],
    }


def evaluate(trace_root: Path = DEFAULT_TRACE_ROOT) -> dict[str, Any]:
    records = [row for path in base._trace_files(trace_root) if (row := _record_from_trace(path, trace_root)) is not None]
    label_counts = Counter(row["typed_satisfaction_label"] for row in records)
    capability_counts = Counter(str(row.get("postcondition_gap") or "unknown") for row in records)
    strong = [row for row in records if row.get("strong_unmet_candidate")]
    low_risk_strong = [row for row in strong if row.get("postcondition_risk_lane") == "low_risk_observation"]
    high_risk_strong = [row for row in strong if row.get("postcondition_risk_lane") == "high_risk_mutation_or_trajectory"]
    return {
        "report_scope": "unmet_postcondition_source_expansion_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "trace_root": str(trace_root),
        "unmet_postcondition_source_expansion_audit_ready": bool(records),
        "trace_count": len(records),
        "typed_satisfaction_distribution": dict(sorted(label_counts.items())),
        "capability_distribution": dict(sorted(capability_counts.items())),
        "strong_unmet_candidate_count": len(strong),
        "low_risk_strong_unmet_candidate_count": len(low_risk_strong),
        "high_risk_strong_unmet_candidate_count": len(high_risk_strong),
        "strong_unmet_capability_distribution": dict(sorted(Counter(str(row.get("postcondition_gap") or "unknown") for row in strong).items())),
        "strong_unmet_risk_lane_distribution": dict(sorted(Counter(str(row.get("postcondition_risk_lane") or "unknown") for row in strong).items())),
        "sample_strong_unmet_candidates": strong[:30],
        "sample_low_risk_strong_unmet_candidates": low_risk_strong[:30],
        "sample_high_risk_strong_unmet_candidates": high_risk_strong[:30],
        "sample_satisfied_strong": [row for row in records if row["typed_satisfaction_label"] == "satisfied_strong"][:20],
        "sample_satisfied_weak": [row for row in records if row["typed_satisfaction_label"] == "satisfied_weak"][:20],
        "sample_ambiguous": [row for row in records if row["typed_satisfaction_label"] == "ambiguous"][:20],
        "full_records_omitted_for_compact_artifact": True,
        "candidate_commands": [],
        "planned_commands": [],
        "next_required_action": "build_high_precision_low_risk_postcondition_policy_pool" if len(low_risk_strong) >= 9 else "expand_source_or_state_abstraction_before_smoke",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Unmet Postcondition Source Expansion Audit",
        "",
        f"- Ready: `{report['unmet_postcondition_source_expansion_audit_ready']}`",
        f"- Trace count: `{report['trace_count']}`",
        f"- Typed satisfaction distribution: `{report['typed_satisfaction_distribution']}`",
        f"- Capability distribution: `{report['capability_distribution']}`",
        f"- Strong unmet candidate count: `{report['strong_unmet_candidate_count']}`",
        f"- Low-risk strong unmet candidate count: `{report['low_risk_strong_unmet_candidate_count']}`",
        f"- High-risk strong unmet candidate count: `{report['high_risk_strong_unmet_candidate_count']}`",
        f"- Strong unmet capability distribution: `{report['strong_unmet_capability_distribution']}`",
        f"- Strong unmet risk lane distribution: `{report['strong_unmet_risk_lane_distribution']}`",
        f"- Full records omitted for compact artifact: `{report['full_records_omitted_for_compact_artifact']}`",
        f"- Next required action: `{report['next_required_action']}`",
        "",
        "Offline diagnostic only. It does not authorize BFCL/model/scorer runs.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.trace_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "unmet_postcondition_source_expansion_audit_ready": report["unmet_postcondition_source_expansion_audit_ready"],
            "trace_count": report["trace_count"],
            "typed_satisfaction_distribution": report["typed_satisfaction_distribution"],
            "strong_unmet_candidate_count": report["strong_unmet_candidate_count"],
            "low_risk_strong_unmet_candidate_count": report["low_risk_strong_unmet_candidate_count"],
            "high_risk_strong_unmet_candidate_count": report["high_risk_strong_unmet_candidate_count"],
            "strong_unmet_capability_distribution": report["strong_unmet_capability_distribution"],
            "strong_unmet_risk_lane_distribution": report["strong_unmet_risk_lane_distribution"],
            "next_required_action": report["next_required_action"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
