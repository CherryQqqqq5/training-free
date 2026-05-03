#!/usr/bin/env python3
"""Build no-provider unknown-status-after-decode replay from compact artifacts."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_bfcl_cli import _preserve_decoded_execution_output_shape  # noqa: E402
from scripts.run_bfcl_exact_2id_generate_smoke import _classify_result_for_run_id  # noqa: E402

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
PROTOCOL_TELEMETRY = ARTIFACT_ROOT / "bfcl_one_id_protocol_error_telemetry_compact.json"
EXACT_8ID = ARTIFACT_ROOT / "bfcl_exact_8id_generate_smoke_compact.json"
DEFAULT_OUTPUT = ARTIFACT_ROOT / "bfcl_unknown_status_after_decode_replay.json"
DEFAULT_MD = ARTIFACT_ROOT / "bfcl_unknown_status_after_decode_replay.md"
RUN_IDS_REPLAYED = ["multi_turn_long_context_0", "irrelevance_0", "live_irrelevance_0-0-0"]
FALSE_FLAGS = {
    "provider_request_executed": False,
    "live_telemetry_executed": False,
    "bfcl_generate_executed": False,
    "bfcl_smoke_executed": False,
    "bfcl_evaluate_executed": False,
    "scorer_executed": False,
    "full_baseline_executed": False,
    "candidate_runtime_activation_authorized": False,
    "candidate_jsonl_authorized": False,
    "candidate_pool_ready": False,
    "performance_evidence": False,
    "sota_3pp_claim_ready": False,
    "huawei_acceptance_ready": False,
}


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain JSON object")
    return data


def _classify_payload(run_id: str, payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="bfcl_unknown_status_replay_") as tmp:
        root = Path(tmp)
        result_root = root / "bfcl" / "result"
        result_root.mkdir(parents=True, exist_ok=True)
        (result_root / f"{run_id}.json").write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        return _classify_result_for_run_id(run_id, result_root)


def _synthetic_variants() -> list[dict[str, Any]]:
    run_id = "synthetic_shape_0"
    entry = {
        "id": run_id,
        "result": [["shape_only_decoded_execution"]],
        "inference_log": [{"step_0": [{"model_response_decoded": ["decoded_execution_shape"]}]}],
    }
    preserved = _preserve_decoded_execution_output_shape(entry)
    covered = _classify_payload(run_id, preserved)
    missing_marker = _classify_payload(
        run_id,
        {"id": run_id, "decoded_output_shape_label": "execution_list_nonempty", "decoded_output_count": 1, "shape_only": True},
    )
    alternate_shape = _classify_payload(
        run_id,
        {"id": run_id, "model_response_decoded_shape_label": "nonempty_execution_list", "shape_only": True},
    )
    protocol_shape = _classify_payload(
        run_id,
        {"id": run_id, "result": "Error during inference: synthetic shape", "shape_only": True},
    )
    return [
        {
            "variant": "prior_function_call_marker_shape",
            "materialization_replay_status": covered.get("status"),
            "classifier_detected_nonempty": bool(covered.get("tool_call_detected")),
            "unknown_status_reason_label": "covered_by_existing_function_call_marker",
        },
        {
            "variant": "execution_list_nonempty_without_nonempty_marker",
            "materialization_replay_status": missing_marker.get("status"),
            "classifier_detected_nonempty": bool(missing_marker.get("tool_call_detected")),
            "unknown_status_reason_label": "missing_nonempty_marker_after_decode",
        },
        {
            "variant": "alternate_decoded_shape_label_without_marker",
            "materialization_replay_status": alternate_shape.get("status"),
            "classifier_detected_nonempty": bool(alternate_shape.get("tool_call_detected")),
            "unknown_status_reason_label": "materialized_shape_unrecognized_by_compact_classifier",
        },
        {
            "variant": "explicit_protocol_status_shape",
            "materialization_replay_status": protocol_shape.get("status"),
            "classifier_detected_nonempty": bool(protocol_shape.get("tool_call_detected")),
            "unknown_status_reason_label": "protocol_status_classifier_maps_explicit_error",
        },
    ]


def _reason_for_protocol_record(record: dict[str, Any]) -> str:
    if record.get("bfcl_decode_execute_nonempty") is True and record.get("materialized_result_nonempty") is False:
        return "missing_nonempty_marker_after_decode"
    if record.get("classifier_status") == "unknown_compact_status":
        return "materialized_shape_unrecognized_by_compact_classifier"
    return "unknown_status_reason_unresolved"


def build_report(protocol_path: Path = PROTOCOL_TELEMETRY, exact8_path: Path = EXACT_8ID) -> dict[str, Any]:
    protocol = _load(protocol_path)
    exact8 = _load(exact8_path)
    protocol_record = protocol.get("records", [{}])[0] if isinstance(protocol.get("records"), list) and protocol.get("records") else {}
    statuses = exact8.get("per_id_compact_status") if isinstance(exact8.get("per_id_compact_status"), dict) else {}
    generated = exact8.get("per_id_generated_detected") if isinstance(exact8.get("per_id_generated_detected"), dict) else {}
    protocol_flags = exact8.get("per_id_protocol_error_detected") if isinstance(exact8.get("per_id_protocol_error_detected"), dict) else {}
    empty_flags = exact8.get("per_id_empty_model_response_detected") if isinstance(exact8.get("per_id_empty_model_response_detected"), dict) else {}
    present = exact8.get("per_id_result_present") if isinstance(exact8.get("per_id_result_present"), dict) else {}

    per_id_decode_nonempty_known: dict[str, Any] = {"multi_turn_long_context_0": protocol_record.get("bfcl_decode_execute_nonempty") is True}
    per_id_materialized_nonempty_known: dict[str, Any] = {"multi_turn_long_context_0": protocol_record.get("materialized_result_nonempty") is True}
    per_id_classifier_status: dict[str, str] = {"multi_turn_long_context_0": str(protocol_record.get("classifier_status") or "missing")}
    per_id_protocol_status_label: dict[str, str] = {"multi_turn_long_context_0": str(protocol_record.get("protocol_status_classifier_label") or "missing")}
    per_id_unknown_status_reason_label: dict[str, str] = {"multi_turn_long_context_0": _reason_for_protocol_record(protocol_record)}

    for run_id in ("irrelevance_0", "live_irrelevance_0-0-0"):
        per_id_decode_nonempty_known[run_id] = "unknown_from_compact_8id_labels"
        per_id_materialized_nonempty_known[run_id] = "unknown_from_compact_8id_labels"
        per_id_classifier_status[run_id] = str(statuses.get(run_id) or "missing")
        per_id_protocol_status_label[run_id] = "unknown_from_compact_8id_labels"
        positives = [
            label for label, enabled in (
                ("generated", generated.get(run_id) is True),
                ("protocol_error", protocol_flags.get(run_id) is True),
                ("empty_model_response", empty_flags.get(run_id) is True),
            ) if enabled
        ]
        if statuses.get(run_id) == "unknown_compact_status" and present.get(run_id) is True and not positives:
            per_id_unknown_status_reason_label[run_id] = "insufficient_compact_labels_needs_live_telemetry"
        else:
            per_id_unknown_status_reason_label[run_id] = "compact_label_flag_mismatch"

    synthetic = _synthetic_variants()
    multi_reason = per_id_unknown_status_reason_label["multi_turn_long_context_0"]
    irrelevance_limited = all(
        per_id_unknown_status_reason_label[run_id] == "insufficient_compact_labels_needs_live_telemetry"
        for run_id in ("irrelevance_0", "live_irrelevance_0-0-0")
    )
    if multi_reason == "missing_nonempty_marker_after_decode":
        suspected = "materialization_preservation_missing_nonempty_marker_after_decode"
        patch_gate = True
    elif multi_reason == "materialized_shape_unrecognized_by_compact_classifier":
        suspected = "compact_classifier_unrecognized_materialized_shape_after_decode"
        patch_gate = True
    else:
        suspected = "insufficient_compact_labels_needs_live_telemetry"
        patch_gate = False
    return {
        "artifact_kind": "bfcl_unknown_status_after_decode_replay",
        "approval_status": "prepared",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "no_provider": True,
        "synthetic_or_compact_labels_only": True,
        "replay_source_artifacts": [str(protocol_path), str(exact8_path)],
        "run_ids_replayed": list(RUN_IDS_REPLAYED),
        **FALSE_FLAGS,
        "per_id_decode_nonempty_known": per_id_decode_nonempty_known,
        "per_id_materialized_nonempty_known": per_id_materialized_nonempty_known,
        "per_id_classifier_status": per_id_classifier_status,
        "per_id_protocol_status_label": per_id_protocol_status_label,
        "per_id_unknown_status_reason_label": per_id_unknown_status_reason_label,
        "materialization_replay_called": True,
        "classifier_replay_called": True,
        "protocol_status_replay_called": True,
        "synthetic_variant_replay": synthetic,
        "irrelevance_unknowns_covered": not irrelevance_limited,
        "irrelevance_unknowns_status": "insufficient_compact_labels_needs_live_telemetry" if irrelevance_limited else "covered_by_compact_replay",
        "suspected_unknown_status_failure_stage": suspected,
        "patch_gate_recommended": patch_gate,
    }


def write_report(output: Path = DEFAULT_OUTPUT, md_output: Path = DEFAULT_MD) -> dict[str, Any]:
    report = build_report()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# BFCL Unknown Status After Decode Replay",
        "",
        "No provider, live telemetry, BFCL generate, smoke, evaluate, scorer, full baseline, candidate path, performance evidence, +3pp, SOTA, or Huawei path was run or authorized.",
        "",
        f"run_ids_replayed: `{', '.join(report['run_ids_replayed'])}`",
        f"suspected_unknown_status_failure_stage: `{report['suspected_unknown_status_failure_stage']}`",
        f"patch_gate_recommended: `{report['patch_gate_recommended']}`",
        f"irrelevance_unknowns_status: `{report['irrelevance_unknowns_status']}`",
    ]
    md_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    report = write_report(args.output, args.md_output)
    summary = {
        "report_scope": "bfcl_unknown_status_after_decode_replay_build",
        "artifact_path": str(args.output),
        "run_ids_replayed": report["run_ids_replayed"],
        "suspected_unknown_status_failure_stage": report["suspected_unknown_status_failure_stage"],
        "patch_gate_recommended": report["patch_gate_recommended"],
        "irrelevance_unknowns_status": report["irrelevance_unknowns_status"],
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
