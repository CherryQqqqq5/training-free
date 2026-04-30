#!/usr/bin/env python3
"""Fail-closed checker for proposed RASHE runtime implementation authorization."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_AUTH = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_runtime_implementation_authorization.json")

REQUIRED_FALSE = [
    "runtime_implementation_authorized",
    "provider_calls_authorized",
    "source_collection_authorized",
    "scorer_authorized",
    "candidate_generation_authorized",
    "performance_evidence",
    "active_acceptance_path",
    "candidate_pool_ready",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "default_enabled",
]
REQUIRED_FILES = {
    "src/grc/skills/schema.py",
    "src/grc/skills/store.py",
    "src/grc/skills/router.py",
    "src/grc/skills/verifier.py",
    "configs/runtime_bfcl_skills.yaml",
}
REQUIRED_FORBIDDEN = {
    "RuleEngine/proxy behavior change",
    "provider calls",
    "BFCL scorer",
    "source collection",
    "candidate JSONL/dev/holdout manifests",
    "skill extraction from BFCL eval cases",
    "prompt injection active in BFCL runtime",
}
REQUIRED_GATES = [
    "v0_offline_checker_passed",
    "no_leakage_policy_passed",
    "seed_skills_validated",
    "router_ambiguity_fail_closed",
    "config_default_disabled",
    "code_change_plan_reviewed",
    "no_provider_scorer_source_paths_touched",
]
NO_LEAKAGE_FALSE = [
    "gold_used",
    "expected_used",
    "scorer_diff_used",
    "candidate_output_used",
    "holdout_used",
    "raw_trace_committed",
]


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("authorization must be a JSON object")
    return data


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = {
        "report_scope": "rashe_runtime_implementation_authorization",
        "authorization_status": "proposed",
        "scope_change_route": "retrieval_augmented_skill_harness_evolution",
        "short_name": "RASHE",
    }
    for key, value in expected.items():
        if data.get(key) != value:
            blockers.append(f"{key}_invalid")
    for key in REQUIRED_FALSE:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    files = set(data.get("allowed_future_implementation_files_after_approval") or [])
    missing = REQUIRED_FILES - files
    if missing:
        blockers.append("allowed_future_files_missing:" + ",".join(sorted(missing)))
    if "synthetic tests only initially" not in str(data.get("allowed_initial_tests_after_approval")):
        blockers.append("synthetic_tests_only_missing")
    forbidden = set(data.get("forbidden_until_later_execution_approval") or [])
    missing_forbidden = REQUIRED_FORBIDDEN - forbidden
    if missing_forbidden:
        blockers.append("forbidden_scope_missing:" + ",".join(sorted(missing_forbidden)))
    gates = data.get("gates_before_runtime_implementation_authorized_true")
    if not isinstance(gates, dict):
        blockers.append("runtime_gates_missing")
    else:
        for key in REQUIRED_GATES:
            if gates.get(key) is not True:
                blockers.append(f"gate_{key}_not_true")
    no_leakage = data.get("no_leakage_required")
    if not isinstance(no_leakage, dict):
        blockers.append("no_leakage_required_missing")
    else:
        for key in NO_LEAKAGE_FALSE:
            if no_leakage.get(key) is not False:
                blockers.append(f"no_leakage_{key}_not_false")
    config = data.get("required_config_defaults_after_approval")
    if not isinstance(config, dict):
        blockers.append("required_config_defaults_missing")
    else:
        runtime_cfg = config.get("configs/runtime_bfcl_skills.yaml")
        if not isinstance(runtime_cfg, dict):
            blockers.append("runtime_config_defaults_missing")
        else:
            for key in ["enabled", "provider_calls_authorized", "scorer_authorized", "source_collection_authorized", "candidate_generation_authorized"]:
                if runtime_cfg.get(key) is not False:
                    blockers.append(f"runtime_config_{key}_not_false")
    return blockers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, default=DEFAULT_AUTH)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    data = load_json(args.authorization)
    blockers = validate(data)
    summary = {
        "report_scope": "rashe_runtime_authorization_check",
        "authorization": str(args.authorization),
        "authorization_status": data.get("authorization_status"),
        "runtime_implementation_authorized": data.get("runtime_implementation_authorized"),
        "provider_calls_authorized": data.get("provider_calls_authorized"),
        "source_collection_authorized": data.get("source_collection_authorized"),
        "scorer_authorized": data.get("scorer_authorized"),
        "candidate_generation_authorized": data.get("candidate_generation_authorized"),
        "performance_evidence": data.get("performance_evidence"),
        "rashe_runtime_authorization_passed": not blockers,
        "blockers": blockers,
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and blockers:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
