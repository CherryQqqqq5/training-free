from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _path_exists(path: Path | None) -> bool:
    return path is not None and path.exists()


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _candidate_dirs(proposal_summary_path: Path, max_candidates: int) -> list[Path]:
    if not proposal_summary_path.exists():
        return []
    data = json.loads(proposal_summary_path.read_text(encoding="utf-8"))
    proposals = data.get("proposals") or []
    return [Path(item["candidate_dir"]) for item in proposals[:max_candidates] if isinstance(item, dict) and item.get("candidate_dir")]


def _parse_optional_run(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("optional rerun must be LABEL=PATH")
    label, raw = value.split("=", 1)
    return label.strip(), Path(raw)


def _first_candidate_dir(proposal_root: Path) -> Path:
    return proposal_root / "fresh_00"


def _target_metric(metrics: dict[str, Any]) -> float | None:
    subsets = metrics.get("subsets")
    category = str(metrics.get("test_category") or "").strip()
    if isinstance(subsets, dict) and category in subsets:
        try:
            return float(subsets[category])
        except Exception:
            return None
    try:
        value = metrics.get("acc")
        return None if value is None else float(value)
    except Exception:
        return None


def _compile_status(candidate_dir: Path) -> dict[str, Any]:
    return _load_json(candidate_dir / "compile_status.json")


def _proposal_metadata(candidate_dir: Path) -> dict[str, Any]:
    return _load_json(candidate_dir / "proposal_metadata.json")


def _proposal_summary(proposal_summary_path: Path) -> dict[str, Any]:
    return _load_json(proposal_summary_path)


def _proposal_count_by_mode(summary: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for proposal in summary.get("proposals") or []:
        if not isinstance(proposal, dict):
            continue
        mode = str(proposal.get("proposal_mode") or proposal.get("proposal_kind") or "unknown")
        counts[mode] = counts.get(mode, 0) + 1
    return counts


def _select_candidate_dir(proposal_summary_path: Path, max_candidates: int) -> Path:
    candidates = _candidate_dirs(proposal_summary_path, max_candidates)
    if not candidates:
        raise SystemExit(f"no proposal candidates found in {proposal_summary_path}")
    for candidate_dir in candidates:
        status = str(_compile_status(candidate_dir).get("status") or _proposal_metadata(candidate_dir).get("compile_status") or "")
        if status == "actionable_patch":
            return candidate_dir
    raise SystemExit("no executable candidate proposals found within the allowed proposal set")


def _run_command(command: str) -> None:
    subprocess.run(command, shell=True, check=True, executable="/bin/bash")


def _run_logged_command(command: str, *, step_name: str, out_root: Path) -> None:
    logs_dir = out_root / "logs"
    status_dir = out_root / "step_status"
    logs_dir.mkdir(parents=True, exist_ok=True)
    status_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{step_name}.log"
    status_path = status_dir / f"{step_name}.json"
    started_at = time.time()
    status = {
        "step": step_name,
        "status": "running",
        "command": command,
        "log_path": str(log_path),
        "started_at": started_at,
    }
    _json_dump(status_path, status)
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"$ {command}\n\n")
        log_file.flush()
        result = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    finished_at = time.time()
    status.update(
        {
            "status": "completed" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "finished_at": finished_at,
            "duration_sec": round(finished_at - started_at, 3),
        }
    )
    _json_dump(status_path, status)
    if result.returncode != 0:
        failure = dict(status)
        failure["reason"] = f"step `{step_name}` exited with status {result.returncode}"
        _json_dump(out_root / "failure_state.json", failure)
        raise subprocess.CalledProcessError(result.returncode, command)


def _build_command_plan(
    *,
    repo_root: Path,
    baseline_root: Path,
    target_root: Path,
    holdout_root: Path | None,
    out_root: Path,
    history: str,
    target_category: str,
    holdout_category: str,
    candidate_dir: Path | None,
) -> dict[str, str]:
    proposal_root = out_root / "proposals"
    taxonomy_json = out_root / "taxonomy_report.json"
    taxonomy_md = out_root / "taxonomy_report.md"
    failures_path = out_root / "failures.jsonl"
    if candidate_dir is None:
        candidate_dir = _first_candidate_dir(proposal_root)
    candidate_rule_path = candidate_dir / "rule.yaml"
    candidate_metrics = candidate_dir / "metrics.json"
    candidate_run_root = out_root / "candidate_run"
    candidate_trace_dir = candidate_run_root / "traces"
    holdout_run_root = out_root / "holdout_run"
    holdout_trace_dir = holdout_run_root / "traces"
    holdout_artifact_dir = holdout_run_root / "artifacts"
    rerun_root = out_root / "candidate_run_rerun"
    rerun_trace_dir = rerun_root / "traces"
    rerun_artifact_dir = candidate_dir / "rerun"
    holdout_baseline_metrics = (holdout_root / "artifacts/metrics.json") if holdout_root else None

    commands = {
        "taxonomy": f"cd {repo_root} && PYTHONPATH=src python scripts/build_phase2_taxonomy_report.py --run baseline={baseline_root / 'traces'} --run primary_v4={target_root / 'traces'} --metrics baseline={baseline_root / 'artifacts/metrics.json'} --metrics primary_v4={target_root / 'artifacts/metrics.json'} --out-json {taxonomy_json} --out-md {taxonomy_md}",
        "mine": f"cd {repo_root} && PYTHONPATH=src python -m grc.cli mine --trace-dir {target_root / 'traces'} --out {failures_path}",
        "propose": f"cd {repo_root} && PYTHONPATH=src python -m grc.cli propose --failures {failures_path} --history {history} --out-dir {proposal_root} --top-k-signatures 3 --target-category {target_category} --holdout-category {holdout_category}",
        "target_run": f"cd {repo_root} && bash scripts/run_bfcl_v4_patch.sh \"$GRC_BFCL_MODEL\" {candidate_run_root} 8022 {target_category} {repo_root / 'configs/runtime_bfcl_structured.yaml'} {candidate_dir} {candidate_trace_dir} {candidate_dir} {baseline_root / 'artifacts/metrics.json'}",
        "holdout_run": f"cd {repo_root} && bash scripts/run_bfcl_v4_patch.sh \"$GRC_BFCL_MODEL\" {holdout_run_root} 8012 {holdout_category} {repo_root / 'configs/runtime_bfcl_structured.yaml'} {candidate_dir} {holdout_trace_dir} {holdout_artifact_dir} {holdout_baseline_metrics}",
        "rerun": f"cd {repo_root} && bash scripts/run_bfcl_v4_patch.sh \"$GRC_BFCL_MODEL\" {rerun_root} 8013 {target_category} {repo_root / 'configs/runtime_bfcl_structured.yaml'} {candidate_dir} {rerun_trace_dir} {rerun_artifact_dir} {baseline_root / 'artifacts/metrics.json'}",
        "paired_rerun": f"cd {repo_root} && PYTHONPATH=src python scripts/assess_paired_rerun.py --baseline {baseline_root / 'artifacts/metrics.json'} --primary {candidate_metrics} --rerun {rerun_artifact_dir / 'metrics.json'} --out {candidate_dir / 'paired_rerun.json'}",
        "select": f"cd {repo_root} && PYTHONPATH=src python -m grc.cli select --baseline-metrics {baseline_root / 'artifacts/metrics.json'} --candidate-metrics {candidate_metrics} --candidate-dir {candidate_dir} --rule-path {candidate_rule_path} --accepted-dir {repo_root / 'rules/accepted'} --rejected-dir {repo_root / 'rules/rejected'} --active-dir {repo_root / 'rules/active'} --out {candidate_dir / 'accept.json'}",
    }
    return commands


def _failure_rate_by_label(taxonomy_report: dict[str, Any], *, run_label: str) -> dict[str, float]:
    for run in taxonomy_report.get("runs") or []:
        if isinstance(run, dict) and str(run.get("run")) == run_label:
            return {
                str(row.get("failure_label")): float(row.get("share") or 0.0)
                for row in (run.get("taxonomy_distribution") or [])
                if isinstance(row, dict)
            }
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or plan one minimal Phase-2 evolution iteration.")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--target-category", default="multi_turn_miss_param")
    parser.add_argument("--holdout-category", default="simple_python")
    parser.add_argument("--baseline-run-root", required=True)
    parser.add_argument("--target-run-root", required=True)
    parser.add_argument("--holdout-run-root")
    parser.add_argument("--history", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--optional-rerun-root", action="append", default=[], type=_parse_optional_run)
    parser.add_argument("--allow-missing-rerun", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=1)
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    baseline_root = Path(args.baseline_run_root)
    target_root = Path(args.target_run_root)
    holdout_root = Path(args.holdout_run_root) if args.holdout_run_root else None
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    if not baseline_root.exists():
        raise SystemExit(f"missing baseline run root: {baseline_root}")
    if not target_root.exists():
        raise SystemExit(f"missing target run root: {target_root}")
    if args.execute and not _path_exists(holdout_root):
        raise SystemExit("executable mode requires --holdout-run-root")
    if args.execute and args.holdout_category != "simple_python":
        raise SystemExit("executable mode currently requires simple_python as the clean holdout")
    if args.execute and args.max_candidates != 1:
        raise SystemExit("executable mode currently only supports --max-candidates 1")

    skipped_optional: list[dict[str, Any]] = []
    for label, path in args.optional_rerun_root:
        if path.exists():
            continue
        if args.allow_missing_rerun:
            skipped_optional.append({"run": label, "status": "skipped_missing", "path": str(path)})
            continue
        raise SystemExit(f"missing optional rerun root without --allow-missing-rerun: {label} -> {path}")

    proposal_root = out_root / "proposals"
    proposal_summary_path = proposal_root / "proposal_summary.json"
    planned_command_map = _build_command_plan(
        repo_root=repo_root,
        baseline_root=baseline_root,
        target_root=target_root,
        holdout_root=holdout_root,
        out_root=out_root,
        history=args.history,
        target_category=args.target_category,
        holdout_category=args.holdout_category,
        candidate_dir=None,
    )
    planned_commands = list(planned_command_map.values())

    summary = {
        "mode": "execute" if args.execute else "dry-run",
        "target_category": args.target_category,
        "holdout_category": args.holdout_category,
        "planned_commands": planned_commands,
        "selected_candidate_dir": None,
        "selected_proposal_mode": None,
        "failure_rate_by_label": {},
        "top_failure_signatures": [],
        "proposal_count_by_mode": {},
        "history_reuse_count": 0,
        "new_policy_count": 0,
        "accepted_count": 0,
        "retained_count": 0,
        "rejected_count": 0,
        "target_delta": None,
        "holdout_delta": None,
        "clean_slice_regression": None,
        "skipped_optional_runs": skipped_optional,
    }

    if args.dry_run and not args.execute:
        _json_dump(out_root / "evolution_iteration_summary.json", summary)
        (out_root / "evolution_iteration_summary.md").write_text(
            "# Evolution Iteration Summary\n\n## Planned Commands\n\n" + "\n".join(f"- `{cmd}`" for cmd in planned_commands) + "\n",
            encoding="utf-8",
        )
        return

    for key in ("taxonomy", "mine", "propose"):
        _run_logged_command(planned_command_map[key], step_name=key, out_root=out_root)

    candidate_dir = _select_candidate_dir(proposal_summary_path, args.max_candidates)
    execute_command_map = _build_command_plan(
        repo_root=repo_root,
        baseline_root=baseline_root,
        target_root=target_root,
        holdout_root=holdout_root,
        out_root=out_root,
        history=args.history,
        target_category=args.target_category,
        holdout_category=args.holdout_category,
        candidate_dir=candidate_dir,
    )
    for key in ("target_run", "holdout_run", "rerun", "paired_rerun", "select"):
        _run_logged_command(execute_command_map[key], step_name=key, out_root=out_root)

    taxonomy_report = _load_json(out_root / "taxonomy_report.json")
    proposal_summary = _proposal_summary(proposal_summary_path)
    decision = _load_json(candidate_dir / "accept.json")
    holdout_metrics = _load_json(out_root / "holdout_run" / "artifacts" / "metrics.json")
    holdout_baseline_metrics = _load_json((holdout_root / "artifacts" / "metrics.json") if holdout_root else None)
    holdout_target = _target_metric(holdout_metrics)
    holdout_baseline_target = _target_metric(holdout_baseline_metrics)
    holdout_delta = None
    if holdout_target is not None and holdout_baseline_target is not None:
        holdout_delta = holdout_target - holdout_baseline_target

    proposal_count_by_mode = _proposal_count_by_mode(proposal_summary)
    selected_metadata = _proposal_metadata(candidate_dir)
    decision_code = str(decision.get("decision_code") or "")
    summary.update(
        {
            "planned_commands": list(execute_command_map.values()),
            "selected_candidate_dir": str(candidate_dir),
            "selected_proposal_mode": selected_metadata.get("proposal_mode") or selected_metadata.get("proposal_kind"),
            "failure_rate_by_label": _failure_rate_by_label(taxonomy_report, run_label="primary_v4"),
            "top_failure_signatures": proposal_summary.get("top_failure_signatures") or [],
            "proposal_count_by_mode": proposal_count_by_mode,
            "history_reuse_count": proposal_count_by_mode.get("reuse", 0) + proposal_count_by_mode.get("specialize", 0),
            "new_policy_count": proposal_count_by_mode.get("fresh", 0),
            "accepted_count": 1 if decision_code == "accepted" else 0,
            "retained_count": 1 if decision_code == "retained" else 0,
            "rejected_count": 1 if decision_code not in {"accepted", "retained"} else 0,
            "target_delta": decision.get("target_delta"),
            "holdout_delta": holdout_delta,
            "clean_slice_regression": max(0.0, -(holdout_delta or 0.0)),
        }
    )
    _json_dump(out_root / "evolution_iteration_summary.json", summary)
    (out_root / "evolution_iteration_summary.md").write_text(
        "# Evolution Iteration Summary\n\n"
        f"- Mode: `{summary['mode']}`\n"
        f"- Selected Candidate: `{summary['selected_candidate_dir']}`\n"
        f"- Selected Proposal Mode: `{summary['selected_proposal_mode']}`\n"
        f"- Target Delta: `{summary['target_delta']}`\n"
        f"- Holdout Delta: `{summary['holdout_delta']}`\n"
        f"- Clean Slice Regression: `{summary['clean_slice_regression']}`\n\n"
        "## Planned Commands\n\n"
        + "\n".join(f"- `{cmd}`" for cmd in summary["planned_commands"])
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
