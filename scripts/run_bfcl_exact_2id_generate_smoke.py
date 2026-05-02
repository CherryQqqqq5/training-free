#!/usr/bin/env python3
"""Plan or execute exact 2-ID BFCL generate-only smoke.

Execution is fail-closed until the exact 2-ID smoke packet is explicitly approved.
The execute path calls BFCL generate only; it never calls BFCL evaluate/scorer.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
SIGNED_IDS = ["web_search_base_0", "multi_turn_base_0"]
SIGNED_ID_MANIFEST = {
    "web_search_base": ["web_search_base_0"],
    "multi_turn_base": ["multi_turn_base_0"],
}
SIGNED_CATEGORIES = "web_search_base,multi_turn_base"
PACKET_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_smoke_approval_packet.json")
DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_generate_smoke_compact.json")
DEFAULT_RUN_ROOT = Path("/tmp/bfcl_exact_2id_generate_smoke")
RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")
RULES_DIR = Path("rules/baseline_empty")
BFCL_MODEL_ALIAS = "gpt-4o-mini-2024-07-18-FC"


def _python() -> str:
    return os.environ.get("GRC_PYTHON") or str(REPO_ROOT / ".venv/bin/python")


def _load_packet(path: Path = PACKET_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _approved_execution_blockers(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = {
        "artifact_kind": "bfcl_exact_2id_smoke_approval_packet",
        "approval_status": "approved",
        "authorized": True,
        "provider_call_authorized": True,
        "bfcl_smoke_authorized": True,
        "bfcl_generate_authorized": True,
        "bfcl_evaluate_authorized": False,
        "scorer_authorized": False,
        "full_baseline_authorized": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "gpt_5_2_active": False,
        "signed_run_ids": SIGNED_IDS,
        "max_cases": 2,
        "generate_only": True,
        "evaluate_command_allowed": False,
        "scorer_command_allowed": False,
        "full_default_runner_allowed": False,
        "baseline_shell_runner_allowed": False,
    }
    for key, value in expected.items():
        if packet.get(key) != value:
            blockers.append(f"packet_{key}_not_approved_for_execute:{packet.get(key)!r}")
    if packet.get("generate_only_runner_path") != "scripts/run_bfcl_exact_2id_generate_smoke.py":
        blockers.append("packet_runner_path_mismatch")
    if packet.get("compact_artifact_checker_path") != "scripts/check_bfcl_exact_2id_generate_smoke_artifact.py":
        blockers.append("packet_artifact_checker_path_mismatch")
    return blockers


def build_plan(packet_path: Path = PACKET_PATH) -> dict[str, Any]:
    packet = _load_packet(packet_path)
    return {
        "report_scope": "bfcl_exact_2id_generate_smoke_plan",
        "approval_status": packet.get("approval_status"),
        "run_ids": SIGNED_IDS,
        "case_count": 2,
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "bfcl_model_alias": BFCL_MODEL_ALIAS,
        "test_category": SIGNED_CATEGORIES,
        "generate_only": True,
        "generate_command_reviewed": True,
        "evaluate_command_present": False,
        "scorer_command_present": False,
        "provider_call_executed": False,
        "bfcl_generate_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "output_artifact": str(DEFAULT_OUTPUT),
        "blockers": [],
    }


def _write_run_ids(run_root: Path) -> Path:
    path = run_root / "bfcl/test_case_ids_to_generate.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_manifest_payload(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _bfcl_package_run_ids_path() -> Path:
    from bfcl_eval.constants import eval_config

    return Path(eval_config.TEST_IDS_TO_GENERATE_PATH)


def _manifest_payload() -> dict[str, list[str]]:
    return {category: list(ids) for category, ids in SIGNED_ID_MANIFEST.items()}


def _manifest_payload_blockers(payload: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if "test_case_ids" in payload:
        blockers.append("legacy_test_case_ids_key_forbidden")
    if payload != SIGNED_ID_MANIFEST:
        blockers.append(f"manifest_schema_or_ids_invalid:{payload!r}")
    return blockers


def _write_manifest(path: Path) -> None:
    payload = _manifest_payload()
    blockers = _manifest_payload_blockers(payload)
    if blockers:
        raise RuntimeError(";".join(blockers))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@contextlib.contextmanager
def _temporary_bfcl_run_ids_manifest(path: Path | None = None):
    target = path or _bfcl_package_run_ids_path()
    backup: bytes | None = target.read_bytes() if target.exists() else None
    existed = target.exists()
    _write_manifest(target)
    try:
        yield target
    finally:
        if existed and backup is not None:
            target.write_bytes(backup)
        else:
            target.unlink(missing_ok=True)


def _generate_command(run_root: Path, port: int, runtime_config: Path, rules_dir: Path) -> list[str]:
    result_dir = run_root / "bfcl/result"
    return [
        _python(),
        str(REPO_ROOT / "scripts/run_bfcl_cli.py"),
        "generate",
        "--model",
        os.environ.get("GRC_BFCL_MODEL", BFCL_MODEL_ALIAS),
        "--skip-server-setup",
        "--num-threads",
        os.environ.get("GRC_BFCL_NUM_THREADS", "1"),
        "--result-dir",
        str(result_dir),
        "--allow-overwrite",
        "--run-ids",
        "--test-category",
        SIGNED_CATEGORIES,
    ]


def _assert_generate_only_command(command: list[str]) -> None:
    joined = " ".join(command)
    forbidden = [" evaluate ", " aggregate_bfcl_metrics.py", " write_run_manifest.py", "run_bfcl_v4_baseline.sh"]
    for token in forbidden:
        if token in f" {joined} ":
            raise RuntimeError(f"forbidden_evaluate_or_scorer_command:{token.strip()}")
    if " generate " not in f" {joined} ":
        raise RuntimeError("generate_command_missing")


def _first_present(env: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = env.get(name)
        if value:
            return value
    return None


def _bfcl_generate_subprocess_env(port: int, source_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(source_env or os.environ)
    if not env.get("OPENAI_API_KEY"):
        bridged_key = _first_present(env, ("CHUANGZHI_API_KEY", "NOVACODE_API_KEY"))
        if bridged_key:
            env["OPENAI_API_KEY"] = bridged_key
    env["OPENAI_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
    return env


def _bfcl_generate_env_summary(env: dict[str, str]) -> dict[str, bool]:
    return {
        "openai_api_key_present": bool(env.get("OPENAI_API_KEY")),
        "openai_base_url_present": bool(env.get("OPENAI_BASE_URL")),
        "approved_key_env_present": bool(env.get("CHUANGZHI_API_KEY") or env.get("NOVACODE_API_KEY")),
        "approved_endpoint_env_present": bool(
            env.get("CHUANGZHI_NOVACODE_ENDPOINT") or env.get("NOVACODE_ENDPOINT") or env.get("NOVACODE_BASE_URL")
        ),
    }


def _wait_proxy(port: int, log_path: Path) -> None:
    for _ in range(60):
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"proxy_healthcheck_failed:{log_path}")


def _start_proxy(port: int, trace_dir: Path, runtime_config: Path, rules_dir: Path, log_path: Path) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + ((":" + env["PYTHONPATH"]) if env.get("PYTHONPATH") else "")
    command = [
        _python(),
        "-m",
        "grc.cli",
        "serve",
        "--config",
        str(runtime_config),
        "--rules-dir",
        str(rules_dir),
        "--trace-dir",
        str(trace_dir),
        "--port",
        str(port),
    ]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("wb")
    proc = subprocess.Popen(command, cwd=REPO_ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT)
    _wait_proxy(port, log_path)
    return proc


def _sync_fixture_env(run_root: Path, port: int) -> None:
    subprocess.run(
        [
            _python(),
            str(REPO_ROOT / "scripts/sync_bfcl_fixture_env.py"),
            "--bfcl-root",
            str(run_root / "bfcl"),
            "--openai-base-url",
            f"http://127.0.0.1:{port}/v1",
            "--local-server-endpoint",
            "http://127.0.0.1",
            "--local-server-port",
            str(port),
            "--openai-api-key",
            os.environ.get("OPENAI_API_KEY", "dummy"),
        ],
        cwd=REPO_ROOT,
        check=True,
    )


def _classify_result_for_run_id(run_id: str, result_root: Path) -> dict[str, Any]:
    text = ""
    for path in result_root.rglob("*.json"):
        try:
            candidate = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if run_id in candidate:
            text += "\n" + candidate[:20000]
    lowered = text.lower()
    if not text:
        status = "missing_result"
    elif "empty response from the model" in lowered or "empty_model_response" in lowered:
        status = "empty_model_response"
    elif "tool_calls" in lowered or "function_call" in lowered:
        status = "generated"
    elif "error" in lowered or "exception" in lowered:
        status = "protocol_error"
    else:
        status = "unknown_compact_status"
    return {
        "run_id": run_id,
        "status": status,
        "empty_model_response_detected": status == "empty_model_response",
        "no_tool_text_recorded": "record_only_no_tool_text" in lowered,
        "tool_call_detected": "tool_calls" in lowered or "function_call" in lowered,
        "protocol_error_detected": status == "protocol_error",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
    }


def _write_compact_artifact(output: Path, *, generated: bool, records: list[dict[str, Any]]) -> dict[str, Any]:
    artifact = {
        "artifact_kind": "bfcl_exact_2id_generate_smoke_compact",
        "approval_status": "executed_generate_only" if generated else "planned_or_failed_closed",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "provider_profile": "Chuangzhi/Novacode",
        "run_ids": SIGNED_IDS,
        "case_count": 2,
        "provider_call_executed": generated,
        "bfcl_generate_executed": generated,
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
        "openrouter_allowed": False,
        "gpt_5_2_active": False,
        "raw_prompt_persisted": False,
        "raw_case_persisted": False,
        "raw_provider_payload_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "endpoint_or_key_committed": False,
        "records": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def execute_generate_smoke(
    *,
    output: Path = DEFAULT_OUTPUT,
    packet_path: Path = PACKET_PATH,
    run_root: Path = DEFAULT_RUN_ROOT,
    port: int = 8131,
    start_proxy: Callable[..., subprocess.Popen[bytes]] | None = None,
    run_generate: Callable[[list[str]], subprocess.CompletedProcess[Any]] | None = None,
) -> dict[str, Any]:
    packet = _load_packet(packet_path)
    blockers = _approved_execution_blockers(packet)
    if blockers:
        return {**build_plan(packet_path), "report_scope": "bfcl_exact_2id_generate_smoke_execute", "blockers": blockers}
    endpoint_read = False
    api_key_read = False
    if os.environ.get("CHUANGZHI_NOVACODE_ENDPOINT") or os.environ.get("NOVACODE_ENDPOINT") or os.environ.get("NOVACODE_BASE_URL"):
        endpoint_read = True
    if os.environ.get("CHUANGZHI_API_KEY") or os.environ.get("NOVACODE_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        api_key_read = True
    if run_root.exists():
        shutil.rmtree(run_root)
    trace_dir = run_root / "traces"
    rules_dir = REPO_ROOT / RULES_DIR
    runtime_config = REPO_ROOT / RUNTIME_CONFIG
    _write_run_ids(run_root)
    _sync_fixture_env(run_root, port)
    proxy_proc = None
    try:
        with _temporary_bfcl_run_ids_manifest():
            proxy_proc = (start_proxy or _start_proxy)(port, trace_dir, runtime_config, rules_dir, run_root / "proxy.log")
            command = _generate_command(run_root, port, runtime_config, rules_dir)
            _assert_generate_only_command(command)
            generate_env = _bfcl_generate_subprocess_env(port)
            completed = (
                run_generate
                or (lambda cmd, env=generate_env: subprocess.run(cmd, cwd=REPO_ROOT, env=env, check=False))
            )(command)
        generated = completed.returncode == 0
        records = [_classify_result_for_run_id(run_id, run_root / "bfcl/result") for run_id in SIGNED_IDS]
        artifact = _write_compact_artifact(output, generated=generated, records=records)
        return {
            "report_scope": "bfcl_exact_2id_generate_smoke_execute",
            "provider_call_executed": generated,
            "bfcl_generate_executed": generated,
            "bfcl_evaluate_executed": False,
            "scorer_executed": False,
            "endpoint_value_read": endpoint_read,
            "api_key_value_read": api_key_read,
            "output_artifact": str(output),
            "run_ids": SIGNED_IDS,
            "case_count": 2,
            "blockers": [] if generated else ["bfcl_generate_failed"],
            "artifact_kind": artifact["artifact_kind"],
        }
    finally:
        if proxy_proc is not None:
            proxy_proc.terminate()
            try:
                proxy_proc.wait(timeout=5)
            except Exception:
                proxy_proc.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--packet", type=Path, default=PACKET_PATH)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--port", type=int, default=8131)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute:
        summary = execute_generate_smoke(output=args.output_artifact, packet_path=args.packet, run_root=args.run_root, port=args.port)
    else:
        summary = build_plan(args.packet)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
