#!/usr/bin/env python3
"""Validate ABHE candidate spec drafts without materializing executable candidates."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

STATE_TRACKING_SPEC = Path("docs/stage1_abhe_state_tracking_candidate_spec_draft.md")
HALLUCINATION_SPEC = Path("docs/stage1_abhe_hallucination_abstain_candidate_spec_draft.md")
DEFAULT_SPECS = [STATE_TRACKING_SPEC, HALLUCINATION_SPEC]
REQUIRED_SECTIONS = [
    "entry_id",
    "target_behavior_cluster",
    "activation_predicates",
    "non_target_exclusion_predicates",
    "primary_metrics",
    "safety_metrics",
    "telemetry_requirements",
    "stop_loss",
    "rollback",
    "not_authorized_surfaces",
]
FORBIDDEN_SPEC_RE = re.compile(
    r"prompt patch|candidate yaml|candidate jsonl|raw examples?|gold\b|expected answer|"
    r"scorer diff|candidate output",
    re.I,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section_present(text: str, section: str) -> bool:
    return ("%s:" % section) in text


def validate_spec(path: Path, text: str) -> List[str]:
    blockers = []
    label = path.stem
    for section in REQUIRED_SECTIONS:
        if not _section_present(text, section):
            blockers.append("%s_missing_section:%s" % (label, section))
    if FORBIDDEN_SPEC_RE.search(text):
        blockers.append("%s_contains_forbidden_material_reference" % label)
    lowered = text.lower()
    if path == STATE_TRACKING_SPEC:
        required_phrases = [
            "entry_id: `state_tracking_v0`",
            "target_behavior_cluster: `multi_turn_state_lost`",
            "multi-turn only",
            "state carryover evidence required",
            "single-turn excluded",
            "search/memory watch excluded",
            "no mutation",
        ]
    elif path == HALLUCINATION_SPEC:
        required_phrases = [
            "entry_id: `hallucination_abstain_v0`",
            "target_behavior_cluster: `unsupported_or_irrelevant_answer`",
            "answerability failure only",
            "valid actionable tool-use case excluded",
            "false abstain tracked",
            "do not suppress valid tool calls",
        ]
    else:
        required_phrases = []
    for phrase in required_phrases:
        if phrase not in lowered:
            blockers.append("%s_missing_required_phrase:%s" % (label, phrase))
    blockers.extend(scan_value({"markdown_lines": [{"text": line} for line in text.splitlines()]}, label=str(path)))
    return sorted(set(blockers))


def check(paths: List[Path] = DEFAULT_SPECS) -> Dict[str, Any]:
    blockers = []
    checked = []
    for path in paths:
        if not path.exists():
            blockers.append("candidate_spec_missing:%s" % path)
            continue
        checked.append(str(path))
        blockers.extend(validate_spec(path, _read(path)))
    return {
        "report_scope": "abhe_candidate_spec_draft_check",
        "checked_paths": checked,
        "candidate_rule_generated": False,
        "candidate_yaml_generated": False,
        "candidate_jsonl_generated": False,
        "abhe_candidate_spec_drafts_passed": not blockers,
        "blockers": sorted(set(blockers)),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.paths or DEFAULT_SPECS)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["abhe_candidate_spec_drafts_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
