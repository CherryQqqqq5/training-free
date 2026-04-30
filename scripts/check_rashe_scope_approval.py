#!/usr/bin/env python3
"""Fail-closed validator for the proposed RASHE scope-change packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_APPROVAL = Path("outputs/artifacts/stage1_bfcl_acceptance/scope_change_approval_rashe.json")

REQUIRED_FALSE_FIELDS = [
    "approved_before_implementation",
    "approved_before_source_collection",
    "approved_before_candidate_generation",
    "approved_before_scorer",
    "model_weights_changed",
    "bfcl_evaluator_modified",
    "candidate_pool_ready",
    "scorer_authorization",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "runtime_implementation_authorized",
    "source_collection_authorized",
    "candidate_generation_authorized",
    "scorer_authorized",
    "active_acceptance_path",
]

REQUIRED_TRUE_FIELDS = [
    "training_free_claim",
    "same_model_same_provider_required",
    "proposed_only",
]

REQUIRED_NO_LEAKAGE_FALSE = [
    "gold_used",
    "expected_used",
    "scorer_diff_used_for_skill",
    "candidate_output_used_for_skill",
    "holdout_used_for_skill",
    "raw_trace_committed",
]

REQUIRED_GATE_TRUE = [
    "subset_approval_id_required_if_not_full_suite",
    "dev_holdout_disjoint_required_before_scorer",
    "candidate_pool_gate_required",
    "paired_comparison_required",
    "cost_gate_required",
    "latency_gate_required",
    "regression_gate_required",
]


def _load(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("approval packet must be a JSON object")
    return data


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = {
        "report_scope": "scope_change_approval_rashe",
        "scope_change_route": "retrieval_augmented_skill_harness_evolution",
        "short_name": "RASHE",
        "approval_status": "proposed",
        "provider": "Chuangzhi/Novacode",
        "provider_profile": "novacode",
        "model": "gpt-5.2",
    }
    for key, value in expected.items():
        if data.get(key) != value:
            blockers.append(f"{key}_invalid")
    for key in REQUIRED_TRUE_FIELDS:
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true")
    for key in REQUIRED_FALSE_FIELDS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    no_leakage = data.get("no_leakage")
    if not isinstance(no_leakage, dict):
        blockers.append("no_leakage_missing")
    else:
        for key in REQUIRED_NO_LEAKAGE_FALSE:
            if no_leakage.get(key) is not False:
                blockers.append(f"no_leakage_{key}_not_false")
    gates = data.get("gate_fields")
    if not isinstance(gates, dict):
        blockers.append("gate_fields_missing")
    else:
        if gates.get("suite_scope") != "full_suite_or_signed_subset":
            blockers.append("suite_scope_invalid")
        for key in REQUIRED_GATE_TRUE:
            if gates.get(key) is not True:
                blockers.append(f"gate_{key}_not_true")
    for key in ["allowed_changes_proposed_only", "forbidden_changes"]:
        if not isinstance(data.get(key), list) or not data.get(key):
            blockers.append(f"{key}_missing")
    return blockers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, default=DEFAULT_APPROVAL)
    parser.add_argument("--compact", action="store_true", help="emit compact JSON summary")
    parser.add_argument("--strict", action="store_true", help="return non-zero on blockers")
    args = parser.parse_args(argv)

    data = _load(args.approval)
    blockers = validate(data)
    summary = {
        "report_scope": "rashe_scope_approval_check",
        "approval": str(args.approval),
        "rashe_scope_approval_passed": not blockers,
        "blockers": blockers,
        "approval_status": data.get("approval_status"),
        "scope_change_route": data.get("scope_change_route"),
        "candidate_pool_ready": data.get("candidate_pool_ready"),
        "scorer_authorization": data.get("scorer_authorization"),
        "performance_evidence": data.get("performance_evidence"),
    }
    if args.compact:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and blockers:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
