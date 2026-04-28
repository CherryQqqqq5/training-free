#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts import diagnose_policy_conversion_opportunities as opportunities

DEFAULT_TRACE_ROOT = Path("outputs/phase2_validation/required_next_tool_choice_v1")
DEFAULT_MANIFEST = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_policy_candidate_manifest.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_negative_control_audit.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_negative_control_audit.md")

NEGATIVE_BUCKETS = {
    "not_no_tool_policy_failure": "no_toolless_failure_slice",
    "no_prior_observation_for_postcondition_policy": "no_prior_observation",
    "no_schema_local_recommended_tool": "missing_recommended_tool",
    "no_rule_hit": "no_rule_hit",
    "no_tools_available": "no_tools_available",
    "postcondition_already_satisfied": "postcondition_already_satisfied",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _negative_bucket(row: dict[str, Any]) -> str | None:
    reason = str(row.get("rejection_reason") or "")
    return NEGATIVE_BUCKETS.get(reason)


def _record_pointer(row: dict[str, Any]) -> str:
    return str(row.get("trace_relative_path") or row.get("trace_id") or "unknown")


def evaluate(trace_root: Path = DEFAULT_TRACE_ROOT, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = _load(manifest_path)
    records = [
        row
        for path in opportunities._trace_files(trace_root)  # type: ignore[attr-defined]
        if (row := opportunities._record_from_trace(path, trace_root)) is not None  # type: ignore[attr-defined]
    ]
    negative_records = []
    bucket_counts: Counter[str] = Counter()
    activation_counts: Counter[str] = Counter()
    sample_by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        bucket = _negative_bucket(row)
        if bucket is None:
            continue
        activated = bool(row.get("candidate_ready"))
        bucket_counts[bucket] += 1
        if activated:
            activation_counts[bucket] += 1
        compact = {
            "trace_pointer": _record_pointer(row),
            "negative_control_bucket": bucket,
            "rejection_reason": row.get("rejection_reason"),
            "policy_candidate_would_activate": activated,
            "postcondition_gap": row.get("postcondition_gap"),
            "recommended_tools": row.get("recommended_tools") or [],
            "failure_labels": row.get("failure_labels") or [],
            "request_predicates": row.get("request_predicates") or [],
        }
        negative_records.append(compact)
        if len(sample_by_bucket[bucket]) < 5:
            sample_by_bucket[bucket].append(compact)
    total_negative = sum(bucket_counts.values())
    total_activations = sum(activation_counts.values())
    postcondition_satisfied_evaluable = bucket_counts.get("postcondition_already_satisfied", 0) > 0
    controls_ready = bool(total_negative) and total_activations == 0 and manifest.get("runtime_enabled") is False and postcondition_satisfied_evaluable
    return {
        "report_scope": "postcondition_guided_policy_negative_control_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "trace_root": str(trace_root),
        "manifest_path": str(manifest_path),
        "negative_control_audit_ready": controls_ready,
        "candidate_manifest_runtime_enabled": manifest.get("runtime_enabled"),
        "candidate_manifest_commands_empty": manifest.get("candidate_commands") == [] and manifest.get("planned_commands") == [],
        "trace_count": len(records),
        "negative_control_trace_count": total_negative,
        "negative_control_activation_count": total_activations,
        "negative_control_activation_rate": (total_activations / total_negative) if total_negative else None,
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "bucket_activation_counts": dict(sorted(activation_counts.items())),
        "postcondition_already_satisfied_control_evaluable": postcondition_satisfied_evaluable,
        "postcondition_already_satisfied_control_note": "satisfied-postcondition witness is extracted from prior tool outputs via schema-local witness key aliases" if postcondition_satisfied_evaluable else "current trace artifacts do not expose a reliable satisfied-postcondition witness predicate; this control must be added before runtime enablement",
        "sample_negative_controls": {key: value for key, value in sorted(sample_by_bucket.items())},
        "candidate_commands": [],
        "planned_commands": [],
        "next_required_action": "review_negative_controls_before_runtime_compiler" if controls_ready else "add_postcondition_satisfied_witness_control_before_runtime_enablement",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Postcondition-Guided Policy Negative-Control Audit",
        "",
        f"- Ready: `{report['negative_control_audit_ready']}`",
        f"- Trace count: `{report['trace_count']}`",
        f"- Negative-control trace count: `{report['negative_control_trace_count']}`",
        f"- Activation count: `{report['negative_control_activation_count']}`",
        f"- Activation rate: `{report['negative_control_activation_rate']}`",
        f"- Bucket counts: `{report['bucket_counts']}`",
        f"- Postcondition-satisfied control evaluable: `{report['postcondition_already_satisfied_control_evaluable']}`",
        "",
        "Offline audit only. This does not enable runtime policy execution or authorize BFCL/model/scorer runs.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.trace_root, args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "negative_control_audit_ready",
            "negative_control_trace_count",
            "negative_control_activation_count",
            "negative_control_activation_rate",
            "bucket_counts",
            "postcondition_already_satisfied_control_evaluable",
            "next_required_action",
        ]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
