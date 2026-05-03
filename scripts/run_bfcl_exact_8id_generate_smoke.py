#!/usr/bin/env python3
"""Dry-run or execute the approved exact 8-ID BFCL generate-only smoke."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_exact_8id_generate_smoke_gate import (  # noqa: E402
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    REQUIRED_STOP_GATES,
    SIGNED_CATEGORIES,
    SIGNED_IDS,
    check as check_packet,
)
from scripts.run_bfcl_exact_2id_generate_smoke import (  # noqa: E402
    BFCL_MODEL_ALIAS,
    REPO_ROOT as BFCL_REPO_ROOT,
    RUNTIME_CONFIG,
    RULES_DIR,
    _assert_generate_only_command,
    _bfcl_generate_subprocess_env,
    _classify_result_for_run_id,
    _start_proxy,
    _sync_fixture_env,
    _bfcl_package_run_ids_path,
)

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_8id_generate_smoke_compact.json")
DEFAULT_RUN_ROOT = Path("/tmp/bfcl_exact_8id_generate_smoke")
SIGNED_CATEGORY_CSV = ",".join(SIGNED_CATEGORIES)
SIGNED_RUN_IDS_BY_CATEGORY = dict(zip(SIGNED_CATEGORIES, [[run_id] for run_id in SIGNED_IDS]))


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    return {
        "report_scope": "bfcl_exact_8id_generate_smoke_plan",
        "approval_status": packet_summary.get("approval_status"),
        "planned_run_ids": list(SIGNED_IDS),
        "planned_run_id_count": 8,
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "candidate_specs_inert": True,
        "generate_only": True,
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
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "output_artifact_planned": str(output_artifact),
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        "stop_gates": list(REQUIRED_STOP_GATES),
        "blockers": [] if packet_summary.get("bfcl_exact_8id_generate_smoke_gate_passed") else packet_summary.get("blockers", []),
    }


def _write_run_ids(run_root: Path) -> Path:
    path = run_root / "bfcl/test_case_ids_to_generate.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(SIGNED_RUN_IDS_BY_CATEGORY, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path




@contextlib.contextmanager
def _temporary_8id_manifest(path: Path | None = None):
    target = path or _bfcl_package_run_ids_path()
    backup = target.read_bytes() if target.exists() else None
    existed = target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(SIGNED_RUN_IDS_BY_CATEGORY, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        yield target
    finally:
        if existed and backup is not None:
            target.write_bytes(backup)
        else:
            target.unlink(missing_ok=True)


def _generate_command(run_root: Path, port: int, runtime_config: Path, rules_dir: Path) -> list[str]:
    return [
        os.environ.get("GRC_PYTHON") or str(BFCL_REPO_ROOT / ".venv/bin/python"),
        str(BFCL_REPO_ROOT / "scripts/run_bfcl_cli.py"),
        "generate",
        "--model",
        os.environ.get("GRC_BFCL_MODEL", BFCL_MODEL_ALIAS),
        "--skip-server-setup",
        "--num-threads",
        os.environ.get("GRC_BFCL_NUM_THREADS", "1"),
        "--result-dir",
        str(run_root / "bfcl/result"),
        "--allow-overwrite",
        "--run-ids",
        "--test-category",
        SIGNED_CATEGORY_CSV,
    ]


def _execute_preflight_blockers(packet_path: Path, output_artifact: Path) -> list[str]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_exact_8id_generate_smoke_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("exact_8id_generate_smoke_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    return sorted(set(blockers))


def _empty_execute_summary(output_artifact: Path, blockers: list[str]) -> dict[str, Any]:
    return {
        "report_scope": "bfcl_exact_8id_generate_smoke_execute",
        "planned_run_ids": list(SIGNED_IDS),
        "planned_run_id_count": 8,
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
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
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "diagnostic_written": False,
        "output_artifact_planned": str(output_artifact),
        "blockers": blockers,
    }


def _stop_gate_for_records(records: list[dict[str, Any]], *, generate_returncode: int) -> tuple[str, str, bool]:
    if generate_returncode != 0:
        return "bfcl_generate_failed", "generate_failed", False
    by_id = {record.get("run_id"): record for record in records}
    if set(by_id) != set(SIGNED_IDS):
        return "extra_or_missing_id", "run_id_set_mismatch", False
    for run_id in SIGNED_IDS:
        record = by_id.get(run_id)
        if not record or record.get("status") == "missing_result":
            return "missing_result", "result_materialization_missing", False
        if record.get("empty_model_response_detected") is True or record.get("status") == "empty_model_response":
            return "empty_model_response", "empty_model_response", False
        if record.get("protocol_error_detected") is True or record.get("status") == "protocol_error":
            return "protocol_error", "protocol_error", False
    return "none", "none", True


def _compact_artifact(records: list[dict[str, Any]], *, generate_returncode: int) -> dict[str, Any]:
    stop_gate, suspected_stage, smoke_passed = _stop_gate_for_records(records, generate_returncode=generate_returncode)
    return {
        "artifact_kind": "bfcl_exact_8id_generate_smoke_compact",
        "run_id_count": 8,
        "signed_run_ids": list(SIGNED_IDS),
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "candidate_specs_inert": True,
        "provider_request_executed": generate_returncode == 0,
        "bfcl_generate_executed": generate_returncode == 0,
        "bfcl_smoke_executed": generate_returncode == 0,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "gpt_5_2_active": False,
        "openrouter_allowed": False,
        "per_id_compact_status": {str(record.get("run_id")): str(record.get("status")) for record in records},
        "per_id_empty_model_response_detected": {str(record.get("run_id")): bool(record.get("empty_model_response_detected")) for record in records},
        "per_id_protocol_error_detected": {str(record.get("run_id")): bool(record.get("protocol_error_detected")) for record in records},
        "per_id_generated_detected": {str(record.get("run_id")): bool(record.get("tool_call_detected")) for record in records},
        "per_id_result_present": {str(record.get("run_id")): str(record.get("status")) != "missing_result" for record in records},
        "stop_gate_triggered": stop_gate,
        "smoke_passed": smoke_passed,
        "suspected_remaining_stage": suspected_stage,
    }


def _terminate_proxy(proc: Any) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def execute_exact_8id_generate_smoke(
    packet_path: Path = DEFAULT_PACKET,
    output_artifact: Path = DEFAULT_OUTPUT,
    run_root: Path = DEFAULT_RUN_ROOT,
    port: int = 8131,
    *,
    start_proxy: Callable[..., Any] | None = None,
    run_generate: Callable[[list[str]], subprocess.CompletedProcess[Any]] | None = None,
    classify_result: Callable[[str, Path], dict[str, Any]] | None = None,
    sync_fixture_env: Callable[[Path, int], None] | None = None,
    manifest_context: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    blockers = _execute_preflight_blockers(packet_path, output_artifact)
    if blockers:
        return _empty_execute_summary(output_artifact, blockers)
    endpoint_read = bool(os.environ.get("CHUANGZHI_NOVACODE_ENDPOINT") or os.environ.get("NOVACODE_ENDPOINT") or os.environ.get("NOVACODE_BASE_URL"))
    api_key_read = bool(os.environ.get("CHUANGZHI_API_KEY") or os.environ.get("NOVACODE_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    runtime_config = BFCL_REPO_ROOT / RUNTIME_CONFIG
    rules_dir = BFCL_REPO_ROOT / RULES_DIR
    proxy_proc = None
    completed: subprocess.CompletedProcess[Any] | None = None
    try:
        if run_root.exists():
            shutil.rmtree(run_root)
        trace_dir = run_root / "traces"
        _write_run_ids(run_root)
        (sync_fixture_env or _sync_fixture_env)(run_root, port)
        with (manifest_context or _temporary_8id_manifest)():
            proxy_proc = (start_proxy or _start_proxy)(port, trace_dir, runtime_config, rules_dir, run_root / "proxy.log")
            command = _generate_command(run_root, port, runtime_config, rules_dir)
            _assert_generate_only_command(command)
            generate_env = _bfcl_generate_subprocess_env(port)
            completed = (run_generate or (lambda cmd, env=generate_env: subprocess.run(cmd, cwd=BFCL_REPO_ROOT, env=env, check=False)))(command)
        classifier = classify_result or _classify_result_for_run_id
        records = [classifier(run_id, run_root / "bfcl/result") for run_id in SIGNED_IDS]
        artifact = _compact_artifact(records, generate_returncode=int(completed.returncode))
        output_artifact.parent.mkdir(parents=True, exist_ok=True)
        output_artifact.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "report_scope": "bfcl_exact_8id_generate_smoke_execute",
            "planned_run_ids": list(SIGNED_IDS),
            "planned_run_id_count": 8,
            "route_profile": "novacode",
            "route_model": "gpt-4.1",
            "provider_request_executed": completed.returncode == 0,
            "bfcl_generate_executed": completed.returncode == 0,
            "bfcl_smoke_executed": completed.returncode == 0,
            "bfcl_evaluate_executed": False,
            "scorer_executed": False,
            "full_baseline_executed": False,
            "candidate_runtime_activation_authorized": False,
            "candidate_jsonl_authorized": False,
            "candidate_pool_ready": False,
            "performance_evidence": False,
            "sota_3pp_claim_ready": False,
            "huawei_acceptance_ready": False,
            "endpoint_value_read": endpoint_read,
            "api_key_value_read": api_key_read,
            "diagnostic_written": True,
            "artifact_path": str(output_artifact),
            "stop_gate_triggered": artifact["stop_gate_triggered"],
            "smoke_passed": artifact["smoke_passed"],
            "suspected_remaining_stage": artifact["suspected_remaining_stage"],
            "blockers": [] if artifact["smoke_passed"] else [str(artifact["stop_gate_triggered"])],
        }
    finally:
        _terminate_proxy(proxy_proc)
        shutil.rmtree(run_root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-exact-8id-generate-smoke", action="store_true")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--port", type=int, default=8131)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_exact_8id_generate_smoke:
        summary = execute_exact_8id_generate_smoke(args.packet, args.output_artifact, args.run_root, args.port)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    ok = not summary.get("blockers")
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
