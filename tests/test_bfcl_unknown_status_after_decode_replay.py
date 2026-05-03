from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.build_bfcl_unknown_status_after_decode_replay import build_report
from scripts.check_bfcl_unknown_status_after_decode_replay import check, validate_artifact, validate_packet

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_unknown_status_after_decode_replay_packet.json")
ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_unknown_status_after_decode_replay.json")


def _packet() -> dict:
    return json.loads(PACKET.read_text(encoding="utf-8"))


def _artifact() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_build_replay_identifies_multi_turn_missing_marker_after_decode() -> None:
    report = build_report()
    assert report["no_provider"] is True
    assert report["synthetic_or_compact_labels_only"] is True
    assert report["per_id_decode_nonempty_known"]["multi_turn_long_context_0"] is True
    assert report["per_id_materialized_nonempty_known"]["multi_turn_long_context_0"] is False
    assert report["per_id_classifier_status"]["multi_turn_long_context_0"] == "unknown_compact_status"
    assert report["per_id_unknown_status_reason_label"]["multi_turn_long_context_0"] == "missing_nonempty_marker_after_decode"
    assert report["suspected_unknown_status_failure_stage"] == "materialization_preservation_missing_nonempty_marker_after_decode"
    assert report["patch_gate_recommended"] is True


def test_irrelevance_unknowns_remain_insufficient_compact_labels() -> None:
    report = build_report()
    assert report["irrelevance_unknowns_covered"] is False
    assert report["irrelevance_unknowns_status"] == "insufficient_compact_labels_needs_live_telemetry"
    for run_id in ("irrelevance_0", "live_irrelevance_0-0-0"):
        assert report["per_id_classifier_status"][run_id] == "unknown_compact_status"
        assert report["per_id_decode_nonempty_known"][run_id] == "unknown_from_compact_8id_labels"
        assert report["per_id_unknown_status_reason_label"][run_id] == "insufficient_compact_labels_needs_live_telemetry"


def test_synthetic_variants_distinguish_marker_and_unknown_classifier_paths() -> None:
    report = build_report()
    variants = {record["variant"]: record for record in report["synthetic_variant_replay"]}
    assert variants["prior_function_call_marker_shape"]["materialization_replay_status"] == "generated"
    assert variants["execution_list_nonempty_without_nonempty_marker"]["materialization_replay_status"] == "unknown_compact_status"
    assert variants["execution_list_nonempty_without_nonempty_marker"]["unknown_status_reason_label"] == "missing_nonempty_marker_after_decode"
    assert variants["alternate_decoded_shape_label_without_marker"]["unknown_status_reason_label"] == "materialized_shape_unrecognized_by_compact_classifier"
    assert variants["explicit_protocol_status_shape"]["materialization_replay_status"] == "protocol_error"


def test_committed_packet_and_artifact_pass_checker() -> None:
    summary = check(PACKET, ARTIFACT)
    assert summary["bfcl_unknown_status_after_decode_replay_passed"] is True
    assert summary["patch_gate_recommended"] is True
    assert summary["suspected_unknown_status_failure_stage"] == "materialization_preservation_missing_nonempty_marker_after_decode"


def test_checker_rejects_execution_flags() -> None:
    packet = _packet()
    packet["bfcl_generate_authorized"] = True
    assert any("bfcl_generate_authorized" in blocker for blocker in validate_packet(packet))
    artifact = _artifact()
    artifact["provider_request_executed"] = True
    assert any("provider_request_executed" in blocker for blocker in validate_artifact(artifact))


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


def test_checker_rejects_missing_required_fields_and_bad_reason() -> None:
    artifact = copy.deepcopy(_artifact())
    artifact.pop("per_id_decode_nonempty_known")
    assert any("required_field_missing:per_id_decode_nonempty_known" in blocker for blocker in validate_artifact(artifact))
    artifact = copy.deepcopy(_artifact())
    artifact["per_id_unknown_status_reason_label"]["multi_turn_long_context_0"] = "insufficient_compact_labels_needs_live_telemetry"
    assert any("multi_turn_reason_invalid" in blocker for blocker in validate_artifact(artifact))


def test_checker_rejects_irrelevance_overclaim() -> None:
    artifact = copy.deepcopy(_artifact())
    artifact["per_id_unknown_status_reason_label"]["irrelevance_0"] = "missing_nonempty_marker_after_decode"
    assert any("irrelevance_reason_invalid:irrelevance_0" in blocker for blocker in validate_artifact(artifact))
