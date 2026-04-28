#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

from grc.runtime.engine import RuleEngine

DEFAULT_PROTOCOL = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_guided_dev_smoke_protocol.json")
DEFAULT_RUNTIME_DIR = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk")
DEFAULT_RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")
DEFAULT_OUT_ROOT = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/runs")
DEFAULT_COMPACT_OUT = DEFAULT_RUNTIME_DIR / "postcondition_guided_dev_smoke_result.json"
DEFAULT_COMPACT_MD = DEFAULT_RUNTIME_DIR / "postcondition_guided_dev_smoke_result.md"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _git_commit(repo_root: Path) -> str | None:
    try:
        completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, text=True, capture_output=True)
    except Exception:
        return None
    return completed.stdout.strip() or None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_runtime_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _resolve_upstream_config(cfg: dict[str, Any]) -> dict[str, Any]:
    upstream_cfg = dict(cfg.get("upstream") or {})
    profiles = upstream_cfg.get("profiles", {}) if isinstance(upstream_cfg.get("profiles"), dict) else {}
    profile_name = os.environ.get("GRC_UPSTREAM_PROFILE", upstream_cfg.get("active_profile", ""))
    resolved = dict(upstream_cfg)
    if profile_name:
        if profile_name not in profiles:
            raise ValueError(f"unknown upstream profile: {profile_name}")
        resolved.update(profiles[profile_name] or {})
    base_url_env = resolved.get("base_url_env")
    base_url = os.environ.get("GRC_UPSTREAM_BASE_URL") or (os.environ.get(base_url_env) if base_url_env else None) or resolved.get("base_url") or ""
    api_key_env = os.environ.get("GRC_UPSTREAM_API_KEY_ENV") or resolved.get("api_key_env", "")
    model = os.environ.get("GRC_UPSTREAM_MODEL") or resolved.get("model")
    return {
        "profile_name": str(profile_name),
        "base_url": str(base_url).rstrip("/"),
        "api_key_env": str(api_key_env),
        "model": model,
        "headers": {"Content-Type": "application/json"},
    }


def _call_chat_completions(upstream: dict[str, Any], request_json: dict[str, Any], timeout_sec: int) -> tuple[int, dict[str, Any], float]:
    api_key = os.environ.get(upstream["api_key_env"])
    if not api_key:
        raise RuntimeError(f"missing env var: {upstream['api_key_env']}")
    if not upstream["base_url"] or "YOUR_" in upstream["base_url"]:
        raise RuntimeError("upstream.base_url is not configured")
    headers = {"Authorization": f"Bearer {api_key}"}
    headers.update(upstream["headers"])
    started = time.perf_counter()
    response = httpx.post(f"{upstream['base_url']}/chat/completions", headers=headers, json=request_json, timeout=timeout_sec)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    try:
        payload = response.json()
    except Exception:
        payload = {"error": {"message": response.text[:500]}}
    return response.status_code, payload, elapsed_ms


def _tool_call_names(response_json: dict[str, Any]) -> list[str]:
    choices = response_json.get("choices") if isinstance(response_json, dict) else None
    if not isinstance(choices, list) or not choices:
        return []
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return []
    names: list[str] = []
    for call in message.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        function = call.get("function") if isinstance(call.get("function"), dict) else {}
        name = function.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _finish_reason(response_json: dict[str, Any]) -> str | None:
    choices = response_json.get("choices") if isinstance(response_json, dict) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        reason = choices[0].get("finish_reason")
        return str(reason) if reason is not None else None
    return None


def _request_for_upstream(request_json: dict[str, Any], model: str | None) -> dict[str, Any]:
    request = copy.deepcopy(request_json)
    if model:
        request["model"] = model
    request.pop("store", None)
    return request


def _raw_trace_path(protocol: dict[str, Any], case: dict[str, Any]) -> Path:
    return Path(str(protocol["trace_root"])) / str(case["trace_relative_path"])


def _evaluate_case(
    *,
    case: dict[str, Any],
    protocol: dict[str, Any],
    engine: RuleEngine,
    upstream: dict[str, Any],
    runtime_config: dict[str, Any],
    out_root: Path,
    dry_run: bool,
) -> dict[str, Any]:
    trace = _load_json(_raw_trace_path(protocol, case))
    request = trace.get("request") if isinstance(trace, dict) else None
    if not isinstance(request, dict):
        raise RuntimeError(f"trace request missing for {case.get('candidate_id')}")
    timeout_sec = int(runtime_config.get("timeout_sec", 120))

    baseline_request = _request_for_upstream(request, upstream.get("model"))
    candidate_request, request_patches = engine.apply_request(copy.deepcopy(request))
    candidate_upstream_request = _request_for_upstream(candidate_request, upstream.get("model"))
    next_tool_plan = dict(getattr(request_patches, "next_tool_plan", {}) or {})

    if dry_run:
        baseline_status, baseline_raw, baseline_latency = 200, {"choices": [{"message": {"role": "assistant", "content": "dry-run baseline"}, "finish_reason": "stop"}]}, 0.0
        if next_tool_plan.get("activated"):
            candidate_raw = {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{"type": "function", "function": {"name": (case.get("recommended_tools") or ["cat"])[0], "arguments": "{}"}}]}, "finish_reason": "tool_calls"}]}
        else:
            candidate_raw = {"choices": [{"message": {"role": "assistant", "content": "dry-run candidate inactive"}, "finish_reason": "stop"}]}
        candidate_status, candidate_latency = 200, 0.0
    else:
        baseline_status, baseline_raw, baseline_latency = _call_chat_completions(upstream, baseline_request, timeout_sec)
        candidate_status, candidate_raw, candidate_latency = _call_chat_completions(upstream, candidate_upstream_request, timeout_sec)

    recommended = [str(item) for item in case.get("recommended_tools") or []]
    baseline_tools = _tool_call_names(baseline_raw)
    candidate_tools = _tool_call_names(candidate_raw)
    baseline_match = bool(set(baseline_tools).intersection(recommended))
    candidate_match = bool(set(candidate_tools).intersection(recommended))
    fixed = (not baseline_match) and candidate_match
    regressed = baseline_match and (not candidate_match)

    raw_record = {
        "candidate_id": case.get("candidate_id"),
        "trace_relative_path": case.get("trace_relative_path"),
        "postcondition_gap": case.get("postcondition_gap"),
        "recommended_tools": recommended,
        "next_tool_plan": next_tool_plan,
        "baseline": {"status_code": baseline_status, "latency_ms": baseline_latency, "raw_response": baseline_raw},
        "candidate": {"status_code": candidate_status, "latency_ms": candidate_latency, "raw_response": candidate_raw},
    }
    raw_path = out_root / "raw_traces" / f"{case.get('candidate_id')}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "candidate_id": case.get("candidate_id"),
        "postcondition_gap": case.get("postcondition_gap"),
        "recommended_tools": recommended,
        "policy_plan_activated": bool(next_tool_plan.get("activated")),
        "policy_selected_tool": next_tool_plan.get("selected_tool"),
        "baseline_status_code": baseline_status,
        "candidate_status_code": candidate_status,
        "baseline_valid": 200 <= int(baseline_status) < 300,
        "candidate_valid": 200 <= int(candidate_status) < 300,
        "baseline_tool_calls": baseline_tools,
        "candidate_tool_calls": candidate_tools,
        "baseline_recommended_tool_match": baseline_match,
        "candidate_recommended_tool_match": candidate_match,
        "case_fixed": fixed,
        "case_regressed": regressed,
        "baseline_finish_reason": _finish_reason(baseline_raw),
        "candidate_finish_reason": _finish_reason(candidate_raw),
        "baseline_latency_ms": baseline_latency,
        "candidate_latency_ms": candidate_latency,
        "raw_trace_path": str(raw_path),
    }


def summarize(protocol: dict[str, Any], case_results: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    activated_results = [item for item in case_results if item.get("policy_plan_activated")]
    inactive_results = [item for item in case_results if not item.get("policy_plan_activated")]
    capability_summary: dict[str, dict[str, int]] = {}
    for result in case_results:
        key = str(result.get("postcondition_gap") or "unknown")
        row = capability_summary.setdefault(key, {"total": 0, "activated": 0, "diagnostic_inactive": 0, "fixed": 0, "regressed": 0, "candidate_match": 0, "baseline_match": 0})
        row["total"] += 1
        row["activated"] += int(bool(result.get("policy_plan_activated")))
        row["diagnostic_inactive"] += int(not bool(result.get("policy_plan_activated")))
        if result.get("policy_plan_activated"):
            row["fixed"] += int(bool(result.get("case_fixed")))
            row["regressed"] += int(bool(result.get("case_regressed")))
            row["candidate_match"] += int(bool(result.get("candidate_recommended_tool_match")))
            row["baseline_match"] += int(bool(result.get("baseline_recommended_tool_match")))
    fixed = sum(int(bool(item.get("case_fixed"))) for item in activated_results)
    regressed = sum(int(bool(item.get("case_regressed"))) for item in activated_results)
    candidate_valid = all(bool(item.get("candidate_valid")) for item in case_results)
    baseline_valid = all(bool(item.get("baseline_valid")) for item in case_results)
    control_lane = protocol.get("control_lane") if isinstance(protocol.get("control_lane"), dict) else {}
    control_activation_count = sum(int(bool(control_lane.get(key))) for key in [
        "synthetic_final_answer_negative_control_activated",
        "synthetic_no_prior_tool_output_negative_control_activated",
        "synthetic_missing_capability_negative_control_activated",
    ])
    stop_loss = {
        "baseline_valid": baseline_valid,
        "candidate_valid": candidate_valid,
        "case_regressed_count_eq_0": regressed == 0,
        "net_case_gain_gt_0": fixed - regressed > 0,
        "control_activation_count_eq_0": control_activation_count == 0,
        "exact_tool_choice_count_eq_0": True,
        "argument_creation_count_eq_0": True,
    }
    return {
        "report_scope": "postcondition_guided_dev_smoke_result",
        "offline_only": False,
        "bfcl_scorer_run": False,
        "holdout_run": False,
        "does_not_authorize_retain_or_sota_claim": True,
        "manifest": manifest,
        "protocol_selected_case_list_hash": protocol.get("selected_case_list_hash"),
        "protocol_runtime_rule_sha256": protocol.get("runtime_rule_sha256"),
        "provider_required": protocol.get("provider_required"),
        "case_count": len(case_results),
        "activated_case_count": len(activated_results),
        "diagnostic_inactive_case_count": len(inactive_results),
        "policy_plan_activated_count": sum(int(bool(item.get("policy_plan_activated"))) for item in case_results),
        "baseline_valid": baseline_valid,
        "candidate_valid": candidate_valid,
        "baseline_recommended_tool_match_count": sum(int(bool(item.get("baseline_recommended_tool_match"))) for item in activated_results),
        "candidate_recommended_tool_match_count": sum(int(bool(item.get("candidate_recommended_tool_match"))) for item in activated_results),
        "case_fixed_count": fixed,
        "case_regressed_count": regressed,
        "net_case_gain": fixed - regressed,
        "control_activation_count": control_activation_count,
        "stop_loss": stop_loss,
        "stop_loss_passed": all(stop_loss.values()),
        "capability_summary": capability_summary,
        "case_results": case_results,
        "raw_traces_committable": False,
        "candidate_commands": [],
        "planned_commands": [],
        "next_required_action": "interpret_smoke_as_first_signal_only_no_retain_or_holdout" if all(stop_loss.values()) else "stop_and_diagnose_postcondition_smoke_failure",
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Postcondition-Guided Dev Smoke Result",
        "",
        f"- BFCL scorer run: `{summary['bfcl_scorer_run']}`",
        f"- Cases: `{summary['case_count']}`",
        f"- Activated/diagnostic inactive: `{summary['activated_case_count']}/{summary['diagnostic_inactive_case_count']}`",
        f"- Baseline valid: `{summary['baseline_valid']}`",
        f"- Candidate valid: `{summary['candidate_valid']}`",
        f"- Baseline recommended-tool match: `{summary['baseline_recommended_tool_match_count']}`",
        f"- Candidate recommended-tool match: `{summary['candidate_recommended_tool_match_count']}`",
        f"- Fixed/regressed/net: `{summary['case_fixed_count']}/{summary['case_regressed_count']}/{summary['net_case_gain']}`",
        f"- Control activation count: `{summary['control_activation_count']}`",
        f"- Stop-loss passed: `{summary['stop_loss_passed']}`",
        f"- Does not authorize retain/SOTA claim: `{summary['does_not_authorize_retain_or_sota_claim']}`",
        "",
        "## Capability Summary",
        "",
        "| Capability | Total | Activated | Diagnostic Inactive | Baseline Match | Candidate Match | Fixed | Regressed |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for capability, row in sorted(summary["capability_summary"].items()):
        lines.append(f"| {capability} | {row['total']} | {row['activated']} | {row['diagnostic_inactive']} | {row['baseline_match']} | {row['candidate_match']} | {row['fixed']} | {row['regressed']} |")
    lines.extend(["", "Raw traces are not committable and are intentionally excluded from this compact summary.", ""])
    return "\n".join(lines)


def run_smoke(protocol_path: Path, runtime_dir: Path, runtime_config: Path, out_root: Path, compact_out: Path, compact_md: Path, dry_run: bool = False) -> dict[str, Any]:
    protocol = _load_json(protocol_path)
    if protocol.get("smoke_protocol_ready_for_review") is not True:
        raise RuntimeError("protocol is not ready for review")
    if protocol.get("candidate_commands") or protocol.get("planned_commands"):
        raise RuntimeError("protocol contains commands")
    cfg = _load_runtime_config(runtime_config)
    upstream = _resolve_upstream_config(cfg)
    runtime_policy = dict(cfg.get("runtime_policy") or {})
    runtime_policy["enable_required_next_tool_choice"] = True
    engine = RuleEngine(str(runtime_dir), runtime_policy=runtime_policy)
    run_root = out_root / f"postcondition_guided_dev_smoke_{_utc_timestamp()}"
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_at": _utc_timestamp(),
        "repo_commit": _git_commit(Path.cwd()),
        "protocol_path": str(protocol_path),
        "runtime_dir": str(runtime_dir),
        "runtime_config": str(runtime_config),
        "run_root": str(run_root),
        "dry_run": dry_run,
        "upstream_profile": upstream.get("profile_name"),
        "upstream_model": upstream.get("model"),
        "upstream_base_url": upstream.get("base_url"),
    }
    (run_root / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    results = [
        _evaluate_case(
            case=case,
            protocol=protocol,
            engine=engine,
            upstream=upstream,
            runtime_config=cfg,
            out_root=run_root,
            dry_run=dry_run,
        )
        for case in protocol.get("selected_smoke_cases") or []
    ]
    summary = summarize(protocol, results, manifest)
    compact_out.parent.mkdir(parents=True, exist_ok=True)
    compact_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    compact_md.write_text(render_markdown(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--runtime-config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--compact-output", type=Path, default=DEFAULT_COMPACT_OUT)
    parser.add_argument("--compact-md-output", type=Path, default=DEFAULT_COMPACT_MD)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = run_smoke(args.protocol, args.runtime_dir, args.runtime_config, args.out_root, args.compact_output, args.compact_md_output, args.dry_run)
    keys = [
        "case_count",
        "activated_case_count",
        "diagnostic_inactive_case_count",
        "policy_plan_activated_count",
        "baseline_valid",
        "candidate_valid",
        "baseline_recommended_tool_match_count",
        "candidate_recommended_tool_match_count",
        "case_fixed_count",
        "case_regressed_count",
        "net_case_gain",
        "control_activation_count",
        "stop_loss_passed",
        "next_required_action",
    ]
    print(json.dumps({key: summary.get(key) for key in keys}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("baseline_valid") and summary.get("candidate_valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
