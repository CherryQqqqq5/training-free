#!/usr/bin/env python3
"""Audit explicit-obligation to observable-capability theory-prior coverage.

Offline-only. This audit unifies existing memory, postcondition, and directory
artifacts into a single retain-prior view. It emits no scorer commands.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from grc.compiler.retention_priors import DEMOTE_CANDIDATE, evaluate_retention_prior

DEFAULT_MEMORY = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_obligation_audit.json")
DEFAULT_UNMET = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/unmet_postcondition_source_expansion_audit.json")
DEFAULT_DIRECTORY = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/directory_obligation_readonly_audit.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_observable_capability_audit.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_observable_capability_audit.md")
FAMILY = "explicit_obligation_to_observable_capability_v1"
READONLY_TOOLS = {"cat", "tail", "grep", "find", "ls", "pwd", "wc"}


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _prior(row: dict[str, Any]) -> dict[str, Any]:
    return evaluate_retention_prior(row)


def _base_record(**kw: Any) -> dict[str, Any]:
    row = {
        "rule_type": FAMILY,
        "candidate_rules_type": FAMILY,
        "soft_guidance_only": True,
        "exact_tool_choice": False,
        "argument_creation": False,
        "tool_choice_mutation": False,
        "trajectory_mutation": False,
        "forbidden_dependency_present": False,
        "candidate_commands": [],
        "planned_commands": [],
    }
    row.update(kw)
    prior = _prior(row)
    row["retention_prior"] = prior
    row["retain_prior_candidate"] = prior.get("retain_eligibility") == DEMOTE_CANDIDATE
    if not row["retain_prior_candidate"] and not row.get("blocked_reason"):
        row["blocked_reason"] = prior.get("prior_rejection_reason") or "not_demote_candidate"
    return row


def _memory_records(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in report.get("candidate_records") or []:
        if not isinstance(item, dict):
            continue
        ready = item.get("candidate_ready") is True and item.get("risk_level") == "low" and item.get("operation") == "retrieve"
        witness = "unmet_strong" if item.get("memory_witness_strength") == "no_witness" else "satisfied_weak"
        rows.append(_base_record(
            record_id=item.get("candidate_id"),
            source_artifact="memory_operation_obligation_audit",
            benchmark_slice="memory",
            user_obligation_text_span=item.get("operation_cue"),
            explicit_obligation_type="memory_retrieve" if ready else "none",
            obligation_source="current_user_turn",
            required_evidence_type="memory_value",
            observed_evidence_types=item.get("memory_postcondition_witnesses") or [],
            compatible_witness_status=witness,
            satisfaction_reason=item.get("memory_witness_strength"),
            available_capability_families=["memory_retrieve"],
            recommended_capability_family="memory_retrieve",
            capability_risk_tier="readonly_low" if ready else "unknown",
            explicit_obligation_present=ready,
            eligible=ready,
            blocked_reason=None if ready else (item.get("rejection_reason") or "not_low_risk_memory_retrieve"),
            negative_control_type="none" if ready else "weak_witness",
            expected_activation=ready,
            actual_activation=None,
            trace_relative_path=item.get("trace_relative_path"),
        ))
    return rows


def _unmet_records(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    samples = []
    for key in ("sample_low_risk_strong_unmet_candidates", "sample_high_risk_strong_unmet_candidates", "sample_satisfied_strong", "sample_satisfied_weak"):
        for item in report.get(key) or []:
            if isinstance(item, dict):
                samples.append((key, item))
    for bucket, item in samples:
        recommended = item.get("recommended_tools") or []
        gap = item.get("postcondition_gap") or "unknown"
        low_risk = bool(item.get("low_risk_observation_candidate"))
        strong_unmet = item.get("typed_satisfaction_label") == "unmet_strong"
        family = "read_content" if gap == "read_content" else "search_or_find" if gap in {"search", "search_or_find"} else "directory_readonly" if gap == "directory_navigation" else "none"
        compatible_tool = any(str(tool) in READONLY_TOOLS for tool in recommended)
        eligible = low_risk and strong_unmet and family != "none" and compatible_tool
        reason = None
        if not strong_unmet:
            reason = "already_satisfied_or_weak_witness"
        elif not low_risk:
            reason = "mutation_or_trajectory_risk"
        elif family == "none" or not compatible_tool:
            reason = "capability_not_readonly_low_or_not_allowed"
        rows.append(_base_record(
            record_id=item.get("trace_id"),
            source_artifact="unmet_postcondition_source_expansion_audit",
            benchmark_slice="multi_turn",
            user_obligation_text_span=item.get("user_text_excerpt"),
            explicit_obligation_type=family,
            obligation_source="current_user_turn",
            required_evidence_type=item.get("required_evidence_type") or "unknown",
            observed_evidence_types=item.get("observed_evidence_types") or [],
            compatible_witness_status="unmet_strong" if strong_unmet else "satisfied_weak",
            satisfaction_reason=item.get("typed_satisfaction_reason"),
            available_capability_families=[family] if family != "none" else [],
            recommended_capability_family=family,
            capability_risk_tier="readonly_low" if low_risk and compatible_tool else "unknown",
            explicit_obligation_present=family != "none",
            eligible=eligible,
            blocked_reason=reason,
            negative_control_type="none" if eligible else ("already_satisfied" if not strong_unmet else "mutation_only"),
            expected_activation=eligible,
            actual_activation=None,
            trace_relative_path=item.get("trace_relative_path"),
        ))
    return rows


def _directory_records(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in report.get("records") or []:
        if not isinstance(item, dict):
            continue
        label = item.get("directory_obligation_label")
        recommended = item.get("recommended_tools") or []
        compatible_tool = any(str(tool) in {"ls", "pwd", "find"} for tool in recommended)
        eligible = label == "readonly_directory_obligation_candidate" and compatible_tool and not item.get("mutation_cue_present")
        reason = None if eligible else "trajectory_navigation_tool_not_p0" if label == "readonly_directory_obligation_candidate" else str(label or "not_directory_candidate")
        rows.append(_base_record(
            record_id=item.get("case_id"),
            source_artifact="directory_obligation_readonly_audit",
            benchmark_slice="multi_turn_directory",
            user_obligation_text_span=item.get("user_text_excerpt"),
            explicit_obligation_type="directory_readonly",
            obligation_source="current_user_turn",
            required_evidence_type=item.get("required_evidence_type") or "directory_listing",
            observed_evidence_types=item.get("observed_evidence_types") or [],
            compatible_witness_status="unmet_strong" if label == "readonly_directory_obligation_candidate" else "ambiguous",
            satisfaction_reason=item.get("classification_reason"),
            available_capability_families=["directory_readonly"],
            recommended_capability_family="directory_readonly",
            capability_risk_tier="readonly_low" if compatible_tool and not item.get("mutation_cue_present") else "unknown",
            explicit_obligation_present=bool(item.get("readonly_directory_cue_present")),
            eligible=eligible,
            blocked_reason=reason,
            negative_control_type="none" if eligible else "mutation_only" if item.get("mutation_cue_present") else "weak_witness",
            expected_activation=eligible,
            actual_activation=None,
            trace_relative_path=item.get("trace_relative_path"),
        ))
    return rows


def evaluate(memory_path: Path = DEFAULT_MEMORY, unmet_path: Path = DEFAULT_UNMET, directory_path: Path = DEFAULT_DIRECTORY) -> dict[str, Any]:
    records = []
    records.extend(_memory_records(_load(memory_path)))
    records.extend(_unmet_records(_load(unmet_path)))
    records.extend(_directory_records(_load(directory_path)))
    eligible = [row for row in records if row.get("retain_prior_candidate")]
    blocked = [row for row in records if not row.get("retain_prior_candidate")]
    eligible_by_capability = Counter(str(row.get("recommended_capability_family") or "unknown") for row in eligible)
    blocked_by_reason = Counter(str(row.get("blocked_reason") or "unknown") for row in blocked)
    witness_counts = Counter(str(row.get("compatible_witness_status") or "unknown") for row in records)
    exact_tool = sum(1 for row in records if row.get("exact_tool_choice") is True)
    arg_creation = sum(1 for row in records if row.get("argument_creation") is True)
    mutation = sum(1 for row in records if row.get("capability_risk_tier") == "mutation_high")
    forbidden = sum(1 for row in records if row.get("forbidden_dependency_present") is True)
    smoke_ready = len(eligible_by_capability) >= 2 and not exact_tool and not arg_creation and not mutation and not forbidden
    blockers = []
    if len(eligible_by_capability) < 2:
        blockers.append("eligible_capability_family_count_below_2")
    if exact_tool:
        blockers.append("exact_tool_choice_present")
    if arg_creation:
        blockers.append("argument_creation_present")
    if mutation:
        blockers.append("mutation_capability_recommended")
    if forbidden:
        blockers.append("forbidden_dependency_present")
    return {
        "report_scope": "explicit_obligation_observable_capability_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "rule_family": FAMILY,
        "theory_class": "trajectory_evidence_sufficiency",
        "record_count_scanned": len(records),
        "explicit_obligation_count": sum(1 for row in records if row.get("explicit_obligation_present")),
        "eligible_candidate_count": len(eligible),
        "eligible_by_capability": dict(sorted(eligible_by_capability.items())),
        "blocked_by_reason": dict(sorted(blocked_by_reason.items())),
        "compatible_witness_status_distribution": dict(sorted(witness_counts.items())),
        "negative_control_candidate_count": sum(1 for row in records if row.get("negative_control_type") != "none"),
        "negative_control_activation_count": 0,
        "exact_tool_choice_by_rule_count": exact_tool,
        "argument_creation_by_rule_count": arg_creation,
        "mutation_capability_recommended_count": mutation,
        "forbidden_dependency_count": forbidden,
        "retain_prior_coverage_ready": smoke_ready,
        "performance_claim_ready": False,
        "smoke_ready": smoke_ready,
        "blockers": blockers,
        "records_sample": records[:30],
        "next_required_action": "build_multi_family_smoke_protocol" if smoke_ready else "expand_read_search_directory_obligation_families_before_smoke",
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Explicit Obligation To Observable Capability Audit",
        "",
        f"- Retain-prior coverage ready: `{report['retain_prior_coverage_ready']}`",
        f"- Smoke ready: `{report['smoke_ready']}`",
        f"- Performance claim ready: `{report['performance_claim_ready']}`",
        f"- Records scanned: `{report['record_count_scanned']}`",
        f"- Explicit obligations: `{report['explicit_obligation_count']}`",
        f"- Eligible candidates: `{report['eligible_candidate_count']}`",
        f"- Eligible by capability: `{report['eligible_by_capability']}`",
        f"- Blocked by reason: `{report['blocked_by_reason']}`",
        f"- Witness status distribution: `{report['compatible_witness_status_distribution']}`",
        f"- Negative-control activations: `{report['negative_control_activation_count']}`",
        f"- Exact tool / arg creation / mutation counts: `{report['exact_tool_choice_by_rule_count']}` / `{report['argument_creation_by_rule_count']}` / `{report['mutation_capability_recommended_count']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "Offline diagnostic only. It does not authorize BFCL/model/scorer runs.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory", type=Path, default=DEFAULT_MEMORY)
    parser.add_argument("--unmet", type=Path, default=DEFAULT_UNMET)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.memory, args.unmet, args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "retain_prior_coverage_ready": report["retain_prior_coverage_ready"],
            "smoke_ready": report["smoke_ready"],
            "performance_claim_ready": report["performance_claim_ready"],
            "eligible_candidate_count": report["eligible_candidate_count"],
            "eligible_by_capability": report["eligible_by_capability"],
            "negative_control_activation_count": report["negative_control_activation_count"],
            "blockers": report["blockers"],
            "next_required_action": report["next_required_action"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
