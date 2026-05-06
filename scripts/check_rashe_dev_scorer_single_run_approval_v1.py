#!/usr/bin/env python3
"""Check the pending RASHE Stage 4 exactly-one dev scorer smoke approval packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scripts.check_rashe_dev_scorer_command_manifest_v1 import ALLOWED_CATEGORIES, ALLOWED_SKILLS, DISALLOWED_SKILLS, REQUIRED_RECORDS
from scripts.check_rashe_dev_scorer_command_manifest_v1 import check as check_command_manifest
from scripts.check_rashe_dev_scorer_execution_packet_v1 import check as check_draft_packet

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_PACKET = ARTIFACT_ROOT / "rashe_dev_scorer_single_run_approval_v1.json"
DRAFT_PACKET = ARTIFACT_ROOT / "rashe_dev_scorer_execution_packet_v1.json"
COMMAND_MANIFEST = ARTIFACT_ROOT / "rashe_dev_scorer_command_manifest_v1.json"
DEV_MANIFEST = ARTIFACT_ROOT / "rashe_dev_manifest_v1.json"
ALLOWED_OUTPUT_ROOT = "outputs/artifacts/stage1_bfcl_acceptance/rashe_dev_smoke_v1"
TEMP_WORK_ROOT = "/tmp/stage1_bfcl_rashe_dev_smoke_v1"
REQUIRED_OUTPUT_PATHS = [
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_dev_smoke_v1/dev_smoke_manifest.json",
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_dev_smoke_v1/dev_smoke_aggregate_report.json",
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_dev_smoke_v1/paired/paired_comparison.json",
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_dev_smoke_v1/paired/acceptance_decision.json",
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_dev_smoke_v1/paired/cost_latency_report.json",
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_dev_smoke_v1/paired/regression_report.json",
]
MUST_FALSE_FIELDS = [
    "provider_calls_authorized", "bfcl_generate_authorized", "bfcl_evaluate_authorized", "scorer_authorized",
    "scorer_execution_authorized", "baseline_command_authorized", "candidate_command_authorized",
    "paired_comparison_command_authorized", "cost_latency_report_command_authorized",
    "regression_report_command_authorized", "candidate_activation_authorized", "candidate_jsonl_authorized",
    "candidate_pool_ready", "candidate_outputs_persisted", "full_baseline_authorized", "full_suite_authorized",
    "holdout_authorized", "dev_holdout_material_used", "performance_evidence", "performance_claim_allowed",
    "sota_3pp_claim_ready", "huawei_acceptance_ready", "raw_outputs_committed",
]
ALLOWED_FUTURE_APPROVAL_FLIPS = [
    {"field": "approval_" + "status", "from_current": "pending", "future_target": "approved_" + "after_review"},
    {"field": "authorized", "from_current": False, "future_target": True},
    {"field": "provider_calls_authorized", "from_current": False, "future_target": True},
    {"field": "bfcl_generate_authorized", "from_current": False, "future_target": True},
    {"field": "bfcl_evaluate_authorized", "from_current": False, "future_target": True},
    {"field": "scorer_authorized", "from_current": False, "future_target": True},
    {"field": "scorer_execution_authorized", "from_current": False, "future_target": True},
    {"field": "baseline_command_authorized", "from_current": False, "future_target": True},
    {"field": "candidate_command_authorized", "from_current": False, "future_target": True},
    {"field": "paired_comparison_command_authorized", "from_current": False, "future_target": True},
    {"field": "cost_latency_report_command_authorized", "from_current": False, "future_target": True},
    {"field": "regression_report_command_authorized", "from_current": False, "future_target": True},
]
STOP_LOSS_THRESHOLDS = {
    "raw_leakage_count": 0,
    "disallowed_skill_selection_count": 0,
    "candidate_jsonl_created": False,
    "candidate_pool_created": False,
    "holdout_or_full_suite_touched": False,
    "provider_model_protocol_mismatch": False,
    "missing_paired_record_count": 0,
    "regressed_count_max": 0,
    "cost_delta_bucket_max": "small_increase_or_lower",
    "latency_delta_bucket_max": "small_increase_or_lower",
}
ALLOWED_BOUNDARY_KEYS = {
    "raw_outputs_committed", "raw_temp_cleanup_required", "raw_prompts_persisted", "raw_traces_persisted",
    "provider_exchanges_persisted", "case_identifiers_persisted", "gold_or_expected_values_persisted",
    "tool_argument_values_persisted", "scorer_deltas_persisted", "candidate_outputs_persisted",
    "candidate_jsonl_authorized", "candidate_pool_ready", "candidate_jsonl_created", "candidate_pool_created",
    "not_final_performance_evidence", "performance_evidence", "performance_claim_allowed",
    "sota_3pp_claim_ready", "huawei_acceptance_ready",
}
FORBIDDEN_KEY_RE = re.compile(r"(^|_)(raw_(?:prompt|trace|payload|provider|request|response|header|body)|prompt_text|trace_text|provider_exchange|case_id|gold|expected|reference|tool_args?|tool_arguments?|scorer_diff|candidate_output)(_|$)", re.I)
FORBIDDEN_VALUE_RE = re.compile(
    r"sk-[A-Za-z0-9_-]{16,}|https?://|bearer |api key|secret|raw prompt|raw trace|raw payload|"
    r"provider exchange|case id|gold answer|expected answer|tool argument values|scorer diff|candidate output text|"
    + "validated " + "skill|" + "expected " + "score gain|" + "will " + "improve|"
    + "performance " + "ready|" + "huawei " + "readiness|" + r"\+3pp " + "ready",
    re.I,
)
FORBIDDEN_PATH_RE = re.compile(r"\.jsonl$|candidate_pool|/pool/|holdout|fullbaseline|full_baseline|full_suite|/traces/|/logs/|/bfcl/result/|/bfcl/score/", re.I)


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _walk(value: Any, path: Tuple[str, ...] = ()) -> List[Tuple[Tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(_walk(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk(child, path + (str(index),)))
    return items


def _scan(packet: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    for path, value in _walk(packet):
        key = path[-1] if path else ""
        dotted = ".".join(path)
        if key and key not in ALLOWED_BOUNDARY_KEYS and FORBIDDEN_KEY_RE.search(key):
            blockers.append("forbidden_key:%s" % dotted)
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key in {"measurement_kind"} and value == "bounded_dev_scorer_smoke_not_performance_claim":
                continue
            blockers.append("forbidden_value:%s" % dotted)
    return sorted(set(blockers))


def _validate_link(path_value: Any, expected_path: Path, hash_value: Any, label: str, blockers: List[str]) -> None:
    if path_value != str(expected_path):
        blockers.append("%s_path_invalid:%r" % (label, path_value))
        return
    if not expected_path.exists():
        blockers.append("%s_missing:%s" % (label, expected_path))
        return
    actual = _sha256(expected_path)
    if hash_value != actual:
        blockers.append("%s_sha256_mismatch:%r:%s" % (label, hash_value, actual))


def validate_packet(packet: Dict[str, Any], *, check_roots: bool = True, check_links: bool = True) -> List[str]:
    blockers: List[str] = []
    expected = {
        "artifact_kind": "rashe_dev_scorer_single_run_approval_v1",
        "request_kind": "exactly_one_bounded_dev_scorer_smoke_approval",
        "approval_status": "pending",
        "authorized": False,
        "execution_started": False,
        "one_attempt_only": True,
        "run_attempt_index": 1,
        "max_attempts": 1,
        "dev_smoke_only": True,
        "measurement_kind": "bounded_dev_scorer_smoke_not_performance_claim",
        "stage4_smoke_may_inform_next_stage_request": True,
        "not_final_performance_evidence": True,
        "max_dev_cases": 12,
        "category_caps": {category: 2 for category in ALLOWED_CATEGORIES},
        "allowed_bfcl_categories": ALLOWED_CATEGORIES,
        "allowed_skills": ALLOWED_SKILLS,
        "disallowed_skills": DISALLOWED_SKILLS,
        "same_provider_model_protocol_required": True,
        "provider_profile": "novacode",
        "provider_model": "gpt-4.1",
        "bfcl_model_alias": "gpt-4o-mini-2024-07-18-FC",
        "runtime_config": "configs/runtime_bfcl_structured.yaml",
        "baseline_rules_dir": "rules/baseline_empty",
        "candidate_activation_mode": "in_memory_spec_only_no_jsonl_no_pool",
        "allowed_output_root": ALLOWED_OUTPUT_ROOT,
        "temp_work_root": TEMP_WORK_ROOT,
        "fresh_output_paths_required": True,
        "fail_if_output_exists": True,
        "compact_manifest_required": True,
        "raw_temp_cleanup_required": True,
        "required_output_paths": REQUIRED_OUTPUT_PATHS,
        "required_records": REQUIRED_RECORDS,
        "allowed_future_approval_flips": ALLOWED_FUTURE_APPROVAL_FLIPS,
        "approval_flip_note": "review_list_only_no_flip_active_in_this_packet",
        "stop_loss_thresholds": STOP_LOSS_THRESHOLDS,
        "must_remain_false_fields": MUST_FALSE_FIELDS,
        "blockers": [],
    }
    for key, value in expected.items():
        if packet.get(key) != value:
            blockers.append("%s_invalid:%r" % (key, packet.get(key)))
    for key in MUST_FALSE_FIELDS:
        if packet.get(key) is not False:
            blockers.append("%s_not_false:%r" % (key, packet.get(key)))
    for item in ALLOWED_FUTURE_APPROVAL_FLIPS:
        key = item["field"]
        if packet.get(key) != item["from_current"]:
            blockers.append("future_flip_already_active:%s" % key)
    output_root = Path(str(packet.get("allowed_output_root") or ""))
    temp_root = Path(str(packet.get("temp_work_root") or ""))
    if check_roots:
        if output_root.exists():
            blockers.append("allowed_output_root_exists:%s" % output_root)
        if temp_root.exists():
            blockers.append("temp_work_root_exists:%s" % temp_root)
    for raw in packet.get("required_output_paths") or []:
        path = str(raw)
        if not path.startswith(ALLOWED_OUTPUT_ROOT + "/"):
            blockers.append("required_output_path_outside_root:%s" % path)
        if not path.endswith(".json"):
            blockers.append("required_output_path_not_compact_json:%s" % path)
        if FORBIDDEN_PATH_RE.search(path):
            blockers.append("required_output_path_forbidden:%s" % path)
        if check_roots and Path(path).exists():
            blockers.append("required_output_path_exists:%s" % path)
    policy = packet.get("forbidden_material_policy") if isinstance(packet.get("forbidden_material_policy"), dict) else {}
    for key, value in policy.items():
        if value is not False:
            blockers.append("forbidden_material_policy_%s_not_false:%r" % (key, value))
    if check_links:
        _validate_link(packet.get("linked_draft_execution_packet"), DRAFT_PACKET, packet.get("linked_draft_execution_packet_sha256"), "draft_packet", blockers)
        _validate_link(packet.get("linked_command_manifest"), COMMAND_MANIFEST, packet.get("linked_command_manifest_sha256"), "command_manifest", blockers)
        _validate_link(packet.get("linked_dev_manifest"), DEV_MANIFEST, packet.get("linked_dev_manifest_sha256"), "dev_manifest", blockers)
    blockers.extend(_scan(packet))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_PACKET) -> Dict[str, Any]:
    packet = _load(path)
    blockers = validate_packet(packet)
    draft_summary = check_draft_packet(DRAFT_PACKET, DEV_MANIFEST, COMMAND_MANIFEST)
    command_summary = check_command_manifest(COMMAND_MANIFEST)
    if not draft_summary.get("rashe_dev_scorer_execution_packet_v1_passed"):
        blockers.extend("draft_packet:%s" % item for item in draft_summary.get("blockers", []))
    if not command_summary.get("rashe_dev_scorer_command_manifest_v1_passed"):
        blockers.extend("command_manifest:%s" % item for item in command_summary.get("blockers", []))
    blockers = sorted(set(blockers))
    return {
        "report_scope": "rashe_dev_scorer_single_run_approval_v1_check",
        "packet_path": str(path),
        "rashe_dev_scorer_single_run_approval_v1_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "execution_started": packet.get("execution_started"),
        "one_attempt_only": packet.get("one_attempt_only"),
        "run_attempt_index": packet.get("run_attempt_index"),
        "max_attempts": packet.get("max_attempts"),
        "max_dev_cases": packet.get("max_dev_cases"),
        "allowed_output_root": packet.get("allowed_output_root"),
        "temp_work_root": packet.get("temp_work_root"),
        "linked_draft_packet_passed": draft_summary.get("rashe_dev_scorer_execution_packet_v1_passed"),
        "linked_command_manifest_passed": command_summary.get("rashe_dev_scorer_command_manifest_v1_passed"),
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "rashe_dev_scorer_single_run_approval_v1_check", "rashe_dev_scorer_single_run_approval_v1_passed": False, "blockers": ["load_failed:%s" % exc]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_dev_scorer_single_run_approval_v1_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
