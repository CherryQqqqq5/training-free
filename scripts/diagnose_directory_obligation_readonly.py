#!/usr/bin/env python3
"""Audit read-only directory obligation candidates from unmet postcondition records.

Offline-only diagnostic. It classifies directory/navigation strong-unmet records
into read-only directory obligations versus trajectory/stateful or mutation-like
cases. It does not authorize runtime, BFCL, model, or scorer execution.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts import diagnose_unmet_postcondition_source_expansion as unmet

DEFAULT_UNMET_AUDIT = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/unmet_postcondition_source_expansion_audit.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/directory_obligation_readonly_audit.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/directory_obligation_readonly_audit.md")

MUTATION_CUES = {"create", "write", "copy", "move", "rename", "delete", "remove", "modify", "edit", "append"}
READONLY_DIRECTORY_CUES = {"list", "show", "display", "current files", "files", "directory", "folder", "pwd", "where"}
TRAJECTORY_CUES = {"for each", "then", "after", "count", "open", "read", "search", "scour"}


def _contains_any(text: str, cues: set[str]) -> bool:
    lowered = text.lower()
    return any(cue in lowered for cue in cues)


def _classify(row: dict[str, Any]) -> dict[str, Any]:
    text = str(row.get("user_text_excerpt") or "")
    mutation = _contains_any(text, MUTATION_CUES)
    readonly = _contains_any(text, READONLY_DIRECTORY_CUES)
    trajectory = _contains_any(text, TRAJECTORY_CUES)
    if mutation:
        label = "reject_mutation_adjacent_directory_request"
        reason = "mutation_cue_present"
    elif readonly and not trajectory:
        label = "readonly_directory_obligation_candidate"
        reason = "readonly_directory_cue_without_trajectory_cue"
    elif readonly and trajectory:
        label = "diagnostic_stateful_directory_trajectory"
        reason = "directory_cue_with_followup_trajectory"
    else:
        label = "ambiguous_directory_obligation"
        reason = "directory_intent_not_specific_enough"
    return {
        "case_id": row.get("trace_id"),
        "trace_relative_path": row.get("trace_relative_path"),
        "postcondition_gap": row.get("postcondition_gap"),
        "recommended_tools": row.get("recommended_tools") or [],
        "required_evidence_type": row.get("required_evidence_type"),
        "observed_evidence_types": row.get("observed_evidence_types") or [],
        "user_text_excerpt": row.get("user_text_excerpt"),
        "directory_obligation_label": label,
        "classification_reason": reason,
        "mutation_cue_present": mutation,
        "readonly_directory_cue_present": readonly,
        "trajectory_cue_present": trajectory,
        "retain_prior_candidate": label == "readonly_directory_obligation_candidate",
    }


def evaluate(unmet_audit_path: Path = DEFAULT_UNMET_AUDIT) -> dict[str, Any]:
    if unmet_audit_path.exists():
        source = json.loads(unmet_audit_path.read_text(encoding="utf-8"))
        rows = list(source.get("sample_strong_unmet_candidates") or [])
    else:
        source = unmet.evaluate()
        rows = list(source.get("sample_strong_unmet_candidates") or [])
    directory_rows = [row for row in rows if row.get("postcondition_gap") == "directory_navigation"]
    records = [_classify(row) for row in directory_rows]
    counts = Counter(row["directory_obligation_label"] for row in records)
    candidate_count = int(counts.get("readonly_directory_obligation_candidate") or 0)
    return {
        "report_scope": "directory_obligation_readonly_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "directory_obligation_readonly_audit_ready": True,
        "directory_strong_unmet_records_scanned": len(directory_rows),
        "readonly_directory_obligation_candidate_count": candidate_count,
        "classification_distribution": dict(sorted(counts.items())),
        "records": records[:50],
        "next_required_action": "manual_review_before_theory_family" if candidate_count else "do_not_promote_directory_family_from_current_pool",
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Directory Obligation Read-Only Audit",
        "",
        f"- Ready: `{report['directory_obligation_readonly_audit_ready']}`",
        f"- Directory strong-unmet records scanned: `{report['directory_strong_unmet_records_scanned']}`",
        f"- Read-only directory candidates: `{report['readonly_directory_obligation_candidate_count']}`",
        f"- Classification distribution: `{report['classification_distribution']}`",
        f"- Next required action: `{report['next_required_action']}`",
        "",
        "Offline diagnostic only. It does not authorize BFCL/model/scorer runs.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unmet-audit", type=Path, default=DEFAULT_UNMET_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.unmet_audit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "directory_obligation_readonly_audit_ready": report["directory_obligation_readonly_audit_ready"],
            "directory_strong_unmet_records_scanned": report["directory_strong_unmet_records_scanned"],
            "readonly_directory_obligation_candidate_count": report["readonly_directory_obligation_candidate_count"],
            "classification_distribution": report["classification_distribution"],
            "next_required_action": report["next_required_action"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
