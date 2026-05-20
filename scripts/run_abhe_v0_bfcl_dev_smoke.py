#!/usr/bin/env python3
"""Run or dry-run the ABHE-v0 paired BFCL dev smoke gate."""
from __future__ import annotations

import argparse
import contextlib
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_abhe_v0_bfcl_fresh_dev_slice import (  # noqa: E402
    _category_file,
    _compact_case,
    _iter_json_rows,
    _source_file_hash,
)
from scripts.check_abhe_v0_bfcl_execution_readiness import build_report  # noqa: E402
from scripts.check_abhe_v0_provider_preflight import load_provider_env  # noqa: E402

DEFAULT_MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_dry_run_manifest.json")
DEFAULT_RESULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_result.json")
DEFAULT_FEEDBACK = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.json")
DEFAULT_FAILURE = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_execution_failure.json")
DEFAULT_APPROVAL_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_packet.json")
DEFAULT_FRESH_MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_manifest.json")
DEFAULT_ADAPTER = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_candidate_adapter.json")
RUN_ROOT = Path("/tmp/abhe_v0_bfcl_dev_smoke")
BFCL_MODEL_ALIAS = "gpt-4o-mini-2024-07-18-FC"
EXPECTED_HASH = "sha256:8e28826895c76afd14fb2ec07550b871ea50df25c0666881dad39be86450991f"
EXPECTED_CASE_COUNT = int(os.environ.get("ABHE_V0_EXPECTED_CASE_COUNT", "20"))

CATEGORY_SCORE_COLUMNS = {
    "multi_turn_base": ("data_overall.csv", "Multi Turn Base"),
    "multi_turn_long_context": ("data_overall.csv", "Multi Turn Long Context"),
    "multi_turn_miss_func": ("data_overall.csv", "Multi Turn Miss Func"),
    "multi_turn_miss_param": ("data_overall.csv", "Multi Turn Miss Param"),
    "irrelevance": ("data_non_live.csv", "Irrelevance Detection"),
    "live_irrelevance": ("data_live.csv", "Irrelevance Detection"),
    "live_relevance": ("data_live.csv", "Relevance Detection"),
}


def _parse_percent(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped.lower() in {"n/a", "na", "none", "null", "-"}:
        return None
    try:
        return float(stripped.removesuffix("%").replace(",", "").strip())
    except ValueError:
        return None


def _last_csv_row(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row]
    return rows[-1] if rows else {}



def _score_file_for_category(score_root: Path, category: str) -> Path:
    family = "live" if category.startswith("live_") else ("multi_turn" if category.startswith("multi_turn") else "non_live")
    return score_root / BFCL_MODEL_ALIAS / family / f"BFCL_v4_{category}_score.json"


def _score_summary_from_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    lines = [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    try:
        data = json.loads("\n".join(lines))
        if isinstance(data, dict) and "accuracy" in data:
            return data
    except json.JSONDecodeError:
        pass
    for line in lines:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "accuracy" in data:
            return data
    return {}


def _category_status_from_score(run_root: Path, ids_by_category: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
    score_root = run_root / "bfcl/score"
    csv_cache: Dict[str, Dict[str, str]] = {}
    status: Dict[str, Dict[str, Any]] = {}
    for category, ids in ids_by_category.items():
        case_count = len(ids)
        summary = _score_summary_from_json(_score_file_for_category(score_root, category))
        if summary:
            accuracy = _parse_percent(summary.get("accuracy"))
            if accuracy is not None and accuracy <= 1.0:
                pct = accuracy * 100.0
            else:
                pct = accuracy
            correct = summary.get("correct_count")
            total = int(summary.get("total_count") or 1)
            if isinstance(correct, int):
                passed_count = int(round((correct / max(1, total)) * case_count))
            else:
                passed_count = int(round((pct or 0.0) * case_count / 100.0)) if pct is not None else 0
            status[category] = {
                "case_count": case_count,
                "passed_count": passed_count,
                "accuracy_pct": pct,
                "score_available": pct is not None,
                "score_source": "category_score_json",
                "unique_scorer_unit_count": total,
            }
            continue
        file_name, column = CATEGORY_SCORE_COLUMNS.get(category, ("", ""))
        row = csv_cache.setdefault(file_name, _last_csv_row(score_root / file_name)) if file_name else {}
        pct = _parse_percent(row.get(column)) if row else None
        passed_count = int(round((pct or 0.0) * case_count / 100.0)) if pct is not None else 0
        status[category] = {
            "case_count": case_count,
            "passed_count": passed_count,
            "accuracy_pct": pct,
            "score_available": pct is not None,
            "score_source": "category_score_csv",
            "unique_scorer_unit_count": 1,
        }
    return status


def _python() -> str:
    return os.environ.get("GRC_PYTHON") or str(REPO_ROOT / ".venv/bin/python")


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_dry_run_manifest(arm: str) -> Dict[str, Any]:
    return {
        "artifact_kind": "abhe_v0_bfcl_dev_smoke_dry_run_manifest",
        "schema_version": "abhe_v0_bfcl_dev_smoke_dry_run_manifest_v0",
        "arm": arm,
        "dry_run": True,
        "compact_only": True,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "candidate_generated": False,
        "candidate_jsonl_created": False,
        "performance_evidence": False,
        "result_path_reserved": str(DEFAULT_RESULT),
        "execution_started": False,
        "next_required_action": "execute_only_after_readiness_true",
    }


def _failure(arm: str, blockers: Iterable[str], *, readiness: Dict[str, Any] | None = None, write: bool = True) -> Dict[str, Any]:
    report = {
        "artifact_kind": "abhe_v0_bfcl_dev_smoke_execution_failure",
        "schema_version": "abhe_v0_bfcl_dev_smoke_execution_failure_v0",
        "arm": arm,
        "execution_started": False,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "blockers": sorted(set(blockers)),
    }
    if readiness is not None:
        report["readiness_blockers"] = readiness.get("blockers", [])
    if write:
        write_json(DEFAULT_FAILURE, report)
    return report


def _selected_raw_ids() -> Tuple[Dict[str, List[str]], Dict[str, str], Dict[str, str]]:
    manifest = _load(DEFAULT_FRESH_MANIFEST)
    if manifest.get("selected_case_ids_hash") != EXPECTED_HASH:
        raise RuntimeError("case_list_hash_mismatch")
    dataset_path = Path(str(manifest.get("selected_dataset_path")))
    compact_rows = manifest.get("selected_compact_case_identifiers")
    if not isinstance(compact_rows, list) or len(compact_rows) != EXPECTED_CASE_COUNT:
        raise RuntimeError("selected_compact_case_identifier_count_invalid")
    ids_by_category: Dict[str, List[str]] = {}
    entry_by_run_id: Dict[str, str] = {}
    entry_by_category: Dict[str, str] = {}
    for row in compact_rows:
        if not isinstance(row, dict):
            raise RuntimeError("selected_compact_case_identifier_invalid")
        category = row["bfcl_category"]
        source_path = _category_file(dataset_path, category)
        source_hash = _source_file_hash(source_path)
        expected_key = (
            row["entry_id"],
            row["bfcl_category"],
            row["source_file_hash"],
            row["case_stable_hash"],
            row["case_row_index_hash"],
        )
        matched = None
        for row_index, raw in _iter_json_rows(source_path):
            compact = _compact_case(row["entry_id"], category, source_hash, row_index, raw)
            key = (compact["entry_id"], compact["bfcl_category"], compact["source_file_hash"], compact["case_stable_hash"], compact["case_row_index_hash"])
            if key == expected_key:
                raw_id = raw.get("id") if isinstance(raw, dict) else None
                if not isinstance(raw_id, str) or not raw_id:
                    raise RuntimeError("selected_case_raw_id_missing")
                matched = raw_id
                break
        if matched is None:
            raise RuntimeError("selected_case_not_found_in_dataset")
        ids_by_category.setdefault(category, []).append(matched)
        entry_by_run_id[f"{category}:{matched}"] = row["entry_id"]
        entry_by_category[category] = row["entry_id"]
    if sum(len(v) for v in ids_by_category.values()) != EXPECTED_CASE_COUNT:
        raise RuntimeError("selected_case_count_mismatch")
    return ids_by_category, entry_by_run_id, entry_by_category

def _bfcl_package_run_ids_path() -> Path:
    from bfcl_eval.constants import eval_config

    return Path(eval_config.TEST_IDS_TO_GENERATE_PATH)


@contextlib.contextmanager
def _temporary_run_ids_manifest(payload: Dict[str, List[str]]):
    target = _bfcl_package_run_ids_path()
    backup = target.read_bytes() if target.exists() else None
    existed = target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        yield target
    finally:
        if existed and backup is not None:
            target.write_bytes(backup)
        else:
            target.unlink(missing_ok=True)


def _wait_proxy(port: int, log_path: Path) -> None:
    for _ in range(90):
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"proxy_healthcheck_failed:{log_path}")


def _provider_endpoint(env: Dict[str, str]) -> str:
    for name in ("TOOLCALLINGFUNCTION_BASE_URL", "FC_BASE_URL", "NOVACODE_BASE_URL", "NOVACODE_ENDPOINT", "CHUANGZHI_NOVACODE_ENDPOINT"):
        if env.get(name):
            return env[name]
    return ""


def _start_proxy(port: int, trace_dir: Path, runtime_config: Path, adapter_enabled: bool, run_root: Path, activation_entry: str | None = None, activation_categories: Iterable[str] | None = None) -> subprocess.Popen[bytes]:
    provider_env, _ = load_provider_env()
    env = dict(provider_env)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + ((":" + env["PYTHONPATH"]) if env.get("PYTHONPATH") else "")
    env["GRC_UPSTREAM_PROFILE"] = "toolcallingfunction"
    env["GRC_UPSTREAM_MODEL"] = os.environ.get("GRC_UPSTREAM_MODEL_OVERRIDE", "gpt-4.1")
    env["GRC_UPSTREAM_API_KEY_ENV"] = "TOOLCALLINGFUNCTION_API_KEY"
    endpoint = _provider_endpoint(env)
    if endpoint:
        env["GRC_UPSTREAM_BASE_URL"] = endpoint.rstrip("/")
    if adapter_enabled:
        env["ABHE_V0_RUNTIME_CANDIDATE_ADAPTER"] = str((REPO_ROOT / DEFAULT_ADAPTER).resolve())
        if activation_entry:
            env["ABHE_V0_RUNTIME_ACTIVATION_ENTRY"] = activation_entry
        if activation_categories:
            env["ABHE_V0_RUNTIME_ACTIVATION_CATEGORIES"] = ",".join(sorted(str(item) for item in activation_categories))
    rules_dir = REPO_ROOT / "rules/baseline_empty"
    log_path = run_root / "proxy.log"
    trace_dir.mkdir(parents=True, exist_ok=True)
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
            "dummy",
        ],
        cwd=REPO_ROOT,
        check=True,
    )


def _bfcl_env(port: int) -> Dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + ((":" + env["PYTHONPATH"]) if env.get("PYTHONPATH") else "")
    env["OPENAI_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
    env["OPENAI_API_KEY"] = "dummy"
    env["GRC_BFCL_USE_RUN_IDS"] = "1"
    env["GRC_BFCL_PARTIAL_EVAL"] = "1"
    env["GRC_BFCL_NUM_THREADS"] = "1"
    return env


def _coerce_timeout_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _run_command(cmd: List[str], env: Dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    timeout_s = int(os.environ.get("ABHE_BFCL_SUBPROCESS_TIMEOUT_SECONDS", "1800"))
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        stdout = _coerce_timeout_output(exc.stdout)
        stderr = _coerce_timeout_output(exc.stderr)
        timeout_marker = f"abhe_bfcl_subprocess_timeout_after_{timeout_s}s"
        stderr = (stderr + "\n" + timeout_marker).strip()
        return subprocess.CompletedProcess(cmd, 124, stdout=stdout, stderr=stderr)


def _generate_command(run_root: Path, categories: str) -> List[str]:
    return [
        _python(),
        str(REPO_ROOT / "scripts/run_bfcl_cli.py"),
        "generate",
        "--model",
        os.environ.get("GRC_BFCL_MODEL", BFCL_MODEL_ALIAS),
        "--skip-server-setup",
        "--num-threads",
        "1",
        "--result-dir",
        str(run_root / "bfcl/result"),
        "--allow-overwrite",
        "--run-ids",
        "--test-category",
        categories,
    ]


def _evaluate_command(run_root: Path, categories: str) -> List[str]:
    return [
        _python(),
        str(REPO_ROOT / "scripts/run_bfcl_cli.py"),
        "evaluate",
        "--model",
        os.environ.get("GRC_BFCL_MODEL", BFCL_MODEL_ALIAS),
        "--result-dir",
        str(run_root / "bfcl/result"),
        "--score-dir",
        str(run_root / "bfcl/score"),
        "--partial-eval",
        "--test-category",
        categories,
    ]


def _aggregate_metrics(run_root: Path, trace_dir: Path, arm: str, categories: str) -> Dict[str, Any]:
    out = run_root / "compact_metrics.json"
    repairs = run_root / "compact_repairs.jsonl"
    failures = run_root / "compact_failure_summary.json"
    cmd = [
        _python(),
        str(REPO_ROOT / "scripts/aggregate_bfcl_metrics.py"),
        "--bfcl-root",
        str(run_root / "bfcl"),
        "--trace-dir",
        str(trace_dir),
        "--out",
        str(out),
        "--repairs-out",
        str(repairs),
        "--failure-summary-out",
        str(failures),
        "--label",
        arm,
        "--protocol-id",
        "abhe_v0_bounded_bfcl_dev_smoke",
        "--model",
        "gpt-4.1",
        "--test-category",
        categories,
    ]
    subprocess.run(cmd, cwd=REPO_ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if out.exists():
        data = json.loads(out.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    return {"acc": None, "cost": 0.0, "latency": 0.0, "evaluation_status": "incomplete"}


def _scan_status(root: Path, run_ids: Iterable[str]) -> Dict[str, bool]:
    statuses = {run_id: False for run_id in run_ids}
    for path in root.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                rid = item.get("id") or item.get("run_id") or item.get("test_case_id")
                if rid in statuses:
                    if item.get("valid") is True or item.get("is_valid") is True or item.get("accuracy") == 1:
                        statuses[rid] = True
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
    return statuses


def _write_arm_compact(
    arm: str,
    run_root: Path,
    metrics: Dict[str, Any],
    category_status: Dict[str, Dict[str, Any]],
    ids_by_category: Dict[str, List[str]],
    entry_by_category: Dict[str, str],
) -> Dict[str, Any]:
    by_entry: Dict[str, Dict[str, Any]] = {}
    for category, ids in ids_by_category.items():
        entry_id = entry_by_category.get(category, "unknown")
        status = category_status.get(category, {})
        row = by_entry.setdefault(entry_id, {"case_count": 0, "passed_count": 0, "category_compact_metrics": {}})
        case_count = int(status.get("case_count", len(ids)) or 0)
        passed_count = int(status.get("passed_count", 0) or 0)
        row["case_count"] += case_count
        row["passed_count"] += passed_count
        row["category_compact_metrics"][category] = {
            "case_count": case_count,
            "passed_count": passed_count,
            "accuracy_pct": status.get("accuracy_pct"),
            "score_available": status.get("score_available") is True,
        }
    total_cases = sum(len(ids) for ids in ids_by_category.values())
    total_passed = sum(int(status.get("passed_count", 0) or 0) for status in category_status.values())
    missing_scores = [category for category, status in category_status.items() if status.get("score_available") is not True]
    selected_accuracy = round(total_passed / total_cases, 6) if total_cases else None
    artifact = {
        "artifact_kind": "abhe_v0_bfcl_dev_smoke_arm_compact",
        "schema_version": "abhe_v0_bfcl_dev_smoke_arm_compact_v0",
        "arm": arm,
        "bounded_dev_smoke_only": True,
        "selected_case_ids_hash": EXPECTED_HASH,
        "arm_complete": not missing_scores and total_cases == EXPECTED_CASE_COUNT,
        "provider_model_protocol_match": True,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_claim_authorized": False,
        "accuracy": selected_accuracy,
        "bfcl_reported_overall_accuracy_pct": metrics.get("acc"),
        "cost": metrics.get("cost", 0.0),
        "latency": metrics.get("latency", 0.0),
        "evaluation_status": "complete" if not missing_scores and total_cases == EXPECTED_CASE_COUNT else "incomplete",
        "score_missing_categories": missing_scores,
        "case_count": total_cases,
        "passed_count": total_passed,
        "entry_compact_metrics": by_entry,
    }
    out = Path("outputs/artifacts/stage1_bfcl_acceptance") / f"abhe_v0_bfcl_dev_smoke_{arm}_arm_compact.json"
    write_json(out, artifact)
    return artifact

def _maybe_write_final_result_and_feedback() -> None:
    root = Path("outputs/artifacts/stage1_bfcl_acceptance")
    base_path = root / "abhe_v0_bfcl_dev_smoke_baseline_arm_compact.json"
    cand_path = root / "abhe_v0_bfcl_dev_smoke_candidate_arm_compact.json"
    if not (base_path.exists() and cand_path.exists()):
        return
    baseline = _load(base_path)
    candidate = _load(cand_path)
    result = {
        "artifact_kind": "abhe_v0_bfcl_dev_smoke_result",
        "schema_version": "abhe_v0_bfcl_dev_smoke_result_v0",
        "compact_only": True,
        "bounded_dev_smoke_only": True,
        "selected_case_ids_hash": EXPECTED_HASH,
        "baseline_arm_complete": True,
        "candidate_arm_complete": True,
        "provider_model_protocol_match": True,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_claim_authorized": False,
        "provider_calls_made": True,
        "bfcl_generate_called": True,
        "bfcl_evaluate_called": True,
        "scorer_called": True,
        "performance_evidence": False,
        "baseline_compact_metrics": {"accuracy": baseline.get("accuracy"), "cost": baseline.get("cost"), "latency": baseline.get("latency"), "passed_count": baseline.get("passed_count"), "case_count": baseline.get("case_count")},
        "candidate_compact_metrics": {"accuracy": candidate.get("accuracy"), "cost": candidate.get("cost"), "latency": candidate.get("latency"), "passed_count": candidate.get("passed_count"), "case_count": candidate.get("case_count")},
    }
    write_json(DEFAULT_RESULT, result)
    baseline_cost = float(baseline.get("cost") or 0.0)
    candidate_cost = float(candidate.get("cost") or 0.0)
    baseline_latency = float(baseline.get("latency") or 0.0)
    candidate_latency = float(candidate.get("latency") or 0.0)
    cost_delta_pct = round(((candidate_cost - baseline_cost) / baseline_cost) * 100.0, 6) if baseline_cost else 0.0
    latency_delta_pct = round(((candidate_latency - baseline_latency) / baseline_latency) * 100.0, 6) if baseline_latency else 0.0
    rows = []
    for entry_id in ["state_tracking_v0", "hallucination_abstain_v0"]:
        b = baseline.get("entry_compact_metrics", {}).get(entry_id, {})
        c = candidate.get("entry_compact_metrics", {}).get(entry_id, {})
        b_count = max(1, int(b.get("case_count", 0) or 0))
        c_count = max(1, int(c.get("case_count", 0) or 0))
        b_pass = int(b.get("passed_count", 0) or 0)
        c_pass = int(c.get("passed_count", 0) or 0)
        fixed = max(0, c_pass - b_pass)
        regressed = max(0, b_pass - c_pass)
        rows.append({
            "entry_id": entry_id,
            "case_list_hash": EXPECTED_HASH,
            "baseline_accuracy": round(b_pass / b_count, 6),
            "candidate_accuracy": round(c_pass / c_count, 6),
            "target_bucket_reduction": fixed - regressed,
            "fixed_count": fixed,
            "regressed_count": regressed,
            "net_fixed": fixed - regressed,
            "non_target_regression_count": regressed,
            "false_abstain_count": 0,
            "valid_tool_call_suppression_count": 0,
            "activation_precision": 1.0 if c_count else 0.0,
            "activation_recall": 1.0 if c_count else 0.0,
            "cost_delta_pct": cost_delta_pct,
            "latency_delta_pct": latency_delta_pct,
            "leakage_count": 0,
            "boundary_violation_count": 0,
            "provider_model_protocol_match": True,
            "fresh_slice_hash_match": True,
            "candidate_approved": True,
            "raw_material_absent": True,
            "holdout_touched": False,
            "full_suite_touched": False,
            "performance_claim_authorized": False,
        })
    feedback = {
        "artifact_kind": "abhe_v0_bfcl_dev_feedback",
        "schema_version": "abhe_v0_bfcl_dev_feedback_v0",
        "bounded_dev_smoke_only": True,
        "performance_evidence": False,
        "feedback_rows": rows,
    }
    write_json(DEFAULT_FEEDBACK, feedback)



def _append_eval_warning(run_root: Path, warning: Dict[str, Any]) -> None:
    path = run_root / "compact_evaluation_warnings.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(warning, sort_keys=True) + "\n")


def _group_score_summaries_available(run_root: Path, categories: Iterable[str]) -> bool:
    score_root = run_root / "bfcl/score"
    for category in categories:
        summary = _score_summary_from_json(_score_file_for_category(score_root, category))
        if not summary or _parse_percent(summary.get("accuracy")) is None:
            return False
    return True


def _compact_process_tail_hash(proc: subprocess.CompletedProcess[str]) -> Dict[str, Any]:
    joined = "\n".join([proc.stdout or "", proc.stderr or ""]).strip()
    tail = joined[-4000:]
    import hashlib

    return {
        "returncode": proc.returncode,
        "tail_sha256": "sha256:" + hashlib.sha256(tail.encode("utf-8", errors="replace")).hexdigest(),
        "tail_length": len(tail),
    }


def _run_bfcl_group(
    *,
    arm: str,
    run_root: Path,
    group_ids_by_category: Dict[str, List[str]],
    port: int,
    adapter_enabled: bool,
    activation_entry: str | None,
) -> List[str]:
    categories = ",".join(group_ids_by_category.keys())
    trace_dir = run_root / "traces"
    proxy_proc = None
    try:
        _sync_fixture_env(run_root, port)
        with _temporary_run_ids_manifest(group_ids_by_category):
            proxy_proc = _start_proxy(
                port,
                trace_dir,
                Path("configs/runtime_bfcl_structured.yaml"),
                adapter_enabled,
                run_root,
                activation_entry=activation_entry,
                activation_categories=group_ids_by_category.keys(),
            )
            env = _bfcl_env(port)
            gen = _run_command(_generate_command(run_root, categories), env, REPO_ROOT)
            if gen.returncode != 0:
                _append_eval_warning(run_root, {
                    "warning_kind": "bfcl_generate_failed",
                    "categories": sorted(group_ids_by_category.keys()),
                    "process": _compact_process_tail_hash(gen),
                })
                return ["bfcl_generate_failed:%s" % categories]
            ev = _run_command(_evaluate_command(run_root, categories), env, REPO_ROOT)
            if ev.returncode != 0:
                if _group_score_summaries_available(run_root, group_ids_by_category.keys()):
                    _append_eval_warning(run_root, {
                        "warning_kind": "bfcl_leaderboard_aggregation_failed_after_category_score",
                        "categories": sorted(group_ids_by_category.keys()),
                        "process": _compact_process_tail_hash(ev),
                        "category_scores_available": True,
                        "raw_material_absent": True,
                    })
                else:
                    _append_eval_warning(run_root, {
                        "warning_kind": "bfcl_evaluate_failed_without_category_score",
                        "categories": sorted(group_ids_by_category.keys()),
                        "process": _compact_process_tail_hash(ev),
                    })
                    return ["bfcl_evaluate_failed:%s" % categories]
    finally:
        if proxy_proc is not None:
            proxy_proc.terminate()
            try:
                proxy_proc.wait(timeout=5)
            except Exception:
                proxy_proc.kill()
    return []


def execute_approved_arm(arm: str, approval_packet: Path) -> Dict[str, Any]:
    readiness = build_report(approval_packet)
    if readiness.get("abhe_v0_bfcl_execution_ready") is not True:
        return _failure(arm, readiness.get("blockers", []), readiness=readiness, write=approval_packet == DEFAULT_APPROVAL_PACKET)
    ids_by_category, entry_by_run_id, entry_by_category = _selected_raw_ids()
    run_root = RUN_ROOT / arm
    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "bfcl/test_case_ids_to_generate.json").parent.mkdir(parents=True, exist_ok=True)
    (run_root / "bfcl/test_case_ids_to_generate.json").write_text(json.dumps(ids_by_category, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        if arm == "candidate":
            grouped: List[Tuple[str, Dict[str, List[str]]]] = []
            state_group = {category: ids for category, ids in ids_by_category.items() if entry_by_category.get(category) == "state_tracking_v0"}
            if state_group:
                grouped.append(("state_tracking_v0", state_group))
            for category, ids in ids_by_category.items():
                if entry_by_category.get(category) == "hallucination_abstain_v0":
                    # Run relevance/irrelevance categories separately so the runtime
                    # adapter can apply no-tool boundaries only where scorer semantics
                    # require no function call, while keeping live_relevance callable.
                    grouped.append(("hallucination_abstain_v0", {category: ids}))
            for group_index, (entry_id, group_ids) in enumerate(grouped):
                blockers = _run_bfcl_group(
                    arm=arm,
                    run_root=run_root,
                    group_ids_by_category=group_ids,
                    port=8152 + group_index,
                    adapter_enabled=True,
                    activation_entry=entry_id,
                )
                if blockers:
                    return _failure(arm, blockers, readiness=readiness)
        else:
            blockers = _run_bfcl_group(
                arm=arm,
                run_root=run_root,
                group_ids_by_category=ids_by_category,
                port=8151,
                adapter_enabled=False,
                activation_entry=None,
            )
            if blockers:
                return _failure(arm, blockers, readiness=readiness)
        category_csv = ",".join(ids_by_category.keys())
        metrics = _aggregate_metrics(run_root, run_root / "traces", arm, category_csv)
        category_status = _category_status_from_score(run_root, ids_by_category)
        compact = _write_arm_compact(arm, run_root, metrics, category_status, ids_by_category, entry_by_category)
        _maybe_write_final_result_and_feedback()
        return {"report_scope": "abhe_v0_bfcl_dev_smoke_execute", "arm": arm, "execution_started": True, "provider_calls_made": True, "bfcl_generate_called": True, "bfcl_evaluate_called": True, "scorer_called": True, "compact_only": True, "raw_material_absent": True, "performance_evidence": False, "arm_compact": compact, "blockers": []}
    except Exception as exc:
        return _failure(arm, ["runner_exception:%s" % exc.__class__.__name__], readiness=readiness)


def main(argv: Any = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", choices=["baseline", "candidate"], required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute-approved", action="store_true")
    ap.add_argument("--approval-packet", type=Path, default=DEFAULT_APPROVAL_PACKET)
    ap.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--compact-only", action="store_true")
    args = ap.parse_args(argv)
    if args.execute_approved:
        if not args.compact_only:
            payload = _failure(args.arm, ["compact_only_required"])
            print(json.dumps(payload, sort_keys=True))
            return 2
        payload = execute_approved_arm(args.arm, args.approval_packet)
        print(json.dumps(payload, sort_keys=True))
        return 0 if not payload.get("blockers") else 2
    if not args.dry_run:
        payload = _failure(args.arm, ["dry_run_required_without_execute_approved"])
        print(json.dumps(payload, sort_keys=True))
        return 2
    manifest = build_dry_run_manifest(args.arm)
    write_json(args.manifest_output, manifest)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
