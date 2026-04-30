#!/usr/bin/env python3
"""Offline checker for the default-disabled inert RASHE runtime skeleton."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

RUNTIME_MODULE_PREFIXES = (
    "grc.runtime",
    "grc.runtime.proxy",
    "grc.runtime.engine",
)
DEFAULT_CONFIG = Path("configs/runtime_bfcl_skills.yaml")
DEFAULT_FIXTURE_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/fixtures")


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def runtime_modules_loaded() -> list[str]:
    return sorted(name for name in sys.modules if name in RUNTIME_MODULE_PREFIXES or name.startswith("grc.runtime."))


def check(config_path: Path = DEFAULT_CONFIG, fixture_root: Path = DEFAULT_FIXTURE_ROOT) -> dict[str, Any]:
    before_runtime_modules = set(runtime_modules_loaded())

    from grc.skills.router import SkillRouter
    from grc.skills.store import SkillStore
    from grc.skills.verifier import load_simple_yaml, verify_runtime_config, verify_trace

    after_runtime_modules = set(runtime_modules_loaded())
    blockers: list[str] = []
    if after_runtime_modules - before_runtime_modules:
        blockers.append("ruleengine_proxy_active_path_imported")

    config = load_simple_yaml(config_path)
    config_report = verify_runtime_config(config)
    if not config_report.verifier_passed:
        blockers.extend(f"config_{item}" for item in config_report.blockers)

    store = SkillStore.load_manifest(Path(str(config.get("skillbank_manifest_path"))))
    if not store.is_valid():
        blockers.extend(f"skill_store_{item}" for item in store.blockers)

    router = SkillRouter(
        enabled=bool(config.get("enabled")),
        runtime_behavior_authorized=bool(config.get("runtime_behavior_authorized")),
    )
    selected_skill_counts: Counter[str] = Counter()
    reject_reason_counts: Counter[str] = Counter()
    fixture_count = 0
    router_decision_count = 0
    positive_fixture_count = 0
    reject_fixture_count = 0
    case_hash_allowed_count = 0
    raw_case_id_rejected_count = 0
    forbidden_field_rejected_count = 0
    path_indicator_rejected_count = 0
    unexpected_forbidden_violation_count = 0
    provider_call_count = 0
    scorer_call_count = 0
    source_collection_call_count = 0

    fixture_paths = sorted(p for p in fixture_root.glob("*.json") if p.name != "aggregate_verifier_report.json")
    if not fixture_paths:
        blockers.append("fixtures_missing")
    for path in fixture_paths:
        trace = load_json(path)
        if not isinstance(trace, dict):
            blockers.append(f"trace_not_object:{path}")
            continue
        fixture_count += 1
        provider_call_count += int(trace.get("provider_call_count") or 0)
        scorer_call_count += int(trace.get("scorer_call_count") or 0)
        source_collection_call_count += int(trace.get("source_collection_call_count") or 0)
        report = verify_trace(trace)
        decision = router.route(trace).to_dict()
        router_decision_count += 1
        expected_status = trace.get("expected_router_status")
        expected_skill = trace.get("expected_skill_id")
        expected_reject = trace.get("expected_reject_reason")

        if expected_status == "selected":
            positive_fixture_count += 1
            if not report.verifier_passed:
                blockers.append(f"positive_fixture_verifier_failed:{path.name}")
                unexpected_forbidden_violation_count += report.forbidden_field_violation_count
            if decision.get("decision_status") != "selected" or decision.get("selected_skill_id") != expected_skill:
                blockers.append(f"positive_fixture_route_mismatch:{path.name}")
            else:
                selected_skill_counts[str(decision["selected_skill_id"])] += 1
            if trace.get("case_hash"):
                case_hash_allowed_count += 1
        elif expected_status in {"ambiguous_reject", "forbidden_field_reject", "path_indicator_reject", "raw_case_id_reject"}:
            reject_fixture_count += 1
            if expected_reject:
                reject_reason_counts[str(expected_reject)] += 1
            if expected_status == "ambiguous_reject":
                if decision.get("decision_status") != "ambiguous_reject":
                    blockers.append(f"ambiguous_fixture_route_mismatch:{path.name}")
            elif expected_status == "forbidden_field_reject":
                if report.forbidden_field_violation_count <= 0:
                    blockers.append(f"forbidden_fixture_not_rejected:{path.name}")
                else:
                    forbidden_field_rejected_count += 1
            elif expected_status == "path_indicator_reject":
                if report.path_indicator_violation_count <= 0:
                    blockers.append(f"path_indicator_fixture_not_rejected:{path.name}")
                else:
                    path_indicator_rejected_count += 1
                    forbidden_field_rejected_count += 1
            elif expected_status == "raw_case_id_reject":
                if report.raw_case_id_rejected_count <= 0:
                    blockers.append(f"raw_case_id_fixture_not_rejected:{path.name}")
                else:
                    raw_case_id_rejected_count += 1
                    forbidden_field_rejected_count += 1
        else:
            blockers.append(f"fixture_expected_status_invalid:{path.name}")

    summary = {
        "report_scope": "rashe_runtime_skeleton_check",
        "offline_only": True,
        "enabled": config.get("enabled"),
        "runtime_behavior_authorized": config.get("runtime_behavior_authorized"),
        "runtime_authorized": False,
        "provider_call_count": provider_call_count,
        "scorer_call_count": scorer_call_count,
        "source_collection_call_count": source_collection_call_count,
        "candidate_generation_authorized": config.get("candidate_generation_authorized"),
        "prompt_injection_authorized": config.get("prompt_injection_authorized"),
        "retry_authorized": config.get("retry_authorized"),
        "ruleengine_proxy_active_path_imported": bool(after_runtime_modules - before_runtime_modules),
        "skill_count": len(store.skills),
        "fixture_count": fixture_count,
        "positive_fixture_count": positive_fixture_count,
        "reject_fixture_count": reject_fixture_count,
        "router_decision_count": router_decision_count,
        "selected_skill_counts": dict(selected_skill_counts),
        "reject_reason_counts": dict(reject_reason_counts),
        "case_hash_allowed_count": case_hash_allowed_count,
        "raw_case_id_rejected_count": raw_case_id_rejected_count,
        "forbidden_field_rejected_count": forbidden_field_rejected_count,
        "path_indicator_rejected_count": path_indicator_rejected_count,
        "forbidden_field_violation_count": unexpected_forbidden_violation_count,
        "rashe_runtime_skeleton_passed": not blockers,
        "blockers": blockers,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.config, args.fixture_root)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_runtime_skeleton_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
