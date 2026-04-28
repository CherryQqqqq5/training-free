from __future__ import annotations

import json
from pathlib import Path

import scripts.build_memory_operation_dev_smoke_protocol as protocol


def _write_ids(root: Path, category: str, ids: list[str]) -> None:
    path = root / category / "baseline" / "bfcl" / "test_case_ids_to_generate.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"test_case_ids": ids}), encoding="utf-8")


def _write_runtime(runtime_dir: Path, *, ready: bool = True) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "rule.yaml").write_text("rule_id: memory_first_pass_retrieve_soft_v1_runtime_adapter\n", encoding="utf-8")
    (runtime_dir / "memory_operation_runtime_smoke_readiness.json").write_text(
        json.dumps({
            "memory_dev_smoke_ready": ready,
            "memory_runtime_adapter_ready": ready,
            "negative_control_activation_count": 0,
            "argument_creation_count": 0,
        }),
        encoding="utf-8",
    )
    (runtime_dir / "memory_operation_runtime_adapter_compile_status.json").write_text(
        json.dumps({"runtime_adapter_compile_ready": ready}),
        encoding="utf-8",
    )


def test_protocol_builds_six_case_memory_only_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    runtime = tmp_path / "runtime"
    _write_ids(source, "memory_kv", [f"memory_kv_{i}" for i in range(5)])
    _write_ids(source, "memory_rec_sum", [f"memory_rec_sum_{i}" for i in range(5)])
    _write_runtime(runtime, ready=True)

    report = protocol.evaluate(source, runtime, max_cases=6)

    assert report["smoke_protocol_ready_for_review"] is True
    assert report["provider_required"] == "novacode"
    assert report["selected_case_count"] == 6
    assert report["selected_category_counts"] == {"memory_kv": 3, "memory_rec_sum": 3}
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["does_not_authorize_scorer"] is True


def test_protocol_fails_when_runtime_not_ready(tmp_path: Path) -> None:
    source = tmp_path / "source"
    runtime = tmp_path / "runtime"
    _write_ids(source, "memory_kv", [f"memory_kv_{i}" for i in range(5)])
    _write_ids(source, "memory_rec_sum", [f"memory_rec_sum_{i}" for i in range(5)])
    _write_runtime(runtime, ready=False)

    report = protocol.evaluate(source, runtime, max_cases=6)

    assert report["smoke_protocol_ready_for_review"] is False
    assert report["failure_count"] == 1


def test_protocol_fails_when_category_ids_missing(tmp_path: Path) -> None:
    source = tmp_path / "source"
    runtime = tmp_path / "runtime"
    _write_ids(source, "memory_kv", [f"memory_kv_{i}" for i in range(5)])
    _write_runtime(runtime, ready=True)

    report = protocol.evaluate(source, runtime, max_cases=6)

    assert report["smoke_protocol_ready_for_review"] is False
    assert report["first_failure"]["missing_categories"] == ["memory_rec_sum"]
