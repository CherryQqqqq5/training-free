from __future__ import annotations

import json

from scripts.check_rashe_dev_scorer_command_manifest_v1 import ALLOWED_CATEGORIES, ALLOWED_SKILLS, DISALLOWED_SKILLS
from scripts.check_rashe_dev_scorer_execution_packet_v1 import DEFAULT_COMMAND_MANIFEST, DEFAULT_DEV_MANIFEST, DEFAULT_PACKET, STOP_LOSS, validate_dev_manifest, validate_packet


def _packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _dev() -> dict:
    return json.loads(DEFAULT_DEV_MANIFEST.read_text(encoding="utf-8"))


def _command() -> dict:
    return json.loads(DEFAULT_COMMAND_MANIFEST.read_text(encoding="utf-8"))


def test_execution_packet_is_pending_draft_only() -> None:
    packet = _packet()
    dev = _dev()
    command = _command()
    assert validate_packet(packet, dev, command) == []
    assert packet["approval_status"] == "pending"
    assert packet["authorized"] is False
    assert packet["execution_started"] is False
    assert packet["one_attempt_only"] is True
    assert packet["dev_smoke_only"] is True
    assert packet["holdout_authorized"] is False
    assert packet["full_suite_authorized"] is False
    assert packet["full_baseline_authorized"] is False
    assert packet["max_dev_cases"] == 12
    assert packet["allowed_bfcl_categories"] == ALLOWED_CATEGORIES
    assert packet["allowed_skills"] == ALLOWED_SKILLS
    assert packet["disallowed_skills"] == DISALLOWED_SKILLS
    assert packet["stop_loss_rules"] == STOP_LOSS


def test_execution_packet_rejects_approval_flip_without_review() -> None:
    for key in ("authorized", "execution_started", "provider_calls_authorized", "bfcl_generate_authorized", "bfcl_evaluate_authorized", "scorer_authorized", "candidate_jsonl_authorized", "candidate_pool_ready", "performance_evidence", "huawei_acceptance_ready"):
        packet = _packet()
        packet[key] = True
        blockers = validate_packet(packet, _dev(), _command())
        assert any(key in blocker for blocker in blockers)
    packet = _packet()
    packet["approval_status"] = "not_pending"
    blockers = validate_packet(packet, _dev(), _command())
    assert any("approval_status" in blocker for blocker in blockers)


def test_dev_manifest_is_aggregate_only_and_fixed_cap() -> None:
    dev = _dev()
    assert validate_dev_manifest(dev) == []
    assert dev["dev_case_selection_mode"] == "compact_bucket_counts_only_no_case_ids"
    assert set(dev["category_case_caps"]) == set(ALLOWED_CATEGORIES)
    assert sum(dev["category_case_caps"].values()) == 12
    assert dev["candidate_activation_mode"] == "in_memory_spec_only_no_jsonl_no_pool"
    assert dev["candidate_jsonl_authorized"] is False
    assert dev["candidate_outputs_persisted"] is False


def test_dev_manifest_rejects_case_or_raw_fields() -> None:
    for key in ("case_id", "raw_prompt", "provider_exchange", "gold", "expected", "tool_args", "scorer_diff", "candidate_output"):
        dev = _dev()
        dev[key] = "redacted"
        blockers = validate_dev_manifest(dev)
        assert any("forbidden_key" in blocker for blocker in blockers)


def test_packet_rejects_disallowed_skill_or_command_drift() -> None:
    packet = _packet()
    packet["allowed_skills"] = ["bfcl_web_search_decomposition"]
    blockers = validate_packet(packet, _dev(), _command())
    assert any("allowed_skills" in blocker for blocker in blockers)

    packet = _packet()
    packet["allowed_command_patterns"] = list(packet["allowed_command_patterns"]) + ["holdout full_baseline huawei"]
    blockers = validate_packet(packet, _dev(), _command())
    assert any("allowed_command_patterns" in blocker for blocker in blockers)


def test_packet_and_dev_manifest_must_match() -> None:
    dev = _dev()
    dev["max_dev_cases"] = 14
    blockers = validate_packet(_packet(), dev, _command())
    assert any("case_cap" in blocker or "dev_max_dev_cases" in blocker for blocker in blockers)
