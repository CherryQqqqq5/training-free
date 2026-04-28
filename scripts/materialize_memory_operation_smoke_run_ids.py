#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_PROTOCOL = Path("outputs/artifacts/phase2/memory_operation_dev_smoke_v1/memory_operation_dev_smoke_protocol.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/memory_operation_dev_smoke_v1/memory_operation_smoke_run_ids_materialization.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/memory_operation_dev_smoke_v1/memory_operation_smoke_run_ids_materialization.md")


def _load_protocol(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _write_run_ids(run_root: Path, generation_ids_by_category: dict[str, list[str]]) -> dict[str, Any]:
    path = run_root / "bfcl" / "test_case_ids_to_generate.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(generation_ids_by_category, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return {
        "run_root": str(run_root),
        "path": str(path),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "case_count": sum(len(ids) for ids in generation_ids_by_category.values()),
    }


def materialize(protocol_path: Path, baseline_run_root: Path, candidate_run_root: Path) -> dict[str, Any]:
    protocol = _load_protocol(protocol_path)
    generation = protocol.get("generation_ids_by_category") or {}
    normalized = {str(category): [str(case_id) for case_id in ids] for category, ids in generation.items() if isinstance(ids, list)}
    baseline = _write_run_ids(baseline_run_root, normalized)
    candidate = _write_run_ids(candidate_run_root, normalized)
    pair_hash_match = baseline["sha256"] == candidate["sha256"]
    return {
        "report_scope": "memory_operation_smoke_run_ids_materialization",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "protocol_path": str(protocol_path),
        "target_case_count": int(protocol.get("target_case_count") or protocol.get("selected_case_count") or 0),
        "generation_case_count": sum(len(ids) for ids in normalized.values()),
        "prereq_case_count": sum(1 for ids in normalized.values() for case_id in ids if "prereq" in case_id),
        "generation_ids_hash": _stable_hash(normalized),
        "baseline": baseline,
        "candidate": candidate,
        "baseline_candidate_run_ids_hash_match": pair_hash_match,
        "candidate_commands": [],
        "planned_commands": [],
        "materialization_ready": bool(normalized and pair_hash_match),
        "next_required_action": "run_snapshot_preflight_with_run_roots" if normalized and pair_hash_match else "fix_protocol_generation_ids_before_smoke",
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Memory Operation Smoke Run IDs Materialization",
        "",
        f"- Ready: `{report['materialization_ready']}`",
        f"- Target case count: `{report['target_case_count']}`",
        f"- Generation case count: `{report['generation_case_count']}`",
        f"- Prereq case count: `{report['prereq_case_count']}`",
        f"- Generation IDs hash: `{report['generation_ids_hash']}`",
        f"- Baseline run ids hash: `{report['baseline']['sha256']}`",
        f"- Candidate run ids hash: `{report['candidate']['sha256']}`",
        f"- Baseline/candidate hash match: `{report['baseline_candidate_run_ids_hash_match']}`",
        f"- Candidate commands: `{report['candidate_commands']}`",
        f"- Planned commands: `{report['planned_commands']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "This writes only BFCL run-id manifests for a pre-approved smoke. It does not run BFCL/model/scorer.",
        "",
    ])


def write_outputs(report: dict[str, Any], out_path: Path, md_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--baseline-run-root", type=Path, required=True)
    parser.add_argument("--candidate-run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = materialize(args.protocol, args.baseline_run_root, args.candidate_run_root)
    write_outputs(report, args.output, args.markdown_output)
    if args.compact:
        keys = [
            "materialization_ready",
            "target_case_count",
            "generation_case_count",
            "prereq_case_count",
            "generation_ids_hash",
            "baseline_candidate_run_ids_hash_match",
            "candidate_commands",
            "planned_commands",
            "next_required_action",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    return 0 if report["materialization_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
