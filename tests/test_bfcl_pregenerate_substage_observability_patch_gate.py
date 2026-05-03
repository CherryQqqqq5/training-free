from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_pregenerate_substage_observability_patch_gate import (
    DEFAULT_PACKET,
    DEFAULT_SUMMARY,
    FUTURE_COMPACT_LABELS,
    check,
    validate_packet,
    validate_summary,
)


def _packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _summary() -> dict:
    return json.loads(DEFAULT_SUMMARY.read_text(encoding="utf-8"))


def test_committed_patch_gate_and_summary_pass_fail_closed() -> None:
    result = check(DEFAULT_PACKET, DEFAULT_SUMMARY)
    assert result["bfcl_pregenerate_substage_observability_patch_gate_passed"] is True
    assert result["approval_status"] in {"prepared", "pending"}
    assert result["authorized"] is False
    assert result["future_compact_label_count"] == len(FUTURE_COMPACT_LABELS)
    assert result["import_probe_behavior"] == "not_run_by_design"
    assert result["argument_probe_behavior"] == "not_run_by_design"
    assert result["next_gate_recommended"] == "implement_pregenerate_substage_observability_patch_offline"


def test_packet_rejects_execution_and_performance_flags() -> None:
    base = _packet()
    for key in (
        "authorized",
        "provider_request_authorized",
        "bfcl_generate_authorized",
        "bfcl_smoke_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        data = copy.deepcopy(base)
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_packet_rejects_wrong_route_or_live_scope() -> None:
    data = _packet()
    data["route_model"] = "gpt-5.2"
    assert any("route" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["no_provider"] = False
    assert any("no_provider" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["no_bfcl_execution"] = False
    assert any("no_bfcl_execution" in blocker for blocker in validate_packet(data))


def test_packet_requires_exact_future_labels_and_patch_points() -> None:
    data = _packet()
    data["allowed_future_compact_labels"] = FUTURE_COMPACT_LABELS[:-1]
    assert any("allowed_future_compact_labels" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["required_future_patch_points"] = []
    assert any("required_future_patch_points" in blocker for blocker in validate_packet(data))


def test_summary_requires_fail_closed_no_behavior_patch_state() -> None:
    for key in ("behavior_patch_implemented", "patch_authorized"):
        data = _summary()
        data[key] = True
        assert any("patch_not_fail_closed" in blocker for blocker in validate_summary(data))


def test_summary_requires_exact_future_labels_and_probe_behavior() -> None:
    data = _summary()
    data["future_compact_labels"] = FUTURE_COMPACT_LABELS + ["raw_log"]
    assert any("future_compact_labels" in blocker for blocker in validate_summary(data))
    data = _summary()
    data["labels_added_for_future_schema"] = FUTURE_COMPACT_LABELS[:-1]
    assert any("labels_added_for_future_schema" in blocker for blocker in validate_summary(data))
    data = _summary()
    data["no_provider_import_probe_behavior"] = "importable_without_generate"
    assert any("probe_behavior_not_gate_safe" in blocker for blocker in validate_summary(data))
    data = _summary()
    data["no_provider_argument_probe_behavior"] = "argparse_ok_without_generate"
    assert any("probe_behavior_not_gate_safe" in blocker for blocker in validate_summary(data))


def test_summary_requires_boundaries_and_next_gate() -> None:
    data = _summary()
    data["raw_logging_added"] = True
    assert any("raw_logging_added" in blocker for blocker in validate_summary(data))
    data = _summary()
    data["candidate_runtime_unchanged"] = False
    assert any("candidate_runtime_unchanged" in blocker for blocker in validate_summary(data))
    data = _summary()
    data["next_gate_recommended"] = ""
    assert any("next_gate_recommended" in blocker for blocker in validate_summary(data))


def test_rejects_raw_secret_case_provider_scorer_material() -> None:
    data = _packet()
    data["raw_prompt_value"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_packet(data))
    data = _summary()
    data["endpoint_value"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_summary(data))
    data = _summary()
    data["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_summary(data))


def test_temp_packet_and_summary_paths_can_be_checked(tmp_path: Path) -> None:
    packet = _packet()
    summary = _summary()
    packet_path = tmp_path / "packet.json"
    summary_path = tmp_path / "summary.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    result = check(packet_path, summary_path)
    assert result["bfcl_pregenerate_substage_observability_patch_gate_passed"] is True
