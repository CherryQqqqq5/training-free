#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_AUDIT = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/policy_conversion_opportunity_audit.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_policy_candidate_manifest.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_policy_family_card.md")

LOW_RISK_CAPABILITIES = {"read_content", "search_or_find"}
MEDIUM_RISK_CAPABILITIES = {"create_file", "write_content", "directory_navigation"}
HIGH_RISK_CAPABILITIES = {"copy", "move_or_rename"}
LOW_RISK_TOOLS = {"cat", "find", "grep"}
STATE_MUTATING_CAPABILITIES = MEDIUM_RISK_CAPABILITIES | HIGH_RISK_CAPABILITIES
RUNTIME_TRIGGER_FIELDS = [
    "postcondition_gap",
    "recommended_tools",
    "expected_observation_keys",
    "request_predicates",
    "failure_labels",
    "disambiguation_cue",
]
FORBIDDEN_TRIGGER_TOKENS = ("gold", "score", "scorer", "target_answer", "expected_answer", "bfcl_result")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _risk(row: dict[str, Any]) -> tuple[str, str]:
    cap = str(row.get("postcondition_gap") or "")
    if cap in LOW_RISK_CAPABILITIES:
        return "low", "read_or_search_postcondition_with_local_witness"
    if cap in MEDIUM_RISK_CAPABILITIES:
        return "medium", "state_mutating_or_navigation_policy_requires_reviewer_approval"
    if cap in HIGH_RISK_CAPABILITIES:
        return "high", "copy_or_move_policy_is_trajectory_sensitive"
    return "unknown", "capability_not_in_reviewed_risk_table"


def _audit_record_id(row: dict[str, Any], idx: int) -> str:
    payload = json.dumps({
        "idx": idx,
        "trace_relative_path": row.get("trace_relative_path"),
        "postcondition_gap": row.get("postcondition_gap"),
        "recommended_tools": row.get("recommended_tools") or [],
        "failure_labels": row.get("failure_labels") or [],
    }, sort_keys=True, ensure_ascii=False)
    return "pcop_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _text(row: dict[str, Any]) -> str:
    return str(row.get("user_text_excerpt") or "")


def _contains_word(text: str, word: str) -> bool:
    return re.search(r"(?<![a-z0-9_])" + re.escape(word) + r"(?![a-z0-9_])", text.lower()) is not None


def _ambiguity_flags(row: dict[str, Any], risk: str) -> list[str]:
    cap = str(row.get("postcondition_gap") or "")
    cue = str(row.get("disambiguation_cue") or "")
    text = _text(row)
    flags: set[str] = set()
    if cap == "create_file" and any(_contains_word(text, w) for w in ["directory", "folder"]):
        flags.add("directory_vs_file_ambiguous")
    if cap in {"copy", "move_or_rename"}:
        flags.add("copy_move_destructive")
    if cap == "write_content" and cue not in {"write", "append", "add content", "put", "save"}:
        flags.add("write_intent_unconfirmed")
    if cap in STATE_MUTATING_CAPABILITIES:
        flags.add("state_mutating_capability")
    if any(phrase in text.lower() for phrase in ["then", "after", "once", "while", "make sure", "and then"]):
        flags.add("multi_step_required")
    if cue and risk != "low" and len(cue) <= 6:
        flags.add("cue_only_match")
    return sorted(flags)


def _scan_forbidden_trigger_dependency(row: dict[str, Any]) -> dict[str, Any]:
    scanned: dict[str, Any] = {key: row.get(key) for key in RUNTIME_TRIGGER_FIELDS}
    serialized = json.dumps(scanned, ensure_ascii=False, sort_keys=True).lower()
    pointer_text = " ".join(str(row.get(key) or "") for key in ["trace_relative_path", "trace_id", "run_name"])
    case_like_in_trigger = bool(re.search(r"multi_turn_[a-z_]+_\d+", serialized))
    trace_id_in_trigger = bool(re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", serialized))
    forbidden_tokens = [token for token in FORBIDDEN_TRIGGER_TOKENS if token in serialized]
    return {
        "runtime_trigger_fields_scanned": RUNTIME_TRIGGER_FIELDS,
        "case_id_in_trigger_logic": case_like_in_trigger,
        "trace_id_in_trigger_logic": trace_id_in_trigger,
        "gold_or_scorer_token_in_trigger_logic": bool(forbidden_tokens),
        "forbidden_tokens": forbidden_tokens,
        "target_or_scorer_field_dependency": bool(row.get("target_or_scorer_field_dependency")),
        "audit_pointer_contains_trace_identity": bool(pointer_text),
        "audit_pointers_excluded_from_runtime_fields": True,
        "forbidden_dependency_present": bool(case_like_in_trigger or trace_id_in_trigger or forbidden_tokens or row.get("target_or_scorer_field_dependency")),
    }


def _dry_run_review(row: dict[str, Any], risk: str, flags: list[str], scan: dict[str, Any]) -> tuple[bool, str | None]:
    tools = set(str(tool) for tool in (row.get("recommended_tools") or []))
    if risk != "low":
        return False, "only_low_risk_read_search_allowed_for_first_dry_run_review"
    if not tools or not tools <= LOW_RISK_TOOLS:
        return False, "recommended_tool_not_in_low_risk_allowlist"
    if scan.get("forbidden_dependency_present"):
        return False, "forbidden_trigger_dependency_present"
    if not bool(row.get("precondition_observable")):
        return False, "precondition_not_observable"
    if not bool(row.get("postcondition_witness_available")):
        return False, "postcondition_witness_missing"
    if bool(row.get("exact_tool_choice")):
        return False, "exact_tool_choice_not_allowed"
    if "postcondition_already_satisfied" in flags:
        return False, "postcondition_already_satisfied"
    return True, None


def evaluate(audit_path: Path = DEFAULT_AUDIT) -> dict[str, Any]:
    audit = _load(audit_path)
    rows = list(audit.get("candidate_records") or audit.get("sample_candidates") or [])
    manifest_rows = []
    for idx, row in enumerate(rows):
        risk, reason = _risk(row)
        flags = _ambiguity_flags(row, risk)
        forbidden_scan = _scan_forbidden_trigger_dependency(row)
        dry_run_ok, dry_run_rejection = _dry_run_review(row, risk, flags, forbidden_scan)
        retained = {
            "candidate_id": f"postcondition_guided_trajectory_policy_{idx:04d}",
            "source_audit_record_id": _audit_record_id(row, idx),
            "source_audit_record_pointer": row.get("trace_relative_path"),
            "trace_relative_path": row.get("trace_relative_path"),
            "run_name": row.get("run_name"),
            "policy_family": "postcondition_guided_trajectory_policy",
            "theory_class": "postcondition_guided_trajectory_progress",
            "postcondition_gap": row.get("postcondition_gap"),
            "recommended_tools": row.get("recommended_tools") or [],
            "available_tools": row.get("available_tools") or [],
            "expected_observation_keys": row.get("expected_observation_keys") or [],
            "request_predicates": row.get("request_predicates") or [],
            "failure_labels": row.get("failure_labels") or [],
            "disambiguation_cue": row.get("disambiguation_cue"),
            "rejection_reason": row.get("rejection_reason"),
            "ambiguity_flags": flags,
            "negative_control_bucket": "positive_policy_candidate",
            "forbidden_field_scan": forbidden_scan,
            "precondition_observable": bool(row.get("precondition_observable")),
            "postcondition_witness_available": bool(row.get("postcondition_witness_available")),
            "target_or_scorer_field_dependency": bool(row.get("target_or_scorer_field_dependency")),
            "intervention_strength": "guidance_only",
            "exact_tool_choice": False,
            "retention_eligibility": "diagnostic_only_until_family_review",
            "risk_level": risk,
            "risk_reason": reason,
            "runtime_enabled": False,
            "requires_reviewer_approval_before_runtime": True,
            "low_risk_dry_run_review_eligible": dry_run_ok,
            "dry_run_review_rejection_reason": dry_run_rejection,
        }
        manifest_rows.append(retained)
    risk_counts = Counter(row["risk_level"] for row in manifest_rows)
    cap_counts = Counter(str(row.get("postcondition_gap") or "unknown") for row in manifest_rows)
    flag_counts = Counter(flag for row in manifest_rows for flag in row.get("ambiguity_flags") or [])
    low_risk_eligible = sum(1 for row in manifest_rows if row.get("low_risk_dry_run_review_eligible"))
    return {
        "report_scope": "postcondition_guided_policy_candidate_manifest",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "runtime_enabled": False,
        "policy_family": "postcondition_guided_trajectory_policy",
        "theory_class": "postcondition_guided_trajectory_progress",
        "family_card_status": "review_required_before_runtime_integration",
        "first_runtime_review_scope": "low_risk_read_search_only",
        "admission_criteria": [
            "no_tool_policy_failure_label_present",
            "rule_hit_present",
            "prior_tool_observation_or_predicate_present",
            "recommended_tool_is_available_in_schema",
            "postcondition_witness_declared",
            "guidance_only",
            "exact_tool_choice_false",
            "no_target_or_scorer_field_dependency",
        ],
        "rejection_criteria": [
            "case_id_or_gold_answer_dependency",
            "recommended_tool_not_in_schema",
            "no_observable_prior_context",
            "destructive_or_state_mutating_tool_without_explicit_intent",
            "copy_move_or_directory_policy_without_reviewer_approval",
            "exact_tool_choice_required",
            "argument_creation_or_binding_not_allowed_in_this_family",
        ],
        "hard_invariants": [
            "progress_invariant_unsatisfied_postcondition_only",
            "non_satisfaction_invariant_no_activation_when_witness_already_present",
            "schema_availability_invariant_recommended_tool_in_current_schema",
            "guidance_only_invariant_no_exact_tool_choice",
            "argument_non_creation_invariant_policy_recommends_capability_only",
            "state_mutation_invariant_medium_high_require_reviewer_approval",
        ],
        "negative_controls_required": [
            "activation_near_zero_on_no_toolless_failure_slices",
            "activation_near_zero_when_required_postcondition_already_satisfied",
            "no_activation_without_available_recommended_tool",
            "no_activation_without_prior_observation",
            "destructive_false_positive_count_zero",
            "target_or_scorer_dependency_count_zero",
        ],
        "candidate_count": len(manifest_rows),
        "low_risk_dry_run_review_eligible_count": low_risk_eligible,
        "risk_level_distribution": dict(sorted(risk_counts.items())),
        "capability_distribution": dict(sorted(cap_counts.items())),
        "ambiguity_flag_distribution": dict(sorted(flag_counts.items())),
        "candidate_records": manifest_rows,
        "candidate_commands": [],
        "planned_commands": [],
        "next_required_action": "manifest_boundary_review_and_negative_control_audit_before_runtime_compiler",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Postcondition-Guided Trajectory Policy Family Card",
        "",
        "Status: `review_required_before_runtime_integration`",
        "",
        "This is an offline theory-prior family card. It does not enable runtime policy execution and does not authorize BFCL/model/scorer runs.",
        "",
        f"- Candidate count: `{report['candidate_count']}`",
        f"- Low-risk dry-run review eligible: `{report['low_risk_dry_run_review_eligible_count']}`",
        f"- Risk distribution: `{report['risk_level_distribution']}`",
        f"- Capability distribution: `{report['capability_distribution']}`",
        f"- Ambiguity flags: `{report['ambiguity_flag_distribution']}`",
        "",
        "## Theory Prior",
        "",
        "A tool-use trajectory should not terminate in prose when an unsatisfied, observable postcondition can be advanced by an available schema-local tool. The policy recommends a capability/tool family only; it does not create arguments, force exact tool choice, or encode case-specific values.",
        "",
        "## Hard Invariants",
        "",
    ]
    lines.extend(f"- `{item}`" for item in report["hard_invariants"])
    lines.extend(["", "## Admission Criteria", ""])
    lines.extend(f"- `{item}`" for item in report["admission_criteria"])
    lines.extend(["", "## Rejection Criteria", ""])
    lines.extend(f"- `{item}`" for item in report["rejection_criteria"])
    lines.extend(["", "## Negative Controls Required", ""])
    lines.extend(f"- `{item}`" for item in report["negative_controls_required"])
    lines.extend([
        "",
        "## First Runtime Review Boundary",
        "",
        "Only `read_content` and `search_or_find` low-risk candidates may be considered for a later dry-run review. Medium/high risk capabilities remain diagnostic-only until explicitly approved.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.audit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "family_card_status",
            "candidate_count",
            "low_risk_dry_run_review_eligible_count",
            "risk_level_distribution",
            "capability_distribution",
            "ambiguity_flag_distribution",
            "runtime_enabled",
            "next_required_action",
        ]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
