#!/usr/bin/env python3
"""Check bounded RASHE candidate proposer spec artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_proposals")
SOURCE_DIAGNOSTICS_COMMIT = "cc21c96b70ab51c2bf586c0e79cdde3838dcb05d"
REVIEWED_APPROVAL_COMMIT = "b03b155210faaf534ab168bd955fe8e655e83aaa"
ROUTE_MODEL = "gpt-4.1"
ALLOWED_SKILLS = ["bfcl_multi_turn_state_tracking", "bfcl_hallucination_abstain"]
DISALLOWED_SKILLS = [
    "bfcl_web_search_decomposition",
    "bfcl_memory_retrieve_before_answer",
    "bfcl_parser_feedback_retry",
]
REQUIRED_FILES = {"SKILL.md", "candidate_spec.json", "no_leakage_audit.json"}
REQUIRED_EVIDENCE = {
    "bfcl_multi_turn_state_tracking": {
        "primary_bucket_total": 80,
        "category_coverage_count": 4,
        "compact_evidence": {
            "multi_turn_base": {"multi_turn_state_lost": 20},
            "multi_turn_long_context": {"multi_turn_state_lost": 20},
            "multi_turn_miss_param": {"multi_turn_state_lost": 20},
            "multi_turn_miss_func": {"multi_turn_state_lost": 20},
        },
    },
    "bfcl_hallucination_abstain": {
        "primary_bucket_total": 40,
        "category_coverage_count": 2,
        "compact_evidence": {
            "hallucination": {"unsupported_hallucinated_answer": 20},
            "irrelevance": {"irrelevant_tool_call": 20},
        },
    },
}
REQUIRED_FALSE = (
    "candidate_generation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
)
AUDIT_FALSE = (
    "prompt_material_used",
    "trace_material_used",
    "provider_exchange_material_used",
    "identity_material_used",
    "answer_key_material_used",
    "scorer_material_used",
    "repair_material_used",
    "holdout_or_full_suite_material_used",
    "credential_material_used",
    "source_slot_mapping_used",
    "candidate_jsonl_or_pool_created",
)
FORBIDDEN_TEXT = (
    "api_key",
    "secret_token",
    "https://",
    "case_id",
    "case id",
    "raw prompt",
    "raw trace",
    "raw payload",
    "provider request",
    "provider response",
    "gold",
    "expected",
    "reference",
    "scorer diff",
    "feedback",
    "candidate output",
    "source nonce",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _relative_files(root: Path) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _content_blockers(root: Path) -> list[str]:
    blockers: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        lowered_name = path.name.lower()
        if lowered_name.endswith(".jsonl"):
            blockers.append(f"candidate_proposer_jsonl_forbidden:{path}")
        rel = str(path.relative_to(root)).lower()
        for disallowed in DISALLOWED_SKILLS:
            if disallowed in rel:
                blockers.append(f"candidate_proposer_disallowed_skill_path:{path}")
        text = _read_text(path).lower()
        for fragment in FORBIDDEN_TEXT:
            if fragment in text:
                blockers.append(f"candidate_proposer_forbidden_text:{path}:{fragment}")
    return blockers


def _validate_spec(skill_id: str, spec: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = {
        "artifact_kind": "rashe_bounded_candidate_proposer_spec",
        "skill_id": skill_id,
        "source_diagnostics_commit": SOURCE_DIAGNOSTICS_COMMIT,
        "reviewed_approval_commit": REVIEWED_APPROVAL_COMMIT,
        "route_model": ROUTE_MODEL,
        "authorized_scope": "bounded_candidate_proposer_execution_only",
        "candidate_artifact_format": "spec_only_no_jsonl_no_pool",
    }
    for key, value in expected.items():
        if spec.get(key) != value:
            blockers.append(f"candidate_proposer_spec_{skill_id}_{key}_invalid:{spec.get(key)!r}")
    for key in REQUIRED_FALSE:
        if spec.get(key) is not False:
            blockers.append(f"candidate_proposer_spec_{skill_id}_{key}_not_false:{spec.get(key)!r}")
    evidence = REQUIRED_EVIDENCE[skill_id]
    for key in ["primary_bucket_total", "category_coverage_count", "compact_evidence"]:
        if spec.get(key) != evidence[key]:
            blockers.append(f"candidate_proposer_spec_{skill_id}_{key}_invalid")
    inputs = set(spec.get("provenance_inputs") or [])
    required_inputs = {
        "compact_source_diagnostics",
        "failure_bucket_counts",
        "category_coverage_counts",
        "frozen_skill_bucket_mapping",
        "no_leakage_booleans",
        "route_metadata_gpt_4_1",
    }
    if inputs != required_inputs:
        blockers.append(f"candidate_proposer_spec_{skill_id}_provenance_inputs_invalid:{sorted(inputs)}")
    return blockers


def _validate_audit(skill_id: str, audit: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if audit.get("artifact_kind") != "rashe_bounded_candidate_proposer_no_leakage_audit":
        blockers.append(f"candidate_proposer_audit_{skill_id}_kind_invalid:{audit.get('artifact_kind')!r}")
    if audit.get("skill_id") != skill_id:
        blockers.append(f"candidate_proposer_audit_{skill_id}_skill_id_invalid:{audit.get('skill_id')!r}")
    if audit.get("audit_passed") is not True:
        blockers.append(f"candidate_proposer_audit_{skill_id}_not_passed:{audit.get('audit_passed')!r}")
    if audit.get("diagnostic_summary_only") is not True:
        blockers.append(f"candidate_proposer_audit_{skill_id}_diagnostic_summary_only_not_true:{audit.get('diagnostic_summary_only')!r}")
    for key in AUDIT_FALSE:
        if audit.get(key) is not False:
            blockers.append(f"candidate_proposer_audit_{skill_id}_{key}_not_false:{audit.get(key)!r}")
    return blockers


def validate_root(root: Path = DEFAULT_ROOT) -> list[str]:
    blockers: list[str] = []
    if not root.exists():
        return [f"candidate_proposer_root_missing:{root}"]
    if not root.is_dir():
        return [f"candidate_proposer_root_not_directory:{root}"]
    skill_dirs = sorted(path.name for path in root.iterdir() if path.is_dir())
    if set(skill_dirs) != set(ALLOWED_SKILLS):
        blockers.append(f"candidate_proposer_skill_dirs_invalid:{skill_dirs}")
    extra_files_at_root = sorted(path.name for path in root.iterdir() if path.is_file())
    if extra_files_at_root:
        blockers.append(f"candidate_proposer_root_extra_files:{extra_files_at_root}")
    blockers.extend(_content_blockers(root))
    for skill_id in ALLOWED_SKILLS:
        skill_dir = root / skill_id
        if not skill_dir.is_dir():
            blockers.append(f"candidate_proposer_skill_dir_missing:{skill_id}")
            continue
        files = {path.name for path in skill_dir.iterdir() if path.is_file()}
        if files != REQUIRED_FILES:
            blockers.append(f"candidate_proposer_files_invalid:{skill_id}:{sorted(files)}")
        nested_dirs = [path.name for path in skill_dir.iterdir() if path.is_dir()]
        if nested_dirs:
            blockers.append(f"candidate_proposer_nested_dirs_forbidden:{skill_id}:{nested_dirs}")
        try:
            spec = load_json(skill_dir / "candidate_spec.json")
            audit = load_json(skill_dir / "no_leakage_audit.json")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            blockers.append(f"candidate_proposer_load_failed:{skill_id}:{exc}")
            continue
        blockers.extend(_validate_spec(skill_id, spec))
        blockers.extend(_validate_audit(skill_id, audit))
        skill_text = _read_text(skill_dir / "SKILL.md") if (skill_dir / "SKILL.md").exists() else ""
        for required in [skill_id, SOURCE_DIAGNOSTICS_COMMIT, REVIEWED_APPROVAL_COMMIT, ROUTE_MODEL, "spec_only_no_jsonl_no_pool"]:
            if required not in skill_text:
                blockers.append(f"candidate_proposer_skill_md_missing:{skill_id}:{required}")
    return blockers


def check(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    blockers = validate_root(root)
    files = [str(path) for path in _relative_files(root)] if root.exists() and root.is_dir() else []
    return {
        "report_scope": "rashe_candidate_proposer_artifacts_check",
        "root": str(root),
        "allowed_seed_skills": ALLOWED_SKILLS,
        "source_diagnostics_commit": SOURCE_DIAGNOSTICS_COMMIT,
        "reviewed_approval_commit": REVIEWED_APPROVAL_COMMIT,
        "route_model": ROUTE_MODEL,
        "artifact_files": files,
        "rashe_candidate_proposer_artifacts_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.root)
    except Exception as exc:  # noqa: BLE001 - checker should fail closed with compact blocker.
        summary = {
            "report_scope": "rashe_candidate_proposer_artifacts_check",
            "root": str(args.root),
            "rashe_candidate_proposer_artifacts_passed": False,
            "blockers": [f"candidate_proposer_artifacts_check_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_candidate_proposer_artifacts_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
