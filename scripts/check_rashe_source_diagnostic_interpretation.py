#!/usr/bin/env python3
"""Check source diagnostic interpretation spec wording stays fail-closed."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_DOC = Path("docs/stage1_rashe_source_diagnostic_interpretation.md")
SEED_SKILLS = {
    "bfcl_web_search_decomposition": ["answered_without_tool", "wrong_first_tool", "search_query_too_broad", "fetch_missing_after_search"],
    "bfcl_memory_retrieve_before_answer": ["memory_not_retrieved", "memory_update_when_should_search", "final_answer_before_tool"],
    "bfcl_multi_turn_state_tracking": ["multi_turn_state_lost", "wrong_first_tool", "final_answer_before_tool"],
    "bfcl_parser_feedback_retry": ["invalid_tool_call_format", "parser_schema_failure"],
    "bfcl_hallucination_abstain": ["unsupported_hallucinated_answer", "irrelevant_tool_call"],
}
ALL_BUCKETS = {
    "answered_without_tool",
    "wrong_first_tool",
    "search_query_too_broad",
    "fetch_missing_after_search",
    "memory_not_retrieved",
    "memory_update_when_should_search",
    "multi_turn_state_lost",
    "invalid_tool_call_format",
    "parser_schema_failure",
    "final_answer_before_tool",
    "irrelevant_tool_call",
    "unsupported_hallucinated_answer",
}
FORBIDDEN_BOUNDARY_PHRASES = (
    "raw prompts",
    "raw case IDs",
    "gold",
    "expected",
    "reference",
    "scorer diff",
    "provider raw payload",
    "performance evidence",
    "+3pp claims",
    "Huawei acceptance",
)
REQUIRED_THRESHOLD_PHRASES = (
    "skill-level aggregate count across that skill's frozen primary buckets",
    "at least `12/160` across the 160 signed source cases",
    "cover at least `2` signed categories",
    "not a single-bucket threshold",
    "every skill-level aggregate is below `12`",
    "skill design review",
)


def parse_mapping(text: str) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    pattern = re.compile(r"^- `(?P<skill>[^`]+)`: (?P<buckets>.+)$", re.MULTILINE)
    for match in pattern.finditer(text):
        skill = match.group("skill")
        buckets = re.findall(r"`([^`]+)`", match.group("buckets"))
        if skill.startswith("bfcl_"):
            mapping[skill] = buckets
    return mapping


def check(path: Path = DEFAULT_DOC) -> dict:
    blockers: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"doc_path": str(path), "blockers": [f"interpretation_doc_missing:{exc}"]}
    mapping = parse_mapping(text)
    if set(mapping) != set(SEED_SKILLS):
        for skill in sorted(set(SEED_SKILLS) - set(mapping)):
            blockers.append(f"interpretation_seed_skill_missing:{skill}")
        for skill in sorted(set(mapping) - set(SEED_SKILLS)):
            blockers.append(f"interpretation_seed_skill_extra:{skill}")
    for skill, expected_buckets in SEED_SKILLS.items():
        actual = mapping.get(skill, [])
        if actual != expected_buckets:
            blockers.append(f"interpretation_bucket_mapping_invalid:{skill}:{actual!r}")
        for bucket in actual:
            if bucket not in ALL_BUCKETS:
                blockers.append(f"interpretation_bucket_not_taxonomy:{skill}:{bucket}")
        missing = [bucket for bucket in expected_buckets if bucket not in actual]
        extra = [bucket for bucket in actual if bucket not in expected_buckets]
        for bucket in missing:
            blockers.append(f"interpretation_bucket_missing:{skill}:{bucket}")
        for bucket in extra:
            blockers.append(f"interpretation_bucket_extra:{skill}:{bucket}")
    for required in REQUIRED_THRESHOLD_PHRASES:
        if required not in text:
            blockers.append(f"interpretation_threshold_wording_missing:{required}")
    for phrase in FORBIDDEN_BOUNDARY_PHRASES:
        if phrase not in text:
            blockers.append(f"interpretation_forbidden_boundary_missing:{phrase}")
    for bad in [
        "candidate generation is authorized",
        "scorer is authorized",
        "Huawei readiness is approved",
        "performance evidence is ready",
        "single bucket count is at least",
    ]:
        if bad.lower() in text.lower():
            blockers.append(f"interpretation_unauthorized_claim_present:{bad}")
    return {
        "doc_path": str(path),
        "seed_skills": sorted(SEED_SKILLS),
        "rashe_source_diagnostic_interpretation_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.doc)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_source_diagnostic_interpretation_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
