from __future__ import annotations

import json
from pathlib import Path

import scripts.materialize_memory_operation_smoke_run_ids as materializer


def test_materialize_writes_expanded_generation_ids_to_both_run_roots(tmp_path: Path) -> None:
    protocol = tmp_path / "protocol.json"
    generation = {"memory_kv": ["memory_kv_prereq_0-customer-0", "memory_kv_0-customer-0"]}
    protocol.write_text(
        json.dumps({
            "target_case_count": 1,
            "generation_ids_by_category": generation,
        }),
        encoding="utf-8",
    )

    report = materializer.materialize(protocol, tmp_path / "baseline", tmp_path / "candidate")

    assert report["materialization_ready"] is True
    assert report["generation_case_count"] == 2
    assert report["prereq_case_count"] == 1
    for label in ("baseline", "candidate"):
        path = tmp_path / label / "bfcl" / "test_case_ids_to_generate.json"
        assert json.loads(path.read_text(encoding="utf-8")) == generation
    assert report["baseline_candidate_run_ids_hash_match"] is True
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
