#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_OUTPUT = DEFAULT_ROOT / "m27r_arg_realization.json"
DEFAULT_MD = DEFAULT_ROOT / "m27r_arg_realization.md"


def _read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _guard_cases(root: Path) -> dict[str, dict[str, Any]]:
    data = _read_json(root / "m27i_guard_preflight.json", default={})
    return {str(row.get("case_id")): row for row in data.get("cases") or [] if isinstance(row, dict) and row.get("case_id")}


def _candidate_from_guard(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    after_plan = row.get("after_guard_plan") if isinstance(row.get("after_guard_plan"), dict) else {}
    candidate = after_plan.get("selected_action_candidate") if isinstance(after_plan.get("selected_action_candidate"), dict) else {}
    return candidate or {}


def _binding_sources(candidate: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    bindings = candidate.get("arg_bindings") if isinstance(candidate.get("arg_bindings"), dict) else {}
    for binding in bindings.values():
        if isinstance(binding, dict) and binding.get("source"):
            sources.append(str(binding.get("source")))
    if candidate.get("binding_source"):
        sources.append(str(candidate.get("binding_source")))
    return sorted(set(sources))


def _schema_arg_names(candidate: dict[str, Any]) -> list[str]:
    args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
    return sorted(str(key) for key in args)


def classify_arg_case(case_row: dict[str, Any], guard_row: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate = _candidate_from_guard(guard_row)
    candidate_args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
    tool_match = bool(case_row.get("recommended_tool_match"))
    raw_match = bool(case_row.get("raw_normalized_arg_match"))
    final_match = bool(case_row.get("final_normalized_arg_match"))
    candidate_arg_validity = "unknown"
    if not candidate:
        candidate_arg_validity = "missing_candidate"
    elif not candidate_args:
        candidate_arg_validity = "missing_candidate_args"
    elif not tool_match:
        candidate_arg_validity = "candidate_tool_mismatch_proxy"
    else:
        candidate_arg_validity = "plausible_candidate_args"
    if raw_match or final_match:
        failure_reason = "arg_realized"
    elif not tool_match:
        failure_reason = "tool_mismatch_before_arg_realization"
    elif candidate_arg_validity in {"missing_candidate", "missing_candidate_args"}:
        failure_reason = "candidate_arg_wrong"
    else:
        failure_reason = "emitted_arg_wrong_or_guidance_not_followed"
    return {
        "case_id": case_row.get("case_id"),
        "selected_tool": case_row.get("selected_next_tool"),
        "candidate_args": candidate_args,
        "emitted_args": None,
        "arg_binding_source": _binding_sources(candidate),
        "candidate_arg_validity": candidate_arg_validity,
        "emitted_arg_match": raw_match or final_match,
        "schema_arg_names": _schema_arg_names(candidate),
        "normalization_result": {
            "raw_normalized_arg_match": raw_match,
            "final_normalized_arg_match": final_match,
            "raw_strict_arg_match": bool(case_row.get("raw_strict_arg_match")),
            "final_strict_arg_match": bool(case_row.get("final_strict_arg_match")),
        },
        "failure_reason": failure_reason,
        "repair_kinds": case_row.get("repair_kinds") or [],
        "baseline_success": bool(case_row.get("baseline_success")),
        "candidate_success": bool(case_row.get("candidate_success")),
    }


def evaluate_arg_realization(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    rows = _read_jsonl(root / "subset_case_report.jsonl")
    guards = _guard_cases(root)
    target_rows = [row for row in rows if row.get("policy_plan_activated") and not row.get("raw_normalized_arg_match")]
    cases = [classify_arg_case(row, guards.get(str(row.get("case_id")))) for row in target_rows]
    distribution = Counter(str(case.get("failure_reason")) for case in cases)
    report = {
        "report_scope": "m2_7r_arg_realization_audit",
        "artifact_root": str(root),
        "activated_arg_mismatch_case_count": len(cases),
        "failure_reason_distribution": dict(sorted(distribution.items())),
        "cases": cases,
        "m27r_arg_realization_audit_ready": len(cases) > 0 and sum(distribution.values()) == len(cases),
        "diagnostic": {"no_bfcl_rerun": True, "emitted_args_are_not_available_in_compact_case_report": True},
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7r Arg Realization Audit",
        "",
        f"- Ready: `{report.get('m27r_arg_realization_audit_ready')}`",
        f"- Activated arg mismatch cases: `{report.get('activated_arg_mismatch_case_count')}`",
        f"- Failure reason distribution: `{report.get('failure_reason_distribution')}`",
        "",
        "| Case | Tool | Failure Reason | Candidate Arg Validity | Binding Source | Raw Match | Final Match |",
        "| --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for case in report.get("cases") or []:
        norm = case.get("normalization_result") or {}
        lines.append(f"| `{case['case_id']}` | `{case.get('selected_tool')}` | `{case['failure_reason']}` | `{case['candidate_arg_validity']}` | `{case.get('arg_binding_source')}` | `{norm.get('raw_normalized_arg_match')}` | `{norm.get('final_normalized_arg_match')}` |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose M2.7r argument realization failures.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_arg_realization(args.root)
    _write_json(args.output, report)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "activated_arg_mismatch_case_count": report.get("activated_arg_mismatch_case_count"),
            "failure_reason_distribution": report.get("failure_reason_distribution"),
            "m27r_arg_realization_audit_ready": report.get("m27r_arg_realization_audit_ready"),
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
