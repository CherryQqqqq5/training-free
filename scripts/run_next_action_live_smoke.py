from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

from grc.runtime.engine import RuleEngine
from grc.types import Rule
from grc.utils.tool_schema import tool_map_from_tools_payload
from scripts.build_next_action_smoke_report import _compile_rules_from_case, load_cases


ACCEPTANCE_THRESHOLDS = {
    "policy_plan_activated_count": 15,
    "next_tool_emitted_count": 8,
    "recommended_tool_match_count": 8,
    "arg_binding_match_count": 6,
    "stop_allowed_false_positive_count": 0,
}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _git_commit(repo_root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            text=True,
            capture_output=True,
        )
    except Exception:
        return None
    return completed.stdout.strip() or None


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
    base_url = (
        os.environ.get("GRC_UPSTREAM_BASE_URL")
        or (os.environ.get(base_url_env) if base_url_env else None)
        or resolved.get("base_url")
        or ""
    )
    api_key_env = os.environ.get("GRC_UPSTREAM_API_KEY_ENV") or resolved.get("api_key_env", "")
    model = os.environ.get("GRC_UPSTREAM_MODEL") or resolved.get("model")

    headers = {"Content-Type": "application/json"}
    http_referer_env = resolved.get("http_referer_env")
    title_env = resolved.get("title_env")
    http_referer = os.environ.get(http_referer_env, "") if http_referer_env else ""
    title = os.environ.get(title_env, "") if title_env else ""
    if http_referer:
        headers["HTTP-Referer"] = http_referer
    if title:
        headers["X-Title"] = title
    elif resolved.get("default_title"):
        headers["X-Title"] = str(resolved["default_title"])

    return {
        "profile_name": str(profile_name),
        "base_url": str(base_url).rstrip("/"),
        "api_key_env": str(api_key_env),
        "model": model,
        "headers": headers,
    }


def _call_chat_completions(
    *,
    upstream: dict[str, Any],
    request_json: dict[str, Any],
    timeout_sec: int,
) -> tuple[int, dict[str, Any], float]:
    api_key_env = upstream["api_key_env"]
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"missing env var: {api_key_env}")
    if not upstream["base_url"] or "YOUR_" in upstream["base_url"]:
        raise RuntimeError("upstream.base_url is not configured")

    headers = {"Authorization": f"Bearer {api_key}"}
    headers.update(upstream["headers"])
    started = time.perf_counter()
    response = httpx.post(
        f"{upstream['base_url']}/chat/completions",
        headers=headers,
        json=request_json,
        timeout=timeout_sec,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    try:
        payload = response.json()
    except Exception:
        payload = {"error": {"message": response.text}}
    return response.status_code, payload, elapsed_ms


def _case_result_from_trace(trace: dict[str, Any]) -> dict[str, Any]:
    validation = trace.get("validation") if isinstance(trace.get("validation"), dict) else {}
    family = str(trace.get("family") or "")
    should_activate = bool(trace.get("should_activate"))
    return {
        "case_id": trace.get("case_id"),
        "family": family,
        "should_activate": should_activate,
        "selected_next_tool": validation.get("selected_next_tool"),
        "selected_action_candidate": validation.get("selected_action_candidate"),
        "tool_choice_mode": validation.get("tool_choice_mode"),
        "next_tool_plan_activated": bool(validation.get("next_tool_plan_activated", False)),
        "next_tool_plan_blocked_reason": validation.get("next_tool_plan_blocked_reason"),
        "next_tool_emitted": validation.get("next_tool_emitted"),
        "next_tool_matches_recommendation": validation.get("next_tool_matches_recommendation"),
        "next_tool_args_emitted": validation.get("next_tool_args_emitted"),
        "next_tool_args_match_binding": validation.get("next_tool_args_match_binding"),
        "arg_binding_validation": validation.get("arg_binding_validation") or {},
        "next_tool_final_args_match_binding": validation.get("next_tool_final_args_match_binding"),
        "final_arg_binding_validation": validation.get("final_arg_binding_validation") or {},
        "status_code": trace.get("status_code"),
        "latency_ms": trace.get("latency_ms"),
        "upstream_model": trace.get("upstream_model"),
        "dry_run": bool(trace.get("dry_run", False)),
        "stop_allowed_false_positive": family == "stop_allowed" and bool(validation.get("next_tool_plan_activated", False)),
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    blocked_reasons = Counter(str(item.get("next_tool_plan_blocked_reason") or "unknown") for item in results)
    family_summary: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "total": 0,
            "expected_activate": 0,
            "policy_plan_activated": 0,
            "next_tool_emitted": 0,
            "recommended_tool_match": 0,
            "arg_emitted": 0,
            "arg_binding_match": 0,
            "final_arg_binding_match": 0,
            "stop_allowed_false_positive": 0,
        }
    )
    for item in results:
        family = family_summary[str(item.get("family") or "unknown")]
        family["total"] += 1
        family["expected_activate"] += int(bool(item.get("should_activate")))
        family["policy_plan_activated"] += int(bool(item.get("next_tool_plan_activated")))
        family["next_tool_emitted"] += int(item.get("next_tool_emitted") is True)
        family["recommended_tool_match"] += int(item.get("next_tool_matches_recommendation") is True)
        family["arg_emitted"] += int(item.get("next_tool_args_emitted") is True)
        family["arg_binding_match"] += int(item.get("next_tool_args_match_binding") is True)
        family["final_arg_binding_match"] += int(item.get("next_tool_final_args_match_binding") is True)
        family["stop_allowed_false_positive"] += int(bool(item.get("stop_allowed_false_positive")))

    summary = {
        "case_count": len(results),
        "policy_plan_activated_count": sum(int(bool(item.get("next_tool_plan_activated"))) for item in results),
        "next_tool_emitted_count": sum(int(item.get("next_tool_emitted") is True) for item in results),
        "recommended_tool_match_count": sum(int(item.get("next_tool_matches_recommendation") is True) for item in results),
        "arg_emitted_count": sum(int(item.get("next_tool_args_emitted") is True) for item in results),
        "arg_binding_match_count": sum(int(item.get("next_tool_args_match_binding") is True) for item in results),
        "final_arg_binding_match_count": sum(
            int(item.get("next_tool_final_args_match_binding") is True) for item in results
        ),
        "stop_allowed_false_positive_count": sum(int(bool(item.get("stop_allowed_false_positive"))) for item in results),
        "blocked_reason_distribution": dict(sorted(blocked_reasons.items())),
        "family_summary": dict(sorted(family_summary.items())),
        "results": results,
    }
    summary["acceptance"] = {
        "policy_plan_activated_count": summary["policy_plan_activated_count"] >= ACCEPTANCE_THRESHOLDS["policy_plan_activated_count"],
        "next_tool_emitted_count": summary["next_tool_emitted_count"] >= ACCEPTANCE_THRESHOLDS["next_tool_emitted_count"],
        "recommended_tool_match_count": summary["recommended_tool_match_count"] >= ACCEPTANCE_THRESHOLDS["recommended_tool_match_count"],
        "arg_binding_match_count": summary["arg_binding_match_count"] >= ACCEPTANCE_THRESHOLDS["arg_binding_match_count"],
        "stop_allowed_false_positive_count": summary["stop_allowed_false_positive_count"] == ACCEPTANCE_THRESHOLDS["stop_allowed_false_positive_count"],
    }
    summary["accepted"] = all(summary["acceptance"].values())
    return summary


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Next-Action Live Smoke Summary",
        "",
        f"- Cases: `{summary['case_count']}`",
        f"- Policy plan activated: `{summary['policy_plan_activated_count']}`",
        f"- Next tool emitted: `{summary['next_tool_emitted_count']}`",
        f"- Recommended tool match: `{summary['recommended_tool_match_count']}`",
        f"- Args emitted: `{summary['arg_emitted_count']}`",
        f"- Arg binding match: `{summary['arg_binding_match_count']}`",
        f"- Final arg binding match: `{summary['final_arg_binding_match_count']}`",
        f"- Stop-allowed false positives: `{summary['stop_allowed_false_positive_count']}`",
        f"- Accepted: `{summary['accepted']}`",
        "",
        "## Acceptance",
        "",
        "| Metric | Pass |",
        "| --- | ---: |",
    ]
    for metric, passed in summary["acceptance"].items():
        lines.append(f"| {metric} | {int(bool(passed))} |")
    lines.extend(["", "## Family Summary", "", "| Family | Total | Expected Activate | Activated | Emitted | Tool Match | Arg Emitted | Raw Arg Match | Final Arg Match | Stop FP |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for family, row in summary["family_summary"].items():
        lines.append(
            f"| {family} | {row['total']} | {row['expected_activate']} | {row['policy_plan_activated']} | "
            f"{row['next_tool_emitted']} | {row['recommended_tool_match']} | {row['arg_emitted']} | "
            f"{row['arg_binding_match']} | {row['final_arg_binding_match']} | {row['stop_allowed_false_positive']} |"
        )
    lines.extend(["", "## Blocked Reasons", "", "| Reason | Count |", "| --- | ---: |"])
    for reason, count in summary["blocked_reason_distribution"].items():
        lines.append(f"| {reason} | {count} |")
    lines.extend(["", "## Cases", "", "| Case | Family | Activated | Emitted | Tool Match | Raw Arg Match | Final Arg Match | Status |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for result in summary["results"]:
        lines.append(
            f"| {result['case_id']} | {result['family']} | {int(result['next_tool_plan_activated'])} | "
            f"{int(result.get('next_tool_emitted') is True)} | {int(result.get('next_tool_matches_recommendation') is True)} | "
            f"{int(result.get('next_tool_args_match_binding') is True)} | "
            f"{int(result.get('next_tool_final_args_match_binding') is True)} | {result.get('status_code') or '-'} |"
        )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _request_for_upstream(request_json: dict[str, Any]) -> dict[str, Any]:
    """Convert fixture-only orphan tool outputs into provider-valid context.

    Smoke fixtures model prior tool state directly with role=tool messages. That
    is valid for the runtime state extractor, but OpenAI-compatible providers
    require tool messages to be linked to a prior assistant tool_call_id. For
    live smoke, preserve the information while sending a valid chat payload.
    """
    converted = copy.deepcopy(request_json)
    messages = converted.get("messages")
    if not isinstance(messages, list):
        return converted

    normalized: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            normalized.append(message)
            continue
        if message.get("role") != "tool" or message.get("tool_call_id"):
            normalized.append(message)
            continue
        name = message.get("name") or "tool"
        content = message.get("content")
        normalized.append(
            {
                "role": "user",
                "content": f"Prior tool output from {name}: {content}",
            }
        )
    converted["messages"] = normalized
    return converted


def _evaluate_case(
    *,
    case: dict[str, Any],
    cfg: dict[str, Any],
    upstream: dict[str, Any],
    out_root: Path,
    dry_run: bool,
    compiler_generated: bool,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp_raw:
        tmp = Path(tmp_raw)
        rules = _compile_rules_from_case(case, tmp) if compiler_generated else list(case.get("rules", []))
        runtime_policy = dict(cfg.get("runtime_policy") or {})
        runtime_policy["enable_required_next_tool_choice"] = True
        engine = RuleEngine(str(tmp), runtime_policy=runtime_policy)
        engine.rules = [Rule(**rule) for rule in rules]
        patched, request_patches = engine.apply_request(case["request"])

        upstream_request = _request_for_upstream(patched)
        if upstream.get("model"):
            upstream_request["model"] = upstream["model"]

        status_code = None
        latency_ms = None
        raw_response: dict[str, Any]
        if dry_run:
            raw_response = case["mock_response"]
        else:
            status_code, raw_response, latency_ms = _call_chat_completions(
                upstream=upstream,
                request_json=upstream_request,
                timeout_sec=int(cfg.get("timeout_sec", 120)),
            )

        final_response, repairs, validation = engine.apply_response(
            patched,
            raw_response,
            request_patches=request_patches,
        )

    trace = {
        "case_id": case["id"],
        "family": case["family"],
        "should_activate": bool(case.get("should_activate")),
        "dry_run": dry_run,
        "request_original": case["request"],
        "request": upstream_request,
        "runtime_request": patched,
        "tool_schema_snapshot": tool_map_from_tools_payload(patched.get("tools", [])),
        "raw_response": raw_response,
        "final_response": final_response,
        "repairs": repairs,
        "validation": validation.model_dump(mode="json"),
        "request_patches": list(request_patches),
        "status_code": status_code,
        "latency_ms": latency_ms,
        "upstream_profile": upstream.get("profile_name"),
        "upstream_model": upstream.get("model"),
        "upstream_base_url": upstream.get("base_url"),
    }
    trace_path = out_root / "traces" / f"{case['id']}.json"
    _write_json(trace_path, trace)
    return _case_result_from_trace(trace)


def run_live_smoke(
    *,
    fixtures_dir: Path,
    runtime_config: Path,
    out_root: Path,
    max_cases: int,
    compiler_generated: bool,
    dry_run: bool,
) -> dict[str, Any]:
    cfg = _load_runtime_config(runtime_config)
    upstream = _resolve_upstream_config(cfg)
    cases = load_cases(fixtures_dir)[:max_cases]
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "traces").mkdir(parents=True, exist_ok=True)

    manifest = {
        "created_at": _utc_timestamp(),
        "repo_commit": _git_commit(Path.cwd()),
        "fixtures_dir": str(fixtures_dir),
        "runtime_config": str(runtime_config),
        "out_root": str(out_root),
        "max_cases": max_cases,
        "case_count": len(cases),
        "compiler_generated": compiler_generated,
        "dry_run": dry_run,
        "upstream_profile": upstream.get("profile_name"),
        "upstream_model": upstream.get("model"),
        "upstream_base_url": upstream.get("base_url"),
    }
    _write_json(out_root / "run_manifest.json", manifest)

    results = [
        _evaluate_case(
            case=case,
            cfg=cfg,
            upstream=upstream,
            out_root=out_root,
            dry_run=dry_run,
            compiler_generated=compiler_generated,
        )
        for case in cases
    ]
    summary = summarize_results(results)
    summary["manifest"] = manifest
    _write_json(out_root / "live_smoke_summary.json", summary)
    (out_root / "live_smoke_summary.md").write_text(render_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run next-action live smoke without BFCL scorer.")
    parser.add_argument("--fixtures-dir", type=Path, default=Path("tests/fixtures/phase2_next_action_smoke"))
    parser.add_argument("--compiler-generated", action="store_true")
    parser.add_argument("--runtime-config", type=Path, default=Path("configs/runtime_bfcl_structured.yaml"))
    parser.add_argument("--out-root", type=Path, default=None)
    parser.add_argument("--max-cases", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true", help="Compile and validate with fixture mock responses; do not call upstream.")
    args = parser.parse_args()

    out_root = args.out_root or Path("outputs/phase2_smoke") / f"next_action_live_{_utc_timestamp()}"
    summary = run_live_smoke(
        fixtures_dir=args.fixtures_dir,
        runtime_config=args.runtime_config,
        out_root=out_root,
        max_cases=args.max_cases,
        compiler_generated=args.compiler_generated,
        dry_run=args.dry_run,
    )
    print(json.dumps({key: summary[key] for key in [
        "case_count",
        "policy_plan_activated_count",
        "next_tool_emitted_count",
        "recommended_tool_match_count",
        "arg_emitted_count",
        "arg_binding_match_count",
        "final_arg_binding_match_count",
        "stop_allowed_false_positive_count",
        "accepted",
    ]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
