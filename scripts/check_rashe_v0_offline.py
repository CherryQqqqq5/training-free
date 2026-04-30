#!/usr/bin/env python3
"""Offline-only validator for the RASHE v0/v0.1 skeleton."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0")
EXPECTED_SKILLS = {
    "bfcl_current_turn_focus",
    "bfcl_schema_reading",
    "bfcl_tool_call_format_guard",
    "bfcl_memory_web_search_discipline",
}
REQUIRED_SCHEMA_FILES = {
    "skill.schema.json",
    "step_trace.schema.json",
    "router_decision.schema.json",
    "verifier_report.schema.json",
}
FORBIDDEN_FIELD_NAMES = {
    "gold", "expected", "answer", "ground_truth", "oracle", "checker", "reference",
    "possible_answer", "score", "scorer_diff", "candidate", "candidate_output", "repair", "case_id",
}
PATH_INDICATORS = (
    "provider://", "scorer://", "source_collection://", "/provider/", "/scorer/",
    "/source_collection/", "outputs/bfcl_runs", "raw_trace",
)


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def walk_forbidden(obj: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            if key_l in FORBIDDEN_FIELD_NAMES:
                hits.append(f"{path}.{key}" if path else str(key))
            hits.extend(walk_forbidden(value, f"{path}.{key}" if path else str(key)))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            hits.extend(walk_forbidden(value, f"{path}[{i}]"))
    elif isinstance(obj, str):
        value_l = obj.lower()
        for indicator in PATH_INDICATORS:
            if indicator in value_l:
                hits.append(path or "<string>")
    return hits


def require_const(obj: dict[str, Any], key: str, value: Any, blockers: list[str], prefix: str) -> None:
    if obj.get(key) != value:
        blockers.append(f"{prefix}_{key}_invalid")


def validate_schema_file(path: Path) -> list[str]:
    blockers: list[str] = []
    data = load_json(path)
    if not isinstance(data, dict):
        return [f"schema_{path.name}_not_object"]
    if data.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        blockers.append(f"schema_{path.name}_draft_missing")
    if data.get("type") != "object":
        blockers.append(f"schema_{path.name}_type_not_object")
    if not data.get("required"):
        blockers.append(f"schema_{path.name}_required_missing")
    return blockers


def validate_skill(path: Path) -> tuple[list[str], str | None]:
    blockers: list[str] = []
    data = load_json(path)
    if not isinstance(data, dict):
        return [f"skill_{path.name}_not_object"], None
    skill_id = data.get("skill_id")
    require_const(data, "schema_version", "rashe_skill_v0", blockers, f"skill_{path.stem}")
    require_const(data, "offline_only", True, blockers, f"skill_{path.stem}")
    require_const(data, "enabled", False, blockers, f"skill_{path.stem}")
    require_const(data, "runtime_authorized", False, blockers, f"skill_{path.stem}")
    require_const(data, "training_free", True, blockers, f"skill_{path.stem}")
    for key in ["allowed_triggers", "forbidden_triggers", "actions"]:
        if not isinstance(data.get(key), list) or not data[key]:
            blockers.append(f"skill_{path.stem}_{key}_missing")
    for key in ["no_leakage_policy", "rollback_policy", "source_boundary"]:
        if not isinstance(data.get(key), dict):
            blockers.append(f"skill_{path.stem}_{key}_missing")
    no_leakage = data.get("no_leakage_policy", {})
    for key in ["gold_used", "expected_used", "scorer_diff_used", "candidate_output_used", "holdout_used", "case_specific_content_allowed", "raw_trace_committed"]:
        if no_leakage.get(key) is not False:
            blockers.append(f"skill_{path.stem}_{key}_not_false")
    if data.get("rollback_policy", {}).get("disable_by_default") is not True:
        blockers.append(f"skill_{path.stem}_rollback_disable_by_default_not_true")
    forbidden = walk_forbidden(data)
    if forbidden:
        blockers.append(f"skill_{path.stem}_forbidden_fields:{','.join(forbidden)}")
    return blockers, skill_id if isinstance(skill_id, str) else None


def route_trace(trace: dict[str, Any]) -> dict[str, Any]:
    signals = set(trace.get("signals") or [])
    matches: list[str] = []
    if {"multi_turn", "current_turn"} & signals:
        matches.append("bfcl_current_turn_focus")
    if {"malformed_tool_call_json", "no_tool_call", "tool_like_payload"} & signals:
        matches.append("bfcl_tool_call_format_guard")
    if {"schema_present", "required_properties", "argument_name_choice"} & signals:
        matches.append("bfcl_schema_reading")
    if {"memory_tool_visible", "web_search_tool_visible", "external_search_not_required"} & signals:
        matches.append("bfcl_memory_web_search_discipline")
    if trace.get("ambiguous") is True or len(matches) > 1:
        return router_decision(None, "ambiguous_reject", "ambiguous_skill_match")
    if not matches:
        return router_decision(None, "no_match_reject", "no_skill_match")
    return router_decision(matches[0], "selected", None)


def router_decision(skill_id: str | None, status: str, reason: str | None) -> dict[str, Any]:
    return {
        "schema_version": "rashe_router_decision_v0",
        "offline_only": True,
        "enabled": False,
        "runtime_authorized": False,
        "selected_skill_id": skill_id,
        "decision_status": status,
        "reject_reason": reason,
        "provider_call_count": 0,
        "scorer_call_count": 0,
        "source_collection_call_count": 0,
    }


def validate_trace(trace: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    require_const(trace, "schema_version", "rashe_step_trace_v0", blockers, "trace")
    require_const(trace, "offline_only", True, blockers, "trace")
    require_const(trace, "synthetic_fixture", True, blockers, "trace")
    for key in ["provider_call_count", "scorer_call_count", "source_collection_call_count"]:
        require_const(trace, key, 0, blockers, "trace")
    if not isinstance(trace.get("signals"), list):
        blockers.append("trace_signals_missing")
    forbidden = walk_forbidden(trace)
    if forbidden:
        blockers.append(f"trace_forbidden_fields:{','.join(forbidden)}")
    return blockers


def validate_router_decision(decision: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    require_const(decision, "schema_version", "rashe_router_decision_v0", blockers, "router")
    require_const(decision, "offline_only", True, blockers, "router")
    require_const(decision, "enabled", False, blockers, "router")
    require_const(decision, "runtime_authorized", False, blockers, "router")
    for key in ["provider_call_count", "scorer_call_count", "source_collection_call_count"]:
        require_const(decision, key, 0, blockers, "router")
    if decision.get("decision_status") not in {"selected", "ambiguous_reject", "no_match_reject"}:
        blockers.append("router_decision_status_invalid")
    if decision.get("decision_status") != "selected" and decision.get("selected_skill_id") is not None:
        blockers.append("router_rejected_selected_skill_not_null")
    return blockers


def validate_verifier_report(report: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    require_const(report, "schema_version", "rashe_verifier_report_v0", blockers, "verifier")
    require_const(report, "offline_only", True, blockers, "verifier")
    require_const(report, "enabled", False, blockers, "verifier")
    require_const(report, "runtime_authorized", False, blockers, "verifier")
    require_const(report, "candidate_generation_authorized", False, blockers, "verifier")
    for key in ["provider_call_count", "scorer_call_count", "source_collection_call_count", "forbidden_field_violation_count"]:
        require_const(report, key, 0, blockers, "verifier")
    forbidden = walk_forbidden(report)
    if forbidden:
        blockers.append(f"verifier_forbidden_fields:{','.join(forbidden)}")
    return blockers


def validate_skillbank_manifest(root: Path, skill_ids: set[str]) -> tuple[list[str], bool]:
    path = root / "skillbank_manifest.json"
    if not path.exists():
        return ["skillbank_manifest_missing"], False
    data = load_json(path)
    blockers: list[str] = []
    require_const(data, "schema_version", "rashe_skillbank_manifest_v0_1", blockers, "skillbank_manifest")
    require_const(data, "offline_only", True, blockers, "skillbank_manifest")
    require_const(data, "enabled", False, blockers, "skillbank_manifest")
    require_const(data, "runtime_authorized", False, blockers, "skillbank_manifest")
    require_const(data, "provider_call_count", 0, blockers, "skillbank_manifest")
    require_const(data, "scorer_call_count", 0, blockers, "skillbank_manifest")
    require_const(data, "source_collection_call_count", 0, blockers, "skillbank_manifest")
    require_const(data, "candidate_generation_authorized", False, blockers, "skillbank_manifest")
    entries = data.get("skills")
    if not isinstance(entries, list):
        blockers.append("skillbank_manifest_skills_missing")
        return blockers, True
    manifest_ids = {entry.get("skill_id") for entry in entries if isinstance(entry, dict)}
    if manifest_ids != skill_ids:
        blockers.append("skillbank_manifest_skill_ids_mismatch")
    if data.get("skill_count") != len(skill_ids):
        blockers.append("skillbank_manifest_skill_count_mismatch")
    for entry in entries:
        if not isinstance(entry, dict):
            blockers.append("skillbank_manifest_entry_not_object")
            continue
        for key, expected in [("enabled", False), ("offline_only", True), ("runtime_authorized", False)]:
            if entry.get(key) is not expected:
                blockers.append(f"skillbank_manifest_{entry.get('skill_id')}_{key}_invalid")
        if entry.get("schema_version") != "rashe_skill_v0":
            blockers.append(f"skillbank_manifest_{entry.get('skill_id')}_schema_version_invalid")
    return blockers, True


def validate_root(root: Path) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    counters: dict[str, Any] = {
        "schema_file_count": 0,
        "seed_skill_count": 0,
        "skillbank_manifest_present": False,
        "provider_call_count": 0,
        "scorer_call_count": 0,
        "source_collection_call_count": 0,
        "candidate_generation_authorized": False,
        "forbidden_field_violation_count": 0,
    }
    for name in REQUIRED_SCHEMA_FILES:
        path = root / name
        if not path.exists():
            blockers.append(f"schema_missing:{name}")
            continue
        counters["schema_file_count"] += 1
        blockers.extend(validate_schema_file(path))
    skill_dir = root / "seed_skills"
    skill_ids: set[str] = set()
    if not skill_dir.exists():
        blockers.append("seed_skills_dir_missing")
    else:
        for path in sorted(skill_dir.glob("*.json")):
            skill_blockers, skill_id = validate_skill(path)
            blockers.extend(skill_blockers)
            if skill_id:
                skill_ids.add(skill_id)
        counters["seed_skill_count"] = len(skill_ids)
    missing = EXPECTED_SKILLS - skill_ids
    extra = skill_ids - EXPECTED_SKILLS
    if missing:
        blockers.append("seed_skills_missing:" + ",".join(sorted(missing)))
    if extra:
        blockers.append("seed_skills_unexpected:" + ",".join(sorted(extra)))
    manifest_blockers, present = validate_skillbank_manifest(root, skill_ids)
    counters["skillbank_manifest_present"] = present
    blockers.extend(manifest_blockers)
    counters["forbidden_field_violation_count"] = sum(1 for b in blockers if "forbidden_fields" in b)
    return blockers, counters


def evaluate_expected_fixture(trace: dict[str, Any], decision: dict[str, Any], forbidden_hits: list[str]) -> tuple[list[str], dict[str, int]]:
    blockers: list[str] = []
    counts = {
        "positive_fixture_count": 0,
        "reject_fixture_count": 0,
        "case_hash_allowed_count": 0,
        "raw_case_id_rejected_count": 0,
    }
    expected_status = trace.get("expected_router_status")
    expected_skill = trace.get("expected_skill_id")
    expected_reject = trace.get("expected_reject_reason")
    if expected_status == "selected" and "case_hash" in trace and "case_id" not in trace:
        counts["case_hash_allowed_count"] += 1
    if expected_status == "selected":
        counts["positive_fixture_count"] += 1
        if forbidden_hits:
            blockers.append("fixture_selected_has_forbidden_fields")
        if decision.get("decision_status") != "selected" or decision.get("selected_skill_id") != expected_skill:
            blockers.append("fixture_selected_expectation_mismatch")
    elif expected_status in {"ambiguous_reject", "forbidden_field_reject", "path_indicator_reject", "raw_case_id_reject"}:
        counts["reject_fixture_count"] += 1
        if expected_status == "ambiguous_reject":
            if decision.get("decision_status") != "ambiguous_reject":
                blockers.append("fixture_ambiguous_expectation_mismatch")
        elif expected_status == "forbidden_field_reject":
            if not forbidden_hits:
                blockers.append("fixture_forbidden_expected_without_hit")
        elif expected_status == "path_indicator_reject":
            if not forbidden_hits:
                blockers.append("fixture_path_indicator_expected_without_hit")
        elif expected_status == "raw_case_id_reject":
            counts["raw_case_id_rejected_count"] += 1
            if not any(hit.endswith("case_id") or hit == "case_id" for hit in forbidden_hits):
                blockers.append("fixture_raw_case_id_expected_without_hit")
        if expected_reject is None:
            blockers.append("fixture_reject_reason_missing")
    else:
        blockers.append("fixture_expected_status_invalid")
    return blockers, counts


def default_fixture_paths(root: Path) -> tuple[list[Path], list[Path]]:
    fixture_dir = root / "fixtures"
    if not fixture_dir.exists():
        return [], []
    trace_paths = sorted(p for p in fixture_dir.glob("*.json") if p.name != "aggregate_verifier_report.json")
    verifier_paths = sorted(fixture_dir.glob("aggregate_verifier_report.json"))
    return trace_paths, verifier_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--trace", type=Path, action="append", default=[])
    parser.add_argument("--router-decision", type=Path, action="append", default=[])
    parser.add_argument("--verifier-report", type=Path, action="append", default=[])
    parser.add_argument("--no-default-fixtures", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    blockers, counters = validate_root(args.root)
    reject_reasons: Counter[str] = Counter()
    selected_skills: Counter[str] = Counter()
    fixture_count = 0
    positive_fixture_count = 0
    reject_fixture_count = 0
    router_decision_count = 0
    case_hash_allowed_count = 0
    raw_case_id_rejected_count = 0
    expected_fixture_unexpected_forbidden_count = 0

    explicit_inputs_present = bool(args.trace or args.router_decision or args.verifier_report)
    default_traces, default_verifiers = ([], []) if (args.no_default_fixtures or explicit_inputs_present) else default_fixture_paths(args.root)
    if not args.no_default_fixtures and not explicit_inputs_present and not default_traces:
        blockers.append("fixtures_missing")
    trace_inputs = [(path, True) for path in default_traces] + [(path, False) for path in args.trace]
    for path, expected_fixture in trace_inputs:
        trace = load_json(path)
        if not isinstance(trace, dict):
            blockers.append(f"trace_not_object:{path}")
            continue
        fixture_count += 1 if expected_fixture else 0
        trace_blockers = validate_trace(trace)
        forbidden_hits: list[str] = []
        for item in trace_blockers:
            if item.startswith("trace_forbidden_fields:"):
                forbidden_hits = item.split(":", 1)[1].split(",")
                if not expected_fixture:
                    blockers.append(item)
            elif expected_fixture:
                blockers.append(f"fixture_{path.name}_{item}")
            else:
                blockers.append(item)
        decision = route_trace(trace)
        router_decision_count += 1
        blockers.extend(validate_router_decision(decision))
        if expected_fixture:
            fixture_blockers, fixture_counts = evaluate_expected_fixture(trace, decision, forbidden_hits)
            blockers.extend(f"fixture_{path.name}_{b}" for b in fixture_blockers)
            positive_fixture_count += fixture_counts["positive_fixture_count"]
            reject_fixture_count += fixture_counts["reject_fixture_count"]
            case_hash_allowed_count += fixture_counts["case_hash_allowed_count"]
            raw_case_id_rejected_count += fixture_counts["raw_case_id_rejected_count"]
            if forbidden_hits and trace.get("expected_router_status") == "selected":
                expected_fixture_unexpected_forbidden_count += 1
            if trace.get("expected_reject_reason"):
                reject_reasons[str(trace["expected_reject_reason"])] += 1
            elif decision["decision_status"] != "selected":
                reject_reasons[str(decision["reject_reason"])] += 1
        else:
            if decision["decision_status"] == "selected":
                selected_skills[str(decision["selected_skill_id"])] += 1
            else:
                reject_reasons[str(decision["reject_reason"])] += 1
        if expected_fixture and trace.get("expected_router_status") == "selected" and decision["decision_status"] == "selected":
            selected_skills[str(decision["selected_skill_id"])] += 1
    for path in args.router_decision:
        decision = load_json(path)
        if not isinstance(decision, dict):
            blockers.append(f"router_decision_not_object:{path}")
            continue
        router_decision_count += 1
        blockers.extend(validate_router_decision(decision))
    verifier_paths = default_verifiers + args.verifier_report
    for path in verifier_paths:
        report = load_json(path)
        if not isinstance(report, dict):
            blockers.append(f"verifier_report_not_object:{path}")
            continue
        fixture_count += 1 if path in default_verifiers else 0
        blockers.extend(validate_verifier_report(report))
    unexpected_forbidden = sum(1 for b in blockers if "forbidden_fields" in b)
    counters["forbidden_field_violation_count"] = unexpected_forbidden + expected_fixture_unexpected_forbidden_count
    summary = {
        "report_scope": "rashe_v0_offline_skeleton_check",
        "offline_only": True,
        "enabled": False,
        "runtime_authorized": False,
        "provider_call_count": counters["provider_call_count"],
        "scorer_call_count": counters["scorer_call_count"],
        "source_collection_call_count": counters["source_collection_call_count"],
        "candidate_generation_authorized": counters["candidate_generation_authorized"],
        "forbidden_field_violation_count": counters["forbidden_field_violation_count"],
        "schema_file_count": counters["schema_file_count"],
        "seed_skill_count": counters["seed_skill_count"],
        "skillbank_manifest_present": counters["skillbank_manifest_present"],
        "fixture_count": fixture_count,
        "positive_fixture_count": positive_fixture_count,
        "reject_fixture_count": reject_fixture_count,
        "router_decision_count": router_decision_count,
        "selected_skill_counts": dict(selected_skills),
        "reject_reason_counts": dict(reject_reasons),
        "case_hash_allowed_count": case_hash_allowed_count,
        "raw_case_id_rejected_count": raw_case_id_rejected_count,
        "rashe_v0_offline_passed": not blockers,
        "blockers": blockers,
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and blockers:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
