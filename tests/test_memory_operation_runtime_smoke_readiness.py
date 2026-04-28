from __future__ import annotations

from pathlib import Path

import scripts.check_memory_operation_runtime_smoke_readiness as readiness


def _stub_upstream(monkeypatch):
    monkeypatch.setattr(
        readiness.dry_check,
        "evaluate",
        lambda policy_dir: {"dry_run_policy_boundary_check_passed": True},
    )
    monkeypatch.setattr(
        readiness.activation_sim,
        "evaluate",
        lambda: {
            "activation_simulation_passed": True,
            "activation_count": 48,
            "negative_control_activation_count": 0,
            "argument_creation_count": 0,
        },
    )


def test_readiness_fails_without_runtime_adapter(tmp_path: Path, monkeypatch) -> None:
    _stub_upstream(monkeypatch)
    report = readiness.evaluate(tmp_path / "policy", tmp_path / "missing_runtime")

    assert report["memory_dev_smoke_ready"] is False
    assert report["memory_runtime_adapter_ready"] is False
    assert report["first_failure"]["check"] == "runtime_rules_dir_exists"
    assert report["candidate_commands"] == []


def test_readiness_fails_for_policy_unit_metadata_only(tmp_path: Path, monkeypatch) -> None:
    _stub_upstream(monkeypatch)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "policy_unit.yaml").write_text(
        """
policy_units:
  - policy_unit_id: memory_first_pass_retrieve_soft_v1
    runtime_enabled: false
candidate_commands: []
planned_commands: []
""".strip(),
        encoding="utf-8",
    )

    report = readiness.evaluate(tmp_path / "policy", runtime_dir)

    assert report["memory_dev_smoke_ready"] is False
    checks = {failure["check"] for failure in report["failures"]}
    assert "runtime_rules_not_policy_unit_metadata" in checks
    assert "runtime_adapter_rules_loaded" in checks


def test_readiness_passes_for_sanitized_runtime_rule(tmp_path: Path, monkeypatch) -> None:
    _stub_upstream(monkeypatch)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "rule.yaml").write_text(
        """
rule_id: memory_first_pass_retrieve_soft_v1_runtime_adapter
priority: 8
enabled: true
trigger:
  error_types:
    - memory_first_pass_retrieve_obligation
  request_predicates:
    - tools_available
scope:
  patch_sites:
    - prompt_injector
action:
  guidance: "When memory retrieval is required and no witness is present, prefer a schema-available memory retrieval capability before answering. Do not create arguments."
  decision_policy:
    policy_family: memory_operation_obligation
    recommended_tools: []
    candidate_commands: []
    planned_commands: []
""".strip(),
        encoding="utf-8",
    )

    report = readiness.evaluate(tmp_path / "policy", runtime_dir, provider="novacode", max_cases=6)

    assert report["memory_dev_smoke_ready"] is True
    assert report["memory_runtime_adapter_ready"] is True
    assert report["loaded_memory_runtime_rule_count"] == 1


def test_readiness_rejects_openrouter_provider(tmp_path: Path, monkeypatch) -> None:
    _stub_upstream(monkeypatch)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "rule.yaml").write_text(
        """
rule_id: memory_first_pass_retrieve_soft_v1_runtime_adapter
enabled: true
trigger:
  error_types:
    - memory_first_pass_retrieve_obligation
scope:
  patch_sites:
    - prompt_injector
action:
  guidance: "Prefer memory retrieval capability."
""".strip(),
        encoding="utf-8",
    )

    report = readiness.evaluate(tmp_path / "policy", runtime_dir, provider="openrouter")

    assert report["memory_dev_smoke_ready"] is False
    assert any(failure["check"] == "provider_is_novacode" for failure in report["failures"])


def test_readiness_rejects_forbidden_runtime_text(tmp_path: Path, monkeypatch) -> None:
    _stub_upstream(monkeypatch)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "rule.yaml").write_text(
        """
rule_id: memory_first_pass_retrieve_soft_v1_runtime_adapter
enabled: true
trigger:
  error_types:
    - memory_first_pass_retrieve_obligation
scope:
  patch_sites:
    - prompt_injector
action:
  guidance: "Use support_record_hash memsup_1."
""".strip(),
        encoding="utf-8",
    )

    report = readiness.evaluate(tmp_path / "policy", runtime_dir)

    assert report["memory_dev_smoke_ready"] is False
    assert any(failure["check"] == "runtime_rule_forbidden_text" for failure in report["failures"])
