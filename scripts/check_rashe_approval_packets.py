#!/usr/bin/env python3
"""Fail-closed checker for RASHE approval packet skeletons."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_BASE = Path("outputs/artifacts/stage1_bfcl_acceptance")
PACKET_STEMS = (
    "rashe_runtime_behavior_approval_packet",
    "rashe_source_real_trace_approval_packet",
    "rashe_candidate_proposer_execution_approval_packet",
    "rashe_scorer_dev_holdout_full_approval_packet",
    "rashe_performance_3pp_huawei_acceptance_approval_packet",
)
ALLOWED_STATUSES = {"pending", "not_approved"}
REQUIRED_LIST_FIELDS = ("prerequisites", "allowed_if_approved", "forbidden_until_approved", "rollback_stop_gates")
FORBIDDEN_TRUE_FIELDS = {
    "authorized", "runtime_behavior_authorized", "source_collection_authorized", "candidate_generation_authorized",
    "candidate_pool_ready", "scorer_authorized", "performance_evidence", "sota_3pp_claim_ready",
    "huawei_acceptance_ready", "bfcl_performance_ready", "provider_calls_authorized", "prompt_injection_authorized",
    "retry_authorized", "tool_path_mutation_authorized", "raw_trace_authorized", "raw_payload_capture_authorized",
    "proposer_execution_authorized", "candidate_jsonl_authorized", "dev_holdout_authorized", "paired_comparison_authorized",
}
NO_LEAKAGE_FALSE_FIELDS = {
    "gold_used", "expected_used", "scorer_diff_used", "candidate_output_used", "holdout_feedback_used",
    "full_suite_feedback_used", "raw_trace_committed", "case_id_specific_rules_allowed",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def iter_truthy_forbidden(data: Any, path: str = ""):
    if isinstance(data, dict):
        for key, value in data.items():
            current = f"{path}.{key}" if path else key
            if key in FORBIDDEN_TRUE_FIELDS and value is True:
                yield current
            yield from iter_truthy_forbidden(value, current)
    elif isinstance(data, list):
        for index, value in enumerate(data):
            yield from iter_truthy_forbidden(value, f"{path}[{index}]")


def check(base: Path = DEFAULT_BASE) -> dict[str, Any]:
    blockers: list[str] = []
    status_counts: Counter[str] = Counter()
    packet_summaries: dict[str, dict[str, Any]] = {}
    forbidden_true_paths: list[str] = []
    section_missing_count = 0
    md_missing_count = 0

    for stem in PACKET_STEMS:
        json_path = base / f"{stem}.json"
        md_path = base / f"{stem}.md"
        if not json_path.exists():
            blockers.append(f"missing_packet_json:{json_path}")
            continue
        if not md_path.exists():
            md_missing_count += 1
            blockers.append(f"missing_packet_md:{md_path}")
        try:
            packet = load_json(json_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            blockers.append(f"invalid_packet_json:{json_path}:{exc}")
            continue
        status = packet.get("approval_status")
        status_counts[str(status)] += 1
        if status not in ALLOWED_STATUSES:
            blockers.append(f"packet_status_not_fail_closed:{stem}:{status}")
        if status == "approved":
            blockers.append(f"packet_approved:{stem}")
        if packet.get("report_scope") != f"rashe_{packet.get('approval_packet_kind')}_approval_packet":
            blockers.append(f"packet_report_scope_mismatch:{stem}")
        for field in REQUIRED_LIST_FIELDS:
            value = packet.get(field)
            if not isinstance(value, list) or not value:
                section_missing_count += 1
                blockers.append(f"packet_required_section_missing:{stem}:{field}")
        for path in iter_truthy_forbidden(packet):
            forbidden_true_paths.append(f"{stem}:{path}")
            blockers.append(f"packet_forbidden_true:{stem}:{path}")
        no_leakage = packet.get("no_leakage_required")
        if not isinstance(no_leakage, dict):
            blockers.append(f"packet_no_leakage_missing:{stem}")
        else:
            for field in NO_LEAKAGE_FALSE_FIELDS:
                if no_leakage.get(field) is not False:
                    blockers.append(f"packet_no_leakage_field_not_false:{stem}:{field}")
        packet_summaries[stem] = {
            "approval_status": status,
            "authorized": packet.get("authorized"),
            "performance_evidence": packet.get("performance_evidence"),
            "scorer_authorized": packet.get("scorer_authorized"),
            "candidate_generation_authorized": packet.get("candidate_generation_authorized"),
            "huawei_acceptance_ready": packet.get("huawei_acceptance_ready"),
        }

    summary = {
        "report_scope": "rashe_approval_packets_check",
        "packet_count": len(packet_summaries),
        "expected_packet_count": len(PACKET_STEMS),
        "approval_status_counts": dict(sorted(status_counts.items())),
        "md_missing_count": md_missing_count,
        "required_section_missing_count": section_missing_count,
        "authorized_true_count": sum(1 for item in packet_summaries.values() if item.get("authorized") is True),
        "performance_evidence_true_count": sum(1 for item in packet_summaries.values() if item.get("performance_evidence") is True),
        "scorer_authorized_true_count": sum(1 for item in packet_summaries.values() if item.get("scorer_authorized") is True),
        "candidate_generation_authorized_true_count": sum(1 for item in packet_summaries.values() if item.get("candidate_generation_authorized") is True),
        "huawei_acceptance_ready_true_count": sum(1 for item in packet_summaries.values() if item.get("huawei_acceptance_ready") is True),
        "forbidden_true_path_count": len(forbidden_true_paths),
        "forbidden_true_paths": forbidden_true_paths,
        "runtime_behavior_authorized": False,
        "source_collection_authorized": False,
        "candidate_generation_authorized": False,
        "candidate_pool_ready": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "rashe_approval_packets_passed": not blockers,
        "packet_summaries": packet_summaries,
        "blockers": blockers,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.base)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_approval_packets_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
