from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.build_bfcl_protocol_status_after_nonempty_decode_replay import build_report
from scripts.check_bfcl_protocol_status_after_nonempty_decode_replay import (
    check,
    validate_artifact,
    validate_packet,
)

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_protocol_status_after_nonempty_decode_replay_packet.json")
ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_protocol_status_after_nonempty_decode_replay.json")


def _packet() -> dict:
    return json.loads(PACKET.read_text(encoding="utf-8"))


def _artifact() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def _variants(report: dict) -> dict[str, dict]:
    return {record["variant"]: record for record in report["shape_variant_replay"]}


def test_build_replay_identifies_protocol_status_after_nonempty_decode() -> None:
    report = build_report()
    assert report["no_provider"] is True
    assert report["compact_labels_only"] is True
    assert report["replay_run_id"] == "multi_turn_long_context_0"
    assert report["decoded_nonempty"] is True
    assert report["decoded_output_count"] == 1
    assert report["materialized_shape_label"] == "protocol_error_shape"
    assert report["classifier_status_replayed"] == "protocol_error"
    assert report["protocol_status_label_replayed"] == "protocol_error"
    assert report["false_protocol_error_on_nonempty_decode"] is True
    assert report["suspected_protocol_status_failure_stage"] == "materialization_entry_shape_protocol_error_after_nonempty_decode"
    assert report["patch_gate_recommended"] is True


def test_clean_nonempty_decoded_shapes_do_not_replay_protocol_error() -> None:
    variants = _variants(build_report())
    clean = variants["clean_nonempty_decoded_execution_list"]
    assert clean["protocol_error_indicator_detected"] is False
    assert clean["classifier_status_replayed"] == "generated"
    assert clean["false_protocol_error_on_nonempty_decode"] is False
    ordinary = variants["ordinary_protocol_label_nonempty_decoded"]
    assert ordinary["protocol_error_indicator_detected"] is False
    assert ordinary["classifier_status_replayed"] == "generated"
    assert ordinary["false_protocol_error_on_nonempty_decode"] is False


def test_explicit_error_and_mixed_success_error_replay_as_protocol_error() -> None:
    variants = _variants(build_report())
    phrase = variants["mixed_nonempty_decode_with_explicit_handler_error_phrase"]
    assert phrase["protocol_error_indicator_detected"] is True
    assert phrase["protocol_error_indicator_source_label"] == "explicit_handler_error_phrase"
    assert phrase["classifier_status_replayed"] == "protocol_error"
    structured = variants["mixed_nonempty_decode_with_structured_error_key"]
    assert structured["protocol_error_indicator_detected"] is True
    assert structured["protocol_error_indicator_source_label"] == "structured_error_key"
    assert structured["classifier_status_replayed"] == "protocol_error"


def test_materialized_protocol_error_shape_label_replays_as_generated_after_patch() -> None:
    variant = _variants(build_report())["materialized_protocol_error_shape_label"]
    assert variant["protocol_error_indicator_detected"] is False
    assert variant["protocol_error_indicator_source_label"] == "shape_label_contains_error"
    assert variant["materialized_shape_label_replayed"] == "protocol_error_shape"
    assert variant["classifier_status_replayed"] == "generated"
    assert variant["protocol_status_label_replayed"] == "generated"
    assert variant["false_protocol_error_on_nonempty_decode"] is False


def test_committed_packet_and_artifact_pass_checker() -> None:
    summary = check(PACKET, ARTIFACT)
    assert summary["bfcl_protocol_status_after_nonempty_decode_replay_passed"] is True
    assert summary["patch_gate_recommended"] is True
    assert summary["false_protocol_error_on_nonempty_decode"] is True


def test_checker_rejects_execution_flags() -> None:
    packet = _packet()
    packet["bfcl_generate_authorized"] = True
    assert any("bfcl_generate_authorized" in blocker for blocker in validate_packet(packet))
    artifact = _artifact()
    artifact["provider_request_executed"] = True
    assert any("provider_request_executed" in blocker for blocker in validate_artifact(artifact))


def test_checker_rejects_wrong_run_id_and_missing_fields() -> None:
    packet = _packet()
    packet["replay_run_id"] = "web_search_base_0"
    assert any("replay_run_id_invalid" in blocker for blocker in validate_packet(packet))
    artifact = copy.deepcopy(_artifact())
    artifact.pop("suspected_protocol_status_failure_stage")
    assert any("required_field_missing:suspected_protocol_status_failure_stage" in blocker for blocker in validate_artifact(artifact))


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


def test_checker_rejects_clean_variant_false_protocol_error() -> None:
    artifact = copy.deepcopy(_artifact())
    for record in artifact["shape_variant_replay"]:
        if record["variant"] == "clean_nonempty_decoded_execution_list":
            record["classifier_status_replayed"] = "protocol_error"
            record["false_protocol_error_on_nonempty_decode"] = True
    blockers = validate_artifact(artifact)
    assert any("clean_variant_not_generated" in blocker for blocker in blockers)
    assert any("clean_variant_false_error" in blocker for blocker in blockers)
