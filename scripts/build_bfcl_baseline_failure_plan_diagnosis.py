#!/usr/bin/env python3
"""Build a no-provider diagnosis for the failed BFCL baseline attempt."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_baseline_failure_diagnosis_gate_packet.json")
DEFAULT_FAILURE_SUMMARY = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_failure_closed_summary.json")
DEFAULT_EXECUTION_PLAN = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_execution_plan.json")
DEFAULT_RUNNER = Path("scripts/run_bfcl_v4_baseline.sh")
DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_baseline_failure_plan_diagnosis.json")
DEFAULT_MD_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_baseline_failure_plan_diagnosis.md")

REQUIRED_ENV_NAMES = {
    "GRC_UPSTREAM_PROFILE",
    "GRC_UPSTREAM_MODEL",
    "GRC_BFCL_TEST_CATEGORY",
    "GRC_BFCL_USE_RUN_IDS",
    "GRC_BFCL_CLEAN_RUN",
    "GRC_BFCL_NUM_THREADS",
    "NOVACODE_API_KEY",
    "OPENAI_API_KEY",
    "NOVACODE_BASE_URL",
    "OPENAI_BASE_URL",
}
STAGE_MARKERS = {
    "validate_model_split": "validate_model_split",
    "ensure_upstream_auth": "ensure_upstream_auth",
    "clean_run_state": "clean_run_state",
    "sync_bfcl_fixture_env": "sync_bfcl_fixture_env.py",
    "start_proxy": "grc_wait_proxy_healthy",
    "preflight": "run_bfcl_preflight.py",
    "bfcl_generate": "GENERATE_ARGS",
    "fix_result_layout": "bfcl_fix_result_layout",
    "bfcl_evaluate": "EVAL_ARGS",
    "aggregate_bfcl_metrics": "aggregate_bfcl_metrics.py",
    "write_run_manifest": "write_run_manifest.py",
}
SANITIZED_STAGE_RE = re.compile(r"failure_stage|stage_code|sanitized_stage|suspected_.*stage", re.IGNORECASE)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _command_env_names(command: list[Any], packet: dict[str, Any], plan: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    text = "\n".join(str(item) for item in command)
    for name in REQUIRED_ENV_NAMES:
        if name in text:
            names.add(name)
    for container in (packet.get("required_env_name_labels"), plan.get("api_key_env_names"), plan.get("endpoint_env_names")):
        if isinstance(container, list):
            for value in container:
                if isinstance(value, str) and value in REQUIRED_ENV_NAMES:
                    names.add(value)
    return names


def _runner_stages(script_text: str) -> dict[str, bool]:
    return {stage: marker in script_text for stage, marker in STAGE_MARKERS.items()}


def _postcondition_checker_present() -> bool:
    return Path("scripts/check_bfcl_current_system_baseline_artifacts.py").exists()


def build(packet_path: Path = DEFAULT_PACKET, failure_summary_path: Path = DEFAULT_FAILURE_SUMMARY, plan_path: Path = DEFAULT_EXECUTION_PLAN, runner_path: Path = DEFAULT_RUNNER) -> dict[str, Any]:
    packet = _load(packet_path)
    failure = _load(failure_summary_path)
    plan = _load(plan_path)
    runner_text = runner_path.read_text(encoding="utf-8") if runner_path.exists() else ""
    command = plan.get("runner_command_template") if isinstance(plan.get("runner_command_template"), list) else []
    roots = plan.get("output_roots") if isinstance(plan.get("output_roots"), dict) else {}
    env_names = _command_env_names(command, packet, plan)
    runner_stages = _runner_stages(runner_text)
    missing_runner_stages = sorted(stage for stage, present in runner_stages.items() if not present)
    failure_has_stage = any(key in failure for key in ("suspected_failure_stage", "baseline_failure_stage", "sanitized_failure_stage_code"))
    runner_stage_codes = bool(SANITIZED_STAGE_RE.search(runner_text))
    diagnosis_stage = "baseline_exit_1_without_sanitized_stage_observability" if not failure_has_stage else str(failure.get("suspected_failure_stage") or failure.get("baseline_failure_stage") or failure.get("sanitized_failure_stage_code"))
    missing_stage_observability = not failure_has_stage or not runner_stage_codes
    diagnosis = {
        "artifact_kind": "bfcl_baseline_failure_plan_diagnosis",
        "source_packet": str(packet_path),
        "source_baseline_failure_summary": str(failure_summary_path),
        "source_baseline_execution_plan": str(plan_path),
        "no_provider": True,
        "no_bfcl_execution": True,
        "baseline_failure_summary_present": failure_summary_path.exists(),
        "baseline_execution_exit_code": failure.get("baseline_execution_exit_code"),
        "baseline_execution_succeeded": failure.get("baseline_execution_succeeded"),
        "command_template_present": bool(command) and "scripts/run_bfcl_v4_baseline.sh" in command,
        "runner_script_present": runner_path.exists(),
        "runner_stage_markers_present": runner_stages,
        "runner_stage_markers_missing": missing_runner_stages,
        "env_name_handoff_complete": env_names.issuperset(REQUIRED_ENV_NAMES),
        "env_name_labels_present": sorted(env_names),
        "env_value_material_present": False,
        "output_root_expected": roots.get("run_root") == "outputs/bfcl_v4/current_system_baseline",
        "artifact_dir_expected": roots.get("artifact_dir") == "outputs/bfcl_v4/current_system_baseline/artifacts",
        "compact_metrics_expected": roots.get("compact_metrics") == "outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_compact_metrics.json",
        "compact_manifest_expected": roots.get("compact_manifest") == "outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_compact_manifest.json",
        "run_manifest_expected": "write_run_manifest.py" in runner_text and "run_manifest.json" in runner_text,
        "aggregate_metrics_expected": "aggregate_bfcl_metrics.py" in runner_text and "metrics.json" in runner_text,
        "failure_summary_expected": "failure_summary.json" in runner_text,
        "postcondition_checker_present": _postcondition_checker_present(),
        "sanitized_stage_codes_available": runner_stage_codes and failure_has_stage,
        "failure_summary_has_stage_code": failure_has_stage,
        "runner_has_sanitized_stage_code_emitters": runner_stage_codes,
        "missing_stage_observability": missing_stage_observability,
        "suspected_failure_diagnosis_stage": diagnosis_stage,
        "live_failure_telemetry_gate_recommended": missing_stage_observability,
        "provider_call_authorized": False,
        "bfcl_generate_authorized": False,
        "bfcl_evaluate_authorized": False,
        "scorer_authorized": False,
        "full_baseline_authorized": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_outputs_committed": False,
        "secret_values_printed_or_artifacted": False,
    }
    return diagnosis


def write_outputs(diagnosis: dict[str, Any], output: Path, md_output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(diagnosis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = (
        "# BFCL Baseline Failure Plan Diagnosis\n\n"
        f"- No provider: `{str(diagnosis['no_provider']).lower()}`\n"
        f"- No BFCL execution: `{str(diagnosis['no_bfcl_execution']).lower()}`\n"
        f"- Runner script present: `{str(diagnosis['runner_script_present']).lower()}`\n"
        f"- Env name handoff complete: `{str(diagnosis['env_name_handoff_complete']).lower()}`\n"
        f"- Postcondition checker present: `{str(diagnosis['postcondition_checker_present']).lower()}`\n"
        f"- Sanitized stage codes available: `{str(diagnosis['sanitized_stage_codes_available']).lower()}`\n"
        f"- Missing stage observability: `{str(diagnosis['missing_stage_observability']).lower()}`\n"
        f"- Suspected diagnosis stage: `{diagnosis['suspected_failure_diagnosis_stage']}`\n"
        f"- Live failure telemetry gate recommended: `{str(diagnosis['live_failure_telemetry_gate_recommended']).lower()}`\n"
    )
    md_output.write_text(md, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--failure-summary", type=Path, default=DEFAULT_FAILURE_SUMMARY)
    parser.add_argument("--plan", type=Path, default=DEFAULT_EXECUTION_PLAN)
    parser.add_argument("--runner", type=Path, default=DEFAULT_RUNNER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD_OUTPUT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        diagnosis = build(args.packet, args.failure_summary, args.plan, args.runner)
        write_outputs(diagnosis, args.output, args.md_output)
        summary = diagnosis
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "artifact_kind": "bfcl_baseline_failure_plan_diagnosis",
            "no_provider": True,
            "no_bfcl_execution": True,
            "diagnosis_build_failed": True,
            "blockers": [f"load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and (summary.get("diagnosis_build_failed") or summary.get("no_provider") is not True or summary.get("no_bfcl_execution") is not True):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
