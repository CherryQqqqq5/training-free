#!/usr/bin/env python3
"""Build sanitized trace telemetry for ABHE runtime slot-controller residual run."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict

RUN_ROOT = Path("/tmp/abhe_v0_runtime_slot_controller_residual_dev_smoke")
OUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_sanitized_trace_audit.json")
ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
CATEGORIES = ["multi_turn_miss_param", "multi_turn_miss_func", "multi_turn_base", "multi_turn_long_context", "irrelevance", "live_irrelevance"]
SLOT_REPAIR_KIND = "abhe_runtime_slot_controller_v2_bind_required_slot"


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> Dict[str, Any]:
    rows = []
    summary: Dict[str, Any] = {}
    blockers = []
    if not RUN_ROOT.exists():
        blockers.append("run_root_missing")
    for arm in ARMS:
        arm_counts = Counter()
        arm_categories: Dict[str, Any] = {}
        for category in CATEGORIES:
            trace_dir = RUN_ROOT / arm / category / "traces"
            paths = sorted(trace_dir.glob("*.json")) if trace_dir.exists() else []
            repair_count = 0
            policy_hit_count = 0
            controller_enabled_patch_count = 0
            issue_kinds = Counter()
            repair_kinds = Counter()
            sample_hashes = []
            for path in paths:
                data = _load(path)
                validation = data.get("validation") if isinstance(data.get("validation"), dict) else {}
                repairs = validation.get("repairs") if isinstance(validation.get("repairs"), list) else []
                repair_kinds.update(str(item.get("kind")) for item in repairs if isinstance(item, dict) and item.get("kind"))
                repair_count += sum(1 for item in repairs if isinstance(item, dict) and item.get("kind") == SLOT_REPAIR_KIND)
                policy_hits = validation.get("policy_hits") if isinstance(validation.get("policy_hits"), list) else []
                if "abhe_runtime_slot_controller_v2" in policy_hits:
                    policy_hit_count += 1
                request_patches = validation.get("request_patches") if isinstance(validation.get("request_patches"), list) else []
                if "abhe_v0_runtime_slot_controller_v2:enabled" in request_patches:
                    controller_enabled_patch_count += 1
                issue_kinds.update(str(item.get("kind")) for item in (validation.get("issues") or []) if isinstance(item, dict) and item.get("kind"))
                if len(sample_hashes) < 3:
                    sample_hashes.append(_hash(path))
            row = {
                "arm": arm,
                "bfcl_category": category,
                "sampled_artifact_count": len(paths),
                "slot_controller_policy_hit_count": policy_hit_count,
                "slot_controller_enabled_patch_count": controller_enabled_patch_count,
                "slot_bind_repair_count": repair_count,
                "issue_kind_counts": dict(sorted(issue_kinds.items())),
                "repair_kind_counts": dict(sorted(repair_kinds.items())),
                "sample_artifact_hashes": sample_hashes,
                "safe_fields_only": True,
                "raw_material_absent": True,
                "argument_values_committed": False,
                "provider_payload_committed": False,
                "scorer_diff_committed": False,
            }
            rows.append(row)
            arm_counts["sampled_artifact_count"] += len(paths)
            arm_counts["slot_controller_policy_hit_count"] += policy_hit_count
            arm_counts["slot_controller_enabled_patch_count"] += controller_enabled_patch_count
            arm_counts["slot_bind_repair_count"] += repair_count
            arm_categories[category] = {
                "sampled_artifact_count": len(paths),
                "slot_bind_repair_count": repair_count,
                "slot_controller_policy_hit_count": policy_hit_count,
                "slot_controller_enabled_patch_count": controller_enabled_patch_count,
            }
        summary[arm] = dict(arm_counts)
        summary[arm]["category_summary"] = arm_categories
    return {
        "artifact_kind": "abhe_v0_runtime_slot_controller_sanitized_trace_audit",
        "schema_version": "abhe_v0_runtime_slot_controller_sanitized_trace_audit_v0",
        "run_scope": "bounded_residual_dev_smoke_only",
        "safe_fields_only": True,
        "rows": rows,
        "summary": summary,
        "raw_material_absent": True,
        "prompt_literal_committed": False,
        "argument_values_committed": False,
        "provider_payload_committed": False,
        "bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_evidence": False,
        "archive_updated": False,
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    payload = build()
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True) if args.compact else json.dumps(payload, indent=2, sort_keys=True))
    return 1 if args.strict and payload.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
