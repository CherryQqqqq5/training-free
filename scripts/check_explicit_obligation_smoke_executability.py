#!/usr/bin/env python3
"""Check whether the explicit-obligation smoke protocol is BFCL executable.

The explicit-obligation protocol is built from offline audit candidates. Those
candidate ids are not necessarily BFCL dataset case ids. This checker keeps the
smoke path fail-closed until every selected positive/control can be mapped to a
real BFCL case id and dependency closure.
"""

from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

try:  # Imported at module scope so tests can monkeypatch it.
    from bfcl_eval.utils import load_dataset_entry
except Exception:  # pragma: no cover - minimal test env
    load_dataset_entry = None  # type: ignore[assignment]

DEFAULT_PROTOCOL = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_smoke_protocol.json")
DEFAULT_SOURCE_ROOT = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
DEFAULT_OUT = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_smoke_executability.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_smoke_executability.md")
CASE_ID_KEYS = ("case_id", "test_case_id", "id", "bfcl_case_id")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


@lru_cache(maxsize=None)
def _ids_for_category(source_root: Path, category: str) -> tuple[str, ...]:
    path = source_root / category / "baseline" / "bfcl" / "test_case_ids_to_generate.json"
    data = _load_json(path)
    ids: Any = []
    if isinstance(data, dict):
        ids = data.get("test_case_ids") or data.get("ids")
        if ids is None and category in data:
            ids = data.get(category)
        if ids is None and len(data) == 1:
            ids = next(iter(data.values()))
    elif isinstance(data, list):
        ids = data
    return tuple(str(item) for item in ids or [])


@lru_cache(maxsize=None)
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


def _trace_case_ids(trace_path: Path) -> list[str]:
    data = _load_json(trace_path)
    found: list[str] = []

    def visit(obj: Any, depth: int = 0) -> None:
        if depth > 4:
            return
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in CASE_ID_KEYS and isinstance(value, (str, int)):
                    found.append(str(value))
                elif isinstance(value, (dict, list)):
                    visit(value, depth + 1)
        elif isinstance(obj, list):
            for item in obj[:20]:
                visit(item, depth + 1)

    visit(data)
    return list(dict.fromkeys(found))


def _expand_deps(case_id: str, entries_by_id: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    expanded: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    def add(item_id: str) -> None:
        if item_id in seen:
            return
        seen.add(item_id)
        entry = entries_by_id.get(item_id)
        if entry is None:
            missing.append(item_id)
            return
        for dep_id in entry.get("depends_on") or []:
            add(str(dep_id))
        expanded.append(item_id)

    add(case_id)
    return expanded, sorted(set(missing))


def _records(protocol: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for kind, key in (("positive", "positive_cases"), ("control", "control_cases")):
        for item in protocol.get(key) or []:
            if isinstance(item, dict):
                rows.append((kind, item))
    return rows


def _evaluate_record(kind: str, item: dict[str, Any], source_root: Path) -> dict[str, Any]:
    category = str(item.get("category") or "")
    candidate_case_id = str(item.get("case_id") or "")
    source_ids = set(_ids_for_category(source_root, category)) if category else set()
    entries_by_id = _bfcl_entries_by_id(category) if category else {}
    dataset_ids = set(entries_by_id)
    trace_relative = str(item.get("trace_relative_path") or "")
    trace_path = source_root / trace_relative if trace_relative else None
    trace_ids = _trace_case_ids(trace_path) if trace_path else []

    mapped_case_id = None
    mapping_source = None
    if candidate_case_id in source_ids or candidate_case_id in dataset_ids:
        mapped_case_id = candidate_case_id
        mapping_source = "protocol_case_id"
    else:
        for trace_id in trace_ids:
            if trace_id in source_ids or trace_id in dataset_ids:
                mapped_case_id = trace_id
                mapping_source = "trace_case_id_field"
                break

    expanded_ids: list[str] = []
    missing_deps: list[str] = []
    dependency_metadata_available = bool(entries_by_id)
    if mapped_case_id and entries_by_id:
        expanded_ids, missing_deps = _expand_deps(mapped_case_id, entries_by_id)
    elif mapped_case_id:
        expanded_ids = [mapped_case_id]

    executable = bool(mapped_case_id)
    dependency_closure_ready = bool(mapped_case_id and dependency_metadata_available and not missing_deps)
    if executable and not dependency_metadata_available:
        status = "bfcl_case_id_found_but_dependency_metadata_missing"
    elif executable and missing_deps:
        status = "bfcl_case_id_found_but_dependency_missing"
    elif executable:
        status = "bfcl_case_id_ready"
    elif trace_ids:
        status = "trace_case_id_fields_not_in_source_or_dataset"
    else:
        status = "no_bfcl_case_id_found"

    return {
        "record_type": kind,
        "candidate_or_control_id": candidate_case_id,
        "category": category,
        "trace_relative_path": trace_relative,
        "trace_exists": bool(trace_path and trace_path.exists()),
        "trace_case_id_candidates": trace_ids,
        "bfcl_case_id": mapped_case_id,
        "bfcl_case_id_mapping_source": mapping_source,
        "executable_case_id_present": executable,
        "candidate_id_is_bfcl_case_id": bool(mapped_case_id and candidate_case_id == mapped_case_id),
        "dependency_metadata_available": dependency_metadata_available,
        "dependency_closure_ready": dependency_closure_ready,
        "generation_case_ids": expanded_ids,
        "missing_dependency_ids": missing_deps,
        "mapping_status": status,
    }


def evaluate(protocol_path: Path = DEFAULT_PROTOCOL, source_root: Path = DEFAULT_SOURCE_ROOT) -> dict[str, Any]:
    _ids_for_category.cache_clear()
    _bfcl_entries_by_id.cache_clear()
    protocol = _load_json(protocol_path)
    protocol = protocol if isinstance(protocol, dict) else {}
    records = [_evaluate_record(kind, item, source_root) for kind, item in _records(protocol)]
    missing_case_id_count = sum(1 for item in records if not item["executable_case_id_present"])
    dependency_not_ready_count = sum(1 for item in records if item["executable_case_id_present"] and not item["dependency_closure_ready"])
    protocol_id_is_audit_id_count = sum(1 for item in records if not item["candidate_id_is_bfcl_case_id"])
    executable_count = sum(1 for item in records if item["executable_case_id_present"])
    dependency_ready_count = sum(1 for item in records if item["dependency_closure_ready"])
    positive_count = sum(1 for kind, _ in _records(protocol) if kind == "positive")
    control_count = sum(1 for kind, _ in _records(protocol) if kind == "control")
    ready = bool(records and missing_case_id_count == 0 and dependency_not_ready_count == 0)
    blockers: list[str] = []
    if not records:
        blockers.append("explicit_obligation_protocol_empty_or_missing")
    if missing_case_id_count:
        blockers.append("explicit_protocol_not_bfcl_executable")
    if dependency_not_ready_count:
        blockers.append("dependency_closure_not_ready")
    if protocol_id_is_audit_id_count:
        blockers.append("protocol_case_ids_include_audit_ids")
    return {
        "report_scope": "explicit_obligation_smoke_executability",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "protocol_path": str(protocol_path),
        "source_root": str(source_root),
        "protocol_id": protocol.get("protocol_id"),
        "protocol_ready_for_review": bool(protocol.get("protocol_ready_for_review")),
        "approval_status": protocol.get("approval_status") or "pending",
        "execution_allowed": False,
        "bfcl_executable_manifest_ready": ready,
        "dependency_closure_ready": bool(records and dependency_not_ready_count == 0 and missing_case_id_count == 0),
        "positive_record_count": positive_count,
        "control_record_count": control_count,
        "record_count": len(records),
        "executable_case_id_count": executable_count,
        "dependency_ready_record_count": dependency_ready_count,
        "missing_bfcl_case_id_count": missing_case_id_count,
        "dependency_not_ready_count": dependency_not_ready_count,
        "protocol_id_is_audit_id_count": protocol_id_is_audit_id_count,
        "records": records,
        "blockers": blockers,
        "next_required_action": "request_separate_controlled_smoke_approval" if ready else "materialize_explicit_obligation_candidates_to_bfcl_case_ids_before_smoke",
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Explicit Obligation Smoke Executability",
        "",
        f"- BFCL executable manifest ready: `{report['bfcl_executable_manifest_ready']}`",
        f"- Protocol ready for review: `{report['protocol_ready_for_review']}`",
        f"- Positive / control records: `{report['positive_record_count']}` / `{report['control_record_count']}`",
        f"- Executable case ids: `{report['executable_case_id_count']}` / `{report['record_count']}`",
        f"- Dependency closure ready: `{report['dependency_closure_ready']}`",
        f"- Missing BFCL case ids: `{report['missing_bfcl_case_id_count']}`",
        f"- Protocol ids that are not BFCL ids: `{report['protocol_id_is_audit_id_count']}`",
        f"- Candidate commands: `{report['candidate_commands']}`",
        f"- Planned commands: `{report['planned_commands']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "This check is offline only and never authorizes BFCL/model/scorer execution.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.protocol, args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        keys = [
            "bfcl_executable_manifest_ready",
            "protocol_ready_for_review",
            "positive_record_count",
            "control_record_count",
            "executable_case_id_count",
            "record_count",
            "missing_bfcl_case_id_count",
            "dependency_not_ready_count",
            "protocol_id_is_audit_id_count",
            "candidate_commands",
            "planned_commands",
            "blockers",
            "next_required_action",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    return 0 if report["bfcl_executable_manifest_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
