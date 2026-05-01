#!/usr/bin/env python3
"""Check source diagnostic interpretation spec wording stays fail-closed."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_DOC = Path("docs/stage1_rashe_source_diagnostic_interpretation.md")
SEED_SKILLS = {
    "bfcl_web_search_decomposition": ["search_query_too_broad", "fetch_missing_after_search", "wrong_first_tool"],
    "bfcl_memory_retrieve_before_answer": ["memory_not_retrieved", "memory_update_when_should_search"],
    "bfcl_multi_turn_state_tracking": ["multi_turn_state_lost", "invalid_tool_call_format"],
    "bfcl_parser_feedback_retry": ["parser_schema_failure", "final_answer_before_tool"],
    "bfcl_hallucination_abstain": ["unsupported_hallucinated_answer", "answered_without_tool", "irrelevant_tool_call"],
}
FORBIDDEN_PHRASES = (
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


def check(path: Path = DEFAULT_DOC) -> dict:
    blockers: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"doc_path": str(path), "blockers": [f"interpretation_doc_missing:{exc}"]}
    for skill, buckets in SEED_SKILLS.items():
        if skill not in text:
            blockers.append(f"interpretation_seed_skill_missing:{skill}")
        for bucket in buckets:
            if bucket not in text:
                blockers.append(f"interpretation_bucket_missing:{skill}:{bucket}")
    for required in ["12/160", "at least `2` signed categories", "all primary bucket counts are below `12`", "skill design review"]:
        if required not in text:
            blockers.append(f"interpretation_threshold_wording_missing:{required}")
    for phrase in FORBIDDEN_PHRASES:
        if phrase not in text:
            blockers.append(f"interpretation_forbidden_boundary_missing:{phrase}")
    for bad in ["candidate generation is authorized", "scorer is authorized", "Huawei readiness is approved", "performance evidence is ready"]:
        if bad.lower() in text.lower():
            blockers.append(f"interpretation_unauthorized_claim_present:{bad}")
    return {"doc_path": str(path), "rashe_source_diagnostic_interpretation_passed": not blockers, "blockers": blockers}


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
