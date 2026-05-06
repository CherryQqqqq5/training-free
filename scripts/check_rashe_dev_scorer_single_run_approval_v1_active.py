#!/usr/bin/env python3
"""Check the active RASHE Stage 4 exactly-one dev scorer smoke approval artifact."""

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
from scripts.check_rashe_dev_scorer_single_run_approval_v1 import check as check_pending_packet

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_ACTIVE = ARTIFACT_ROOT / "rashe_dev_scorer_single_run_approval_v1_active.json"
PENDING_PACKET = ARTIFACT_ROOT / "rashe_dev_scorer_single_run_approval_v1.json"
DRAFT_PACKET = ARTIFACT_ROOT / "rashe_dev_scorer_execution_packet_v1.json"
COMMAND_MANIFEST = ARTIFACT_ROOT / "rashe_dev_scorer_command_manifest_v1.json"
DEV_MANIFEST = ARTIFACT_ROOT / "rashe_dev_manifest_v1.json"
ALLOWED_OUTPUT_ROOT = "outputs/artifacts/stage1_bfcl_acceptance/rashe_dev_smoke_v1"
TEMP_WORK_ROOT = "/tmp/stage1_bfcl_rashe_dev_smoke_v1"
ALLOWED_FLIP_FIELDS = {
    "artifact_kind",
    "request_kind",
    "approval_status",
    "authorized",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "scorer_execution_authorized",
    "baseline_command_authorized",
    "candidate_command_authorized",
    "paired_comparison_command_authorized",
    "cost_latency_report_command_authorized",
    "regression_report_command_authorized",
    "candidate_activation_authorized",
    "linked_pending_approval_packet",
    "linked_pending_approval_packet_sha256",
    "active_approval_state",
    "active_approval_scope",
    "activated_from_pending_packet",
    "owner_approved_flip_fields",
    "must_remain_false_fields",
    "approval_flip_note",
}
AUTHORIZED_TRUE_FIELDS = [
    "authorized",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "scorer_execution_authorized",
    "baseline_command_authorized",
    "candidate_command_authorized",
    "paired_comparison_command_authorized",
    "cost_latency_report_command_authorized",
    "regression_report_command_authorized",
    "candidate_activation_authorized",
]
MUST_FALSE_FIELDS = [
    "execution_started",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "candidate_outputs_persisted",
    "full_baseline_authorized",
    "full_suite_authorized",
    "holdout_authorized",
    "dev_holdout_material_used",
    "performance_evidence",
    "performance_claim_allowed",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "raw_outputs_committed",
]
OWNER_APPROVED_FLIP_FIELDS = [
    "approval_status",
    "authorized",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "scorer_execution_authorized",
    "baseline_command_authorized",
    "candidate_command_authorized",
    "paired_comparison_command_authorized",
    "cost_latency_report_command_authorized",
    "regression_report_command_authorized",
    "candidate_activation_authorized",
]
IMMUTABLE_EXPECTED = {
    "one_attempt_only": True,
    "run_attempt_index": 1,
    "max_attempts": 1,
    "dev_smoke_only": True,
    "max_dev_cases": 12,
    "allowed_bfcl_categories": ALLOWED_CATEGORIES,
    "allowed_skills": ALLOWED_SKILLS,
    "disallowed_skills": DISALLOWED_SKILLS,
    "candidate_activation_mode": "in_memory_spec_only_no_jsonl_no_pool",
    "same_provider_model_protocol_required": True,
    "provider_profile": "novacode",
    "provider_model": "gpt-4.1",
    "bfcl_model_alias": "gpt-4o-mini-2024-07-18-FC",
    "runtime_config": "configs/runtime_bfcl_structured.yaml",
    "baseline_rules_dir": "rules/baseline_empty",
    "allowed_output_root": ALLOWED_OUTPUT_ROOT,
    "temp_work_root": TEMP_WORK_ROOT,
    "fresh_output_paths_required": True,
    "fail_if_output_exists": True,
    "compact_manifest_required": True,
    "raw_temp_cleanup_required": True,
    "required_records": REQUIRED_RECORDS,
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


def _validate_hash(active: Dict[str, Any], key_path: str, key_hash: str, expected: Path, blockers: List[str]) -> None:
    if active.get(key_path) != str(expected):
        blockers.append("%s_invalid:%r" % (key_path, active.get(key_path)))
        return
    if active.get(key_hash) != _sha256(expected):
        blockers.append("%s_mismatch" % key_hash)


def _compare_to_pending(active: Dict[str, Any], pending: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    keys = set(active) | set(pending)
    for key in keys:
        if active.get(key) != pending.get(key) and key not in ALLOWED_FLIP_FIELDS:
            blockers.append("unexpected_active_diff:%s" % key)
    return sorted(set(blockers))


def validate_active(active: Dict[str, Any], pending: Dict[str, Any], *, check_roots: bool = True, check_hashes: bool = True) -> List[str]:
    blockers: List[str] = []
    if active.get("artifact_kind") != "rashe_dev_scorer_single_run_approval_v1_active":
        blockers.append("artifact_kind_invalid:%r" % active.get("artifact_kind"))
    if active.get("request_kind") != "exactly_one_bounded_dev_scorer_smoke_active_approval":
        blockers.append("request_kind_invalid:%r" % active.get("request_kind"))
    if active.get("approval_status") != "approved":
        blockers.append("approval_status_not_approved:%r" % active.get("approval_status"))
    if active.get("active_approval_state") != "approved_not_started":
        blockers.append("active_approval_state_invalid:%r" % active.get("active_approval_state"))
    if active.get("active_approval_scope") != "exactly_one_bounded_dev_scorer_smoke":
        blockers.append("active_approval_scope_invalid:%r" % active.get("active_approval_scope"))
    if active.get("activated_from_pending_packet") is not True:
        blockers.append("activated_from_pending_packet_not_true")
    if active.get("owner_approved_flip_fields") != OWNER_APPROVED_FLIP_FIELDS:
        blockers.append("owner_approved_flip_fields_invalid:%r" % active.get("owner_approved_flip_fields"))
    if active.get("must_remain_false_fields") != MUST_FALSE_FIELDS:
        blockers.append("must_remain_false_fields_invalid:%r" % active.get("must_remain_false_fields"))
    overlap = set(active.get("owner_approved_flip_fields") or []) & set(active.get("must_remain_false_fields") or [])
    if overlap:
        blockers.append("owner_flip_fields_overlap_must_false:%r" % sorted(overlap))
    if active.get("approval_flip_note") != "approval_flip_active_after_project_owner_review":
        blockers.append("approval_flip_note_invalid:%r" % active.get("approval_flip_note"))
    for key in AUTHORIZED_TRUE_FIELDS:
        if active.get(key) is not True:
            blockers.append("%s_not_true:%r" % (key, active.get(key)))
    for key in MUST_FALSE_FIELDS:
        if active.get(key) is not False:
            blockers.append("%s_not_false:%r" % (key, active.get(key)))
    for key, value in IMMUTABLE_EXPECTED.items():
        if active.get(key) != value:
            blockers.append("%s_invalid:%r" % (key, active.get(key)))
    if active.get("category_caps") != {category: 2 for category in ALLOWED_CATEGORIES}:
        blockers.append("category_caps_invalid:%r" % active.get("category_caps"))
    if active.get("required_output_paths") != pending.get("required_output_paths"):
        blockers.append("required_output_paths_not_pending")
    for raw in active.get("required_output_paths") or []:
        path = str(raw)
        if not path.startswith(ALLOWED_OUTPUT_ROOT + "/"):
            blockers.append("required_output_path_outside_root:%s" % path)
        if not path.endswith(".json"):
            blockers.append("required_output_path_not_compact_json:%s" % path)
        if FORBIDDEN_PATH_RE.search(path):
            blockers.append("required_output_path_forbidden:%s" % path)
        if check_roots and Path(path).exists():
            blockers.append("required_output_path_exists:%s" % path)
    if check_roots:
        if Path(ALLOWED_OUTPUT_ROOT).exists():
            blockers.append("allowed_output_root_exists:%s" % ALLOWED_OUTPUT_ROOT)
        if Path(TEMP_WORK_ROOT).exists():
            blockers.append("temp_work_root_exists:%s" % TEMP_WORK_ROOT)
    if check_hashes:
        _validate_hash(active, "linked_pending_approval_packet", "linked_pending_approval_packet_sha256", PENDING_PACKET, blockers)
        _validate_hash(active, "linked_draft_execution_packet", "linked_draft_execution_packet_sha256", DRAFT_PACKET, blockers)
        _validate_hash(active, "linked_command_manifest", "linked_command_manifest_sha256", COMMAND_MANIFEST, blockers)
        _validate_hash(active, "linked_dev_manifest", "linked_dev_manifest_sha256", DEV_MANIFEST, blockers)
    blockers.extend(_compare_to_pending(active, pending))
    blockers.extend(_scan(active))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ACTIVE) -> Dict[str, Any]:
    active = _load(path)
    pending = _load(PENDING_PACKET)
    blockers = validate_active(active, pending)
    pending_summary = check_pending_packet(PENDING_PACKET)
    draft_summary = check_draft_packet(DRAFT_PACKET, DEV_MANIFEST, COMMAND_MANIFEST)
    command_summary = check_command_manifest(COMMAND_MANIFEST)
    if not pending_summary.get("rashe_dev_scorer_single_run_approval_v1_passed"):
        blockers.extend("pending_packet:%s" % item for item in pending_summary.get("blockers", []))
    if not draft_summary.get("rashe_dev_scorer_execution_packet_v1_passed"):
        blockers.extend("draft_packet:%s" % item for item in draft_summary.get("blockers", []))
    if not command_summary.get("rashe_dev_scorer_command_manifest_v1_passed"):
        blockers.extend("command_manifest:%s" % item for item in command_summary.get("blockers", []))
    blockers = sorted(set(blockers))
    return {
        "report_scope": "rashe_dev_scorer_single_run_approval_v1_active_check",
        "active_packet_path": str(path),
        "rashe_dev_scorer_single_run_approval_v1_active_passed": not blockers,
        "approval_status": active.get("approval_status"),
        "authorized": active.get("authorized"),
        "execution_started": active.get("execution_started"),
        "one_attempt_only": active.get("one_attempt_only"),
        "run_attempt_index": active.get("run_attempt_index"),
        "max_attempts": active.get("max_attempts"),
        "linked_pending_packet_passed": pending_summary.get("rashe_dev_scorer_single_run_approval_v1_passed"),
        "linked_draft_packet_passed": draft_summary.get("rashe_dev_scorer_execution_packet_v1_passed"),
        "linked_command_manifest_passed": command_summary.get("rashe_dev_scorer_command_manifest_v1_passed"),
        "owner_approved_flip_fields": active.get("owner_approved_flip_fields"),
        "must_remain_false_fields": active.get("must_remain_false_fields"),
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_ACTIVE)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "rashe_dev_scorer_single_run_approval_v1_active_check", "rashe_dev_scorer_single_run_approval_v1_active_passed": False, "blockers": ["load_failed:%s" % exc]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_dev_scorer_single_run_approval_v1_active_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
