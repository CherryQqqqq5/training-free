#!/usr/bin/env python3
"""Build no-provider protocol/unknown classifier replay from compact 8-ID smoke labels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_exact_8id_generate_smoke_gate import SIGNED_IDS  # noqa: E402

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
SOURCE_ARTIFACT = ARTIFACT_ROOT / "bfcl_exact_8id_generate_smoke_compact.json"
DEFAULT_OUTPUT = ARTIFACT_ROOT / "bfcl_protocol_unknown_classifier_replay.json"
DEFAULT_MD = ARTIFACT_ROOT / "bfcl_protocol_unknown_classifier_replay.md"
TARGET_PROTOCOL_ID = "multi_turn_long_context_0"
TARGET_UNKNOWN_IDS = ["irrelevance_0", "live_irrelevance_0-0-0"]
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


def _load_source(path: Path = SOURCE_ARTIFACT) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain JSON object")
    return data


def _record(run_id: str, source: dict[str, Any]) -> dict[str, Any]:
    statuses = source.get("per_id_compact_status") if isinstance(source.get("per_id_compact_status"), dict) else {}
    generated = source.get("per_id_generated_detected") if isinstance(source.get("per_id_generated_detected"), dict) else {}
    protocol = source.get("per_id_protocol_error_detected") if isinstance(source.get("per_id_protocol_error_detected"), dict) else {}
    empty = source.get("per_id_empty_model_response_detected") if isinstance(source.get("per_id_empty_model_response_detected"), dict) else {}
    present = source.get("per_id_result_present") if isinstance(source.get("per_id_result_present"), dict) else {}
    status = str(statuses.get(run_id) or "missing_status_label")
    generated_flag = generated.get(run_id) is True
    protocol_flag = protocol.get(run_id) is True
    empty_flag = empty.get(run_id) is True
    present_flag = present.get(run_id) is True
    positive_flags = [name for name, enabled in (("generated", generated_flag), ("protocol_error", protocol_flag), ("empty_model_response", empty_flag)) if enabled]
    if status == "protocol_error" and protocol_flag and not generated_flag and not empty_flag:
        replay_label = "protocol_error_label_consistent"
        suspected = "protocol_error_classifier_or_materialized_protocol_shape"
        shape_sufficient = True
    elif status == "unknown_compact_status" and present_flag and not positive_flags:
        replay_label = "unknown_status_present_without_positive_compact_flags"
        suspected = "unknown_requires_live_shape_or_materialized_status_telemetry"
        shape_sufficient = False
    elif status == "generated" and generated_flag and not protocol_flag and not empty_flag:
        replay_label = "generated_label_consistent"
        suspected = "not_target_generated_control"
        shape_sufficient = True
    elif not present_flag:
        replay_label = "missing_result_label_consistent"
        suspected = "missing_result"
        shape_sufficient = True
    else:
        replay_label = "compact_label_flag_mismatch"
        suspected = "compact_classifier_label_flag_mismatch"
        shape_sufficient = False
    return {
        "run_id": run_id,
        "compact_status": status,
        "result_present": present_flag,
        "generated_detected": generated_flag,
        "protocol_error_detected": protocol_flag,
        "empty_model_response_detected": empty_flag,
        "positive_compact_flag_count": len(positive_flags),
        "positive_compact_flag_labels": positive_flags,
        "replay_classification_label": replay_label,
        "compact_shape_data_sufficient_for_root_cause": shape_sufficient,
        "suspected_classifier_replay_stage": suspected,
    }


def build_report(source_path: Path = SOURCE_ARTIFACT) -> dict[str, Any]:
    source = _load_source(source_path)
    records = [_record(run_id, source) for run_id in SIGNED_IDS]
    target_protocol = next(record for record in records if record["run_id"] == TARGET_PROTOCOL_ID)
    unknown_records = [record for record in records if record["run_id"] in TARGET_UNKNOWN_IDS]
    unknown_limited = any(record["compact_shape_data_sufficient_for_root_cause"] is False for record in unknown_records)
    suspected = (
        "protocol_error_label_explicit_unknown_status_shape_limited"
        if target_protocol["replay_classification_label"] == "protocol_error_label_consistent" and unknown_limited
        else "compact_classifier_replay_inconclusive"
    )
    return {
        "artifact_kind": "bfcl_protocol_unknown_classifier_replay",
        "approval_status": "prepared",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "no_provider": True,
        "synthetic_fixtures_only": False,
        "compact_artifact_labels_only": True,
        "source_artifact": str(source_path),
        "source_artifact_kind": source.get("artifact_kind"),
        "source_run_id_count": source.get("run_id_count"),
        "source_signed_run_ids": source.get("signed_run_ids"),
        **FALSE_FLAGS,
        "target_protocol_run_id": TARGET_PROTOCOL_ID,
        "target_unknown_run_ids": list(TARGET_UNKNOWN_IDS),
        "protocol_error_replay_label": target_protocol["replay_classification_label"],
        "unknown_status_replay_labels": {record["run_id"]: record["replay_classification_label"] for record in unknown_records},
        "classifier_replay_feasible": True,
        "unknown_root_cause_resolved_by_compact_replay": False,
        "records": records,
        "suspected_classifier_replay_stage": suspected,
        "next_recommended_gate": "one_id_protocol_error_telemetry_for_multi_turn_long_context_0",
    }


def write_report(output: Path = DEFAULT_OUTPUT, md_output: Path = DEFAULT_MD, source_path: Path = SOURCE_ARTIFACT) -> dict[str, Any]:
    report = build_report(source_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# BFCL Protocol/Unknown Classifier Replay",
        "",
        "No provider, live telemetry, BFCL generate, smoke, evaluate, scorer, full baseline, candidate path, performance evidence, +3pp, SOTA, or Huawei path was run or authorized.",
        "",
        "Replay source: compact 8-ID smoke labels only.",
        f"target_protocol_run_id: `{report['target_protocol_run_id']}`",
        f"protocol_error_replay_label: `{report['protocol_error_replay_label']}`",
        f"target_unknown_run_ids: `{', '.join(report['target_unknown_run_ids'])}`",
        f"unknown_root_cause_resolved_by_compact_replay: `{report['unknown_root_cause_resolved_by_compact_replay']}`",
        f"suspected_classifier_replay_stage: `{report['suspected_classifier_replay_stage']}`",
        f"next_recommended_gate: `{report['next_recommended_gate']}`",
    ]
    md_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_ARTIFACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    report = write_report(args.output, args.md_output, args.source)
    summary = {
        "report_scope": "bfcl_protocol_unknown_classifier_replay_build",
        "artifact_path": str(args.output),
        "classifier_replay_feasible": report["classifier_replay_feasible"],
        "protocol_error_replay_label": report["protocol_error_replay_label"],
        "unknown_root_cause_resolved_by_compact_replay": report["unknown_root_cause_resolved_by_compact_replay"],
        "suspected_classifier_replay_stage": report["suspected_classifier_replay_stage"],
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
