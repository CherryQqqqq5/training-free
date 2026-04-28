#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from bfcl_eval.utils import load_dataset_entry
except Exception:  # pragma: no cover
    load_dataset_entry = None  # type: ignore[assignment]

DEFAULT_PROTOCOL = Path("outputs/artifacts/phase2/memory_operation_dev_smoke_v1/memory_operation_dev_smoke_protocol.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/memory_operation_dev_smoke_v1/memory_operation_smoke_snapshot_preflight.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/memory_operation_dev_smoke_v1/memory_operation_smoke_snapshot_preflight.md")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _entries_by_id(category: str) -> dict[str, dict[str, Any]]:
    if load_dataset_entry is None:
        return {}
    try:
        entries = load_dataset_entry(category, include_prereq=True)  # type: ignore[misc]
    except TypeError:
        entries = load_dataset_entry(category)  # type: ignore[misc]
    except Exception:
        return {}
    return {str(entry.get("id")): entry for entry in entries if isinstance(entry, dict) and entry.get("id")}


def _normalize_ids_payload(data: Any) -> dict[str, list[str]]:
    if not isinstance(data, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for category, ids in data.items():
        if isinstance(ids, list):
            normalized[str(category)] = [str(item) for item in ids]
    return normalized


def _load_run_ids(run_root: Path) -> dict[str, list[str]]:
    path = run_root / "bfcl" / "test_case_ids_to_generate.json"
    if not path.exists():
        return {}
    return _normalize_ids_payload(json.loads(path.read_text(encoding="utf-8")))


def evaluate(protocol_path: Path = DEFAULT_PROTOCOL, baseline_run_root: Path | None = None, candidate_run_root: Path | None = None) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    protocol = _load_json(protocol_path)
    selected = protocol.get("target_ids_by_category") or {}
    generation = protocol.get("generation_ids_by_category") or {}
    checks: list[dict[str, Any]] = []

    if protocol.get("candidate_commands") != [] or protocol.get("planned_commands") != []:
        failures.append({"check": "protocol_has_no_commands"})

    for category, target_ids in selected.items():
        entries = _entries_by_id(category)
        generation_ids = set(str(item) for item in generation.get(category) or [])
        if not entries:
            failures.append({"check": "bfcl_memory_metadata_available", "category": category})
            continue
        for target_id in target_ids:
            entry = entries.get(str(target_id))
            deps = [str(dep_id) for dep_id in (entry or {}).get("depends_on") or []]
            missing_deps = [dep_id for dep_id in deps if dep_id not in generation_ids]
            has_first_prereq = any("prereq" in dep_id and dep_id.endswith("-0") for dep_id in deps)
            target_in_generation = str(target_id) in generation_ids
            check = {
                "category": category,
                "target_id": target_id,
                "target_in_generation_ids": target_in_generation,
                "dependency_count": len(deps),
                "missing_dependency_ids": missing_deps,
                "has_first_prereq_entry": has_first_prereq,
                "snapshot_safe": target_in_generation and not missing_deps and has_first_prereq,
            }
            checks.append(check)
            if not check["snapshot_safe"]:
                failures.append({"check": "memory_snapshot_dependency_closure", **check})

    expected_generation = _normalize_ids_payload(generation)
    run_id_checks: list[dict[str, Any]] = []
    for label, run_root in (("baseline", baseline_run_root), ("candidate", candidate_run_root)):
        if run_root is None:
            continue
        actual = _load_run_ids(run_root)
        matches = actual == expected_generation
        check = {
            "label": label,
            "run_root": str(run_root),
            "run_ids_path": str(run_root / "bfcl" / "test_case_ids_to_generate.json"),
            "run_ids_present": bool(actual),
            "matches_protocol_generation_ids": matches,
            "expected_generation_case_count": sum(len(ids) for ids in expected_generation.values()),
            "actual_generation_case_count": sum(len(ids) for ids in actual.values()),
        }
        run_id_checks.append(check)
        if not matches:
            failures.append({"check": "run_ids_match_protocol_generation_ids", **check})
    if baseline_run_root is not None and candidate_run_root is not None:
        baseline_ids = _load_run_ids(baseline_run_root)
        candidate_ids = _load_run_ids(candidate_run_root)
        if baseline_ids != candidate_ids:
            failures.append({
                "check": "baseline_candidate_run_ids_match",
                "baseline_run_root": str(baseline_run_root),
                "candidate_run_root": str(candidate_run_root),
            })

    passed = not failures
    return {
        "report_scope": "memory_operation_smoke_snapshot_preflight",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "protocol_path": str(protocol_path),
        "memory_snapshot_preflight_passed": passed,
        "target_case_count": sum(len(v) for v in selected.values() if isinstance(v, list)),
        "generation_case_count": sum(len(v) for v in generation.values() if isinstance(v, list)),
        "prereq_case_count": sum(1 for ids in generation.values() if isinstance(ids, list) for case_id in ids if "prereq" in str(case_id)),
        "checks": checks,
        "run_id_checks": run_id_checks,
        "failure_count": len(failures),
        "first_failure": failures[0] if failures else None,
        "failures": failures[:50],
        "candidate_commands": [],
        "planned_commands": [],
        "next_required_action": "request_explicit_memory_only_dev_smoke_execution_approval" if passed else "fix_memory_snapshot_dependency_closure_before_smoke",
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Memory Operation Smoke Snapshot Preflight",
        "",
        f"- Passed: `{report['memory_snapshot_preflight_passed']}`",
        f"- Target case count: `{report['target_case_count']}`",
        f"- Generation case count: `{report['generation_case_count']}`",
        f"- Prereq case count: `{report['prereq_case_count']}`",
        f"- Failure count: `{report['failure_count']}`",
        f"- First failure: `{report['first_failure']}`",
        f"- Candidate commands: `{report['candidate_commands']}`",
        f"- Planned commands: `{report['planned_commands']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "This is an offline preflight. It verifies BFCL memory prerequisite closure before any smoke execution.",
        "",
    ])


def write_outputs(report: dict[str, Any], out_path: Path, md_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--baseline-run-root", type=Path)
    parser.add_argument("--candidate-run-root", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.protocol, args.baseline_run_root, args.candidate_run_root)
    write_outputs(report, args.output, args.markdown_output)
    if args.compact:
        keys = [
            "memory_snapshot_preflight_passed",
            "target_case_count",
            "generation_case_count",
            "prereq_case_count",
            "failure_count",
            "first_failure",
            "candidate_commands",
            "planned_commands",
            "next_required_action",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    if args.strict and not report["memory_snapshot_preflight_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
