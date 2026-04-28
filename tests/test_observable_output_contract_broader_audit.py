import json
from pathlib import Path

from scripts.diagnose_observable_output_contract_broader_audit import evaluate


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_broader_audit_counts_memory_preservation_pairs(tmp_path: Path):
    repair = tmp_path / "memory_repair.json"
    fix = tmp_path / "fix.json"
    post = tmp_path / "post.json"
    readiness = tmp_path / "readiness.json"
    _write_json(repair, {
        "records": [
            {
                "trace_id": "t1",
                "output_format_requirement_observable": True,
                "new_offline_replay_content_preserved": True,
                "new_offline_replay_repair_kinds": [],
                "new_offline_replay_issue_kinds": [],
            }
        ]
    })
    _write_json(fix, {"baseline_accuracy": 1.0})
    _write_json(post, {"report_scope": "postcondition_guided_dev_smoke_result"})
    _write_json(readiness, {"memory_runtime_adapter_ready": True})
    report = evaluate(repair, fix, post, readiness)
    assert report["eligible_preservation_candidate_count"] == 1
    assert report["raw_repair_pair_count"] == 1
    assert report["eligible_by_payload_kind"] == {"final_answer": 1}
    assert report["eligible_by_benchmark_slice"] == {"memory": 1}
    assert report["retain_prior_coverage_ready"] is False
    assert report["performance_claim_ready"] is False
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []


def test_broader_audit_blocks_mutated_or_unpreserved_payload(tmp_path: Path):
    repair = tmp_path / "memory_repair.json"
    missing = tmp_path / "missing.json"
    _write_json(repair, {
        "records": [
            {
                "trace_id": "t1",
                "output_format_requirement_observable": True,
                "new_offline_replay_content_preserved": False,
                "new_offline_replay_repair_kinds": ["coerce_no_tool_text_to_empty"],
                "new_offline_replay_issue_kinds": ["actionable_no_tool_decision"],
            }
        ]
    })
    report = evaluate(repair, missing, missing, missing)
    assert report["eligible_preservation_candidate_count"] == 0
    assert report["blocked_count"] == 1
    assert report["blocked_by_reason"] == {"payload_mutated_or_not_preserved": 1}
    assert report["retain_prior_coverage_ready"] is False
