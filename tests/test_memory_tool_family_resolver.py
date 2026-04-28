from __future__ import annotations

import json
from pathlib import Path

import yaml

import scripts.diagnose_memory_tool_family_resolver as resolver


def _write_inputs(root: Path, *, tools: list[str] | None = None, support_class: str = "first_pass_retrieve", witness: str = "no_witness") -> tuple[Path, Path, Path]:
    audit_path = root / "audit.json"
    allowlist_path = root / "allowlist.json"
    policy_dir = root / "policy"
    policy_dir.mkdir(parents=True)
    row = {
        "category": "memory_kv",
        "operation": "retrieve",
        "operation_scope": "retrieve_only",
        "memory_witness_strength": witness,
        "available_memory_tools": tools or ["core_memory_retrieve", "archival_memory_key_search", "core_memory_list_keys", "core_memory_add"],
    }
    support_hash = resolver._support_hash(row, 0)
    audit_path.write_text(json.dumps({"candidate_records": [row]}), encoding="utf-8")
    allowlist_path.write_text(json.dumps({
        "compiler_input_eligible_count": 1,
        "weak_witness_compiler_input_count": 0,
        "allowlist_records": [{
            "support_record_hash": support_hash,
            "category": "memory_kv",
            "support_class": support_class,
            "memory_witness_strength": witness,
            "recommended_tool_capability_families": ["memory_key_or_text_search", "memory_list_keys", "memory_value_retrieve"],
            "compiler_input_eligible": True,
            "runtime_enabled": False,
            "exact_tool_choice": False,
        }],
    }), encoding="utf-8")
    (policy_dir / "policy_unit.yaml").write_text(yaml.safe_dump({
        "runtime_enabled": False,
        "candidate_commands": [],
        "planned_commands": [],
        "policy_units": [{
            "policy_unit_id": "memory_first_pass_retrieve_soft_v1",
            "runtime_enabled": False,
            "exact_tool_choice": False,
            "decision_policy": {
                "recommended_tool_capability_families": ["memory_key_or_text_search", "memory_list_keys", "memory_value_retrieve"],
                "argument_policy": "no_argument_creation_or_binding",
            },
        }],
    }), encoding="utf-8")
    return audit_path, allowlist_path, policy_dir


def test_memory_tool_family_resolver_projects_schema_tools(tmp_path: Path) -> None:
    audit, allowlist, policy_dir = _write_inputs(tmp_path)

    report = resolver.evaluate(audit, allowlist, policy_dir)

    assert report["resolver_audit_passed"] is True
    assert report["resolved_schema_count"] == 1
    record = report["resolver_records"][0]
    assert record["resolved_tool_families"]["memory_value_retrieve"] == ["core_memory_retrieve"]
    assert record["resolved_tool_families"]["memory_key_or_text_search"] == ["archival_memory_key_search"]
    assert record["resolved_tool_families"]["memory_list_keys"] == ["core_memory_list_keys"]
    assert record["blocked_mutation_tools"] == ["core_memory_add"]
    assert report["forbidden_memory_mutation_tools_resolved_count"] == 0


def test_memory_tool_family_resolver_negative_controls_do_not_resolve_non_memory_search() -> None:
    report = resolver.evaluate(*_write_inputs(Path("/tmp/nonexistent-resolver-input"))) if False else None
    controls = resolver._negative_controls()
    assert controls["non_memory_search_tools"]["resolved_tool_count"] == 0
    assert controls["mutation_only_memory_schema"]["resolved_tool_count"] == 0
    assert controls["mutation_only_memory_schema"]["blocked_tool_count"] > 0


def test_memory_tool_family_resolver_excludes_weak_witness_allowlist_rows(tmp_path: Path) -> None:
    audit, allowlist, policy_dir = _write_inputs(tmp_path, support_class="second_pass_retrieve", witness="weak_lookup_witness")

    report = resolver.evaluate(audit, allowlist, policy_dir)

    assert report["schema_records_scanned"] == 0
    assert report["resolver_audit_passed"] is False
