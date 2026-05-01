#!/usr/bin/env python3
"""Strict approved-provider-transport gate for RASHE Phase B."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_rashe_provider_transport_approval_packet import (
    APPROVED_CATEGORIES,
    DEFAULT_PACKET,
    FAILURE_BUCKETS,
    SIGNED_ADAPTER,
    SIGNED_CASE_PROVIDER,
    SIGNED_FACTORY,
    SIGNED_OUTPUT_ROOT,
    SIGNED_SCHEMA_PATH,
    SIGNED_SOURCE_INPUT_ROOT,
    check as check_packet,
)
from scripts.run_rashe_source_diagnostic_compact import SIGNED_PUBLISH_FIELDS

SIGNED_PROVIDER_PROFILE = "Chuangzhi/Novacode"
SIGNED_MODEL = "gpt-5.2"
SIGNED_CASES_PER_CATEGORY = 20
SIGNED_TOTAL_CASES = 160
ROOT = Path(__file__).resolve().parents[1]


def _run_json(args: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0:
        return None, result.stdout.strip() or result.stderr.strip() or "checker_failed"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, f"checker_json_invalid:{args[0]}:{exc}"
    if not isinstance(data, dict):
        return None, f"checker_output_not_object:{args[0]}"
    return data, None


def _run_plain(args: list[str]) -> str | None:
    result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0:
        return result.stdout.strip() or result.stderr.strip() or "checker_failed"
    return None


def _signed_runner_args() -> list[str]:
    return [
        "scripts/run_rashe_source_diagnostic_compact.py",
        "--provider-profile",
        SIGNED_PROVIDER_PROFILE,
        "--model",
        SIGNED_MODEL,
        "--categories",
        ",".join(APPROVED_CATEGORIES),
        "--min-cases-per-category",
        str(SIGNED_CASES_PER_CATEGORY),
        "--max-cases-per-category",
        str(SIGNED_CASES_PER_CATEGORY),
        "--max-total-cases",
        str(SIGNED_TOTAL_CASES),
        "--output-root",
        SIGNED_OUTPUT_ROOT,
        "--schema",
        SIGNED_SCHEMA_PATH,
        "--source-input-root",
        SIGNED_SOURCE_INPUT_ROOT,
        "--compact-sanitized-only",
        "--publish-fields",
        ",".join(SIGNED_PUBLISH_FIELDS),
        "--no-raw-trace",
        "--no-raw-payload",
        "--no-candidate-jsonl",
        "--no-scorer",
        "--execution-adapter",
        SIGNED_ADAPTER,
        "--provider-client-factory",
        SIGNED_FACTORY,
        "--source-case-provider",
        SIGNED_CASE_PROVIDER,
        "--dry-run",
        "--compact",
        "--strict",
    ]


def _validate_runner_summary(summary: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = {
        "provider_profile": SIGNED_PROVIDER_PROFILE,
        "model": SIGNED_MODEL,
        "categories": list(APPROVED_CATEGORIES),
        "min_cases_per_category": SIGNED_CASES_PER_CATEGORY,
        "max_cases_per_category": SIGNED_CASES_PER_CATEGORY,
        "planned_case_count_per_category": SIGNED_CASES_PER_CATEGORY,
        "planned_total_cases": SIGNED_TOTAL_CASES,
        "max_total_cases": SIGNED_TOTAL_CASES,
        "output_root": SIGNED_OUTPUT_ROOT.rstrip("/"),
        "schema_path": SIGNED_SCHEMA_PATH,
        "source_input_root": SIGNED_SOURCE_INPUT_ROOT.rstrip("/"),
        "publish_fields": list(SIGNED_PUBLISH_FIELDS),
        "dry_run": True,
        "execute_requested": False,
        "provider_call_executed": False,
        "api_key_read": False,
        "diagnostic_written": False,
        "execution_adapter_status": "loadable",
        "provider_client_factory_status": "loadable",
        "source_case_provider_status": "loadable",
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            blockers.append(f"signed_runner_{key}_invalid:{summary.get(key)!r}")
    if summary.get("rashe_source_diagnostic_compact_plan_passed") is not True:
        blockers.append("signed_runner_dry_run_not_passed")
    artifacts = summary.get("compact_artifact_plan")
    if not isinstance(artifacts, list) or len(artifacts) != len(APPROVED_CATEGORIES):
        blockers.append("signed_runner_compact_artifact_plan_invalid")
    else:
        for artifact, category in zip(artifacts, APPROVED_CATEGORIES):
            if artifact.get("category") != category:
                blockers.append(f"signed_runner_artifact_category_invalid:{artifact.get('category')!r}:{category}")
            if artifact.get("case_count") != SIGNED_CASES_PER_CATEGORY:
                blockers.append(f"signed_runner_artifact_case_count_invalid:{category}:{artifact.get('case_count')!r}")
            if artifact.get("provider_call_count") != 0:
                blockers.append(f"signed_runner_dry_run_provider_count_not_zero:{category}")
            if set((artifact.get("failure_bucket_counts") or {}).keys()) != set(FAILURE_BUCKETS):
                blockers.append(f"signed_runner_failure_bucket_keys_invalid:{category}")
            for field in ["raw_payload_tracked_count", "forbidden_field_violation_count"]:
                if artifact.get(field) != 0:
                    blockers.append(f"signed_runner_{field}_not_zero:{category}")
            for field in ["candidate_generation_authorized", "scorer_authorized", "performance_evidence"]:
                if artifact.get(field) is not False:
                    blockers.append(f"signed_runner_{field}_not_false:{category}")
    return blockers


def check(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    summary = check_packet(packet_path)
    blockers = list(summary.get("blockers", []))
    if summary.get("approval_status") != "approved":
        blockers.append(f"provider_transport_not_approved:{summary.get('approval_status')!r}")
    for key in ["authorized", "provider_transport_authorized", "source_diagnostic_execution_authorized", "provider_calls_authorized"]:
        if summary.get(key) is not True:
            blockers.append(f"provider_transport_gate_{key}_not_true:{summary.get(key)!r}")

    gate_commands = [
        ("metadata_root", ["scripts/check_rashe_source_metadata_compact.py", "--root", SIGNED_SOURCE_INPUT_ROOT.replace("rashe_source_inputs_compact/", "approved_source_metadata_compact/"), "--compact", "--strict"], "rashe_source_metadata_compact_passed"),
        ("source_input", ["scripts/check_rashe_source_inputs_compact.py", "--root", SIGNED_SOURCE_INPUT_ROOT, "--compact", "--strict"], "rashe_source_inputs_compact_passed"),
    ]
    gate_status: dict[str, bool] = {}
    for name, command, passed_key in gate_commands:
        data, error = _run_json(command)
        if error:
            blockers.append(f"{name}_checker_failed:{error}")
            gate_status[name] = False
        else:
            passed = data.get(passed_key) is True
            gate_status[name] = passed
            if not passed:
                blockers.append(f"{name}_checker_not_passed")
    artifact_error = _run_plain([sys.executable, "scripts/check_artifact_boundary.py"])
    gate_status["artifact_boundary"] = artifact_error is None
    if artifact_error:
        blockers.append(f"artifact_boundary_checker_failed:{artifact_error}")

    runner_summary, runner_error = _run_json(_signed_runner_args())
    if runner_error:
        blockers.append(f"signed_runner_dry_run_failed:{runner_error}")
        runner_status = False
    else:
        runner_blockers = _validate_runner_summary(runner_summary)
        blockers.extend(runner_blockers)
        runner_status = not runner_blockers
    gate_status["signed_runner_dry_run"] = runner_status

    return {
        **summary,
        "report_scope": "rashe_provider_transport_approved_check",
        "metadata_checker_passed": gate_status.get("metadata_root", False),
        "source_input_checker_passed": gate_status.get("source_input", False),
        "artifact_boundary_checker_passed": gate_status.get("artifact_boundary", False),
        "signed_runner_dry_run_passed": gate_status.get("signed_runner_dry_run", False),
        "signed_runner_command": " ".join([sys.executable, *_signed_runner_args()]),
        "rashe_provider_transport_approved_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.packet)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_provider_transport_approved_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
