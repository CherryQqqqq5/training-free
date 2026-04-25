#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scripts.check_m27f_artifact_completeness import DEFAULT_ROOT, evaluate_artifact_completeness  # noqa: E402

DEFAULT_OUTPUT = DEFAULT_ROOT / "m27l_trace_completeness_preflight.json"
DEFAULT_MARKDOWN_OUTPUT = DEFAULT_ROOT / "m27l_trace_completeness_preflight.md"


def _first_failed_run(runs: dict[str, Any]) -> str | None:
    for name in ("baseline", "candidate"):
        run = runs.get(name) if isinstance(runs.get(name), dict) else {}
        if not run.get("gate_passed"):
            return name
    return None


def evaluate_m27l_trace_completeness(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    base = evaluate_artifact_completeness(
        root,
        require_baseline_prompt_traces=True,
        require_candidate_prompt_traces=True,
    )
    runs = base.get("runs") if isinstance(base.get("runs"), dict) else {}
    missing_trace_ids = {
        name: list((run if isinstance(run, dict) else {}).get("missing_trace_ids") or [])
        for name, run in runs.items()
    }
    missing_result_ids = {
        name: list((run if isinstance(run, dict) else {}).get("missing_result_ids") or [])
        for name, run in runs.items()
    }
    missing_effective_score_ids = {
        name: list((run if isinstance(run, dict) else {}).get("missing_effective_score_ids") or [])
        for name, run in runs.items()
    }
    passed = bool(base.get("m2_7f_artifact_completeness_passed"))
    first_failed_run = _first_failed_run(runs)
    first_failed_criterion = None
    if not passed:
        if any(missing_trace_ids.values()):
            first_failed_criterion = "missing_prompt_prefix_trace_ids"
        elif any(missing_result_ids.values()):
            first_failed_criterion = "missing_result_ids"
        elif any(missing_effective_score_ids.values()):
            first_failed_criterion = "missing_effective_score_ids"
        else:
            first_failed_criterion = "artifact_completeness"
    return {
        "title": "M2.7l Trace Completeness Preflight",
        "artifact_root": str(root),
        "selected_case_count": base.get("selected_case_count"),
        "m2_7l_trace_completeness_passed": passed,
        "case_level_gate_allowed": passed,
        "missing_trace_ids": missing_trace_ids,
        "missing_result_ids": missing_result_ids,
        "missing_effective_score_ids": missing_effective_score_ids,
        "runs": runs,
        "diagnostic": {
            "checker_scope": "m2_7l_prompt_prefix_trace_and_effective_score_result_coverage",
            "first_failed_run": first_failed_run,
            "first_failed_criterion": first_failed_criterion,
            "case_level_report_is_durable": passed,
            "do_not_compute_case_level_gate_until_passed": not passed,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# M2.7l Trace Completeness Preflight",
        "",
        f"- Passed: `{report.get('m2_7l_trace_completeness_passed')}`",
        f"- Case-level gate allowed: `{report.get('case_level_gate_allowed')}`",
        f"- Selected cases: `{report.get('selected_case_count')}`",
        f"- Missing trace ids: `{report.get('missing_trace_ids')}`",
        f"- Missing result ids: `{report.get('missing_result_ids')}`",
        f"- Missing effective score ids: `{report.get('missing_effective_score_ids')}`",
        f"- First failed criterion: `{(report.get('diagnostic') or {}).get('first_failed_criterion')}`",
        "",
        "This preflight is a hard durability gate for case-level attribution. If it fails, downstream M2.7f case-level performance gates are diagnostic only.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Check M2.7l strict prompt-prefix trace completeness.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_m27l_trace_completeness(args.root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        payload = {k: report.get(k) for k in (
            "m2_7l_trace_completeness_passed",
            "case_level_gate_allowed",
            "selected_case_count",
            "missing_trace_ids",
            "missing_result_ids",
            "missing_effective_score_ids",
            "diagnostic",
        )}
    else:
        payload = report
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if report.get("m2_7l_trace_completeness_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
