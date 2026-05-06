from __future__ import annotations

import copy
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from scripts.check_rashe_dev_scorer_single_run_approval_v1 import (
    ALLOWED_CATEGORIES,
    ALLOWED_FUTURE_APPROVAL_FLIPS,
    ALLOWED_OUTPUT_ROOT,
    DEFAULT_PACKET,
    MUST_FALSE_FIELDS,
    REQUIRED_OUTPUT_PATHS,
    STOP_LOSS_THRESHOLDS,
    validate_packet,
)


def _packet() -> dict:
    return json.loads((REPO_ROOT / DEFAULT_PACKET).read_text(encoding="utf-8"))


def test_single_run_packet_is_pending_review_only() -> None:
    packet = _packet()
    assert validate_packet(packet) == []
    assert packet["artifact_kind"] == "rashe_dev_scorer_single_run_approval_v1"
    assert packet["request_kind"] == "exactly_one_bounded_dev_scorer_smoke_approval"
    assert packet["approval_status"] == "pending"
    assert packet["authorized"] is False
    assert packet["execution_started"] is False
    assert packet["one_attempt_only"] is True
    assert packet["run_attempt_index"] == 1
    assert packet["max_attempts"] == 1
    assert packet["max_dev_cases"] == 12
    assert packet["category_caps"] == {category: 2 for category in ALLOWED_CATEGORIES}
    assert packet["required_output_paths"] == REQUIRED_OUTPUT_PATHS
    assert packet["stop_loss_thresholds"] == STOP_LOSS_THRESHOLDS


def test_all_must_remain_false_fields_are_false() -> None:
    packet = _packet()
    assert packet["must_remain_false_fields"] == MUST_FALSE_FIELDS
    for key in MUST_FALSE_FIELDS:
        assert packet[key] is False


def test_allowed_future_flips_are_listed_but_inactive() -> None:
    packet = _packet()
    assert packet["allowed_future_approval_flips"] == ALLOWED_FUTURE_APPROVAL_FLIPS
    for item in packet["allowed_future_approval_flips"]:
        assert packet[item["field"]] == item["from_current"]

    for item in packet["allowed_future_approval_flips"]:
        mutated = copy.deepcopy(packet)
        mutated[item["field"]] = item["future_target"]
        blockers = validate_packet(mutated, check_roots=False)
        assert any("future_flip_already_active" in blocker or item["field"] in blocker for blocker in blockers)


def test_hashes_must_match_linked_files() -> None:
    packet = _packet()
    packet["linked_dev_manifest_sha256"] = "0" * 64
    blockers = validate_packet(packet, check_roots=False)
    assert any("dev_manifest_sha256_mismatch" in blocker for blocker in blockers)


def test_required_output_paths_are_compact_and_under_root() -> None:
    packet = _packet()
    packet["required_output_paths"] = list(packet["required_output_paths"]) + [ALLOWED_OUTPUT_ROOT + "/candidate_pool.jsonl"]
    blockers = validate_packet(packet, check_roots=False)
    assert any("required_output_path" in blocker for blocker in blockers)

    packet = _packet()
    packet["required_output_paths"] = ["outputs/artifacts/stage1_bfcl_acceptance/holdout/result.json"]
    blockers = validate_packet(packet, check_roots=False)
    assert any("required_output_path" in blocker for blocker in blockers)


def test_existing_output_or_temp_root_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    packet = _packet()
    Path(packet["allowed_output_root"]).mkdir(parents=True)
    blockers = validate_packet(packet, check_roots=True, check_links=False)
    assert any("allowed_output_root_exists" in blocker for blocker in blockers)

    packet = _packet()
    packet["allowed_output_root"] = ALLOWED_OUTPUT_ROOT
    packet["temp_work_root"] = str(tmp_path / "stage4_tmp_root")
    Path(packet["temp_work_root"]).mkdir(parents=True, exist_ok=True)
    blockers = validate_packet(packet, check_roots=True, check_links=False)
    assert any("temp_work_root_exists" in blocker for blocker in blockers)


def test_raw_or_claim_material_is_rejected() -> None:
    for key in ("prompt_text", "raw_trace", "provider_exchange", "case_id", "gold", "expected", "tool_args", "scorer_diff", "candidate_output"):
        packet = _packet()
        packet[key] = "redacted"
        blockers = validate_packet(packet, check_roots=False)
        assert any("forbidden_key" in blocker for blocker in blockers)

    packet = _packet()
    packet["note"] = "expected " + "score gain " + "will " + "improve"
    blockers = validate_packet(packet, check_roots=False)
    assert any("forbidden_value" in blocker for blocker in blockers)
