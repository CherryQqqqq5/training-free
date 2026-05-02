#!/usr/bin/env python3
"""Check the pending RASHE candidate proposer approval packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_proposer_approval_packet.json")
SOURCE_DIAGNOSTICS_COMMIT = "cc21c96b70ab51c2bf586c0e79cdde3838dcb05d"
ALLOWED_SEED_SKILLS = ["bfcl_multi_turn_state_tracking", "bfcl_hallucination_abstain"]
DISALLOWED_SEED_SKILLS = [
    "bfcl_web_search_decomposition",
    "bfcl_memory_retrieve_before_answer",
    "bfcl_parser_feedback_retry",
]
REQUIRED_FALSE = (
    "authorized",
    "candidate_proposer_execution_authorized",
    "candidate_generation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
)
FORBIDDEN_FRAGMENTS = (
    "raw prompt",
    "raw trace",
    "provider request/response",
    "case id",
    "gold",
    "expected",
    "reference",
    "scorer diff",
    "candidate output",
    "repair feedback",
    "holdout/full feedback",
    "endpoint/key",
    "source nonce mapping",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        values: list[str] = []
        for key, child in value.items():
            values.append(str(key))
            values.extend(_walk_strings(child))
        return values
    if isinstance(value, list):
        values = []
        for child in value:
            values.extend(_walk_strings(child))
        return values
    if isinstance(value, str):
        return [value]
    return []


def validate(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = {
        "approval_packet_kind": "candidate_proposer_execution_approval",
        "approval_status": "pending",
        "source_diagnostics_commit": SOURCE_DIAGNOSTICS_COMMIT,
        "route_model": "gpt-4.1",
        "allowed_seed_skills": ALLOWED_SEED_SKILLS,
        "disallowed_seed_skills": DISALLOWED_SEED_SKILLS,
    }
    for key, value in expected.items():
        if packet.get(key) != value:
            blockers.append(f"candidate_packet_{key}_invalid:{packet.get(key)!r}")
    for key in REQUIRED_FALSE:
        if packet.get(key) is not False:
            blockers.append(f"candidate_packet_{key}_not_false:{packet.get(key)!r}")
    if packet.get("no_leakage_required") is not True:
        blockers.append(f"candidate_packet_no_leakage_required_not_true:{packet.get('no_leakage_required')!r}")
    evidence = packet.get("evidence") if isinstance(packet.get("evidence"), dict) else {}
    mt = evidence.get("bfcl_multi_turn_state_tracking", {}) if isinstance(evidence.get("bfcl_multi_turn_state_tracking"), dict) else {}
    if mt.get("primary_bucket_total") != 80 or mt.get("category_coverage_count") != 4:
        blockers.append("candidate_packet_multi_turn_evidence_invalid")
    mt_categories = mt.get("required_category_buckets") if isinstance(mt.get("required_category_buckets"), dict) else {}
    for category in ["multi_turn_base", "multi_turn_long_context", "multi_turn_miss_param", "multi_turn_miss_func"]:
        if mt_categories.get(category, {}).get("multi_turn_state_lost") != 20:
            blockers.append(f"candidate_packet_multi_turn_bucket_missing:{category}")
    ha = evidence.get("bfcl_hallucination_abstain", {}) if isinstance(evidence.get("bfcl_hallucination_abstain"), dict) else {}
    if ha.get("primary_bucket_total") != 40 or ha.get("category_coverage_count") != 2:
        blockers.append("candidate_packet_hallucination_evidence_invalid")
    ha_categories = ha.get("required_category_buckets") if isinstance(ha.get("required_category_buckets"), dict) else {}
    if ha_categories.get("hallucination", {}).get("unsupported_hallucinated_answer") != 20:
        blockers.append("candidate_packet_hallucination_bucket_missing")
    if ha_categories.get("irrelevance", {}).get("irrelevant_tool_call") != 20:
        blockers.append("candidate_packet_irrelevance_bucket_missing")
    trigger = packet.get("trigger_policy_verifier") if isinstance(packet.get("trigger_policy_verifier"), dict) else {}
    if set(trigger) != set(ALLOWED_SEED_SKILLS):
        blockers.append("candidate_packet_trigger_policy_verifier_skills_invalid")
    allowed_inputs = set(packet.get("allowed_inputs") or [])
    required_inputs = {
        "compact_source_diagnostics",
        "failure_bucket_counts",
        "frozen_skill_bucket_mapping",
        "category_coverage_counts",
        "no_leakage_booleans",
        "route_metadata_gpt_4_1",
    }
    if allowed_inputs != required_inputs:
        blockers.append("candidate_packet_allowed_inputs_invalid")
    strings = "\n".join(_walk_strings(packet)).lower()
    for disallowed in DISALLOWED_SEED_SKILLS:
        if disallowed not in packet.get("disallowed_seed_skills", []):
            blockers.append(f"candidate_packet_disallowed_skill_not_listed:{disallowed}")
    for fragment in FORBIDDEN_FRAGMENTS:
        normalized = fragment.lower()
        if normalized not in strings:
            blockers.append(f"candidate_packet_forbidden_boundary_missing:{fragment}")
    for bad in [
        "approval_status=approved",
        "candidate_generation_authorized=true",
        "candidate pool ready",
        "scorer authorized",
        "performance ready",
        "huawei ready",
    ]:
        if bad in strings:
            blockers.append(f"candidate_packet_unauthorized_claim_present:{bad}")
    return blockers


def check(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = load_json(packet_path)
    blockers = validate(packet)
    return {
        "report_scope": "rashe_candidate_proposer_approval_packet_check",
        "packet_path": str(packet_path),
        "approval_status": packet.get("approval_status"),
        "candidate_proposer_execution_authorized": packet.get("candidate_proposer_execution_authorized"),
        "candidate_generation_authorized": packet.get("candidate_generation_authorized"),
        "candidate_jsonl_authorized": packet.get("candidate_jsonl_authorized"),
        "candidate_pool_ready": packet.get("candidate_pool_ready"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "performance_evidence": packet.get("performance_evidence"),
        "allowed_seed_skills": packet.get("allowed_seed_skills"),
        "rashe_candidate_proposer_approval_packet_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "rashe_candidate_proposer_approval_packet_check",
            "packet_path": str(args.packet),
            "rashe_candidate_proposer_approval_packet_passed": False,
            "blockers": [f"candidate_packet_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_candidate_proposer_approval_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
