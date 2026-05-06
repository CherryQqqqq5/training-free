#!/usr/bin/env python3
"""Check the RASHE Stage 4 dev scorer command manifest draft."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_MANIFEST = ARTIFACT_ROOT / "rashe_dev_scorer_command_manifest_v1.json"
ALLOWED_SKILLS = ["bfcl_multi_turn_state_tracking", "bfcl_hallucination_abstain"]
DISALLOWED_SKILLS = ["bfcl_web_search_decomposition", "bfcl_memory_retrieve_before_answer", "bfcl_parser_feedback_retry"]
ALLOWED_CATEGORIES = ["multi_turn_base", "multi_turn_long_context", "multi_turn_miss_param", "multi_turn_miss_func", "hallucination", "irrelevance"]
REQUIRED_RECORDS = ["fixed_count", "regressed_count", "unchanged_count", "candidate_only_failure_count", "baseline_only_failure_count", "cost_delta_bucket", "latency_delta_bucket"]
REQUIRED_COMMAND_IDS = {
    "baseline_dev_smoke": "baseline_command",
    "candidate_dev_smoke": "candidate_command",
    "paired_comparison_check": "paired_comparison_command",
    "cost_latency_report_check": "cost_latency_report_command",
    "regression_report_check": "regression_report_command",
    "checker_suite": "checker_command",
}
FALSE_KEYS = ("authorized", "execution_started", "performance_evidence", "performance_claim_allowed", "sota_3pp_claim_ready", "huawei_acceptance_ready", "raw_outputs_committed")
TRUE_KEYS = ("exact_commands_frozen", "one_attempt_only", "dev_smoke_only", "fresh_output_paths_required", "fail_if_output_exists", "raw_temp_cleanup_required", "compact_manifest_required")
ALLOWED_RAW_KEYS = {"raw_outputs_committed", "raw_temp_cleanup_required"}
FORBIDDEN_KEY_RE = re.compile(r"(^|_)(raw_(?:prompt|trace|payload|provider|request|response|header|body)|prompt_text|trace_text|provider_exchange|case_id|gold|expected|reference|tool_args?|tool_arguments?|scorer_diff|candidate_output)(_|$)", re.I)
FORBIDDEN_VALUE_RE = re.compile(r"sk-[A-Za-z0-9_-]{16,}|https?://|bearer |api key|secret|raw prompt|raw trace|provider exchange|case id|gold answer|expected answer|tool argument values|scorer diff|candidate output text|huawei readiness|\+3pp ready", re.I)
FORBIDDEN_COMMAND_RE = re.compile(r"holdout|full_suite|full_baseline|check_stage1_bfcl_performance_ready\.py|performance_ready|huawei|\+3pp", re.I)


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _walk(value: Any, path: Tuple[str, ...] = ()) -> List[Tuple[Tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(_walk(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk(child, path + (str(index),)))
    return items


def _scan(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    for path, value in _walk(data):
        key = path[-1] if path else ""
        dotted = ".".join(path)
        if key and key not in ALLOWED_RAW_KEYS and FORBIDDEN_KEY_RE.search(key):
            blockers.append("forbidden_key:%s" % dotted)
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append("forbidden_value:%s" % dotted)
    return sorted(set(blockers))


def _flatten_command(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(_flatten_command(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_flatten_command(item) for item in value.values())
    return str(value)


def _fresh_paths(manifest: Dict[str, Any]) -> List[str]:
    paths: List[str] = []
    commands = manifest.get("command_templates") if isinstance(manifest.get("command_templates"), dict) else {}
    for command in commands.values():
        if isinstance(command, dict):
            for key in ("fresh_output_paths", "required_report_paths"):
                values = command.get(key)
                if isinstance(values, list):
                    paths.extend(str(item) for item in values)
    return sorted(set(paths))


def validate_manifest(manifest: Dict[str, Any], *, check_existing_outputs: bool = True) -> List[str]:
    blockers: List[str] = []
    expected = {
        "artifact_kind": "rashe_dev_scorer_command_manifest_v1",
        "approval_status": "pending",
        "manifest_scope": "stage4_dev_scorer_smoke_command_draft_only",
        "measurement_kind": "dev_scorer_smoke_not_performance_claim",
        "max_dev_cases": 12,
        "allowed_bfcl_categories": ALLOWED_CATEGORIES,
        "allowed_skills": ALLOWED_SKILLS,
        "disallowed_skills": DISALLOWED_SKILLS,
        "required_records": REQUIRED_RECORDS,
        "blockers": [],
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            blockers.append("%s_invalid:%r" % (key, manifest.get(key)))
    for key in FALSE_KEYS:
        if manifest.get(key) is not False:
            blockers.append("%s_not_false:%r" % (key, manifest.get(key)))
    for key in TRUE_KEYS:
        if manifest.get(key) is not True:
            blockers.append("%s_not_true:%r" % (key, manifest.get(key)))
    commands = manifest.get("command_templates") if isinstance(manifest.get("command_templates"), dict) else {}
    if set(commands) != set(REQUIRED_COMMAND_IDS):
        blockers.append("command_ids_invalid:%r" % sorted(commands))
    for command_id, command_kind in REQUIRED_COMMAND_IDS.items():
        command = commands.get(command_id) if isinstance(commands.get(command_id), dict) else {}
        if command.get("command_id") != command_id:
            blockers.append("command_id_mismatch:%s" % command_id)
        if command.get("command_kind") != command_kind:
            blockers.append("command_kind_invalid:%s:%r" % (command_id, command.get("command_kind")))
        if command.get("execution_authorized_now") is not False:
            blockers.append("command_execution_not_blocked:%s" % command_id)
        text = _flatten_command(command.get("template") or command.get("template_set") or [])
        if command_id != "checker_suite" and FORBIDDEN_COMMAND_RE.search(text):
            blockers.append("forbidden_command_pattern:%s" % command_id)
    patterns = manifest.get("allowed_command_patterns")
    if not isinstance(patterns, list) or len(patterns) != 8:
        blockers.append("allowed_command_patterns_invalid")
    else:
        joined = "\n".join(str(item) for item in patterns)
        for required in ("scripts/run_bfcl_v4_baseline.sh", "scripts/run_bfcl_v4_patch.sh", "scripts/check_bfcl_paired_comparison.py", "cost_latency_report.json", "regression_report.json"):
            if required not in joined:
                blockers.append("allowed_command_pattern_missing:%s" % required)
        if FORBIDDEN_COMMAND_RE.search(joined):
            blockers.append("allowed_command_patterns_include_forbidden")
    for path in _fresh_paths(manifest):
        if not path.startswith("outputs/artifacts/stage1_bfcl_acceptance/rashe_dev_smoke_v1/"):
            blockers.append("fresh_or_report_path_outside_dev_smoke_root:%s" % path)
        if check_existing_outputs and manifest.get("fail_if_output_exists") is True and Path(path).exists():
            blockers.append("output_path_exists:%s" % path)
    blockers.extend(_scan(manifest))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_MANIFEST, *, require_report: Path | None = None) -> Dict[str, Any]:
    manifest = _load(path)
    blockers = validate_manifest(manifest)
    if require_report is not None and not require_report.exists():
        blockers.append("required_report_missing:%s" % require_report)
    return {
        "report_scope": "rashe_dev_scorer_command_manifest_v1_check",
        "manifest_path": str(path),
        "rashe_dev_scorer_command_manifest_v1_passed": not blockers,
        "approval_status": manifest.get("approval_status"),
        "authorized": manifest.get("authorized"),
        "execution_started": manifest.get("execution_started"),
        "max_dev_cases": manifest.get("max_dev_cases"),
        "allowed_bfcl_categories": manifest.get("allowed_bfcl_categories"),
        "command_count": len(manifest.get("command_templates", {})) if isinstance(manifest.get("command_templates"), dict) else 0,
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--require-report", type=Path)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.manifest, require_report=args.require_report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "rashe_dev_scorer_command_manifest_v1_check", "rashe_dev_scorer_command_manifest_v1_passed": False, "blockers": ["load_failed:%s" % exc]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_dev_scorer_command_manifest_v1_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
