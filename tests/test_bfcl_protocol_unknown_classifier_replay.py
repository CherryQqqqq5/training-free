from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.build_bfcl_protocol_unknown_classifier_replay import build_report
from scripts.check_bfcl_protocol_unknown_classifier_replay import check, validate_artifact, validate_packet

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_protocol_unknown_classifier_replay_packet.json")
ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_protocol_unknown_classifier_replay.json")


def _packet() -> dict:
    return json.loads(PACKET.read_text(encoding="utf-8"))


def _artifact() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_replay_build_distinguishes_protocol_error_and_unknown_compact_status() -> None:
    report = build_report()
    by_id = {record["run_id"]: record for record in report["records"]}
    assert by_id["multi_turn_long_context_0"]["compact_status"] == "protocol_error"
    assert by_id["multi_turn_long_context_0"]["protocol_error_detected"] is True
    assert by_id["multi_turn_long_context_0"]["replay_classification_label"] == "protocol_error_label_consistent"
    for run_id in ("irrelevance_0", "live_irrelevance_0-0-0"):
        assert by_id[run_id]["compact_status"] == "unknown_compact_status"
        assert by_id[run_id]["result_present"] is True
        assert by_id[run_id]["positive_compact_flag_count"] == 0
        assert by_id[run_id]["compact_shape_data_sufficient_for_root_cause"] is False
    assert report["unknown_root_cause_resolved_by_compact_replay"] is False


def test_committed_replay_artifact_and_packet_pass() -> None:
    summary = check(PACKET, ARTIFACT)
    assert summary["bfcl_protocol_unknown_classifier_replay_passed"] is True
    assert summary["classifier_replay_feasible"] is True
    assert summary["unknown_root_cause_resolved_by_compact_replay"] is False


def test_checker_rejects_execution_flags() -> None:
    artifact = _artifact()
    artifact["provider_request_executed"] = True
    assert any("provider_request_executed" in blocker for blocker in validate_artifact(artifact))
    packet = _packet()
    packet["bfcl_generate_authorized"] = True
    assert any("bfcl_generate_authorized" in blocker for blocker in validate_packet(packet))


def test_checker_rejects_raw_or_secret_material() -> None:
    artifact = _artifact()
    artifact["raw_" + "provider_response_body"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_artifact(artifact))
    artifact = _artifact()
    artifact["notes"] = "api " + "key " + "value"
    assert any("forbidden_value" in blocker for blocker in validate_artifact(artifact))
    packet = _packet()
    packet["notes"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(packet))


def test_checker_rejects_target_record_drift() -> None:
    artifact = copy.deepcopy(_artifact())
    for record in artifact["records"]:
        if record["run_id"] == "multi_turn_long_context_0":
            record["protocol_error_detected"] = False
    assert any("target_protocol_record_not_protocol_error" in blocker for blocker in validate_artifact(artifact))


def test_checker_rejects_unknown_not_marked_limited() -> None:
    artifact = copy.deepcopy(_artifact())
    for record in artifact["records"]:
        if record["run_id"] == "irrelevance_0":
            record["compact_shape_data_sufficient_for_root_cause"] = True
    assert any("unknown_record_not_marked_limited" in blocker for blocker in validate_artifact(artifact))
