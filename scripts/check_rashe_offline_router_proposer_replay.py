#!/usr/bin/env python3
"""Check compact offline RASHE router/proposer replay report gate."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_PACKET = ARTIFACT_ROOT / "rashe_offline_router_proposer_replay_packet.json"
DEFAULT_REPORT = ARTIFACT_ROOT / "rashe_offline_router_proposer_replay.json"
SOURCE_DIAGNOSTICS_COMMIT = "cc21c96b70ab51c2bf586c0e79cdde3838dcb05d"
APPROVAL_PACKET = "outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_proposer_approval_packet.json"
ALLOWED_SEED_SKILLS = ["bfcl_multi_turn_state_tracking", "bfcl_hallucination_abstain"]
DISALLOWED_SEED_SKILLS = ["bfcl_web_search_decomposition", "bfcl_memory_retrieve_before_answer", "bfcl_parser_feedback_retry"]
SELECTED_SKILL_COUNTS = {"state_tracking": 80, "hallucination_abstain": 40, "no_spec_selected": 40}
CATEGORY_ROUTING = {
    "multi_turn_base": {"selected_skill": "bfcl_multi_turn_state_tracking", "case_count": 20, "routing_reason": "compact_multi_turn_state_lost_bucket"},
    "multi_turn_long_context": {"selected_skill": "bfcl_multi_turn_state_tracking", "case_count": 20, "routing_reason": "compact_multi_turn_state_lost_bucket"},
    "multi_turn_miss_param": {"selected_skill": "bfcl_multi_turn_state_tracking", "case_count": 20, "routing_reason": "compact_multi_turn_state_lost_bucket"},
    "multi_turn_miss_func": {"selected_skill": "bfcl_multi_turn_state_tracking", "case_count": 20, "routing_reason": "compact_multi_turn_state_lost_bucket"},
    "hallucination": {"selected_skill": "bfcl_hallucination_abstain", "case_count": 20, "routing_reason": "compact_abstain_bucket"},
    "irrelevance": {"selected_skill": "bfcl_hallucination_abstain", "case_count": 20, "routing_reason": "compact_abstain_bucket"},
    "agentic_web_search": {"selected_skill": "no_spec_selected", "case_count": 20, "routing_reason": "fail_closed_disallowed_seed_skill"},
    "agentic_memory": {"selected_skill": "no_spec_selected", "case_count": 20, "routing_reason": "fail_closed_disallowed_seed_skill"},
}
FALSE_KEYS = (
    "candidate_jsonl_created", "candidate_pool_created", "candidate_activation_authorized",
    "bfcl_generate_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed",
    "dev_holdout_material_used", "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "raw_outputs_committed",
)
TRUE_KEYS = ("candidate_proposer_ready_passed", "no_leakage_audit_passed")
FORBIDDEN_KEY_RE = re.compile(r"(raw_(?:prompt|trace|payload|provider|request|response|header|body)|prompt_text|trace_text|provider_exchange|case_id|gold|expected|reference|tool_args?|tool_arguments?|scorer_diff|candidate_output|candidate_jsonl|candidate_pool|dev_holdout|holdout_manifest|performance_claim|huawei_ready)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|raw prompt|raw trace|raw payload|provider exchange|provider request|provider response|case id|case_id|gold|expected|reference|tool args|tool arguments|scorer diff|candidate output|candidate jsonl|candidate pool|performance evidence|huawei|\+3pp"), re.IGNORECASE)
ALLOWED_RAWISH_KEYS = {"raw_outputs_committed", "candidate_jsonl_created", "candidate_pool_created", "dev_holdout_material_used", "no_candidate_jsonl_or_pool"}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain JSON object" % path)
    return data


def _walk(value: Any, path: Tuple[str, ...] = ()) -> List[Tuple[Tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(_walk(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk(child, path + (str(index),)))
    return items


def _scan(data: Dict[str, Any]) -> List[str]:
    blockers = []
    for path, value in _walk(data):
        key = path[-1] if path else ""
        dotted = ".".join(path)
        if key and key not in ALLOWED_RAWISH_KEYS and FORBIDDEN_KEY_RE.search(key):
            blockers.append("forbidden_key:%s" % dotted)
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key == "candidate_proposer_approval_packet_path" and value == APPROVAL_PACKET:
                continue
            if key == "source_diagnostics_commit" and value == SOURCE_DIAGNOSTICS_COMMIT:
                continue
            blockers.append("forbidden_value:%s" % dotted)
    return sorted(set(blockers))


def validate_packet(packet: Dict[str, Any]) -> List[str]:
    blockers = []
    expected = {
        "artifact_kind": "rashe_offline_router_proposer_replay_packet",
        "approval_status": "approved",
        "authorized": True,
        "source_diagnostics_commit": SOURCE_DIAGNOSTICS_COMMIT,
        "candidate_proposer_approval_packet_path": APPROVAL_PACKET,
        "input_mode": "compact_source_diagnostics_only",
        "replay_mode": "offline_router_proposer_report_only",
        "allowed_seed_skills": ALLOWED_SEED_SKILLS,
        "disallowed_seed_skills": DISALLOWED_SEED_SKILLS,
        "no_provider": True,
        "no_bfcl": True,
        "no_scorer": True,
        "no_candidate_jsonl_or_pool": True,
        "compact_report_only": True,
    }
    for key, value in expected.items():
        if packet.get(key) != value:
            blockers.append("packet_%s_invalid:%r" % (key, packet.get(key)))
    for key in FALSE_KEYS:
        if packet.get(key) is not False:
            blockers.append("packet_%s_not_false:%r" % (key, packet.get(key)))
    blockers.extend("packet_%s" % item for item in _scan(packet))
    return sorted(set(blockers))


def validate_report(report: Dict[str, Any]) -> List[str]:
    blockers = []
    expected = {
        "artifact_kind": "rashe_offline_router_proposer_replay_report",
        "source_diagnostics_commit": SOURCE_DIAGNOSTICS_COMMIT,
        "candidate_proposer_approval_packet_path": APPROVAL_PACKET,
        "candidate_proposer_ready_passed": True,
        "input_mode": "compact_source_diagnostics_only",
        "replay_mode": "offline_router_proposer_report_only",
        "allowed_seed_skills": ALLOWED_SEED_SKILLS,
        "disallowed_seed_skills": DISALLOWED_SEED_SKILLS,
        "total_source_cases": 160,
        "selected_skill_counts": SELECTED_SKILL_COUNTS,
        "category_routing": CATEGORY_ROUTING,
        "forbidden_skill_selection_count": 0,
        "ambiguous_or_leakage_fail_closed_count": 0,
        "no_leakage_audit_passed": True,
        "blockers": [],
    }
    for key, value in expected.items():
        if report.get(key) != value:
            blockers.append("report_%s_invalid:%r" % (key, report.get(key)))
    for key in FALSE_KEYS:
        if report.get(key) is not False:
            blockers.append("report_%s_not_false:%r" % (key, report.get(key)))
    if sum(SELECTED_SKILL_COUNTS.values()) != report.get("total_source_cases"):
        blockers.append("report_selected_skill_counts_sum_invalid")
    category_total = 0
    routing = report.get("category_routing") if isinstance(report.get("category_routing"), dict) else {}
    for category, row in routing.items():
        if not isinstance(row, dict):
            blockers.append("report_category_routing_row_not_object:%s" % category)
            continue
        category_total += int(row.get("case_count") or 0)
        selected = row.get("selected_skill")
        if selected not in set(ALLOWED_SEED_SKILLS + ["no_spec_selected"]):
            blockers.append("report_category_selected_skill_invalid:%s:%r" % (category, selected))
    if category_total != report.get("total_source_cases"):
        blockers.append("report_category_routing_total_invalid:%r" % category_total)
    blockers.extend("report_%s" % item for item in _scan(report))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, report_path: Path = DEFAULT_REPORT) -> Dict[str, Any]:
    packet = _load(packet_path)
    report = _load(report_path)
    blockers = validate_packet(packet) + validate_report(report)
    return {
        "report_scope": "rashe_offline_router_proposer_replay_check",
        "packet_path": str(packet_path),
        "report_path": str(report_path),
        "rashe_offline_router_proposer_replay_passed": not blockers,
        "candidate_proposer_ready_passed": report.get("candidate_proposer_ready_passed"),
        "selected_skill_counts": report.get("selected_skill_counts"),
        "forbidden_skill_selection_count": report.get("forbidden_skill_selection_count"),
        "ambiguous_or_leakage_fail_closed_count": report.get("ambiguous_or_leakage_fail_closed_count"),
        "blockers": sorted(set(blockers)),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "rashe_offline_router_proposer_replay_check", "rashe_offline_router_proposer_replay_passed": False, "blockers": ["load_failed:%s" % exc]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_offline_router_proposer_replay_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
