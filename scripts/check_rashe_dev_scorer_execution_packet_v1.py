#!/usr/bin/env python3
"""Check the RASHE Stage 4 dev scorer execution packet draft."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scripts.check_rashe_dev_scorer_command_manifest_v1 import ALLOWED_CATEGORIES, ALLOWED_SKILLS, DISALLOWED_SKILLS, REQUIRED_RECORDS, validate_manifest as validate_command_manifest

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_PACKET = ARTIFACT_ROOT / "rashe_dev_scorer_execution_packet_v1.json"
DEFAULT_DEV_MANIFEST = ARTIFACT_ROOT / "rashe_dev_manifest_v1.json"
DEFAULT_COMMAND_MANIFEST = ARTIFACT_ROOT / "rashe_dev_scorer_command_manifest_v1.json"
STOP_LOSS = ["raw_leakage", "unexpected_provider_profile_path", "case_count_exceeds_cap", "provider_model_protocol_mismatch", "dev_manifest_drift", "disallowed_skill_selected", "candidate_jsonl_or_pool_created", "holdout_or_full_baseline_touched", "scorer_or_bfcl_command_outside_allowlist", "output_path_exists", "cost_token_request_cap_exceeded", "missing_paired_records", "checker_failure", "incomplete_compact_manifest", "candidate_artifacts_drift_from_spec_only"]
FALSE_KEYS = ("authorized", "execution_started", "holdout_authorized", "full_suite_authorized", "full_baseline_authorized", "candidate_jsonl_authorized", "candidate_pool_ready", "candidate_outputs_persisted", "candidate_activation_authorized", "raw_outputs_committed", "performance_evidence", "performance_claim_allowed", "sota_3pp_claim_ready", "huawei_acceptance_ready", "provider_calls_authorized", "bfcl_generate_authorized", "bfcl_evaluate_authorized", "scorer_authorized", "scorer_execution_authorized", "baseline_command_authorized", "candidate_command_authorized", "paired_comparison_command_authorized", "cost_latency_report_command_authorized", "regression_report_command_authorized")
TRUE_KEYS = ("execution_packet", "one_attempt_only", "dev_smoke_only", "exact_commands_frozen", "fresh_output_paths_required", "fail_if_output_exists", "raw_temp_cleanup_required", "compact_manifest_required", "same_provider_model_protocol_required", "fixed_dev_manifest_required", "paired_comparison_required", "baseline_run_required", "candidate_run_required")
ALLOWED_RAW_KEYS = {"raw_outputs_committed", "raw_temp_cleanup_required"}
ALLOWED_FORBIDDEN_LIST_VALUES = {"raw_prompt", "raw_trace", "raw_payload", "provider_exchange", "case_identifier", "gold_answer", "expected_answer", "tool_argument_values", "scorer_delta", "candidate_output_text"}
FORBIDDEN_KEY_RE = re.compile(r"(^|_)(raw_(?:prompt|trace|payload|provider|request|response|header|body)|prompt_text|trace_text|provider_exchange|case_id|gold|expected|reference|tool_args?|tool_arguments?|scorer_diff|candidate_output)(_|$)", re.I)
FORBIDDEN_VALUE_RE = re.compile(r"sk-[A-Za-z0-9_-]{16,}|https?://|bearer |api key|secret|raw prompt|raw trace|provider exchange|case id|gold answer|expected answer|tool argument values|scorer diff|candidate output text|huawei readiness|\+3pp ready", re.I)
FORBIDDEN_ALLOWED_PATTERN_RE = re.compile(r"holdout|full_suite|full_baseline|check_stage1_bfcl_performance_ready\.py|performance_ready|huawei|\+3pp", re.I)


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
        if key and key not in ALLOWED_RAW_KEYS and key != "forbidden_material" and FORBIDDEN_KEY_RE.search(key):
            blockers.append("forbidden_key:%s" % dotted)
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if len(path) >= 2 and path[-2] == "forbidden_material" and value in ALLOWED_FORBIDDEN_LIST_VALUES:
                continue
            blockers.append("forbidden_value:%s" % dotted)
    return sorted(set(blockers))


def validate_dev_manifest(dev: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    expected = {
        "artifact_kind": "rashe_dev_manifest_v1",
        "approval_status": "pending",
        "authorized": False,
        "execution_started": False,
        "manifest_scope": "fixed_dev_smoke_manifest_draft_only",
        "measurement_kind": "dev_scorer_smoke_not_performance_claim",
        "fixed_dev_manifest_required": True,
        "fixed_dev_manifest_status": "pending_reviewer_confirmation",
        "max_dev_cases": 12,
        "dev_case_selection_mode": "compact_bucket_counts_only_no_case_ids",
        "allowed_bfcl_categories": ALLOWED_CATEGORIES,
        "allowed_skills": ALLOWED_SKILLS,
        "disallowed_skills": DISALLOWED_SKILLS,
        "candidate_activation_mode": "in_memory_spec_only_no_jsonl_no_pool",
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "candidate_outputs_persisted": False,
        "holdout_authorized": False,
        "full_suite_authorized": False,
        "full_baseline_authorized": False,
        "dev_holdout_material_used": False,
        "performance_evidence": False,
        "performance_claim_allowed": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_outputs_committed": False,
        "required_records": REQUIRED_RECORDS,
        "blockers": [],
    }
    for key, value in expected.items():
        if dev.get(key) != value:
            blockers.append("dev_%s_invalid:%r" % (key, dev.get(key)))
    caps = dev.get("category_case_caps") if isinstance(dev.get("category_case_caps"), dict) else {}
    if set(caps) != set(ALLOWED_CATEGORIES) or any(caps.get(category) != 2 for category in ALLOWED_CATEGORIES):
        blockers.append("dev_category_case_caps_invalid")
    if sum(int(value) for value in caps.values()) != dev.get("max_dev_cases"):
        blockers.append("dev_case_cap_sum_invalid")
    blockers.extend("dev_%s" % item for item in _scan(dev))
    return sorted(set(blockers))


def validate_packet(packet: Dict[str, Any], dev: Dict[str, Any], command: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    expected = {
        "artifact_kind": "rashe_dev_scorer_execution_packet_v1",
        "approval_status": "pending",
        "packet_scope": "stage4_dev_scorer_smoke_execution_packet_draft_only",
        "request_kind": "pending_execution_packet_draft_not_authorized",
        "max_dev_cases": 12,
        "allowed_bfcl_categories": ALLOWED_CATEGORIES,
        "allowed_skills": ALLOWED_SKILLS,
        "disallowed_skills": DISALLOWED_SKILLS,
        "candidate_activation_mode": "in_memory_spec_only_no_jsonl_no_pool",
        "command_manifest": str(DEFAULT_COMMAND_MANIFEST),
        "dev_manifest": str(DEFAULT_DEV_MANIFEST),
        "measurement_kind": "dev_scorer_smoke_not_performance_claim",
        "provider_profile": "novacode",
        "provider_model": "gpt-4.1",
        "bfcl_model_alias": "gpt-4o-mini-2024-07-18-FC",
        "required_records": REQUIRED_RECORDS,
        "stop_loss_rules": STOP_LOSS,
        "blockers": [],
    }
    for key, value in expected.items():
        if packet.get(key) != value:
            blockers.append("packet_%s_invalid:%r" % (key, packet.get(key)))
    for key in FALSE_KEYS:
        if packet.get(key) is not False:
            blockers.append("packet_%s_not_false:%r" % (key, packet.get(key)))
    for key in TRUE_KEYS:
        if packet.get(key) is not True:
            blockers.append("packet_%s_not_true:%r" % (key, packet.get(key)))
    if packet.get("allowed_command_patterns") != command.get("allowed_command_patterns"):
        blockers.append("packet_allowed_command_patterns_not_manifest")
    joined = "\n".join(str(item) for item in packet.get("allowed_command_patterns") or [])
    if FORBIDDEN_ALLOWED_PATTERN_RE.search(joined):
        blockers.append("packet_allowed_command_patterns_include_forbidden")
    if packet.get("max_dev_cases") != dev.get("max_dev_cases"):
        blockers.append("packet_dev_manifest_case_cap_mismatch")
    if packet.get("allowed_bfcl_categories") != dev.get("allowed_bfcl_categories"):
        blockers.append("packet_dev_manifest_categories_mismatch")
    if packet.get("allowed_skills") != dev.get("allowed_skills"):
        blockers.append("packet_dev_manifest_skills_mismatch")
    allowed_outputs = packet.get("allowed_outputs")
    if allowed_outputs != ["outputs/artifacts/stage1_bfcl_acceptance/rashe_dev_smoke_v1/dev_smoke_manifest.json", "outputs/artifacts/stage1_bfcl_acceptance/rashe_dev_smoke_v1/dev_smoke_aggregate_report.json"]:
        blockers.append("packet_allowed_outputs_invalid:%r" % allowed_outputs)
    blockers.extend("packet_%s" % item for item in _scan(packet))
    blockers.extend("dev_manifest:%s" % item for item in validate_dev_manifest(dev))
    blockers.extend("command_manifest:%s" % item for item in validate_command_manifest(command))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, dev_manifest_path: Path = DEFAULT_DEV_MANIFEST, command_manifest_path: Path = DEFAULT_COMMAND_MANIFEST) -> Dict[str, Any]:
    packet = _load(packet_path)
    dev = _load(dev_manifest_path)
    command = _load(command_manifest_path)
    blockers = validate_packet(packet, dev, command)
    return {
        "report_scope": "rashe_dev_scorer_execution_packet_v1_check",
        "packet_path": str(packet_path),
        "dev_manifest_path": str(dev_manifest_path),
        "command_manifest_path": str(command_manifest_path),
        "rashe_dev_scorer_execution_packet_v1_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "execution_started": packet.get("execution_started"),
        "one_attempt_only": packet.get("one_attempt_only"),
        "dev_smoke_only": packet.get("dev_smoke_only"),
        "max_dev_cases": packet.get("max_dev_cases"),
        "allowed_skills": packet.get("allowed_skills"),
        "performance_evidence": packet.get("performance_evidence"),
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--dev-manifest", type=Path, default=DEFAULT_DEV_MANIFEST)
    parser.add_argument("--command-manifest", type=Path, default=DEFAULT_COMMAND_MANIFEST)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.dev_manifest, args.command_manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "rashe_dev_scorer_execution_packet_v1_check", "rashe_dev_scorer_execution_packet_v1_passed": False, "blockers": ["load_failed:%s" % exc]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_dev_scorer_execution_packet_v1_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
