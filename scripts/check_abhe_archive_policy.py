#!/usr/bin/env python3
"""Check the ABHE behavior archive and opportunity table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_ARCHIVE = Path("abhe_archive/archive_index.json")
DEFAULT_OPPORTUNITY = Path("abhe_archive/opportunity_table.json")

REQUIRED_ENTRY_FIELDS = {
    "entry_id",
    "target_behavior_cluster",
    "source_evidence_count",
    "coverage_strata",
    "status",
    "mechanism_hypothesis",
    "risk_flags",
    "recommended_action",
    "dev_feedback_history",
    "state_transition_history",
}
REQUIRED_FALSE_KEYS = {
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "candidate_generation_authorized",
    "candidate_jsonl_authorized",
    "candidate_activation_authorized",
    "candidate_pool_ready",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
}
ALLOWED_STATUSES = {
    "observed_cluster",
    "seed_archive_entry",
    "proposal_ready",
    "dev_smoke_requested",
    "watch",
    "dev_smoke_authorized",
    "dev_smoke_executed",
    "dev_passed",
    "narrow_router_requested",
    "split_requested",
    "demoted",
    "rejected",
    "rejected_boundary_failure",
    "demoted_no_mechanism_signal",
    "demoted_regression_not_controlled",
    "holdout_requested",
    "holdout_authorized",
    "holdout_passed",
}
PROPOSAL_READY_ACTION = "request_bounded_dev_smoke"
WATCH_ACTION = "split_or_collect_more_compact_diagnostics"
CATEGORY_BOUND_BAD_PREFIXES = ("bfcl_", "multi_turn_", "agentic_memory_", "agentic_web_search_")


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _false_key_blockers(data: Dict[str, Any], prefix: str) -> List[str]:
    blockers = []
    for key in sorted(REQUIRED_FALSE_KEYS):
        if data.get(key) is not False:
            blockers.append("%s_%s_not_false:%r" % (prefix, key, data.get(key)))
    return blockers


def validate_entry(entry: Dict[str, Any]) -> List[str]:
    blockers = []
    entry_id = str(entry.get("entry_id", "<unknown>"))
    missing = sorted(REQUIRED_ENTRY_FIELDS - set(entry))
    if missing:
        blockers.append("entry_%s_missing_fields:%s" % (entry_id, ",".join(missing)))
        return blockers
    if entry_id.startswith(CATEGORY_BOUND_BAD_PREFIXES):
        blockers.append("entry_%s_category_bound_or_legacy_name" % entry_id)
    if entry.get("status") not in ALLOWED_STATUSES:
        blockers.append("entry_%s_status_invalid:%r" % (entry_id, entry.get("status")))
    if not isinstance(entry.get("source_evidence_count"), int) or entry["source_evidence_count"] <= 0:
        blockers.append("entry_%s_source_evidence_count_invalid:%r" % (entry_id, entry.get("source_evidence_count")))
    if not isinstance(entry.get("coverage_strata"), list) or not entry["coverage_strata"]:
        blockers.append("entry_%s_coverage_strata_empty" % entry_id)
    if entry.get("status") == "proposal_ready" and entry.get("recommended_action") != PROPOSAL_READY_ACTION:
        blockers.append("entry_%s_proposal_action_invalid:%r" % (entry_id, entry.get("recommended_action")))
    if entry.get("status") == "watch" and entry.get("recommended_action") != WATCH_ACTION:
        blockers.append("entry_%s_watch_action_invalid:%r" % (entry_id, entry.get("recommended_action")))
    if entry.get("dev_feedback_history") != []:
        blockers.append("entry_%s_dev_feedback_history_must_be_empty_pre_dev" % entry_id)
    if not isinstance(entry.get("state_transition_history"), list) or not entry["state_transition_history"]:
        blockers.append("entry_%s_state_transition_history_empty" % entry_id)
    blockers.extend(scan_value(entry, label="entry_%s" % entry_id))
    return sorted(set(blockers))


def validate_archive(archive: Dict[str, Any], opportunity: Dict[str, Any]) -> List[str]:
    blockers = []
    expected = {
        "artifact_kind": "abhe_archive_index",
        "schema_version": "abhe_archive_v0",
        "archive_scope": "behavior_level_archive_not_bfcl_category_skill_mapping",
        "bfcl_category_role": "sampling_reporting_validation_strata_only",
        "source_evidence_role": "discovery_archive_seed_only",
        "not_bfcl_category_bound": True,
        "total_compact_source_cases": 160,
        "raw_material_persisted": False,
    }
    for key, value in expected.items():
        if archive.get(key) != value:
            blockers.append("archive_%s_invalid:%r" % (key, archive.get(key)))
    blockers.extend(_false_key_blockers(archive, "archive"))
    entries = archive.get("entries")
    if not isinstance(entries, list) or not entries:
        blockers.append("archive_entries_missing_or_empty")
        return sorted(set(blockers))
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            blockers.append("archive_entry_not_object:%r" % entry)
            continue
        entry_id = entry.get("entry_id")
        if entry_id in seen:
            blockers.append("archive_duplicate_entry_id:%r" % entry_id)
        seen.add(entry_id)
        blockers.extend(validate_entry(entry))
    opp_entries = opportunity.get("entries") if isinstance(opportunity.get("entries"), list) else []
    opp_by_id = {row.get("entry_id"): row for row in opp_entries if isinstance(row, dict)}
    if set(seen) != set(opp_by_id):
        blockers.append("opportunity_entry_set_mismatch")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        row = opp_by_id.get(entry.get("entry_id"))
        if not row:
            continue
        for key in ("status", "target_behavior_cluster", "source_evidence_count"):
            if row.get(key) != entry.get(key):
                blockers.append("opportunity_%s_%s_mismatch" % (entry.get("entry_id"), key))
        if row.get("action") != entry.get("recommended_action"):
            blockers.append("opportunity_%s_action_mismatch" % entry.get("entry_id"))
    if opportunity.get("artifact_kind") != "abhe_opportunity_table":
        blockers.append("opportunity_artifact_kind_invalid:%r" % opportunity.get("artifact_kind"))
    if opportunity.get("performance_evidence") is not False:
        blockers.append("opportunity_performance_evidence_not_false")
    if opportunity.get("scorer_authorized") is not False:
        blockers.append("opportunity_scorer_authorized_not_false")
    if opportunity.get("candidate_pool_ready") is not False:
        blockers.append("opportunity_candidate_pool_ready_not_false")
    blockers.extend(scan_value(archive, label="archive"))
    blockers.extend(scan_value(opportunity, label="opportunity"))
    return sorted(set(blockers))


def check(archive_path: Path = DEFAULT_ARCHIVE, opportunity_path: Path = DEFAULT_OPPORTUNITY) -> Dict[str, Any]:
    archive = _load(archive_path)
    opportunity = _load(opportunity_path)
    blockers = validate_archive(archive, opportunity)
    entries = archive.get("entries", [])
    return {
        "report_scope": "abhe_archive_policy_check",
        "archive_index": str(archive_path),
        "opportunity_table": str(opportunity_path),
        "entry_count": len(entries) if isinstance(entries, list) else 0,
        "proposal_ready_entry_count": sum(1 for row in entries if isinstance(row, dict) and row.get("status") == "proposal_ready") if isinstance(entries, list) else 0,
        "watch_entry_count": sum(1 for row in entries if isinstance(row, dict) and row.get("status") == "watch") if isinstance(entries, list) else 0,
        "performance_evidence": archive.get("performance_evidence"),
        "scorer_authorized": archive.get("scorer_authorized"),
        "candidate_pool_ready": archive.get("candidate_pool_ready"),
        "abhe_archive_policy_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-index", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--opportunity-table", type=Path, default=DEFAULT_OPPORTUNITY)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.archive_index, args.opportunity_table)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "abhe_archive_policy_check", "abhe_archive_policy_passed": False, "blockers": ["load_failed:%s" % exc]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["abhe_archive_policy_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
