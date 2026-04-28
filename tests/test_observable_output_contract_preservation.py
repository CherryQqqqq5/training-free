from pathlib import Path
import json

import scripts.diagnose_observable_output_contract_preservation as audit


def test_output_contract_audit_reports_wrapper_only_candidates(tmp_path: Path) -> None:
    repair = tmp_path / "repair.json"
    fix = tmp_path / "fix.json"
    repair.write_text(json.dumps({
        "target_post_tool_trace_count": 2,
        "output_format_requirement_observable_count": 2,
        "old_coerce_no_tool_text_to_empty_count": 2,
        "new_offline_replay_preserved_final_answer_count": 2,
    }))
    fix.write_text(json.dumps({"absolute_pp_delta": 0.0, "baseline_accuracy": 1.0, "candidate_accuracy": 1.0}))

    report = audit.evaluate(repair, fix)

    assert report["wrapper_only_repair_candidate_count"] == 2
    assert report["retain_prior_candidate"] is True
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["performance_claim_ready"] is False
