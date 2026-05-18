#!/usr/bin/env python3
"""Check ABHE runtime slot-controller no-provider path replay artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_path_replay.json")


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_path_replay":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_path_replay_v0":
        blockers.append("schema_version_invalid")
    for key in ["no_provider", "safe_fields_only", "raw_material_absent"]:
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true")
    for key in [
        "bfcl_generate_called",
        "bfcl_evaluate_called",
        "scorer_called",
        "provider_calls_made",
        "performance_evidence",
        "holdout_touched",
        "full_suite_touched",
        "archive_updated",
        "prompt_literal_committed",
        "argument_values_committed",
        "provider_payload_committed",
        "bfcl_result_tree_committed",
        "gold_expected_committed",
        "scorer_diff_committed",
    ]:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    fixture = data.get("proxy_fixture") if isinstance(data.get("proxy_fixture"), dict) else {}
    if fixture.get("proxy_fixture_runtime_path_confirmed") is not True:
        blockers.append("proxy_fixture_runtime_path_not_confirmed")
    if int(fixture.get("slot_bind_repair_count") or 0) <= 0:
        blockers.append("proxy_fixture_slot_bind_repair_missing")
    if int(fixture.get("slot_policy_hit_count") or 0) <= 0:
        blockers.append("proxy_fixture_slot_policy_hit_missing")
    same = data.get("same_request_replay") if isinstance(data.get("same_request_replay"), dict) else {}
    if same.get("same_request_noop_replay_confirmed") is not True:
        blockers.append("same_request_noop_replay_not_confirmed")
    if int(same.get("same_request_replay_trace_count") or 0) <= 0:
        blockers.append("same_request_replay_trace_count_missing")
    if int(same.get("runtime_slot_bind_repair_count") or 0) != 0:
        blockers.append("same_request_runtime_slot_bind_repair_not_zero")
    if int(same.get("argument_keyset_changed_count") or 0) != 0:
        blockers.append("same_request_argument_keyset_changed")
    rows = same.get("rows") if isinstance(same.get("rows"), list) else []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            blockers.append(f"same_request_row_invalid:{idx}")
            continue
        if row.get("raw_material_absent") is not True or row.get("argument_values_committed") is not False:
            blockers.append(f"same_request_row_boundary_invalid:{idx}")
    if data.get("blockers"):
        blockers.extend(str(item) for item in data.get("blockers") if str(item))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    try:
        data = _load(path)
        blockers = validate(data)
    except Exception as exc:
        data = {}
        blockers = [f"load_failed:{exc.__class__.__name__}"]
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_path_replay_check",
        "artifact_path": str(path),
        "path_replay_check_passed": not blockers,
        "blockers": blockers,
        "proxy_fixture_runtime_path_confirmed": (data.get("summary") or {}).get("proxy_fixture_runtime_path_confirmed"),
        "same_request_noop_replay_confirmed": (data.get("summary") or {}).get("same_request_noop_replay_confirmed"),
        "performance_evidence": data.get("performance_evidence", False),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.path)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["path_replay_check_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
