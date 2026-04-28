from __future__ import annotations

from pathlib import Path

import yaml

import scripts.build_memory_operation_runtime_smoke_adapter as builder
import scripts.check_memory_operation_runtime_smoke_readiness as readiness


def _stub_upstream(monkeypatch):
    monkeypatch.setattr(builder.dry_check, "evaluate", lambda policy_dir: {"dry_run_policy_boundary_check_passed": True})
    monkeypatch.setattr(builder.activation_sim, "evaluate", lambda: {"activation_simulation_passed": True})
    monkeypatch.setattr(readiness.dry_check, "evaluate", lambda policy_dir: {"dry_run_policy_boundary_check_passed": True})
    monkeypatch.setattr(readiness.activation_sim, "evaluate", lambda: {
        "activation_simulation_passed": True,
        "activation_count": 48,
        "negative_control_activation_count": 0,
        "argument_creation_count": 0,
    })


def _write_policy_unit(policy_dir: Path) -> None:
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "policy_unit.yaml").write_text(
        yaml.safe_dump({
            "runtime_enabled": False,
            "candidate_commands": [],
            "planned_commands": [],
            "policy_units": [{
                "policy_unit_id": "memory_first_pass_retrieve_soft_v1",
                "runtime_enabled": False,
                "exact_tool_choice": False,
                "decision_policy": {
                    "argument_policy": "no_argument_creation_or_binding",
                    "capability_only": True,
                    "recommended_tool_capability_families": ["memory_value_retrieve"],
                },
            }],
        }),
        encoding="utf-8",
    )


def test_runtime_adapter_compiler_writes_loadable_rule(tmp_path: Path, monkeypatch) -> None:
    _stub_upstream(monkeypatch)
    policy_dir = tmp_path / "policy"
    out_dir = tmp_path / "runtime"
    _write_policy_unit(policy_dir)

    report = builder.evaluate(policy_dir)
    builder.write_outputs(report, out_dir)

    assert report["runtime_adapter_compile_ready"] is True
    assert (out_dir / "rule.yaml").exists()
    readiness_report = readiness.evaluate(policy_dir, out_dir)
    assert readiness_report["memory_dev_smoke_ready"] is True
    assert readiness_report["loaded_memory_runtime_rule_count"] == 1


def test_runtime_adapter_compiler_rejects_runtime_enabled_source_policy(tmp_path: Path, monkeypatch) -> None:
    _stub_upstream(monkeypatch)
    policy_dir = tmp_path / "policy"
    _write_policy_unit(policy_dir)
    data = yaml.safe_load((policy_dir / "policy_unit.yaml").read_text(encoding="utf-8"))
    data["policy_units"][0]["runtime_enabled"] = True
    (policy_dir / "policy_unit.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")

    report = builder.evaluate(policy_dir)

    assert report["runtime_adapter_compile_ready"] is False
    assert any(failure["check"] == "source_policy_unit_runtime_disabled" for failure in report["failures"])
