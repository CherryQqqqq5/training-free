#!/usr/bin/env python3
"""Offline checker for RASHE evolution loop schema and synthetic fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from grc.skills.schema import find_forbidden_fields
from grc.skills.trace_buffer import find_path_indicators

DEFAULT_SCHEMA = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/evolution_loop.schema.json")
DEFAULT_FIXTURE_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/fixtures/evolution_loop")
ALLOWED_SOURCE_SCOPES = {"synthetic", "approved_compact"}
ALLOWED_PROPOSAL_KINDS = {"skill_metadata_refinement_draft", "progressive_disclosure_policy_draft", "router_policy_refinement_draft"}
CHAIN_FIELDS = ("trace_buffer_summary", "router_decision_summary", "proposal_draft", "human_review", "skill_metadata_patch_plan")
CALL_COUNT_FIELDS = ("provider_call_count", "scorer_call_count", "source_collection_call_count")
AUTH_FALSE_FIELDS = (
    "enabled",
    "runtime_behavior_authorized",
    "prompt_injection_authorized",
    "retry_authorized",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
)
FORBIDDEN_EVIDENCE_KEYS = {
    "gold",
    "expected",
    "answer",
    "ground_truth",
    "oracle",
    "checker",
    "reference",
    "possible_answer",
    "score",
    "scorer_diff",
    "candidate",
    "candidate_output",
    "repair",
    "repair_output",
    "holdout_feedback",
    "full_suite_feedback",
}
PATCH_PLAN_FORBIDDEN_TRUE_FIELDS = (
    "contains_prompt_injection_text",
    "contains_retry_policy",
    "contains_candidate_jsonl",
    "contains_dev_holdout_manifest",
)


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def fixture_paths(root: Path) -> list[Path]:
    return sorted(root.glob("*.json"))


def walk_keys(obj: Any, path: str = "") -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_s = str(key)
            next_path = f"{path}.{key_s}" if path else key_s
            hits.append((key_s, next_path))
            hits.extend(walk_keys(value, next_path))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            hits.extend(walk_keys(value, f"{path}[{index}]"))
    return hits


def forbidden_evidence_hits(obj: dict[str, Any]) -> list[str]:
    hits = [path for key, path in walk_keys(obj) if key.lower() in FORBIDDEN_EVIDENCE_KEYS]
    hits.extend(hit for hit in find_forbidden_fields(obj) if not hit.endswith("case_id") and hit != "case_id")
    return sorted(set(hits))


def schema_blockers(obj: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if obj.get("schema_version") != "rashe_evolution_loop_v0":
        blockers.append("schema_version_invalid")
    if obj.get("loop_stage") != "trace_buffer_summary_to_skill_metadata_patch_plan":
        blockers.append("loop_stage_invalid")
    for field in CHAIN_FIELDS:
        if not isinstance(obj.get(field), dict):
            blockers.append(f"chain_field_missing:{field}")
    proposal = obj.get("proposal_draft") if isinstance(obj.get("proposal_draft"), dict) else {}
    if proposal.get("proposal_kind") not in ALLOWED_PROPOSAL_KINDS:
        blockers.append("proposal_kind_not_allowed")
    if obj.get("source_scope") not in ALLOWED_SOURCE_SCOPES:
        blockers.append("source_scope_not_allowed")
    for field in AUTH_FALSE_FIELDS:
        if obj.get(field) is not False:
            blockers.append(f"auth_flag_true:{field}")
    for field in CALL_COUNT_FIELDS:
        if obj.get(field) != 0:
            blockers.append(f"call_count_nonzero:{field}")
    review = obj.get("human_review") if isinstance(obj.get("human_review"), dict) else {}
    if review.get("gold_or_expected_used") is not False or review.get("scorer_diff_used") is not False:
        blockers.append("human_review_leakage_flag_true")
    patch = obj.get("skill_metadata_patch_plan") if isinstance(obj.get("skill_metadata_patch_plan"), dict) else {}
    if patch.get("patch_plan_kind") != "inert_docs_metadata_patch_plan":
        blockers.append("patch_plan_kind_invalid")
    for field in PATCH_PLAN_FORBIDDEN_TRUE_FIELDS:
        if patch.get(field) is not False:
            blockers.append(f"forbidden_patch_plan_surface:{field}")
    if find_path_indicators(obj):
        blockers.append("path_indicator")
    return blockers


def reject_reason(obj: dict[str, Any]) -> str | None:
    if forbidden_evidence_hits(obj):
        return "forbidden_evidence"
    blockers = schema_blockers(obj)
    if any(blocker.startswith("call_count_nonzero") for blocker in blockers):
        return "call_count_nonzero"
    if any(blocker == "source_scope_not_allowed" for blocker in blockers):
        return "source_scope_not_allowed"
    if any(blocker == "proposal_kind_not_allowed" for blocker in blockers):
        return "proposal_kind_not_allowed"
    if any(blocker.startswith("auth_flag_true") for blocker in blockers):
        return "auth_flag_true"
    if any(blocker.startswith("forbidden_patch_plan_surface") for blocker in blockers):
        return "forbidden_patch_plan_surface"
    if any(blocker in {"human_review_leakage_flag_true", "path_indicator"} for blocker in blockers):
        return "forbidden_evidence"
    if blockers:
        return "schema_invalid"
    return None


def check(schema_path: Path = DEFAULT_SCHEMA, fixture_root: Path = DEFAULT_FIXTURE_ROOT) -> dict[str, Any]:
    blockers: list[str] = []
    if not schema_path.exists():
        blockers.append("evolution_loop_schema_missing")
    else:
        schema = load_json(schema_path)
        if not isinstance(schema, dict):
            blockers.append("evolution_loop_schema_not_object")
        elif set(schema.get("required", [])) < set(CHAIN_FIELDS):
            blockers.append("evolution_loop_chain_required_fields_missing")
    paths = fixture_paths(fixture_root)
    if not paths:
        blockers.append("evolution_loop_fixtures_missing")
    counters = Counter()
    blocked_reasons = Counter()
    source_scopes = Counter()
    selected_skills = Counter()
    accepted_by_stage_kind = Counter()
    for path in paths:
        counters["loop_fixture_count"] += 1
        obj = load_json(path)
        if not isinstance(obj, dict):
            blockers.append(f"loop_not_object:{path.name}")
            continue
        source_scopes[str(obj.get("source_scope"))] += 1
        router = obj.get("router_decision_summary") if isinstance(obj.get("router_decision_summary"), dict) else {}
        proposal = obj.get("proposal_draft") if isinstance(obj.get("proposal_draft"), dict) else {}
        selected_skills[str(router.get("selected_skill_id"))] += 1
        for field, counter in [
            ("candidate_generation_authorized", "candidate_generation_authorized_count"),
            ("scorer_authorized", "scorer_authorized_count"),
            ("performance_evidence", "performance_evidence_count"),
        ]:
            if obj.get(field) is not False:
                counters[counter] += 1
        reason = reject_reason(obj)
        expected_accept = path.name.startswith("accept_")
        if expected_accept:
            if reason is not None:
                blockers.append(f"accepted_loop_rejected:{path.name}:{reason}")
            else:
                counters["accepted_loop_count"] += 1
                accepted_by_stage_kind[f"{obj.get('loop_stage')}:{proposal.get('proposal_kind')}"] += 1
        else:
            if reason is None:
                blockers.append(f"reject_loop_accepted:{path.name}")
                continue
            counters["rejected_loop_count"] += 1
            blocked_reasons[reason] += 1
            if reason == "forbidden_evidence":
                counters["forbidden_evidence_reject_count"] += 1
            elif reason == "call_count_nonzero":
                counters["call_count_reject_count"] += 1
            elif reason == "auth_flag_true":
                counters["auth_flag_reject_count"] += 1
    for counter in ["candidate_generation_authorized_count", "scorer_authorized_count", "performance_evidence_count"]:
        if counters[counter] != 0:
            blockers.append(f"{counter}_nonzero")
    summary = {
        "report_scope": "rashe_evolution_loop_check",
        "offline_only": True,
        "enabled": False,
        "runtime_behavior_authorized": False,
        "prompt_injection_authorized": False,
        "retry_authorized": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "provider_call_count": 0,
        "scorer_call_count": 0,
        "source_collection_call_count": 0,
        "loop_fixture_count": counters["loop_fixture_count"],
        "accepted_loop_count": counters["accepted_loop_count"],
        "rejected_loop_count": counters["rejected_loop_count"],
        "accepted_by_stage_kind": dict(sorted(accepted_by_stage_kind.items())),
        "blocked_reason_counts": dict(sorted(blocked_reasons.items())),
        "source_scope_counts": dict(sorted(source_scopes.items())),
        "selected_skill_id_counts": dict(sorted(selected_skills.items())),
        "forbidden_evidence_reject_count": counters["forbidden_evidence_reject_count"],
        "call_count_reject_count": counters["call_count_reject_count"],
        "auth_flag_reject_count": counters["auth_flag_reject_count"],
        "candidate_generation_authorized_count": counters["candidate_generation_authorized_count"],
        "scorer_authorized_count": counters["scorer_authorized_count"],
        "performance_evidence_count": counters["performance_evidence_count"],
        "evolution_loop_schema_passed": not blockers,
        "blockers": blockers,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.schema, args.fixture_root)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["evolution_loop_schema_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
