#!/usr/bin/env python3
"""Check ABHE artifacts for forbidden raw or scorer-derived material."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

DEFAULT_PATHS = [
    Path("abhe_archive/archive_index.json"),
    Path("abhe_archive/opportunity_table.json"),
    Path("abhe_archive/policy_config.yaml"),
    Path("abhe_archive/state_transitions.jsonl"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_next_evolution_plan.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_planning_ready.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_temporary_trace_extraction_packet.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_bounded_dev_smoke_execution_packet.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_card.schema.json"),
    Path("docs/stage1_abhe_method_overview.md"),
    Path("docs/stage1_abhe_transition_from_rashe.md"),
    Path("docs/stage1_abhe_archive_policy.md"),
    Path("docs/stage1_abhe_trace_packet_boundary.md"),
    Path("docs/stage1_abhe_trace_card_contract.md"),
    Path("docs/stage1_abhe_state_tracking_candidate_sketch.md"),
    Path("docs/stage1_abhe_hallucination_abstain_candidate_sketch.md"),
    Path("docs/stage1_abhe_post_dev_update_contract.md"),
    Path("docs/stage1_abhe_search_memory_watch_split_proposal.md"),
]

ALLOWED_KEY_NAMES = {
    "forbidden_fields",
    "forbidden_mainline_next_steps",
    "raw_material_persisted",
    "candidate_pool_ready",
    "candidate_generation_authorized",
    "candidate_jsonl_authorized",
    "candidate_activation_authorized",
    "source_evidence_count",
    "source_evidence_role",
    "raw_prompt_allowed",
    "raw_trace_allowed",
    "raw_payload_allowed",
    "raw_case_id_allowed",
    "gold_expected_allowed",
    "scorer_diff_allowed",
    "candidate_output_allowed",
    "raw_material_absent",
}

FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw_(?:prompt|trace|payload|provider|request|response|header|body|case_id)|"
    r"prompt_text|trace_text|provider_exchange|case_id|gold|expected|reference|"
    r"tool_args?|tool_arguments?|scorer_diff|candidate_output|api_key|bearer_token|"
    r"endpoint_value)(_|$)",
    re.I,
)

NEGATIVE_BOUNDARY_CUES = (
    "forbidden",
    "must not",
    "do not",
    "does not",
    "not allowed",
    "not authorize",
    "not include",
    "not contain",
    "absent",
    "excluded",
    "false",
    "fail-closed",
    "no raw",
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|bearer\s+|api key|secret|raw prompt|raw trace|"
     r"raw payload|provider exchange|case id|gold answer|expected answer|reference answer|"
     r"tool argument values|scorer diff|candidate output text|endpoint value"),
    re.I,
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> List[Any]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError("%s:%d invalid jsonl: %s" % (path, line_no, exc))
    return rows


def _load_yamlish(path: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    stack: List[Tuple[int, Any]] = [(-1, data)]
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if stripped.startswith("- "):
            if not isinstance(parent, list):
                continue
            parent.append(stripped[2:].strip())
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            child: Any = []
            if isinstance(parent, dict):
                parent[key] = child
            stack.append((indent, child))
        else:
            if value.lower() == "true":
                parsed: Any = True
            elif value.lower() == "false":
                parsed = False
            else:
                parsed = value
            if isinstance(parent, dict):
                parent[key] = parsed
    return data


def load_path(path: Path) -> Any:
    if path.suffix == ".json":
        return _load_json(path)
    if path.suffix == ".jsonl":
        return _load_jsonl(path)
    if path.suffix in {".yaml", ".yml"}:
        return _load_yamlish(path)
    if path.suffix == ".md":
        return {
            "markdown_lines": [
                {"line_number": line_no, "text": line}
                for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
            ]
        }
    return path.read_text(encoding="utf-8")


def _walk(value: Any, path: Tuple[str, ...] = ()) -> Iterable[Tuple[Tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            for item in _walk(child, path + (str(key),)):
                yield item
    elif isinstance(value, list):
        for index, child in enumerate(value):
            for item in _walk(child, path + (str(index),)):
                yield item


def scan_value(value: Any, *, label: str) -> List[str]:
    blockers: List[str] = []
    for path, child in _walk(value):
        key = path[-1] if path else ""
        dotted = ".".join(path)
        if key and key not in ALLOWED_KEY_NAMES and FORBIDDEN_KEY_RE.search(key):
            blockers.append("%s_forbidden_key:%s" % (label, dotted))
        if isinstance(child, str) and FORBIDDEN_VALUE_RE.search(child):
            if len(path) >= 2 and path[-2] in {"forbidden_fields", "risk_flags"}:
                continue
            if path and path[-1] == "text" and any(cue in child.lower() for cue in NEGATIVE_BOUNDARY_CUES):
                continue
            blockers.append("%s_forbidden_value:%s" % (label, dotted))
    return sorted(set(blockers))


def check_paths(paths: List[Path]) -> Dict[str, Any]:
    blockers: List[str] = []
    checked = []
    for path in paths:
        if not path.exists():
            if path.name == "abhe_next_evolution_plan.json":
                continue
            blockers.append("missing_path:%s" % path)
            continue
        checked.append(str(path))
        try:
            data = load_path(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            blockers.append("load_failed:%s:%s" % (path, exc))
            continue
        blockers.extend(scan_value(data, label=str(path)))
    return {
        "report_scope": "abhe_no_leakage_boundary_check",
        "checked_paths": checked,
        "abhe_no_leakage_boundary_passed": not blockers,
        "blockers": sorted(set(blockers)),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    paths = args.paths or DEFAULT_PATHS
    summary = check_paths(paths)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["abhe_no_leakage_boundary_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
