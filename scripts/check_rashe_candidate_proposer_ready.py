#!/usr/bin/env python3
"""Fail-closed readiness check for pending RASHE candidate proposer approval."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_rashe_candidate_proposer_approval_packet import DEFAULT_PACKET, ALLOWED_SEED_SKILLS, check as check_packet
from scripts.check_rashe_source_diagnostic_compact import SIGNED_ROOT, check_root

CANDIDATE_FORBIDDEN_ROOTS = (
    Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_pool"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_jsonl"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_outputs"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/candidate_pool"),
)
CANDIDATE_FORBIDDEN_GLOBS = (
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate*.jsonl",
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_*/*.jsonl",
)
REQUIRED_EVIDENCE = {
    "bfcl_multi_turn_state_tracking": {
        "multi_turn_base": {"multi_turn_state_lost": 20},
        "multi_turn_long_context": {"multi_turn_state_lost": 20},
        "multi_turn_miss_param": {"multi_turn_state_lost": 20},
        "multi_turn_miss_func": {"multi_turn_state_lost": 20},
    },
    "bfcl_hallucination_abstain": {
        "hallucination": {"unsupported_hallucinated_answer": 20},
        "irrelevance": {"irrelevant_tool_call": 20},
    },
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def run_artifact_boundary() -> tuple[bool, str | None]:
    result = subprocess.run([sys.executable, "scripts/check_artifact_boundary.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0:
        return False, result.stdout.strip() or result.stderr.strip() or "artifact_boundary_failed"
    return True, None


def _candidate_artifact_blockers() -> list[str]:
    blockers: list[str] = []
    for root in CANDIDATE_FORBIDDEN_ROOTS:
        if root.exists():
            blockers.append(f"candidate_artifact_root_exists:{root}")
    for pattern in CANDIDATE_FORBIDDEN_GLOBS:
        for path in Path(".").glob(pattern):
            if "rashe_candidate_proposer_approval_packet" in str(path):
                continue
            blockers.append(f"candidate_artifact_file_exists:{path}")
    return sorted(set(blockers))


def _diagnostic_artifact(category: str) -> dict[str, Any]:
    return load_json(SIGNED_ROOT / f"{category}.json")


def _evidence_blockers() -> list[str]:
    blockers: list[str] = []
    for skill, category_buckets in REQUIRED_EVIDENCE.items():
        covered = 0
        total = 0
        for category, buckets in category_buckets.items():
            artifact = _diagnostic_artifact(category)
            if artifact.get("raw_payload_tracked_count") != 0:
                blockers.append(f"candidate_ready_raw_payload_nonzero:{category}")
            if artifact.get("forbidden_field_violation_count") != 0:
                blockers.append(f"candidate_ready_forbidden_violation_nonzero:{category}")
            if artifact.get("candidate_generation_authorized") is not False:
                blockers.append(f"candidate_ready_diagnostic_candidate_flag_not_false:{category}")
            if artifact.get("scorer_authorized") is not False:
                blockers.append(f"candidate_ready_diagnostic_scorer_flag_not_false:{category}")
            if artifact.get("performance_evidence") is not False:
                blockers.append(f"candidate_ready_diagnostic_performance_flag_not_false:{category}")
            counts = artifact.get("failure_bucket_counts") if isinstance(artifact.get("failure_bucket_counts"), dict) else {}
            category_hit = False
            for bucket, expected in buckets.items():
                actual = counts.get(bucket)
                if actual != expected:
                    blockers.append(f"candidate_ready_bucket_evidence_mismatch:{skill}:{category}:{bucket}:{actual!r}")
                else:
                    category_hit = True
                    total += int(actual)
            if category_hit:
                covered += 1
        if skill == "bfcl_multi_turn_state_tracking" and (total != 80 or covered != 4):
            blockers.append(f"candidate_ready_multi_turn_threshold_invalid:{total}:{covered}")
        if skill == "bfcl_hallucination_abstain" and (total != 40 or covered != 2):
            blockers.append(f"candidate_ready_hallucination_threshold_invalid:{total}:{covered}")
    return blockers


def check_ready(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    blockers: list[str] = []
    packet_summary = check_packet(packet_path)
    if not packet_summary.get("rashe_candidate_proposer_approval_packet_passed"):
        blockers.extend(f"packet:{blocker}" for blocker in packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "pending":
        blockers.append(f"candidate_ready_packet_not_pending:{packet_summary.get('approval_status')!r}")
    for key in [
        "candidate_proposer_execution_authorized",
        "candidate_generation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "scorer_authorized",
        "performance_evidence",
    ]:
        if packet_summary.get(key) is not False:
            blockers.append(f"candidate_ready_packet_{key}_not_false:{packet_summary.get(key)!r}")
    if packet_summary.get("allowed_seed_skills") != ALLOWED_SEED_SKILLS:
        blockers.append("candidate_ready_allowed_seed_skills_invalid")

    diagnostic_summary = check_root(SIGNED_ROOT)
    if diagnostic_summary.get("blockers"):
        blockers.extend(f"diagnostics:{blocker}" for blocker in diagnostic_summary["blockers"])
    if diagnostic_summary.get("total_case_count") != 160:
        blockers.append(f"candidate_ready_diagnostic_total_not_160:{diagnostic_summary.get('total_case_count')!r}")
    blockers.extend(_evidence_blockers())
    ok_boundary, boundary_error = run_artifact_boundary()
    if not ok_boundary:
        blockers.append(f"artifact_boundary:{boundary_error}")
    blockers.extend(_candidate_artifact_blockers())

    return {
        "report_scope": "rashe_candidate_proposer_ready_check",
        "packet_path": str(packet_path),
        "diagnostics_root": str(SIGNED_ROOT),
        "approval_status": packet_summary.get("approval_status"),
        "allowed_seed_skills": packet_summary.get("allowed_seed_skills"),
        "candidate_proposer_execution_authorized": packet_summary.get("candidate_proposer_execution_authorized"),
        "candidate_generation_authorized": packet_summary.get("candidate_generation_authorized"),
        "candidate_jsonl_authorized": packet_summary.get("candidate_jsonl_authorized"),
        "candidate_pool_ready": packet_summary.get("candidate_pool_ready"),
        "scorer_authorized": packet_summary.get("scorer_authorized"),
        "performance_evidence": packet_summary.get("performance_evidence"),
        "source_diagnostic_total_case_count": diagnostic_summary.get("total_case_count"),
        "rashe_candidate_proposer_ready_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check_ready(args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "rashe_candidate_proposer_ready_check",
            "packet_path": str(args.packet),
            "rashe_candidate_proposer_ready_passed": False,
            "blockers": [f"candidate_ready_check_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_candidate_proposer_ready_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
