import json
from pathlib import Path

from scripts.diagnose_observable_output_contract_pair_inventory import evaluate


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_pair_inventory_finds_before_after_memory_pair(tmp_path: Path):
    _write(tmp_path / "memory_operation_final_answer_repair_audit.json", {
        "records": [{
            "trace_id": "t1",
            "old_trace_repair_kinds": ["coerce_no_tool_text_to_empty"],
            "new_offline_replay_content_preserved": True,
            "new_offline_replay_repair_kinds": [],
        }]
    })
    report = evaluate(tmp_path)
    assert report["candidate_raw_repair_pair_count"] == 1
    assert report["candidate_pairs_by_slice"] == {"memory": 1}
    assert report["cross_slice_pair_inventory_ready"] is False
    assert report["candidate_commands"] == []


def test_pair_inventory_marks_cross_slice_when_non_memory_pair_exists(tmp_path: Path):
    _write(tmp_path / "memory_pair.json", {
        "records": [{"old_trace_repair_kinds": ["x"], "new_offline_replay_content_preserved": True}]
    })
    _write(tmp_path / "postcondition_pair.json", {
        "records": [{"old_trace_repair_kinds": ["x"], "new_offline_replay_content_preserved": True}]
    })
    report = evaluate(tmp_path)
    assert report["candidate_raw_repair_pair_count"] == 2
    assert report["non_memory_raw_repair_pair_count"] == 1
    assert report["cross_slice_pair_inventory_ready"] is True
