from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


TARGET_LABELS = {
    "(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)",
    "(POST_TOOL,POST_TOOL_PROSE_SUMMARY)",
}
KEYWORDS = ("file", "path", "matches", "cat", "touch", "mkdir", "find", "folder", "directory")
TARGET_ACTION_TOOLS = {
    "cat",
    "cd",
    "cp",
    "diff",
    "echo",
    "find",
    "grep",
    "ls",
    "mkdir",
    "mv",
    "sort",
    "tail",
    "touch",
}
MIN_SCHEMA_LOCAL_CASES = 20


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _score_json_path(run_root: Path, category: str) -> Path | None:
    bfcl_root = run_root / "bfcl"
    candidates = sorted(bfcl_root.glob(f"**/score/**/multi_turn/BFCL_v4_{category}_score.json"))
    if not candidates:
        candidates = sorted((bfcl_root / "score").glob(f"*/multi_turn/BFCL_v4_{category}_score.json"))
    return candidates[0] if candidates else None


def _result_json_path(run_root: Path, category: str) -> Path | None:
    bfcl_root = run_root / "bfcl"
    candidates = sorted(bfcl_root.glob(f"**/result/**/multi_turn/BFCL_v4_{category}_result.json"))
    if not candidates:
        candidates = sorted((bfcl_root / "result").glob(f"*/multi_turn/BFCL_v4_{category}_result.json"))
    return candidates[0] if candidates else None


def _load_success_map(run_root: Path, category: str) -> dict[str, bool]:
    path = _score_json_path(run_root, category)
    if not path:
        return {}
    success: dict[str, bool] = {}
    for row in _read_jsonl(path):
        case_id = row.get("id")
        if isinstance(case_id, str) and "valid" in row:
            success[case_id] = bool(row.get("valid"))
    return success


def _prompt_text(row: dict[str, Any]) -> str:
    prompt = row.get("prompt") or {}
    question = prompt.get("question") if isinstance(prompt, dict) else None
    return json.dumps(question, ensure_ascii=False).lower()


def _family_records(run_root: Path) -> dict[str, set[str]]:
    records = _read_jsonl(run_root / "artifacts" / "repair_records.jsonl")
    if not records:
        records = _read_jsonl(run_root / "artifacts" / "repairs.jsonl")
    out: dict[str, set[str]] = {}
    for row in records:
        case_id = row.get("case_id")
        label = row.get("failure_label")
        if isinstance(case_id, str) and isinstance(label, str):
            out.setdefault(case_id, set()).add(label)
    return out


def _tool_names_from_trace(trace: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    snapshot = trace.get("tool_schema_snapshot") or {}
    if isinstance(snapshot, dict):
        names.update(str(key) for key in snapshot if str(key))
    elif isinstance(snapshot, list):
        for item in snapshot:
            if not isinstance(item, dict):
                continue
            function = item.get("function") if isinstance(item.get("function"), dict) else {}
            name = function.get("name") or item.get("name")
            if isinstance(name, str) and name:
                names.add(name)

    request = trace.get("request") if isinstance(trace.get("request"), dict) else {}
    tools = request.get("tools") if isinstance(request, dict) else []
    if isinstance(tools, list):
        for item in tools:
            if not isinstance(item, dict):
                continue
            function = item.get("function") if isinstance(item.get("function"), dict) else {}
            name = function.get("name") or item.get("name")
            if isinstance(name, str) and name:
                names.add(name)
    return names


def _case_tools_from_trace_groups(trace_groups: dict[str, list[dict[str, Any]]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for case_id, traces in trace_groups.items():
        tools: set[str] = set()
        for trace in traces:
            tools.update(_tool_names_from_trace(trace))
        out[case_id] = tools
    return out


def candidate_case_infos(source_run_root: Path, category: str) -> list[dict[str, Any]]:
    score_path = _score_json_path(source_run_root, category)
    rows = _read_jsonl(score_path) if score_path else []
    families = _family_records(source_run_root)
    score_case_ids = [row.get("id") for row in rows if isinstance(row.get("id"), str) and "valid" in row]
    counts = _result_step_counts(source_run_root, category, score_case_ids)
    trace_groups = _trace_groups_by_case(source_run_root / "traces", counts)
    tools_by_case = _case_tools_from_trace_groups(trace_groups)
    candidates: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        case_id = row.get("id")
        if not isinstance(case_id, str) or "valid" not in row:
            continue
        labels = families.get(case_id)
        if labels and not labels.intersection(TARGET_LABELS):
            continue
        text = _prompt_text(row)
        keyword_score = sum(1 for keyword in KEYWORDS if keyword in text)
        if keyword_score <= 0:
            continue
        failure_bonus = 1 if row.get("valid") is False else 0
        available_tools = tools_by_case.get(case_id, set())
        target_tools = available_tools.intersection(TARGET_ACTION_TOOLS)
        candidates.append(
            {
                "case_id": case_id,
                "failure_labels": sorted(labels or []),
                "failure_bonus": failure_bonus,
                "keyword_score": keyword_score,
                "available_tools_in_case_schema": sorted(available_tools),
                "target_action_tools_present": sorted(target_tools),
            }
        )
    candidates.sort(key=lambda item: (-int(item["failure_bonus"]), -int(item["keyword_score"]), _case_number(str(item["case_id"]))))
    return candidates


def select_case_ids(source_run_root: Path, category: str, max_cases: int, *, schema_local: bool = True) -> list[str]:
    candidates = candidate_case_infos(source_run_root, category)
    if schema_local:
        candidates = [row for row in candidates if row.get("target_action_tools_present")]
    return [str(row["case_id"]) for row in candidates[:max_cases]]


def _case_number(case_id: str) -> int:
    try:
        return int(case_id.rsplit("_", 1)[-1])
    except Exception:
        return 10**9


def write_test_case_ids(path: Path, category: str, case_ids: list[str]) -> None:
    payload: dict[str, list[str]] = {}
    example = Path("configs/test_case_ids_to_generate.json")
    if example.exists():
        try:
            loaded = json.loads(example.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = {str(key): list(value or []) for key, value in loaded.items()}
        except Exception:
            payload = {}
    payload.setdefault(category, [])
    payload[category] = list(case_ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run(command: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as handle:
        process = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=handle, stderr=subprocess.STDOUT)
    if process.returncode != 0:
        raise RuntimeError(f"command failed ({process.returncode}): {' '.join(command)}; see {log_path}")


def _execution_env(repo_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    venv_bin = repo_root / ".venv" / "bin"
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
    env["GRC_BFCL_USE_RUN_IDS"] = "1"
    env["GRC_BFCL_PARTIAL_EVAL"] = "1"
    env.setdefault("GRC_BFCL_NUM_THREADS", "1")
    return env


def _compile_subset_rules(repo_root: Path, source_trace_dir: Path, rules_dir: Path, log_dir: Path) -> dict[str, Any]:
    failures = rules_dir / "failures.jsonl"
    rules_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{repo_root / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    _run(
        [sys.executable, "-m", "grc.cli", "mine", "--trace-dir", str(source_trace_dir), "--out", str(failures)],
        cwd=repo_root,
        env=env,
        log_path=log_dir / "mine.log",
    )
    _run(
        [
            sys.executable,
            "-m",
            "grc.cli",
            "compile",
            "--failures",
            str(failures),
            "--out",
            str(rules_dir / "rule.yaml"),
            "--patch-id",
            "m27_subset_ctspc",
            "--candidate-dir",
            str(rules_dir),
        ],
        cwd=repo_root,
        env=env,
        log_path=log_dir / "compile.log",
    )
    prune_result = prune_rule_policy_tools(rules_dir / "rule.yaml", allowed_tools=TARGET_ACTION_TOOLS)
    status = json.loads((rules_dir / "compile_status.json").read_text(encoding="utf-8"))
    status["policy_tool_prune"] = prune_result
    (rules_dir / "compile_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def prune_rule_policy_tools(rule_path: Path, *, allowed_tools: set[str]) -> dict[str, Any]:
    if not rule_path.exists():
        return {"kept_tools": [], "removed_tools": [], "kept_action_candidate_count": 0}
    payload = yaml.safe_load(rule_path.read_text(encoding="utf-8")) or {}
    kept: Counter[str] = Counter()
    removed: Counter[str] = Counter()
    kept_candidate_count = 0

    def filter_tools(values: Any) -> list[str]:
        out: list[str] = []
        for value in values or []:
            if not isinstance(value, str) or not value:
                continue
            if value in allowed_tools:
                out.append(value)
                kept[value] += 1
            else:
                removed[value] += 1
        return list(dict.fromkeys(out))

    for rule in payload.get("rules") or []:
        policy = (((rule or {}).get("action") or {}).get("decision_policy") or {})
        policy["recommended_tools"] = filter_tools(policy.get("recommended_tools") or [])
        next_policy = policy.get("next_tool_policy") or {}
        next_policy["recommended_tools"] = filter_tools(next_policy.get("recommended_tools") or [])
        if next_policy:
            policy["next_tool_policy"] = next_policy
        candidates: list[dict[str, Any]] = []
        for candidate in policy.get("action_candidates") or []:
            if not isinstance(candidate, dict):
                continue
            tool = candidate.get("tool")
            recs = filter_tools(candidate.get("recommended_tools") or ([tool] if isinstance(tool, str) else []))
            if not isinstance(tool, str) or tool not in allowed_tools or not recs:
                if isinstance(tool, str) and tool:
                    removed[tool] += 1
                continue
            candidate = dict(candidate)
            candidate["recommended_tools"] = recs
            candidates.append(candidate)
            kept[tool] += 1
            kept_candidate_count += 1
        policy["action_candidates"] = candidates

    rule_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {
        "allowed_tools": sorted(allowed_tools),
        "kept_tools": dict(sorted(kept.items())),
        "removed_tools": dict(sorted(removed.items())),
        "kept_action_candidate_count": kept_candidate_count,
    }


def _case_id_from_trace_id(trace_id: str) -> str:
    return trace_id.split("__", 1)[0]


def _mined_policy_signals_by_case(failures_path: Path) -> dict[str, dict[str, Any]]:
    signals: dict[str, dict[str, Any]] = {}
    if not failures_path.exists():
        return signals
    for row in _read_jsonl(failures_path):
        trace_id = row.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            continue
        case_id = _case_id_from_trace_id(trace_id)
        entry = signals.setdefault(
            case_id,
            {
                "failure_labels": set(),
                "mined_recommended_tools_before_prune": set(),
                "mined_action_candidates_before_prune": set(),
            },
        )
        label = row.get("failure_label")
        if isinstance(label, str) and label:
            entry["failure_labels"].add(label)
        for tool in row.get("recommended_tools") or []:
            if isinstance(tool, str) and tool:
                entry["mined_recommended_tools_before_prune"].add(tool)
        for candidate in row.get("action_candidates") or []:
            if not isinstance(candidate, dict):
                continue
            tool = candidate.get("tool")
            if isinstance(tool, str) and tool:
                entry["mined_action_candidates_before_prune"].add(tool)
            for tool in candidate.get("recommended_tools") or []:
                if isinstance(tool, str) and tool:
                    entry["mined_action_candidates_before_prune"].add(tool)
    return signals


def build_gap_report_rows(
    candidate_infos: list[dict[str, Any]],
    *,
    failures_path: Path | None = None,
    prune_result: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    mined = _mined_policy_signals_by_case(failures_path) if failures_path else {}
    removed_counts = (prune_result or {}).get("removed_tools") or {}
    kept_counts = (prune_result or {}).get("kept_tools") or {}
    rows: list[dict[str, Any]] = []
    for info in candidate_infos:
        case_id = str(info["case_id"])
        mined_entry = mined.get(case_id, {})
        recommended = sorted(mined_entry.get("mined_recommended_tools_before_prune") or [])
        action_candidates = sorted(mined_entry.get("mined_action_candidates_before_prune") or [])
        available = set(info.get("available_tools_in_case_schema") or [])
        target_present = sorted(available.intersection(TARGET_ACTION_TOOLS))
        mined_tools = set(recommended).union(action_candidates)
        removed = sorted(tool for tool in mined_tools.union(available) if tool in removed_counts or (tool and tool not in TARGET_ACTION_TOOLS))
        kept = sorted(tool for tool in mined_tools if tool in kept_counts or tool in TARGET_ACTION_TOOLS)
        if not target_present:
            reason = "non_target_schema"
        elif not recommended and not action_candidates:
            reason = "insufficient_local_evidence"
        elif not kept:
            reason = "generator_gap"
        else:
            reason = "schema_local_candidate"
        labels = sorted(set(info.get("failure_labels") or []).union(mined_entry.get("failure_labels") or []))
        rows.append(
            {
                "case_id": case_id,
                "failure_labels": labels,
                "available_tools_in_case_schema": sorted(available),
                "target_action_tools_present": target_present,
                "mined_recommended_tools_before_prune": recommended,
                "mined_action_candidates_before_prune": action_candidates,
                "removed_tools": removed,
                "kept_tools": kept,
                "why_no_schema_local_candidate": reason,
            }
        )
    return rows


def summarize_gap_report(rows: list[dict[str, Any]], *, selected_ids: list[str], min_schema_local_cases: int) -> dict[str, Any]:
    reasons = Counter(str(row.get("why_no_schema_local_candidate") or "unknown") for row in rows)
    target_tools: Counter[str] = Counter()
    for row in rows:
        target_tools.update(str(tool) for tool in row.get("target_action_tools_present") or [])
    schema_local_count = sum(bool(row.get("target_action_tools_present")) for row in rows)
    return {
        "prompt_family_candidate_count": len(rows),
        "schema_local_candidate_count": schema_local_count,
        "schema_filtered_out_count": len(rows) - schema_local_count,
        "selected_case_count": len(selected_ids),
        "selection_schema_filter": True,
        "min_schema_local_cases": min_schema_local_cases,
        "eligible_for_execution": schema_local_count >= min_schema_local_cases,
        "target_action_tool_distribution": dict(sorted(target_tools.items())),
        "why_no_schema_local_candidate_distribution": dict(sorted(reasons.items())),
    }


def render_gap_summary(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase-2 Target Subset Gap Report",
        "",
        f"- Prompt/family candidates: `{summary['prompt_family_candidate_count']}`",
        f"- Schema-local candidates: `{summary['schema_local_candidate_count']}`",
        f"- Schema-filtered out: `{summary['schema_filtered_out_count']}`",
        f"- Selected cases: `{summary['selected_case_count']}`",
        f"- Eligible for execution: `{summary['eligible_for_execution']}`",
        "",
        "## Reason Distribution",
        "",
    ]
    for reason, count in (summary.get("why_no_schema_local_candidate_distribution") or {}).items():
        lines.append(f"- `{reason}`: `{count}`")
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | Target Tools | Mined Recommended | Mined Candidates | Reason |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {', '.join(row.get('target_action_tools_present') or []) or '-'} | "
            f"{', '.join(row.get('mined_recommended_tools_before_prune') or []) or '-'} | "
            f"{', '.join(row.get('mined_action_candidates_before_prune') or []) or '-'} | "
            f"{row.get('why_no_schema_local_candidate') or '-'} |"
        )
    return "\n".join(lines) + "\n"


def write_gap_artifacts(out_root: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    with (out_root / "gap_report.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_root / "gap_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_root / "gap_summary.md").write_text(render_gap_summary(summary, rows), encoding="utf-8")


def rules_have_ctspc_actions(rule_path: Path) -> bool:
    if not rule_path.exists():
        return False
    payload = yaml.safe_load(rule_path.read_text(encoding="utf-8")) or {}
    for rule in payload.get("rules") or []:
        policy = (((rule or {}).get("action") or {}).get("decision_policy") or {})
        if policy.get("action_candidates"):
            return True
        next_policy = policy.get("next_tool_policy") or {}
        if any(tool in TARGET_ACTION_TOOLS for tool in next_policy.get("recommended_tools") or []):
            return True
    return False


def _result_step_counts(run_root: Path, category: str, selected_ids: list[str]) -> dict[str, int]:
    path = _result_json_path(run_root, category)
    if not path:
        return {case_id: 0 for case_id in selected_ids}
    counts: dict[str, int] = {}
    for row in _read_jsonl(path):
        case_id = row.get("id")
        if case_id not in selected_ids:
            continue
        result = row.get("result") or []
        count = 0
        for turn in result:
            if isinstance(turn, list):
                count += len(turn)
        counts[case_id] = count
    return counts


def _trace_groups_by_case(trace_dir: Path, counts: dict[str, int]) -> dict[str, list[dict[str, Any]]]:
    trace_groups = _trace_paths_by_case(trace_dir, counts)
    groups: dict[str, list[dict[str, Any]]] = {}
    for case_id, case_paths in trace_groups.items():
        groups[case_id] = []
        for path in case_paths:
            try:
                groups[case_id].append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass
    return groups


def _trace_paths_by_case(trace_dir: Path, counts: dict[str, int]) -> dict[str, list[Path]]:
    traces = sorted(trace_dir.glob("*.json"), key=lambda path: path.stat().st_mtime)
    total = sum(counts.values())
    if total and len(traces) >= total:
        traces = traces[-total:]
    groups: dict[str, list[Path]] = {}
    offset = 0
    for case_id, count in counts.items():
        groups[case_id] = traces[offset : offset + count]
        offset += count
    return groups


def materialize_selected_traces(
    *,
    source_run_root: Path,
    category: str,
    selected_ids: list[str],
    out_dir: Path,
) -> dict[str, Any]:
    counts = _result_step_counts(source_run_root, category, selected_ids)
    expected_trace_count = sum(counts.values())
    if expected_trace_count <= 0:
        raise RuntimeError("selected trace materialization failed: no result steps found for selected cases")
    trace_groups = _trace_paths_by_case(source_run_root / "traces", counts)
    actual_trace_count = sum(len(paths) for paths in trace_groups.values())
    if actual_trace_count < expected_trace_count:
        raise RuntimeError(
            "selected trace materialization failed: "
            f"expected {expected_trace_count} traces from result steps, found {actual_trace_count}"
        )

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for case_id in selected_ids:
        for index, path in enumerate(trace_groups.get(case_id, [])):
            target = out_dir / f"{case_id}__{index:03d}__{path.name}"
            shutil.copy2(path, target)
            copied += 1
    return {
        "expected_trace_count": expected_trace_count,
        "selected_trace_count": copied,
        "selected_case_with_trace_count": sum(1 for paths in trace_groups.values() if paths),
        "source_trace_count": len(list((source_run_root / "traces").glob("*.json"))),
    }


def _aggregate_validation(traces: list[dict[str, Any]]) -> dict[str, Any]:
    validations = [trace.get("validation") or {} for trace in traces if isinstance(trace.get("validation"), dict)]
    activated = [v for v in validations if v.get("next_tool_plan_activated") is True]
    selected = next((v.get("selected_next_tool") for v in activated if v.get("selected_next_tool")), None)
    repairs: list[str] = []
    for v in validations:
        repairs.extend(str(item) for item in v.get("repair_kinds") or [] if str(item))
    return {
        "policy_plan_activated": bool(activated),
        "selected_next_tool": selected,
        "next_tool_emitted": any(v.get("next_tool_emitted") is True for v in activated),
        "recommended_tool_match": any(v.get("next_tool_matches_recommendation") is True for v in activated),
        "raw_strict_arg_match": any(v.get("next_tool_args_match_binding") is True for v in activated),
        "raw_normalized_arg_match": any(v.get("next_tool_args_match_binding_normalized") is True for v in activated),
        "final_strict_arg_match": any(v.get("next_tool_final_args_match_binding") is True for v in activated),
        "final_normalized_arg_match": any(v.get("next_tool_final_args_match_binding_normalized") is True for v in activated),
        "blocked_reason": next((v.get("next_tool_plan_blocked_reason") for v in validations if v.get("next_tool_plan_blocked_reason")), None),
        "repair_kinds": sorted(set(repairs)),
    }


def build_case_report(
    *,
    baseline_run: Path,
    candidate_run: Path,
    category: str,
    selected_ids: list[str],
) -> list[dict[str, Any]]:
    baseline_success = _load_success_map(baseline_run, category)
    candidate_success = _load_success_map(candidate_run, category)
    counts = _result_step_counts(candidate_run, category, selected_ids)
    trace_groups = _trace_groups_by_case(candidate_run / "traces", counts)
    rows: list[dict[str, Any]] = []
    for case_id in selected_ids:
        validation = _aggregate_validation(trace_groups.get(case_id, []))
        base = baseline_success.get(case_id)
        cand = candidate_success.get(case_id)
        rows.append(
            {
                "case_id": case_id,
                "baseline_success": base,
                "candidate_success": cand,
                **validation,
                "case_fixed": base is False and cand is True,
                "case_regressed": base is True and cand is False,
            }
        )
    return rows


def summarize_case_report(rows: list[dict[str, Any]], *, baseline_acc: float | None = None, candidate_acc: float | None = None) -> dict[str, Any]:
    activated = [row for row in rows if row.get("policy_plan_activated")]
    denom = len(activated) or 1
    blocked = Counter(row.get("blocked_reason") or "unknown" for row in rows)
    summary = {
        "selected_case_count": len(rows),
        "runnable_ctspc_case_count": len(activated),
        "baseline_accuracy": baseline_acc,
        "candidate_accuracy": candidate_acc,
        "policy_plan_activated_count": len(activated),
        "recommended_tool_match_rate_among_activated": sum(row.get("recommended_tool_match") is True for row in activated) / denom,
        "raw_normalized_arg_match_rate_among_activated": sum(row.get("raw_normalized_arg_match") is True for row in activated) / denom,
        "raw_strict_arg_match_rate_among_activated": sum(row.get("raw_strict_arg_match") is True for row in activated) / denom,
        "final_normalized_arg_match_rate_among_activated": sum(row.get("final_normalized_arg_match") is True for row in activated) / denom,
        "case_fixed_count": sum(row.get("case_fixed") is True for row in rows),
        "case_regressed_count": sum(row.get("case_regressed") is True for row in rows),
        "stop_allowed_false_positive_count": 0,
        "blocked_reason_distribution": dict(blocked),
        "recommended_tools_not_in_schema_count": blocked.get("recommended_tools_not_in_schema", 0),
    }
    summary["net_case_gain"] = summary["case_fixed_count"] - summary["case_regressed_count"]
    summary["accepted"] = (
        summary["policy_plan_activated_count"] > 0
        and summary["recommended_tool_match_rate_among_activated"] >= 0.6
        and summary["raw_normalized_arg_match_rate_among_activated"] >= 0.6
        and summary["stop_allowed_false_positive_count"] == 0
        and summary["case_fixed_count"] > summary["case_regressed_count"]
    )
    return summary


def candidate_policy_tool_distribution(rule_path: Path) -> dict[str, int]:
    if not rule_path.exists():
        return {}
    payload = yaml.safe_load(rule_path.read_text(encoding="utf-8")) or {}
    counts: Counter[str] = Counter()
    for rule in payload.get("rules") or []:
        policy = (((rule or {}).get("action") or {}).get("decision_policy") or {})
        for tool in policy.get("recommended_tools") or []:
            if isinstance(tool, str) and tool:
                counts[tool] += 1
        next_policy = policy.get("next_tool_policy") or {}
        for tool in next_policy.get("recommended_tools") or []:
            if isinstance(tool, str) and tool:
                counts[tool] += 1
        for candidate in policy.get("action_candidates") or []:
            if not isinstance(candidate, dict):
                continue
            tool = candidate.get("tool")
            if isinstance(tool, str) and tool:
                counts[tool] += 1
            for rec in candidate.get("recommended_tools") or []:
                if isinstance(rec, str) and rec:
                    counts[rec] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _metric_acc(run_root: Path, category: str) -> float | None:
    path = run_root / "artifacts" / "metrics.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    subsets = data.get("subsets") if isinstance(data.get("subsets"), dict) else {}
    value = subsets.get(category)
    return float(value) if value is not None else None


def _render_summary(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase-2 Target Subset Summary",
        "",
        f"- Selected cases: `{summary['selected_case_count']}`",
        f"- Runnable CTSPC cases: `{summary['runnable_ctspc_case_count']}`",
        f"- Baseline accuracy: `{summary['baseline_accuracy']}`",
        f"- Candidate accuracy: `{summary['candidate_accuracy']}`",
        f"- Case fixed: `{summary['case_fixed_count']}`",
        f"- Case regressed: `{summary['case_regressed_count']}`",
        f"- Net case gain: `{summary['net_case_gain']}`",
        f"- Accepted: `{summary['accepted']}`",
        "",
        "## Cases",
        "",
        "| Case | Base | Cand | Activated | Tool Match | Raw Norm Arg | Fixed | Regressed | Blocked |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {int(row.get('baseline_success') is True)} | "
            f"{int(row.get('candidate_success') is True)} | {int(row.get('policy_plan_activated') is True)} | "
            f"{int(row.get('recommended_tool_match') is True)} | {int(row.get('raw_normalized_arg_match') is True)} | "
            f"{int(row.get('case_fixed') is True)} | {int(row.get('case_regressed') is True)} | "
            f"{row.get('blocked_reason') or '-'} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Phase-2 BFCL target subset with case-level causal report.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-run-root", type=Path, required=True)
    parser.add_argument("--category", default="multi_turn_miss_param")
    parser.add_argument("--max-cases", type=int, default=50)
    parser.add_argument("--runtime-config", type=Path, default=Path("configs/runtime_bfcl_structured.yaml"))
    parser.add_argument("--out-root", type=Path, default=None)
    parser.add_argument("--baseline-port", type=int, default=8060)
    parser.add_argument("--candidate-port", type=int, default=8061)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--gap-report-only", action="store_true")
    parser.add_argument("--min-schema-local-cases", type=int, default=MIN_SCHEMA_LOCAL_CASES)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    source_run_root = args.source_run_root
    if not source_run_root.is_absolute():
        source_run_root = (repo / source_run_root).resolve()
    out_root = args.out_root or repo / "outputs" / "phase2_subset" / f"ctspc_v0_{_utc_timestamp()}"
    out_root.mkdir(parents=True, exist_ok=True)
    candidate_infos = candidate_case_infos(source_run_root, args.category)
    schema_local_infos = [row for row in candidate_infos if row.get("target_action_tools_present")]
    selected_ids = [str(row["case_id"]) for row in schema_local_infos[: args.max_cases]]
    schema_local_ready = len(schema_local_infos) >= args.min_schema_local_cases
    baseline_run = out_root / "baseline"
    candidate_run = out_root / "candidate"
    if schema_local_ready and not args.gap_report_only:
        for run in (baseline_run, candidate_run):
            write_test_case_ids(run / "bfcl" / "test_case_ids_to_generate.json", args.category, selected_ids)

    rules_dir = out_root / "candidate_rules"
    logs_dir = out_root / "logs"
    compile_status: dict[str, Any] = {"status": "dry_run"}
    has_ctspc_actions = False
    selected_trace_dir = out_root / "source_selected_traces"
    selected_trace_manifest: dict[str, Any] = {}
    compile_scope = "dry_run"
    gap_rows = build_gap_report_rows(candidate_infos)
    gap_summary = summarize_gap_report(gap_rows, selected_ids=selected_ids, min_schema_local_cases=args.min_schema_local_cases)
    if not args.dry_run and (schema_local_ready or args.gap_report_only):
        trace_ids_for_compile = selected_ids if schema_local_ready and not args.gap_report_only else [str(row["case_id"]) for row in candidate_infos]
        selected_trace_manifest = materialize_selected_traces(
            source_run_root=source_run_root,
            category=args.category,
            selected_ids=trace_ids_for_compile,
            out_dir=selected_trace_dir,
        )
        compile_scope = "selected_cases" if trace_ids_for_compile == selected_ids else "prompt_family_candidates"
        compile_status = _compile_subset_rules(repo, selected_trace_dir, rules_dir, logs_dir)
        has_ctspc_actions = rules_have_ctspc_actions(rules_dir / "rule.yaml")
        gap_rows = build_gap_report_rows(
            candidate_infos,
            failures_path=rules_dir / "failures.jsonl",
            prune_result=compile_status.get("policy_tool_prune") if isinstance(compile_status.get("policy_tool_prune"), dict) else None,
        )
        gap_summary = summarize_gap_report(gap_rows, selected_ids=selected_ids, min_schema_local_cases=args.min_schema_local_cases)
    write_gap_artifacts(out_root, gap_rows, gap_summary)
    if args.dry_run:
        has_ctspc_actions = False
    else:
        compile_scope = compile_scope

    model_alias = os.environ.get("GRC_BFCL_MODEL", "gpt-4o-mini-2024-07-18-FC")
    baseline_cmd: list[str] = []
    candidate_cmd: list[str] = []
    if schema_local_ready and not args.gap_report_only:
        baseline_cmd = [
            "bash",
            str(repo / "scripts/run_bfcl_v4_baseline.sh"),
            model_alias,
            str(baseline_run),
            str(args.baseline_port),
            args.category,
            str(repo / args.runtime_config if not args.runtime_config.is_absolute() else args.runtime_config),
        ]
        candidate_cmd = [
            "bash",
            str(repo / "scripts/run_bfcl_v4_patch.sh"),
            model_alias,
            str(candidate_run),
            str(args.candidate_port),
            args.category,
            str(repo / args.runtime_config if not args.runtime_config.is_absolute() else args.runtime_config),
            str(rules_dir),
            str(candidate_run / "traces"),
            str(candidate_run / "artifacts"),
            str(baseline_run / "artifacts" / "metrics.json"),
        ]
    manifest = {
        "created_at": _utc_timestamp(),
        "source_run_root": str(source_run_root),
        "category": args.category,
        "selected_case_ids": selected_ids,
        "prompt_family_candidate_count": len(candidate_infos),
        "schema_local_candidate_count": len(schema_local_infos),
        "schema_filtered_out_count": len(candidate_infos) - len(schema_local_infos),
        "selection_schema_filter": True,
        "min_schema_local_cases": args.min_schema_local_cases,
        "max_cases": args.max_cases,
        "runtime_config": str(args.runtime_config),
        "candidate_rules_dir": str(rules_dir),
        "compile_status": compile_status,
        "has_ctspc_actions": has_ctspc_actions,
        "compile_trace_scope": compile_scope,
        "selected_trace_manifest": selected_trace_manifest,
        "trace_case_mapping": "mtime_by_result_step_count",
        "planned_commands": [" ".join(baseline_cmd), " ".join(candidate_cmd)] if baseline_cmd and candidate_cmd else [],
        "dry_run": args.dry_run,
        "gap_report_only": args.gap_report_only,
    }
    (out_root / "subset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.gap_report_only or not schema_local_ready:
        failure_reason = (
            "schema-local eligible cases below execution threshold"
            if not schema_local_ready
            else "gap report only"
        )
        summary = {
            "selected_case_count": len(selected_ids),
            "runnable_ctspc_case_count": 0,
            "baseline_accuracy": None,
            "candidate_accuracy": None,
            "policy_plan_activated_count": 0,
            "recommended_tool_match_rate_among_activated": 0.0,
            "raw_normalized_arg_match_rate_among_activated": 0.0,
            "raw_strict_arg_match_rate_among_activated": 0.0,
            "final_normalized_arg_match_rate_among_activated": 0.0,
            "case_fixed_count": 0,
            "case_regressed_count": 0,
            "stop_allowed_false_positive_count": 0,
            "blocked_reason_distribution": {failure_reason: len(candidate_infos)},
            "recommended_tools_not_in_schema_count": 0,
            "net_case_gain": 0,
            "accepted": False,
            "failure_reason": failure_reason,
            "candidate_policy_tool_distribution": candidate_policy_tool_distribution(rules_dir / "rule.yaml"),
            "gap_summary": gap_summary,
            "manifest": manifest,
        }
        rows = [
            {
                "case_id": str(row["case_id"]),
                "baseline_success": None,
                "candidate_success": None,
                "policy_plan_activated": False,
                "selected_next_tool": None,
                "next_tool_emitted": None,
                "recommended_tool_match": None,
                "raw_strict_arg_match": None,
                "raw_normalized_arg_match": None,
                "final_strict_arg_match": None,
                "final_normalized_arg_match": None,
                "case_fixed": False,
                "case_regressed": False,
                "blocked_reason": row.get("why_no_schema_local_candidate") or failure_reason,
                "repair_kinds": [],
            }
            for row in gap_rows
        ]
        with (out_root / "subset_case_report.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        (out_root / "subset_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out_root / "subset_summary.md").write_text(_render_summary(summary, rows), encoding="utf-8")
        print(json.dumps({"selected_case_count": len(selected_ids), **gap_summary, "accepted": False}, indent=2))
        if not args.gap_report_only and not args.dry_run:
            raise RuntimeError(f"{failure_reason}: {len(schema_local_infos)} < {args.min_schema_local_cases}")
        return
    if not args.dry_run and not has_ctspc_actions:
        summary = {
            "selected_case_count": len(selected_ids),
            "runnable_ctspc_case_count": 0,
            "baseline_accuracy": None,
            "candidate_accuracy": None,
            "policy_plan_activated_count": 0,
            "recommended_tool_match_rate_among_activated": 0.0,
            "raw_normalized_arg_match_rate_among_activated": 0.0,
            "raw_strict_arg_match_rate_among_activated": 0.0,
            "final_normalized_arg_match_rate_among_activated": 0.0,
            "case_fixed_count": 0,
            "case_regressed_count": 0,
            "stop_allowed_false_positive_count": 0,
            "blocked_reason_distribution": {"no_schema_local_ctspc_actions": len(selected_ids)},
            "recommended_tools_not_in_schema_count": 0,
            "net_case_gain": 0,
            "accepted": False,
            "failure_reason": "compiled candidate rules contain no schema-local CTSPC action candidates after pruning",
            "candidate_policy_tool_distribution": candidate_policy_tool_distribution(rules_dir / "rule.yaml"),
            "manifest": manifest,
        }
        rows = [
            {
                "case_id": case_id,
                "baseline_success": None,
                "candidate_success": None,
                "policy_plan_activated": False,
                "selected_next_tool": None,
                "next_tool_emitted": None,
                "recommended_tool_match": None,
                "raw_strict_arg_match": None,
                "raw_normalized_arg_match": None,
                "final_strict_arg_match": None,
                "final_normalized_arg_match": None,
                "case_fixed": False,
                "case_regressed": False,
                "blocked_reason": "no_schema_local_ctspc_actions",
                "repair_kinds": [],
            }
            for case_id in selected_ids
        ]
        with (out_root / "subset_case_report.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        (out_root / "subset_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out_root / "subset_summary.md").write_text(_render_summary(summary, rows), encoding="utf-8")
        raise RuntimeError("compiled candidate rules contain no schema-local CTSPC action candidates after pruning")
    if args.dry_run:
        rows = [
            {
                "case_id": case_id,
                "baseline_success": None,
                "candidate_success": None,
                "policy_plan_activated": False,
                "selected_next_tool": None,
                "next_tool_emitted": None,
                "recommended_tool_match": None,
                "raw_strict_arg_match": None,
                "raw_normalized_arg_match": None,
                "final_strict_arg_match": None,
                "final_normalized_arg_match": None,
                "case_fixed": False,
                "case_regressed": False,
                "blocked_reason": "dry_run",
                "repair_kinds": [],
            }
            for case_id in selected_ids
        ]
    else:
        env = _execution_env(repo)
        _run(baseline_cmd, cwd=repo, env=env, log_path=logs_dir / "baseline.log")
        _run(candidate_cmd, cwd=repo, env=env, log_path=logs_dir / "candidate.log")
        rows = build_case_report(
            baseline_run=baseline_run,
            candidate_run=candidate_run,
            category=args.category,
            selected_ids=selected_ids,
        )
    with (out_root / "subset_case_report.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = summarize_case_report(
        rows,
        baseline_acc=_metric_acc(baseline_run, args.category),
        candidate_acc=_metric_acc(candidate_run, args.category),
    )
    summary["candidate_policy_tool_distribution"] = candidate_policy_tool_distribution(rules_dir / "rule.yaml")
    summary["manifest"] = manifest
    (out_root / "subset_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_root / "subset_summary.md").write_text(_render_summary(summary, rows), encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("selected_case_count", "runnable_ctspc_case_count", "case_fixed_count", "case_regressed_count", "net_case_gain", "accepted")}, indent=2))


if __name__ == "__main__":
    main()
