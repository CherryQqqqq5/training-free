#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_OUTPUT = DEFAULT_ROOT / "m27r_not_activated_audit.json"
DEFAULT_MD = DEFAULT_ROOT / "m27r_not_activated_audit.md"


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


def _guard_reason(row: dict[str, Any]) -> str | None:
    if row.get("case_final_guard_reason"):
        return str(row.get("case_final_guard_reason"))
    reasons = row.get("guard_rejection_reasons") or []
    return str(reasons[0]) if reasons else None


def classify_not_activated(case_row: dict[str, Any], guard_row: dict[str, Any] | None = None) -> dict[str, Any]:
    baseline_success = bool(case_row.get("baseline_success"))
    candidate_success = bool(case_row.get("candidate_success"))
    before_plan = (guard_row or {}).get("before_guard_plan") if guard_row else {}
    after_plan = (guard_row or {}).get("after_guard_plan") if guard_row else {}
    before_candidate_exists = bool((before_plan or {}).get("activated") and (before_plan or {}).get("selected_action_candidate"))
    after_candidate_exists = bool((after_plan or {}).get("activated") and (after_plan or {}).get("selected_action_candidate"))
    target_failure_trace = bool((guard_row or {}).get("target_failure_trace"))
    should_proxy = (not baseline_success and not candidate_success and (before_candidate_exists or target_failure_trace))
    if should_proxy:
        classification = "not_activated_false_negative"
    elif baseline_success and candidate_success and not before_candidate_exists:
        classification = "not_activated_true_negative"
    else:
        classification = "not_activated_unknown"
    return {
        "case_id": case_row.get("case_id"),
        "baseline_success": baseline_success,
        "candidate_success": candidate_success,
        "source_failure_family": (guard_row or {}).get("target_failure_trace"),
        "available_schema_tools": sorted(((before_plan or {}).get("recommended_tools") or [])),
        "candidate_existed_before_guard": before_candidate_exists,
        "candidate_existed_after_guard": after_candidate_exists,
        "guard_status": (guard_row or {}).get("guard_status") or ("guard_kept" if after_candidate_exists else "unknown"),
        "guard_rejected_reason": _guard_reason(guard_row or {}),
        "blocked_reason": case_row.get("blocked_reason"),
        "should_have_activated_proxy": should_proxy,
        "classification": classification,
    }


def evaluate_not_activated(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    rows = _read_jsonl(root / "subset_case_report.jsonl")
    guards = _guard_cases(root)
    cases = [classify_not_activated(row, guards.get(str(row.get("case_id")))) for row in rows if not row.get("policy_plan_activated")]
    distribution = Counter(str(case.get("classification")) for case in cases)
    guard_reasons = Counter(str(case.get("guard_rejected_reason") or "none") for case in cases)
    report = {
        "report_scope": "m2_7r_not_activated_audit",
        "artifact_root": str(root),
        "not_activated_case_count": len(cases),
        "classification_distribution": dict(sorted(distribution.items())),
        "guard_rejected_reason_distribution": dict(sorted(guard_reasons.items())),
        "cases": cases,
        "unknown_count": distribution.get("not_activated_unknown", 0),
        "m27r_not_activated_audit_ready": len(cases) > 0 and sum(distribution.values()) == len(cases),
        "diagnostic": {"no_bfcl_rerun": True, "classification_is_proxy_not_gold": True},
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7r Not-Activated Audit",
        "",
        f"- Ready: `{report.get('m27r_not_activated_audit_ready')}`",
        f"- Not activated cases: `{report.get('not_activated_case_count')}`",
        f"- Classification distribution: `{report.get('classification_distribution')}`",
        "",
        "| Case | Classification | Before Candidate | Guard Reason | Baseline | Candidate |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for case in report.get("cases") or []:
        lines.append(f"| `{case['case_id']}` | `{case['classification']}` | `{case['candidate_existed_before_guard']}` | `{case.get('guard_rejected_reason')}` | `{case['baseline_success']}` | `{case['candidate_success']}` |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose not-activated M2.7r cases.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_not_activated(args.root)
    _write_json(args.output, report)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "not_activated_case_count": report.get("not_activated_case_count"),
            "classification_distribution": report.get("classification_distribution"),
            "unknown_count": report.get("unknown_count"),
            "m27r_not_activated_audit_ready": report.get("m27r_not_activated_audit_ready"),
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
