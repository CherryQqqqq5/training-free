#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_ROOT = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
DEFAULT_RUNTIME_DIR = Path("outputs/artifacts/phase2/memory_operation_obligation_runtime_smoke_v1/first_pass")
DEFAULT_OUT_DIR = Path("outputs/artifacts/phase2/memory_operation_dev_smoke_v1")
DEFAULT_CATEGORIES = ["memory_kv", "memory_rec_sum"]
PROVIDER = "novacode"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _ids_for_category(source_root: Path, category: str) -> list[str]:
    path = source_root / category / "baseline" / "bfcl" / "test_case_ids_to_generate.json"
    data = _load_json(path)
    if isinstance(data, dict):
        ids = data.get("test_case_ids") or data.get("ids")
        if ids is None and len(data) == 1:
            ids = next(iter(data.values()))
    else:
        ids = data
    return [str(item) for item in ids or []]


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_payload(payload: Any) -> str:
    stable = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(stable).hexdigest()


def evaluate(source_root: Path = DEFAULT_SOURCE_ROOT, runtime_dir: Path = DEFAULT_RUNTIME_DIR, max_cases: int = 6) -> dict[str, Any]:
    selected: list[dict[str, str]] = []
    max_case_bound_valid = max_cases == 6
    per_category = max(1, max_cases // len(DEFAULT_CATEGORIES))
    category_counts = {}
    missing = []
    for category in DEFAULT_CATEGORIES:
        ids = _ids_for_category(source_root, category)
        if not ids:
            missing.append(category)
            continue
        take = ids[:per_category]
        category_counts[category] = len(take)
        selected.extend({"category": category, "case_id": case_id} for case_id in take)
    selected = selected[:max_cases]
    readiness = _load_json(runtime_dir / "memory_operation_runtime_smoke_readiness.json") or {}
    adapter_status = _load_json(runtime_dir / "memory_operation_runtime_adapter_compile_status.json") or {}
    protocol_ready = bool(
        max_case_bound_valid
        and len(selected) == max_cases
        and not missing
        and readiness.get("memory_dev_smoke_ready") is True
        and adapter_status.get("runtime_adapter_compile_ready") is True
    )
    case_hash = _hash_payload(selected)
    report = {
        "report_scope": "memory_operation_dev_smoke_protocol",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "smoke_protocol_ready_for_review": protocol_ready,
        "provider_required": PROVIDER,
        "max_cases": max_cases,
        "selected_case_count": len(selected),
        "max_case_bound_valid": max_case_bound_valid,
        "selected_categories": DEFAULT_CATEGORIES,
        "selected_category_counts": category_counts,
        "selected_cases": selected,
        "selected_case_list_hash": case_hash,
        "runtime_rule_path": str(runtime_dir / "rule.yaml"),
        "runtime_rule_sha256": _sha256_file(runtime_dir / "rule.yaml"),
        "runtime_adapter_compile_ready": adapter_status.get("runtime_adapter_compile_ready") is True,
        "memory_dev_smoke_ready": readiness.get("memory_dev_smoke_ready") is True,
        "memory_runtime_adapter_ready": readiness.get("memory_runtime_adapter_ready") is True,
        "negative_control_activation_count": int(readiness.get("negative_control_activation_count") or 0),
        "argument_creation_count": int(readiness.get("argument_creation_count") or 0),
        "exact_tool_choice": False,
        "candidate_commands": [],
        "planned_commands": [],
        "baseline_command": None,
        "candidate_command": None,
        "forbidden_scope": ["holdout", "100-case", "full_bfcl", "retain_claim", "sota_3pp_claim"],
        "pre_registered_primary_metrics": [
            "baseline_accuracy",
            "candidate_accuracy",
            "absolute_pp_delta",
            "fixed_count",
            "regressed_count",
            "net_case_gain",
            "activated_case_count",
        ],
        "pre_registered_safety_metrics": [
            "argument_creation_count",
            "exact_tool_choice_count",
            "destructive_memory_operation_count",
            "weak_lookup_policy_activation_count",
        ],
        "pass_gate": {
            "activated_case_count_gt_0": True,
            "candidate_accuracy_gte_baseline_accuracy": True,
            "fixed_count_gte_regressed_count": True,
            "net_case_gain_gte_0": True,
            "argument_creation_count_eq_0": True,
            "exact_tool_choice_count_eq_0": True,
            "destructive_memory_operation_count_eq_0": True,
            "weak_lookup_policy_activation_count_eq_0": True,
        },
        "failure_count": 0 if protocol_ready else 1,
        "first_failure": None if protocol_ready else {"check": "protocol_inputs_ready", "missing_categories": missing, "max_case_bound_valid": max_case_bound_valid},
        "next_required_action": "request_explicit_memory_only_dev_smoke_execution_approval" if protocol_ready else "fix_protocol_inputs_before_smoke_request",
    }
    return report


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "memory_operation_dev_smoke_protocol.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Memory Operation Dev Smoke Protocol",
        "",
        f"- Ready for review: `{report['smoke_protocol_ready_for_review']}`",
        f"- Provider required: `{report['provider_required']}`",
        f"- Selected case count: `{report['selected_case_count']}`",
        f"- Selected category counts: `{report['selected_category_counts']}`",
        f"- Case list hash: `{report['selected_case_list_hash']}`",
        f"- Runtime rule hash: `{report['runtime_rule_sha256']}`",
        f"- Candidate commands: `{report['candidate_commands']}`",
        f"- Planned commands: `{report['planned_commands']}`",
        f"- Does not authorize scorer: `{report['does_not_authorize_scorer']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "This protocol freezes the small memory-only dev smoke design. It does not execute BFCL/model/scorer.",
        "",
    ]
    (out_dir / "memory_operation_dev_smoke_protocol.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--max-cases", type=int, default=6)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.source_root, args.runtime_dir, args.max_cases)
    write_outputs(report, args.output_dir)
    if args.compact:
        keys = [
            "smoke_protocol_ready_for_review",
            "provider_required",
            "selected_case_count",
            "max_case_bound_valid",
            "selected_category_counts",
            "selected_case_list_hash",
            "runtime_rule_sha256",
            "candidate_commands",
            "planned_commands",
            "does_not_authorize_scorer",
            "next_required_action",
            "failure_count",
            "first_failure",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    return 0 if report["smoke_protocol_ready_for_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
