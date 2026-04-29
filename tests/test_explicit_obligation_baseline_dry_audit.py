from __future__ import annotations

import json
from pathlib import Path

from scripts.diagnose_explicit_obligation_baseline_dry_audit import evaluate


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _trace(root: Path, rel: str, outputs: list[dict]) -> None:
    _write(root / rel, {"final_response": {"output": outputs}})


def test_dry_audit_marks_memory_call_as_ceiling_risk(tmp_path: Path) -> None:
    source = tmp_path / "source"
    rel = "memory_kv/baseline/traces/p.json"
    _trace(source, rel, [{"type": "function_call", "name": "core_memory_retrieve", "arguments": "{}"}])
    protocol = tmp_path / "protocol.json"
    _write(protocol, {
        "selected_positive_cases": [{"audit_case_id": "p", "bfcl_case_id": "memory_kv_0", "category": "memory_kv", "trace_relative_path": rel}],
        "selected_control_cases": [],
    })

    report = evaluate(protocol, source)

    assert report["positive_bucket_counts"] == {"baseline_process_already_uses_memory": 1}
    assert report["baseline_ceiling_risk"] is True
    assert "primary_positive_capability_miss_below_6" in report["blockers"]


def test_dry_audit_marks_final_answer_without_memory_as_primary_positive(tmp_path: Path) -> None:
    source = tmp_path / "source"
    positives = []
    for i in range(6):
        rel = f"memory_kv/baseline/traces/p{i}.json"
        _trace(source, rel, [{"type": "message", "content": "answer"}])
        positives.append({"audit_case_id": f"p{i}", "bfcl_case_id": f"memory_kv_{i}", "category": "memory_kv", "trace_relative_path": rel})
    controls = []
    for i in range(8):
        rel = f"memory_kv/baseline/traces/c{i}.json"
        _trace(source, rel, [{"type": "message", "content": "answer"}])
        controls.append({"audit_case_id": f"c{i}", "bfcl_case_id": f"memory_kv_c{i}", "category": "memory_kv", "trace_relative_path": rel})
    protocol = tmp_path / "protocol.json"
    _write(protocol, {"selected_positive_cases": positives + positives[:6], "selected_control_cases": controls})

    report = evaluate(protocol, source)

    assert report["primary_positive_capability_miss_count"] == 12
    assert report["control_memory_activation_count"] == 0
    assert report["smoke_selection_ready_after_baseline_dry_audit"] is True


def test_dry_audit_blocks_control_memory_activation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    positives = []
    for i in range(12):
        rel = f"memory_kv/baseline/traces/p{i}.json"
        _trace(source, rel, [{"type": "message", "content": "answer"}])
        positives.append({"audit_case_id": f"p{i}", "bfcl_case_id": f"memory_kv_{i}", "category": "memory_kv", "trace_relative_path": rel})
    controls = []
    for i in range(8):
        rel = f"memory_kv/baseline/traces/c{i}.json"
        output = {"type": "function_call", "name": "archival_memory_key_search", "arguments": "{}"} if i == 0 else {"type": "message", "content": "answer"}
        _trace(source, rel, [output])
        controls.append({"audit_case_id": f"c{i}", "bfcl_case_id": f"memory_kv_c{i}", "category": "memory_kv", "trace_relative_path": rel})
    protocol = tmp_path / "protocol.json"
    _write(protocol, {"selected_positive_cases": positives, "selected_control_cases": controls})

    report = evaluate(protocol, source)

    assert report["control_memory_activation_count"] == 1
    assert report["smoke_selection_ready_after_baseline_dry_audit"] is False
    assert "control_memory_activation_present" in report["blockers"]
