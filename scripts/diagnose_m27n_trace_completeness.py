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

from scripts.check_m27l_trace_completeness_preflight import evaluate_m27l_trace_completeness  # noqa: E402
from scripts.run_phase2_target_subset import (  # noqa: E402
    _read_jsonl,
    _result_failure_reasons,
    _result_json_path,
    _result_rows_by_case,
    _result_step_counts,
    _score_json_path,
    _score_rows_by_case,
    _trace_paths_by_case,
    _trace_paths_by_case_from_prompt_prefix_with_diagnostics,
    _user_texts_from_trace_payload,
)

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_OUTPUT = DEFAULT_ROOT / "m27n_trace_completeness.json"
DEFAULT_MARKDOWN_OUTPUT = DEFAULT_ROOT / "m27n_trace_completeness.md"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _score_case_ids(run_root: Path, category: str) -> set[str]:
    path = _score_json_path(run_root, category)
    if not path:
        return set()
    return {str(row.get("id")) for row in _read_jsonl(path) if isinstance(row.get("id"), str)}


def _trace_user_prefixes(paths: list[Path], limit: int = 3) -> list[list[str]]:
    prefixes: list[list[str]] = []
    for path in paths[:limit]:
        payload = _read_json(path)
        if payload:
            prefixes.append(_user_texts_from_trace_payload(payload)[:3])
    return prefixes


def _case_ambiguity(case_id: str, diagnostic: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in diagnostic.get("resolved_ambiguous_match_sets") or []:
        matches = [str(item) for item in row.get("matches") or []]
        if case_id in matches:
            rows.append({"status": "resolved", **row})
    for row in diagnostic.get("unresolved_ambiguous_match_sets") or []:
        matches = [str(item) for item in row.get("matches") or []]
        if case_id in matches:
            rows.append({"status": "unresolved", **row})
    return rows


def _branch(
    *,
    result_present: bool,
    result_exception: bool,
    prompt_prefix_present: bool,
    mtime_present: bool,
    raw_candidate_count: int,
    ambiguity: list[dict[str, Any]],
) -> str:
    if not result_present:
        return "partial_eval_missing_result"
    if result_exception:
        return "handler_exception"
    if prompt_prefix_present and any(row.get("status") == "resolved" for row in ambiguity):
        return "prompt_prefix_ambiguous_resolved"
    if any(row.get("status") == "unresolved" for row in ambiguity):
        return "prompt_prefix_ambiguous_unresolved"
    if prompt_prefix_present:
        return "prompt_prefix_trace_present"
    if raw_candidate_count > 0:
        return "prompt_prefix_mapping_failed"
    if mtime_present:
        return "prompt_prefix_missing_mtime_present"
    return "trace_write_failure"


def _run_case_reports(run_root: Path, category: str, selected_ids: list[str]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    prompt_groups, prompt_diag = _trace_paths_by_case_from_prompt_prefix_with_diagnostics(
        source_run_root=run_root,
        category=category,
        selected_ids=selected_ids,
    )
    counts = _result_step_counts(run_root, category, selected_ids)
    mtime_groups = _trace_paths_by_case(run_root / "traces", counts)
    score_ids = _score_case_ids(run_root, category)
    result_rows = _result_rows_by_case(run_root, category)
    result_failures = _result_failure_reasons(run_root, category)
    reports: dict[str, dict[str, Any]] = {}
    for case_id in selected_ids:
        raw_groups, _ = _trace_paths_by_case_from_prompt_prefix_with_diagnostics(
            source_run_root=run_root,
            category=category,
            selected_ids=[case_id],
        )
        prompt_paths = list(prompt_groups.get(case_id) or [])
        mtime_paths = list(mtime_groups.get(case_id) or [])
        raw_paths = list(raw_groups.get(case_id) or [])
        ambiguity = _case_ambiguity(case_id, prompt_diag)
        result_present = case_id in result_rows
        result_exception = case_id in result_failures
        reports[case_id] = {
            "score_row_present": case_id in score_ids,
            "result_row_present": result_present,
            "result_exception": result_failures.get(case_id),
            "prompt_prefix_trace_present": bool(prompt_paths),
            "mtime_trace_present": bool(mtime_paths),
            "prompt_prefix_trace_count": len(prompt_paths),
            "mtime_trace_count": len(mtime_paths),
            "expected_result_step_count": counts.get(case_id),
            "raw_trace_candidate_count": len(raw_paths),
            "ambiguous_prompt_prefix_matches": ambiguity,
            "trace_request_user_prefix": _trace_user_prefixes(prompt_paths or raw_paths),
            "candidate_trace_write_count": len(prompt_paths),
            "proxy_status_code": None,
            "handler_exception": bool(result_exception),
            "trace_write_failure": result_present and not raw_paths,
            "diagnostic_branch": _branch(
                result_present=result_present,
                result_exception=result_exception,
                prompt_prefix_present=bool(prompt_paths),
                mtime_present=bool(mtime_paths),
                raw_candidate_count=len(raw_paths),
                ambiguity=ambiguity,
            ),
        }
    return prompt_diag, reports


def evaluate_trace_completeness(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    manifest = _read_json(root / "paired_subset_manifest.json")
    selected_ids = [str(case_id) for case_id in manifest.get("selected_case_ids") or []]
    category = str(manifest.get("category") or "multi_turn_miss_param")
    runs: dict[str, Any] = {}
    for run_name in ("baseline", "candidate"):
        prompt_diag, cases = _run_case_reports(root / run_name, category, selected_ids)
        missing = [case_id for case_id in selected_ids if not cases.get(case_id, {}).get("prompt_prefix_trace_present")]
        unresolved = [row for row in prompt_diag.get("unresolved_ambiguous_match_sets") or []]
        runs[run_name] = {
            "missing_trace_ids": missing,
            "prompt_prefix_ambiguity_unresolved": bool(unresolved),
            "unresolved_ambiguous_match_sets": unresolved,
            "prompt_prefix_mapping_diagnostic": prompt_diag,
            "cases": cases,
        }
    trace_preflight = evaluate_m27l_trace_completeness(root)
    passed = bool(trace_preflight.get("m2_7l_trace_completeness_passed")) and not any(
        run.get("prompt_prefix_ambiguity_unresolved") for run in runs.values()
    )
    return {
        "title": "M2.7n Trace Completeness Diagnostic",
        "artifact_root": str(root),
        "category": category,
        "selected_case_count": len(selected_ids),
        "m2_7n_trace_completeness_passed": passed,
        "case_level_gate_allowed": passed,
        "runs": runs,
        "trace_preflight": trace_preflight,
        "diagnostic": {
            "checker_scope": "m2_7n_trace_completeness_no_bfcl_no_model_call",
            "first_failed_criterion": None if passed else ("prompt_prefix_ambiguous_unresolved" if any(run.get("prompt_prefix_ambiguity_unresolved") for run in runs.values()) else "missing_prompt_prefix_trace_ids"),
            "do_not_rerun_m2_7f_until_passed": not passed,
            "recommended_next_focus": "none" if passed else "trace_completeness",
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7n Trace Completeness Diagnostic",
        "",
        f"- Passed: `{report.get('m2_7n_trace_completeness_passed')}`",
        f"- Case-level gate allowed: `{report.get('case_level_gate_allowed')}`",
        f"- First failed criterion: `{(report.get('diagnostic') or {}).get('first_failed_criterion')}`",
        "",
        "| Run | Missing Trace IDs | Unresolved Ambiguity |",
        "| --- | --- | ---: |",
    ]
    for name, run in (report.get("runs") or {}).items():
        lines.append(
            f"| {name} | `{run.get('missing_trace_ids')}` | `{run.get('prompt_prefix_ambiguity_unresolved')}` |"
        )
    lines.extend(["", "## Candidate Case Branches", "", "| Case | Branch | Prefix Traces | Raw Candidates | Ambiguous |", "| --- | --- | ---: | ---: | --- |"])
    candidate = ((report.get("runs") or {}).get("candidate") or {}).get("cases") or {}
    for case_id, row in candidate.items():
        if row.get("diagnostic_branch") == "prompt_prefix_trace_present":
            continue
        lines.append(
            "| {case_id} | {branch} | {prefix} | {raw} | {ambiguous} |".format(
                case_id=case_id,
                branch=row.get("diagnostic_branch"),
                prefix=row.get("prompt_prefix_trace_count"),
                raw=row.get("raw_trace_candidate_count"),
                ambiguous=bool(row.get("ambiguous_prompt_prefix_matches")),
            )
        )
    lines.extend(["", "This diagnostic is offline only. It does not run BFCL or call an upstream model.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose M2.7n prompt-prefix trace completeness without BFCL/model calls.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_trace_completeness(args.artifact_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        payload = {
            "m2_7n_trace_completeness_passed": report.get("m2_7n_trace_completeness_passed"),
            "case_level_gate_allowed": report.get("case_level_gate_allowed"),
            "runs": {
                name: {
                    "missing_trace_ids": run.get("missing_trace_ids"),
                    "prompt_prefix_ambiguity_unresolved": run.get("prompt_prefix_ambiguity_unresolved"),
                }
                for name, run in (report.get("runs") or {}).items()
            },
            "diagnostic": report.get("diagnostic"),
        }
    else:
        payload = report
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if report.get("m2_7n_trace_completeness_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
