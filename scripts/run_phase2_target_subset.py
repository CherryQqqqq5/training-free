from __future__ import annotations

import argparse
import json
import os
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
    score_root = run_root / "bfcl" / "score"
    candidates = sorted(score_root.glob(f"*/multi_turn/BFCL_v4_{category}_score.json"))
    return candidates[0] if candidates else None


def _result_json_path(run_root: Path, category: str) -> Path | None:
    result_root = run_root / "bfcl" / "result"
    candidates = sorted(result_root.glob(f"*/multi_turn/BFCL_v4_{category}_result.json"))
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


def select_case_ids(source_run_root: Path, category: str, max_cases: int) -> list[str]:
    score_path = _score_json_path(source_run_root, category)
    rows = _read_jsonl(score_path) if score_path else []
    families = _family_records(source_run_root)
    candidates: list[tuple[int, int, str]] = []
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
        candidates.append((failure_bonus, keyword_score, case_id))
    candidates.sort(key=lambda item: (-item[0], -item[1], _case_number(item[2])))
    return [case_id for _, _, case_id in candidates[:max_cases]]


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
    return json.loads((rules_dir / "compile_status.json").read_text(encoding="utf-8"))


def rules_have_ctspc_actions(rule_path: Path) -> bool:
    if not rule_path.exists():
        return False
    payload = yaml.safe_load(rule_path.read_text(encoding="utf-8")) or {}
    for rule in payload.get("rules") or []:
        policy = (((rule or {}).get("action") or {}).get("decision_policy") or {})
        if policy.get("recommended_tools") or policy.get("action_candidates"):
            return True
        next_policy = policy.get("next_tool_policy") or {}
        if next_policy.get("recommended_tools"):
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
    traces = sorted(trace_dir.glob("*.json"), key=lambda path: path.stat().st_mtime)
    total = sum(counts.values())
    if total and len(traces) >= total:
        traces = traces[-total:]
    groups: dict[str, list[dict[str, Any]]] = {}
    offset = 0
    for case_id, count in counts.items():
        case_paths = traces[offset : offset + count]
        offset += count
        groups[case_id] = []
        for path in case_paths:
            try:
                groups[case_id].append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass
    return groups


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
        "blocked_reason_distribution": dict(Counter(row.get("blocked_reason") or "unknown" for row in rows)),
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
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    source_run_root = args.source_run_root
    if not source_run_root.is_absolute():
        source_run_root = (repo / source_run_root).resolve()
    out_root = args.out_root or repo / "outputs" / "phase2_subset" / f"ctspc_v0_{_utc_timestamp()}"
    out_root.mkdir(parents=True, exist_ok=True)
    selected_ids = select_case_ids(source_run_root, args.category, args.max_cases)
    baseline_run = out_root / "baseline"
    candidate_run = out_root / "candidate"
    for run in (baseline_run, candidate_run):
        write_test_case_ids(run / "bfcl" / "test_case_ids_to_generate.json", args.category, selected_ids)

    rules_dir = out_root / "candidate_rules"
    logs_dir = out_root / "logs"
    compile_status: dict[str, Any] = {"status": "dry_run"}
    has_ctspc_actions = False
    if not args.dry_run:
        compile_status = _compile_subset_rules(repo, source_run_root / "traces", rules_dir, logs_dir)
        has_ctspc_actions = rules_have_ctspc_actions(rules_dir / "rule.yaml")
        if not has_ctspc_actions:
            raise RuntimeError("compiled candidate rules contain no recommended_tools/action_candidates")
    else:
        has_ctspc_actions = False

    model_alias = os.environ.get("GRC_BFCL_MODEL", "gpt-4o-mini-2024-07-18-FC")
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
        "max_cases": args.max_cases,
        "runtime_config": str(args.runtime_config),
        "candidate_rules_dir": str(rules_dir),
        "compile_status": compile_status,
        "has_ctspc_actions": has_ctspc_actions,
        "trace_case_mapping": "mtime_by_result_step_count",
        "planned_commands": [" ".join(baseline_cmd), " ".join(candidate_cmd)],
        "dry_run": args.dry_run,
    }
    (out_root / "subset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
        env = dict(os.environ)
        env["GRC_BFCL_USE_RUN_IDS"] = "1"
        env.setdefault("GRC_BFCL_NUM_THREADS", "1")
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
    summary["manifest"] = manifest
    (out_root / "subset_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_root / "subset_summary.md").write_text(_render_summary(summary, rows), encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("selected_case_count", "runnable_ctspc_case_count", "case_fixed_count", "case_regressed_count", "net_case_gain", "accepted")}, indent=2))


if __name__ == "__main__":
    main()
