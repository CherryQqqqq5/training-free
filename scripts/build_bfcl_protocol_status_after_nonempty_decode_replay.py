#!/usr/bin/env python3
"""Build no-provider protocol-status-after-nonempty-decode replay."""

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

from scripts.run_bfcl_cli import (  # noqa: E402
    _entry_has_protocol_error_indicator,
    _preserve_decoded_execution_output_shape,
)
from scripts.run_bfcl_exact_2id_generate_smoke import _classify_result_for_run_id  # noqa: E402

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
SOURCE_ARTIFACT = ARTIFACT_ROOT / "bfcl_one_id_protocol_error_telemetry_after_unknown_status_patch_compact.json"
DEFAULT_OUTPUT = ARTIFACT_ROOT / "bfcl_protocol_status_after_nonempty_decode_replay.json"
DEFAULT_MD = ARTIFACT_ROOT / "bfcl_protocol_status_after_nonempty_decode_replay.md"
REPLAY_RUN_ID = "multi_turn_long_context_0"
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


def _source_record(source: dict[str, Any]) -> dict[str, Any]:
    records = source.get("records")
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        raise ValueError("source artifact must contain exactly one compact record")
    record = records[0]
    if record.get("run_id") != REPLAY_RUN_ID:
        raise ValueError("source artifact run_id mismatch")
    return record


def _classify_payload(run_id: str, payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="bfcl_protocol_status_replay_") as tmp:
        root = Path(tmp)
        result_root = root / "bfcl" / "result"
        result_root.mkdir(parents=True, exist_ok=True)
        (result_root / f"{run_id}.json").write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        return _classify_result_for_run_id(run_id, result_root)


def _variant(name: str, entry: dict[str, Any]) -> dict[str, Any]:
    indicator = _entry_has_protocol_error_indicator(entry)
    preserved = _preserve_decoded_execution_output_shape(entry)
    marker_added = isinstance(preserved, dict) and "grc_decoded_execution_output_shape" in preserved
    classification = _classify_payload(str(entry.get("id") or REPLAY_RUN_ID), preserved if isinstance(preserved, dict) else entry)
    status = str(classification.get("status") or "missing")
    return {
        "variant": name,
        "decoded_nonempty": True,
        "protocol_error_indicator_detected": bool(indicator),
        "marker_added": bool(marker_added),
        "classifier_status_replayed": status,
        "protocol_status_label_replayed": status if status in {"generated", "protocol_error", "empty_model_response", "missing_result", "unknown_compact_status"} else "other",
        "false_protocol_error_on_nonempty_decode": status == "protocol_error" and not indicator,
    }


def _shape_variants() -> list[dict[str, Any]]:
    return [
        {
            **_variant(
                "clean_nonempty_decoded_execution_list",
                {
                    "id": REPLAY_RUN_ID,
                    "result": [["shape_only_decoded_execution"]],
                    "inference_log": [{"step_0": [{"model_response_decoded": ["decoded_execution_shape"]}]}],
                },
            ),
            "protocol_error_indicator_source_label": "none",
            "materialized_shape_label_replayed": "generated_equivalent_shape",
        },
        {
            **_variant(
                "ordinary_protocol_label_nonempty_decoded",
                {
                    "id": REPLAY_RUN_ID,
                    "result": [["ordinary protocol label shape"]],
                    "inference_log": [{"step_0": [{"model_response_decoded": ["decoded protocol label shape"]}]}],
                },
            ),
            "protocol_error_indicator_source_label": "none",
            "materialized_shape_label_replayed": "generated_equivalent_shape",
        },
        {
            **_variant(
                "mixed_nonempty_decode_with_explicit_handler_error_phrase",
                {
                    "id": REPLAY_RUN_ID,
                    "result": "Error during inference: synthetic shape",
                    "inference_log": [{"step_0": [{"model_response_decoded": ["decoded_execution_shape"]}]}],
                },
            ),
            "protocol_error_indicator_source_label": "explicit_handler_error_phrase",
            "materialized_shape_label_replayed": "protocol_error_shape",
        },
        {
            **_variant(
                "mixed_nonempty_decode_with_structured_error_key",
                {
                    "id": REPLAY_RUN_ID,
                    "result": [["shape_only_decoded_execution"]],
                    "inference_log": [{"step_0": [{"model_response_decoded": ["decoded_execution_shape"], "error_type": "synthetic_protocol_error"}]}],
                },
            ),
            "protocol_error_indicator_source_label": "structured_error_key",
            "materialized_shape_label_replayed": "protocol_error_shape",
        },
        {
            **_variant(
                "materialized_protocol_error_shape_label",
                {
                    "id": REPLAY_RUN_ID,
                    "result": "protocol_error_shape",
                    "decoded_output_shape_label": "execution_list_nonempty",
                },
            ),
            "protocol_error_indicator_source_label": "shape_label_contains_error",
            "materialized_shape_label_replayed": "protocol_error_shape",
        },
    ]


def _derive_conclusion(source_record: dict[str, Any], variants: list[dict[str, Any]]) -> dict[str, Any]:
    explicit_error_variants = [v for v in variants if v["protocol_error_indicator_source_label"] in {"explicit_handler_error_phrase", "structured_error_key", "shape_label_contains_error"}]
    clean_false_error = any(v.get("false_protocol_error_on_nonempty_decode") is True for v in variants if v["protocol_error_indicator_source_label"] == "none")
    if clean_false_error:
        stage = "protocol_error_indicator_false_positive_on_clean_nonempty_decode"
        patch_gate = True
    elif source_record.get("materialized_result_shape_label") == "protocol_error_shape" and source_record.get("materialized_result_nonempty") is False:
        stage = "materialization_entry_shape_protocol_error_after_nonempty_decode"
        patch_gate = True
    elif source_record.get("protocol_status_classifier_label") == "protocol_error":
        stage = "protocol_status_classifier_maps_materialized_shape_to_protocol_error"
        patch_gate = True
    else:
        stage = "insufficient_compact_labels_needs_live_telemetry"
        patch_gate = False
    return {
        "suspected_protocol_status_failure_stage": stage,
        "patch_gate_recommended": patch_gate,
        "explicit_error_variant_count": len(explicit_error_variants),
        "clean_nonempty_false_protocol_error_reproduced": clean_false_error,
    }


def build_report(source_artifact: Path = SOURCE_ARTIFACT) -> dict[str, Any]:
    source = _load(source_artifact)
    record = _source_record(source)
    variants = _shape_variants()
    conclusion = _derive_conclusion(record, variants)
    return {
        "artifact_kind": "bfcl_protocol_status_after_nonempty_decode_replay",
        "approval_status": "prepared",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "no_provider": True,
        "compact_labels_only": True,
        "source_artifact": str(source_artifact),
        "replay_run_id": REPLAY_RUN_ID,
        **FALSE_FLAGS,
        "decoded_nonempty": record.get("bfcl_decode_execute_nonempty") is True,
        "decoded_output_count": int(record.get("bfcl_decode_output_count") or 0),
        "materialized_shape_label": str(record.get("materialized_result_shape_label") or "missing"),
        "materialized_result_nonempty": record.get("materialized_result_nonempty") is True,
        "protocol_error_indicator_detected": any(v["protocol_error_indicator_detected"] for v in variants if v["materialized_shape_label_replayed"] == "protocol_error_shape"),
        "protocol_error_indicator_source_label": "explicit_error_or_protocol_error_shape_label",
        "classifier_status_replayed": str(record.get("classifier_status") or "missing"),
        "protocol_status_label_replayed": str(record.get("protocol_status_classifier_label") or "missing"),
        "false_protocol_error_on_nonempty_decode": record.get("bfcl_decode_execute_nonempty") is True and record.get("compact_result_status") == "protocol_error",
        "shape_variant_replay": variants,
        **conclusion,
    }


def write_report(output: Path = DEFAULT_OUTPUT, md_output: Path = DEFAULT_MD) -> dict[str, Any]:
    report = build_report()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# BFCL Protocol Status After Nonempty Decode Replay",
        "",
        "No provider, live telemetry, BFCL generate, smoke, evaluate, scorer, full baseline, candidate path, performance evidence, +3pp, SOTA, or Huawei path was run or authorized.",
        "",
        f"replay_run_id: `{report['replay_run_id']}`",
        f"materialized_shape_label: `{report['materialized_shape_label']}`",
        f"classifier_status_replayed: `{report['classifier_status_replayed']}`",
        f"protocol_status_label_replayed: `{report['protocol_status_label_replayed']}`",
        f"suspected_protocol_status_failure_stage: `{report['suspected_protocol_status_failure_stage']}`",
        f"patch_gate_recommended: `{report['patch_gate_recommended']}`",
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
        "report_scope": "bfcl_protocol_status_after_nonempty_decode_replay_build",
        "artifact_path": str(args.output),
        "replay_run_id": report["replay_run_id"],
        "suspected_protocol_status_failure_stage": report["suspected_protocol_status_failure_stage"],
        "patch_gate_recommended": report["patch_gate_recommended"],
        "false_protocol_error_on_nonempty_decode": report["false_protocol_error_on_nonempty_decode"],
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
