#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:  # Imported at module scope so tests can monkeypatch it.
    from bfcl_eval.utils import load_dataset_entry
except Exception:  # pragma: no cover - defensive for minimal test envs
    load_dataset_entry = None  # type: ignore[assignment]

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


def _bfcl_entries_by_id(category: str) -> dict[str, dict[str, Any]]:
    if load_dataset_entry is None:
        return {}
    try:
        entries = load_dataset_entry(category, include_prereq=True)  # type: ignore[misc]
    except TypeError:
        entries = load_dataset_entry(category)  # type: ignore[misc]
    except Exception:
        return {}
    return {str(entry.get("id")): entry for entry in entries if isinstance(entry, dict) and entry.get("id")}


def _dependency_expanded_ids(category: str, target_ids: list[str]) -> tuple[list[str], dict[str, list[str]], list[str], bool]:
    entries_by_id = _bfcl_entries_by_id(category)
    if not entries_by_id:
        return list(target_ids), {}, [], False

    expanded: list[str] = []
    seen: set[str] = set()
    missing: list[str] = []
    deps_by_target: dict[str, list[str]] = {}

    def add(case_id: str) -> None:
        if case_id in seen:
            return
        entry = entries_by_id.get(case_id)
        if entry is None:
            missing.append(case_id)
            seen.add(case_id)
            return
        for dep_id in entry.get("depends_on") or []:
            add(str(dep_id))
        seen.add(case_id)
        expanded.append(case_id)

    for target_id in target_ids:
        entry = entries_by_id.get(target_id)
        deps = [str(dep_id) for dep_id in (entry or {}).get("depends_on") or []]
        deps_by_target[target_id] = deps
        add(target_id)

    return expanded, deps_by_target, sorted(set(missing)), True


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
    category_counts: dict[str, int] = {}
    generation_case_counts: dict[str, int] = {}
    prereq_case_counts: dict[str, int] = {}
    target_ids_by_category: dict[str, list[str]] = {}
    generation_ids_by_category: dict[str, list[str]] = {}
    deps_by_category: dict[str, dict[str, list[str]]] = {}
    missing_dependency_ids_by_category: dict[str, list[str]] = {}
    metadata_available_by_category: dict[str, bool] = {}
    missing: list[str] = []

    for category in DEFAULT_CATEGORIES:
        ids = _ids_for_category(source_root, category)
        if not ids:
            missing.append(category)
            continue
        take = ids[:per_category]
        expanded, deps_by_target, missing_deps, metadata_available = _dependency_expanded_ids(category, take)
        category_counts[category] = len(take)
        generation_case_counts[category] = len(expanded)
        prereq_case_counts[category] = len([case_id for case_id in expanded if "prereq" in case_id])
        target_ids_by_category[category] = take
        generation_ids_by_category[category] = expanded
        deps_by_category[category] = deps_by_target
        missing_dependency_ids_by_category[category] = missing_deps
        metadata_available_by_category[category] = metadata_available
        selected.extend({"category": category, "case_id": case_id} for case_id in take)

    selected = selected[:max_cases]
    readiness = _load_json(runtime_dir / "memory_operation_runtime_smoke_readiness.json") or {}
    adapter_status = _load_json(runtime_dir / "memory_operation_runtime_adapter_compile_status.json") or {}
    snapshot_dependency_closure_ready = bool(
        generation_ids_by_category
        and all(metadata_available_by_category.get(category) for category in DEFAULT_CATEGORIES if category_counts.get(category))
        and not any(missing_dependency_ids_by_category.get(category) for category in DEFAULT_CATEGORIES)
        and all(prereq_case_counts.get(category, 0) > 0 for category in DEFAULT_CATEGORIES if category_counts.get(category))
    )
    protocol_ready = bool(
        max_case_bound_valid
        and len(selected) == max_cases
        and not missing
        and snapshot_dependency_closure_ready
        and readiness.get("memory_dev_smoke_ready") is True
        and adapter_status.get("runtime_adapter_compile_ready") is True
    )
    case_hash = _hash_payload(selected)
    generation_hash = _hash_payload(generation_ids_by_category)
    first_failure = None
    if not protocol_ready:
        first_failure = {
            "check": "protocol_inputs_ready",
            "missing_categories": missing,
            "max_case_bound_valid": max_case_bound_valid,
            "snapshot_dependency_closure_ready": snapshot_dependency_closure_ready,
            "missing_dependency_ids_by_category": missing_dependency_ids_by_category,
            "memory_dependency_metadata_available_by_category": metadata_available_by_category,
        }
    return {
        "report_scope": "memory_operation_dev_smoke_protocol",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "smoke_protocol_ready_for_review": protocol_ready,
        "provider_required": PROVIDER,
        "max_cases": max_cases,
        "target_case_count": len(selected),
        "selected_case_count": len(selected),
        "generation_case_count": sum(generation_case_counts.values()),
        "prereq_case_count": sum(prereq_case_counts.values()),
        "max_case_bound_valid": max_case_bound_valid,
        "selected_categories": DEFAULT_CATEGORIES,
        "selected_category_counts": category_counts,
        "generation_case_counts": generation_case_counts,
        "prereq_case_counts": prereq_case_counts,
        "selected_cases": selected,
        "target_ids_by_category": target_ids_by_category,
        "generation_ids_by_category": generation_ids_by_category,
        "memory_dependencies_by_target": deps_by_category,
        "missing_dependency_ids_by_category": missing_dependency_ids_by_category,
        "memory_dependency_metadata_available_by_category": metadata_available_by_category,
        "memory_snapshot_dependency_closure_ready": snapshot_dependency_closure_ready,
        "selected_case_list_hash": case_hash,
        "generation_case_list_hash": generation_hash,
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
        "first_failure": first_failure,
        "next_required_action": "request_explicit_memory_only_dev_smoke_execution_approval" if protocol_ready else "fix_protocol_inputs_before_smoke_request",
    }


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
        f"- Target case count: `{report['target_case_count']}`",
        f"- Generation case count: `{report['generation_case_count']}`",
        f"- Prereq case count: `{report['prereq_case_count']}`",
        f"- Selected category counts: `{report['selected_category_counts']}`",
        f"- Generation category counts: `{report['generation_case_counts']}`",
        f"- Snapshot dependency closure ready: `{report['memory_snapshot_dependency_closure_ready']}`",
        f"- Case list hash: `{report['selected_case_list_hash']}`",
        f"- Generation list hash: `{report['generation_case_list_hash']}`",
        f"- Runtime rule hash: `{report['runtime_rule_sha256']}`",
        f"- Candidate commands: `{report['candidate_commands']}`",
        f"- Planned commands: `{report['planned_commands']}`",
        f"- Does not authorize scorer: `{report['does_not_authorize_scorer']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "This protocol freezes the small memory-only dev smoke design. It does not execute BFCL/model/scorer.",
        "Memory target cases require BFCL prerequisite entries to initialize snapshots before the target turns run.",
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
            "target_case_count",
            "generation_case_count",
            "prereq_case_count",
            "max_case_bound_valid",
            "selected_category_counts",
            "generation_case_counts",
            "memory_snapshot_dependency_closure_ready",
            "selected_case_list_hash",
            "generation_case_list_hash",
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
