#!/usr/bin/env python3
"""Offline checker for RASHE proposal draft schema and sanitized fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from grc.skills.schema import find_forbidden_fields
from grc.skills.trace_buffer import find_path_indicators

DEFAULT_SCHEMA = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/proposal_draft.schema.json")
DEFAULT_FIXTURE_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/fixtures/proposal_drafts")
ALLOWED_SOURCE_SCOPES = {"synthetic", "approved_compact"}
ALLOWED_PROPOSAL_KINDS = {
    "skill_metadata_refinement_draft",
    "progressive_disclosure_policy_draft",
    "router_policy_refinement_draft",
}
REQUIRED_FIELDS = (
    "schema_version",
    "proposal_id",
    "proposal_kind",
    "source_trace_hashes",
    "source_scope",
    "selected_skill_id",
    "router_decision_status",
    "rationale_tags",
    "blocked_reason",
    "no_leakage",
    "offline_only",
    "enabled",
    "runtime_behavior_authorized",
    "prompt_injection_authorized",
    "retry_authorized",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
    "provider_call_count",
    "scorer_call_count",
    "source_collection_call_count",
)
REQUIRED_NO_LEAKAGE_FALSE_FIELDS = (
    "gold_used",
    "expected_used",
    "scorer_diff_used",
    "candidate_output_used",
    "repair_output_used",
    "holdout_feedback_used",
    "full_suite_feedback_used",
    "raw_trace_used",
    "raw_provider_payload_used",
    "raw_case_identifier_used",
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
FORBIDDEN_RUNTIME_KEYS = {
    "prompt_injection_text",
    "retry_policy",
    "provider_invocation",
    "scorer_invocation",
    "source_invocation",
    "bfcl_candidate_jsonl",
    "dev_manifest",
    "holdout_manifest",
}
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


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def fixture_paths(root: Path) -> list[Path]:
    return sorted(root.glob("*.json"))


def _walk_keys(obj: Any, path: str = "") -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_s = str(key)
            next_path = f"{path}.{key_s}" if path else key_s
            hits.append((key_s, next_path))
            hits.extend(_walk_keys(value, next_path))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            hits.extend(_walk_keys(value, f"{path}[{index}]"))
    return hits


def forbidden_evidence_hits(obj: dict[str, Any]) -> list[str]:
    hits = [path for key, path in _walk_keys(obj) if key.lower() in FORBIDDEN_EVIDENCE_KEYS]
    hits.extend(hit for hit in find_forbidden_fields(obj) if not hit.endswith("case_id") and hit != "case_id")
    return sorted(set(hits))


def raw_case_identifier_hits(obj: dict[str, Any]) -> list[str]:
    return [path for key, path in _walk_keys(obj) if key.lower() in {"case_id", "raw_case_id", "raw_case_identifier"}]


def raw_trace_or_provider_hits(obj: dict[str, Any]) -> list[str]:
    key_hits = [path for key, path in _walk_keys(obj) if key.lower() in {"raw_trace", "raw_trace_text", "raw_provider_payload", "provider_payload_path"}]
    path_hits = find_path_indicators(obj)
    return sorted(set(key_hits + path_hits))


def runtime_forbidden_hits(obj: dict[str, Any]) -> list[str]:
    return [path for key, path in _walk_keys(obj) if key.lower() in FORBIDDEN_RUNTIME_KEYS]


def schema_blockers(obj: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in obj:
            blockers.append(f"required_missing:{field}")
    if obj.get("schema_version") != "rashe_proposal_draft_v0":
        blockers.append("schema_version_invalid")
    if obj.get("proposal_kind") not in ALLOWED_PROPOSAL_KINDS:
        blockers.append("proposal_kind_not_allowed")
    if obj.get("source_scope") not in ALLOWED_SOURCE_SCOPES:
        blockers.append("source_scope_not_allowed")
    if not isinstance(obj.get("source_trace_hashes"), list) or not obj.get("source_trace_hashes"):
        blockers.append("source_trace_hashes_missing")
    elif any(not isinstance(value, str) or not value.startswith("sha256:") for value in obj["source_trace_hashes"]):
        blockers.append("source_trace_hash_invalid")
    if not isinstance(obj.get("rationale_tags"), list) or not obj.get("rationale_tags"):
        blockers.append("rationale_tags_missing")
    no_leakage = obj.get("no_leakage")
    if not isinstance(no_leakage, dict):
        blockers.append("no_leakage_missing")
    else:
        for field in REQUIRED_NO_LEAKAGE_FALSE_FIELDS:
            if no_leakage.get(field) is not False:
                blockers.append(f"no_leakage_{field}_not_false")
    for field in AUTH_FALSE_FIELDS:
        if obj.get(field) is not False:
            blockers.append(f"{field}_not_false")
    for field in CALL_COUNT_FIELDS:
        if obj.get(field) != 0:
            blockers.append(f"call_count_nonzero:{field}")
    if obj.get("blocked_reason") is not None and not isinstance(obj.get("blocked_reason"), str):
        blockers.append("blocked_reason_invalid")
    return blockers


def reject_reason(obj: dict[str, Any]) -> str | None:
    if any(obj.get(field, 0) != 0 for field in CALL_COUNT_FIELDS):
        return "call_count_nonzero"
    if raw_case_identifier_hits(obj):
        return "raw_case_identifier"
    if raw_trace_or_provider_hits(obj):
        return "raw_trace_or_provider_payload"
    if forbidden_evidence_hits(obj):
        return "forbidden_evidence"
    if obj.get("source_scope") not in ALLOWED_SOURCE_SCOPES:
        return "source_scope_not_allowed"
    if runtime_forbidden_hits(obj):
        return "forbidden_runtime_or_candidate_surface"
    blockers = schema_blockers(obj)
    if blockers:
        if any(blocker == "proposal_kind_not_allowed" for blocker in blockers):
            return "proposal_kind_not_allowed"
        return "schema_invalid"
    return None


def check(schema_path: Path = DEFAULT_SCHEMA, fixture_root: Path = DEFAULT_FIXTURE_ROOT) -> dict[str, Any]:
    blockers: list[str] = []
    if not schema_path.exists():
        blockers.append("proposal_schema_missing")
    else:
        schema = load_json(schema_path)
        if not isinstance(schema, dict):
            blockers.append("proposal_schema_not_object")
        elif set(schema.get("properties", {}).get("proposal_kind", {}).get("enum", [])) != ALLOWED_PROPOSAL_KINDS:
            blockers.append("proposal_kind_enum_mismatch")
    paths = fixture_paths(fixture_root)
    if not paths:
        blockers.append("proposal_fixtures_missing")
    counters = {
        "proposal_fixture_count": 0,
        "accepted_proposal_draft_count": 0,
        "rejected_proposal_draft_count": 0,
        "forbidden_evidence_reject_count": 0,
        "raw_case_identifier_reject_count": 0,
        "raw_trace_or_provider_payload_reject_count": 0,
        "source_scope_reject_count": 0,
        "call_count_nonzero_reject_count": 0,
        "candidate_generation_authorized_count": 0,
        "runtime_behavior_authorized_count": 0,
        "prompt_injection_authorized_count": 0,
        "scorer_authorized_count": 0,
        "performance_evidence_count": 0,
    }
    for path in paths:
        payload = load_json(path)
        counters["proposal_fixture_count"] += 1
        if not isinstance(payload, dict):
            blockers.append(f"proposal_not_object:{path.name}")
            continue
        for field, counter in [
            ("candidate_generation_authorized", "candidate_generation_authorized_count"),
            ("runtime_behavior_authorized", "runtime_behavior_authorized_count"),
            ("prompt_injection_authorized", "prompt_injection_authorized_count"),
            ("scorer_authorized", "scorer_authorized_count"),
            ("performance_evidence", "performance_evidence_count"),
        ]:
            if payload.get(field) is not False:
                counters[counter] += 1
        reason = reject_reason(payload)
        expected_accept = path.name.startswith("accept_")
        if expected_accept:
            if reason is not None:
                blockers.append(f"accepted_fixture_rejected:{path.name}:{reason}")
            else:
                counters["accepted_proposal_draft_count"] += 1
        else:
            if reason is None:
                blockers.append(f"reject_fixture_accepted:{path.name}")
                continue
            counters["rejected_proposal_draft_count"] += 1
            if reason == "forbidden_evidence":
                counters["forbidden_evidence_reject_count"] += 1
            elif reason == "raw_case_identifier":
                counters["raw_case_identifier_reject_count"] += 1
            elif reason == "raw_trace_or_provider_payload":
                counters["raw_trace_or_provider_payload_reject_count"] += 1
            elif reason == "source_scope_not_allowed":
                counters["source_scope_reject_count"] += 1
            elif reason == "call_count_nonzero":
                counters["call_count_nonzero_reject_count"] += 1
    for counter in [
        "candidate_generation_authorized_count",
        "runtime_behavior_authorized_count",
        "prompt_injection_authorized_count",
        "scorer_authorized_count",
        "performance_evidence_count",
    ]:
        if counters[counter] != 0:
            blockers.append(f"{counter}_nonzero")
    summary = {
        "report_scope": "rashe_proposer_schema_check",
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
        **counters,
        "proposer_schema_passed": not blockers,
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
    if args.strict and not summary["proposer_schema_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
