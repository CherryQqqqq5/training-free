#!/usr/bin/env python3
"""Build no-provider BFCL result materialization debug artifact with synthetic fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_result_materialization_debug.json")
DEFAULT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_result_materialization_debug.md")
SIGNED_IDS = ["web_search_base_0", "multi_turn_base_0"]
VARIANTS = [
    "provider_or_proxy_empty",
    "proxy_tool_call_materialized_empty",
    "proxy_text_materialized_empty",
    "result_parser_missed_nonempty",
    "cli_exception_swallowed_as_empty",
]


def _record(run_id: str, variant: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_id": run_id,
        "synthetic_fake_upstream_only": True,
        "provider_request_executed": False,
        "bfcl_generate_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "fake_upstream_variant": variant,
        "provider_or_proxy_returned_empty": False,
        "proxy_returned_nonempty_tool_call": False,
        "proxy_returned_nonempty_text": False,
        "bfcl_handler_stored_empty": False,
        "bfcl_result_file_contains_nonempty_shape": False,
        "bfcl_result_file_classification": "not_applicable",
        "classifier_detected_nonempty_output": False,
        "cli_exception_observed": False,
        "cli_exception_classification": "none",
        "raw_prompt_persisted": False,
        "raw_case_content_persisted": False,
        "raw_provider_payload_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "endpoint_or_key_committed": False,
    }
    if variant == "provider_or_proxy_empty":
        base.update(provider_or_proxy_returned_empty=True, bfcl_handler_stored_empty=True, bfcl_result_file_classification="empty_model_response", suspected_materialization_stage="provider_or_proxy_returned_empty")
    elif variant == "proxy_tool_call_materialized_empty":
        base.update(proxy_returned_nonempty_tool_call=True, bfcl_handler_stored_empty=True, bfcl_result_file_classification="empty_model_response", suspected_materialization_stage="bfcl_handler_or_result_writer_materialized_nonempty_tool_call_as_empty")
    elif variant == "proxy_text_materialized_empty":
        base.update(proxy_returned_nonempty_text=True, bfcl_handler_stored_empty=True, bfcl_result_file_classification="empty_model_response", suspected_materialization_stage="bfcl_handler_or_result_writer_materialized_nonempty_text_as_empty")
    elif variant == "result_parser_missed_nonempty":
        base.update(proxy_returned_nonempty_tool_call=True, bfcl_result_file_contains_nonempty_shape=True, bfcl_result_file_classification="empty_model_response", classifier_detected_nonempty_output=False, suspected_materialization_stage="compact_result_classifier_missed_nonempty_shape")
    elif variant == "cli_exception_swallowed_as_empty":
        base.update(cli_exception_observed=True, cli_exception_classification="synthetic_exception_to_empty", bfcl_handler_stored_empty=True, bfcl_result_file_classification="empty_model_response", suspected_materialization_stage="bfcl_cli_exception_swallowed_as_empty")
    else:
        raise ValueError(f"unknown variant: {variant}")
    return base


def build_report() -> dict[str, Any]:
    records = [_record(run_id, variant) for run_id in SIGNED_IDS for variant in VARIANTS]
    return {
        "artifact_kind": "bfcl_result_materialization_debug",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "signed_run_ids": list(SIGNED_IDS),
        "debug_variants": list(VARIANTS),
        "provider_request_executed": False,
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
        "raw_prompt_persisted": False,
        "raw_case_content_persisted": False,
        "raw_provider_payload_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "endpoint_or_key_committed": False,
        "compact_shape_only": True,
        "synthetic_fake_upstream_only": True,
        "records": records,
        "suspected_next_isolation_target": "bfcl_result_materialization_or_handler_decode_path",
    }


def write_report(output: Path = DEFAULT_OUTPUT, md_output: Path = DEFAULT_MD) -> dict[str, Any]:
    report = build_report()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_output.write_text(
        "# BFCL Result Materialization Debug\n\n"
        "No provider, BFCL generate, evaluate, scorer, full baseline, candidate, performance, +3pp, or Huawei path is executed.\n\n"
        f"Signed IDs: `{SIGNED_IDS[0]}`, `{SIGNED_IDS[1]}`. Route labels: `novacode` / `gpt-4.1`.\n\n"
        "Synthetic variants distinguish provider/proxy empty output, nonempty tool-call or text output materialized as empty, result-classifier misses, and CLI exception-to-empty handling.\n\n"
        f"Suspected next isolation target: `{report['suspected_next_isolation_target']}`.\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    report = write_report(args.output, args.md_output)
    summary = {
        "report_scope": "bfcl_result_materialization_debug_build",
        "artifact_path": str(args.output),
        "record_count": len(report["records"]),
        "provider_request_executed": report["provider_request_executed"],
        "bfcl_generate_executed": report["bfcl_generate_executed"],
        "suspected_next_isolation_target": report["suspected_next_isolation_target"],
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
