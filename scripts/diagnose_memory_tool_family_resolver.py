#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

DEFAULT_AUDIT = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_obligation_audit.json")
DEFAULT_ALLOWLIST = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_compiler_allowlist.json")
DEFAULT_POLICY_DIR = Path("outputs/artifacts/phase2/memory_operation_obligation_dry_run_v1/first_pass")
DEFAULT_OUT = DEFAULT_POLICY_DIR / "memory_tool_family_resolver_audit.json"
DEFAULT_MD = DEFAULT_POLICY_DIR / "memory_tool_family_resolver_audit.md"
MEMORY_NAMESPACES = ("memory", "core_memory", "archival_memory", "user_memory", "profile_memory")
FORBIDDEN_MUTATION = re.compile(r"(clear|remove|delete|add|replace|update|append)", re.IGNORECASE)
ALLOWED_FAMILIES = {"memory_key_or_text_search", "memory_list_keys", "memory_value_retrieve"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def _support_hash(row: dict[str, Any], ordinal: int) -> str:
    strength = str(row.get("memory_witness_strength") or "unknown")
    payload = "|".join([
        str(row.get("category") or "unknown"),
        str(row.get("operation") or "unknown"),
        str(row.get("operation_scope") or "unknown"),
        strength,
        "first_pass_retrieve" if strength == "no_witness" else "second_pass_retrieve" if strength == "weak_lookup_witness" else "blocked",
        str(ordinal),
    ])
    return "memsup_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def classify_memory_tool(tool: str) -> tuple[str | None, str | None]:
    lowered = tool.lower()
    if not any(namespace in lowered for namespace in MEMORY_NAMESPACES):
        return None, "not_memory_namespace"
    if FORBIDDEN_MUTATION.search(lowered):
        return None, "mutation_tool_blocked"
    if "list" in lowered and ("key" in lowered or lowered.endswith("_all")):
        return "memory_list_keys", None
    if "search" in lowered or "query" in lowered or "find" in lowered:
        return "memory_key_or_text_search", None
    if "retrieve" in lowered or "get" in lowered or "read" in lowered or "fetch" in lowered:
        return "memory_value_retrieve", None
    return None, "memory_tool_semantics_unknown"


def _resolve_tools(tools: list[str], requested_families: set[str]) -> tuple[dict[str, list[str]], list[str], list[dict[str, str]]]:
    resolved = {family: [] for family in sorted(requested_families)}
    blocked: list[str] = []
    rejected: list[dict[str, str]] = []
    for tool in sorted(set(tools)):
        family, reason = classify_memory_tool(str(tool))
        if reason == "mutation_tool_blocked":
            blocked.append(str(tool))
            continue
        if family and family in requested_families:
            resolved.setdefault(family, []).append(str(tool))
        elif reason:
            rejected.append({"tool": str(tool), "reason": reason})
    return {key: value for key, value in resolved.items() if value}, blocked, rejected


def _negative_controls() -> dict[str, Any]:
    controls = {
        "no_memory_tools_schema": _resolve_tools(["calculator", "search_tweets"], ALLOWED_FAMILIES),
        "mutation_only_memory_schema": _resolve_tools(["core_memory_add", "core_memory_remove", "archival_memory_clear"], ALLOWED_FAMILIES),
        "non_memory_search_tools": _resolve_tools(["web_search", "search_tweets", "get_ticket"], ALLOWED_FAMILIES),
        "ambiguous_destructive_memory_names": _resolve_tools(["memory_delete_search", "core_memory_replace"], ALLOWED_FAMILIES),
    }
    out: dict[str, Any] = {}
    for name, (resolved, blocked, rejected) in controls.items():
        out[name] = {
            "resolved_tool_count": sum(len(items) for items in resolved.values()),
            "blocked_tool_count": len(blocked),
            "rejected_tool_count": len(rejected),
            "passed": sum(len(items) for items in resolved.values()) == 0,
            "blocked_tools": blocked,
            "rejected_tools": rejected,
        }
    return out


def evaluate(audit_path: Path = DEFAULT_AUDIT, allowlist_path: Path = DEFAULT_ALLOWLIST, policy_dir: Path = DEFAULT_POLICY_DIR) -> dict[str, Any]:
    audit = _load_json(audit_path)
    allowlist = _load_json(allowlist_path)
    policy = _load_yaml(policy_dir / "policy_unit.yaml")
    units = policy.get("policy_units") or []
    requested_families = set()
    for unit in units:
        requested_families.update(((unit.get("decision_policy") or {}).get("recommended_tool_capability_families") or []))
    requested_families &= ALLOWED_FAMILIES
    indexed = {_support_hash(row, idx): row for idx, row in enumerate(audit.get("candidate_records") or [])}
    records = []
    missing_support_hashes = []
    forbidden_resolved = 0
    blocked_destructive = 0
    for support in allowlist.get("allowlist_records") or []:
        support_hash = support.get("support_record_hash")
        row = indexed.get(support_hash)
        if row is None:
            missing_support_hashes.append(support_hash)
            continue
        if support.get("support_class") != "first_pass_retrieve" or support.get("memory_witness_strength") != "no_witness":
            continue
        resolved, blocked, rejected = _resolve_tools(row.get("available_memory_tools") or [], requested_families)
        forbidden_resolved += sum(1 for tools in resolved.values() for tool in tools if FORBIDDEN_MUTATION.search(tool))
        blocked_destructive += len(blocked)
        records.append({
            "support_record_hash": support_hash,
            "category": support.get("category"),
            "policy_unit_id": "memory_first_pass_retrieve_soft_v1",
            "resolved_tool_families": resolved,
            "blocked_mutation_tools": blocked,
            "rejected_tools": rejected,
            "argument_policy": "no_argument_creation_or_binding",
            "exact_tool_choice": False,
            "runtime_enabled": False,
            "tool_call_mapping_unique": True,
        })
    negative = _negative_controls()
    resolved_schema_count = sum(1 for record in records if sum(len(items) for items in record["resolved_tool_families"].values()) > 0)
    empty_resolution_count = len(records) - resolved_schema_count
    negative_passed = all(control["passed"] for control in negative.values())
    return {
        "report_scope": "memory_tool_family_resolver_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "runtime_enabled": False,
        "exact_tool_choice": False,
        "argument_creation_count": 0,
        "candidate_commands": [],
        "planned_commands": [],
        "resolver_audit_passed": bool(records) and not missing_support_hashes and resolved_schema_count > 0 and forbidden_resolved == 0 and negative_passed,
        "resolver_contract": {
            "runtime_resolver_must_read_policy_unit_and_schema_only": True,
            "raw_audit_forbidden_as_runtime_input": True,
            "review_manifest_forbidden_as_runtime_input": True,
            "scorer_or_gold_dependency_forbidden": True,
        },
        "policy_unit_count": len(units),
        "first_pass_allowlist_count": int(allowlist.get("compiler_input_eligible_count") or 0),
        "weak_witness_records_resolved_count": 0,
        "schema_records_scanned": len(records),
        "resolved_schema_count": resolved_schema_count,
        "empty_resolution_count": empty_resolution_count,
        "forbidden_memory_mutation_tools_resolved_count": forbidden_resolved,
        "blocked_destructive_tool_count": blocked_destructive,
        "missing_support_hashes": missing_support_hashes[:20],
        "requested_capability_families": sorted(requested_families),
        "negative_controls": negative,
        "resolver_records": records,
        "next_required_action": "runtime_like_activation_design_requires_separate_review",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Memory Tool-Family Resolver Audit",
        "",
        f"Passed: `{report['resolver_audit_passed']}`",
        f"Schema records scanned: `{report['schema_records_scanned']}`",
        f"Resolved schema count: `{report['resolved_schema_count']}`",
        f"Empty resolution count: `{report['empty_resolution_count']}`",
        f"Blocked destructive tool count: `{report['blocked_destructive_tool_count']}`",
        f"Forbidden mutation tools resolved: `{report['forbidden_memory_mutation_tools_resolved_count']}`",
        "",
        "This is an offline schema-capability projection. It does not enable runtime policy execution or authorize BFCL/model/scorer runs.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--policy-dir", type=Path, default=DEFAULT_POLICY_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.audit, args.allowlist, args.policy_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "resolver_audit_passed",
            "schema_records_scanned",
            "resolved_schema_count",
            "empty_resolution_count",
            "blocked_destructive_tool_count",
            "forbidden_memory_mutation_tools_resolved_count",
            "weak_witness_records_resolved_count",
            "next_required_action",
        ]}, indent=2, sort_keys=True))
    return 0 if report["resolver_audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
