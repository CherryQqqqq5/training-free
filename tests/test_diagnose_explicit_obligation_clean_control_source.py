from __future__ import annotations

import json
from pathlib import Path

from scripts import diagnose_explicit_obligation_clean_control_source as diag


def _write_trace(path: Path, outputs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "request_original": {"input": [{"role": "user", "content": f"prompt for {path.stem}"}]},
                "final_response": {"output": outputs},
            }
        ),
        encoding="utf-8",
    )


def _message_output() -> list[dict]:
    return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "done"}]}]


def _memory_call_output() -> list[dict]:
    return [{"type": "function_call", "name": "core_memory_retrieve", "arguments": "{}"}]


def _protocol(control_rows: list[dict] | None = None) -> dict:
    return {
        "control_target_count": 8,
        "selected_positive_cases": [
            {
                "audit_case_id": "pos-1",
                "bfcl_case_id": "memory_kv_9-customer-9",
                "trace_relative_path": "memory_kv/baseline/traces/positive.json",
            }
        ],
        "selected_control_cases": control_rows or [],
        "control_selection_rejections": [],
    }


def _audit(sample_rejections: list[dict]) -> dict:
    return {"candidate_records": [], "sample_candidates": [], "sample_rejections": sample_rejections}


def test_evaluate_explains_materialized_true_control_shortage(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    clean_trace = "memory_kv/baseline/traces/clean.json"
    activated_trace = "memory_kv/baseline/traces/activated.json"
    _write_trace(source_root / clean_trace, _message_output())
    _write_trace(source_root / activated_trace, _memory_call_output())

    control_rows = [
        {
            "audit_case_id": "ctrl-clean",
            "source_audit_record_id": "src-clean",
            "category": "memory_kv",
            "trace_relative_path": clean_trace,
            "bfcl_case_id": "memory_kv_1-customer-1",
            "prompt_match_count": 1,
            "dependency_closure_ready": True,
            "negative_control_type": "no_memory_operation_intent",
            "operation": None,
        }
    ]
    for idx in range(7):
        control_rows.append(
            {
                "audit_case_id": f"ctrl-activated-{idx}",
                "source_audit_record_id": f"src-activated-{idx}",
                "category": "memory_kv",
                "trace_relative_path": activated_trace,
                "bfcl_case_id": f"memory_kv_{idx + 2}-customer-{idx + 2}",
                "prompt_match_count": 1,
                "dependency_closure_ready": True,
                "negative_control_type": "no_memory_operation_intent",
                "operation": None,
            }
        )
    protocol_path = tmp_path / "protocol.json"
    audit_path = tmp_path / "audit.json"
    protocol_path.write_text(json.dumps(_protocol(control_rows)), encoding="utf-8")
    audit_path.write_text(
        json.dumps(
            _audit(
                [
                    {
                        "source_audit_record_id": "src-clean",
                        "trace_relative_path": clean_trace,
                        "category": "memory_kv",
                    },
                    {
                        "source_audit_record_id": "src-activated",
                        "trace_relative_path": activated_trace,
                        "category": "memory_kv",
                    },
                ]
            )
        ),
        encoding="utf-8",
    )

    def fake_map(item, _source_root, _record_type):
        return {
            "bfcl_case_id": item.get("bfcl_case_id") or item.get("audit_case_id"),
            "prompt_match_count": 1,
            "mapping_status": "exact_current_user_prompt_match",
            "dependency_closure_ready": True,
            "generation_case_ids": [item.get("bfcl_case_id") or item.get("audit_case_id")],
            "missing_dependency_ids": [],
        }

    monkeypatch.setattr(diag, "_map_record", fake_map)
    report = diag.evaluate(protocol_path, audit_path, source_root, ("memory_kv",))

    assert report["clean_control_source_audit_ready"] is True
    assert report["scorer_or_model_run"] is False
    assert report["smoke_ready"] is False
    assert report["selection_gate_passed"] is False
    assert report["claim_boundary_acknowledged"] is True
    assert report["diagnostic_only"] is True
    assert report["polluted_controls_not_counted_as_clean"] is True
    assert report["materialized_protocol_control_count"] == 8
    assert report["materialized_selected_control_count"] == 8
    assert report["true_control_available_count"] == 1
    assert report["required_true_control_count"] == 8
    assert report["clean_selected_control_count"] == 1
    assert "selected_control_count" not in report
    assert report["source_pool_negative_control_activation_count"] == 1
    assert report["materialized_protocol_negative_control_activation_count"] == 7
    assert report["materialized_selected_control_activation_count"] == 7
    assert report["materialized_selected_control_baseline_activation_count"] == 7
    assert report["selected_smoke_control_count"] == 0
    assert report["selected_smoke_baseline_control_activation_count"] == 0
    assert report["duplicate_bfcl_case_id_count"] == 0
    assert report["duplicate_trace_relative_path_count"] == 0
    assert report["duplicate_audit_case_id_count"] == 0
    assert report["positive_control_overlap_count"] == 0
    assert report["ambiguous_bfcl_mapping_count"] == 0
    assert report["dependency_missing_count"] == 0
    assert report["summary"]["materialized_protocol_control_count"] == 8
    assert report["summary"]["materialized_protocol_true_control_count"] == 1
    assert report["summary"]["materialized_protocol_negative_control_activation_count"] == 7
    assert "materialized_protocol_true_controls_below_target" in report["blockers"]


def test_source_scan_finds_clean_no_activation_control_candidate(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    trace = "memory_kv/baseline/traces/clean.json"
    _write_trace(source_root / trace, _message_output())
    protocol_path = tmp_path / "protocol.json"
    audit_path = tmp_path / "audit.json"
    protocol_path.write_text(json.dumps(_protocol([])), encoding="utf-8")
    audit_path.write_text(
        json.dumps(
            _audit(
                [
                    {
                        "source_audit_record_id": "src-clean",
                        "trace_relative_path": trace,
                        "category": "memory_kv",
                        "operation": None,
                        "operation_scope": "non_retrieve_blocked",
                        "rejection_reason": "no_memory_operation_intent",
                        "review_rejection_reason": "no_memory_operation_intent",
                        "memory_witness_strength": "no_witness",
                        "memory_postcondition_witness_present": False,
                        "memory_postcondition_witnesses": [],
                        "recommended_tools": [],
                        "called_memory_tools": [],
                    }
                ]
            )
        ),
        encoding="utf-8",
    )

    def fake_map(item, _source_root, _record_type):
        return {
            "bfcl_case_id": "memory_kv_1-customer-1",
            "prompt_match_count": 1,
            "mapping_status": "exact_current_user_prompt_match",
            "dependency_closure_ready": True,
            "generation_case_ids": ["memory_kv_1-customer-1"],
            "missing_dependency_ids": [],
        }

    monkeypatch.setattr(diag, "_map_record", fake_map)
    report = diag.evaluate(protocol_path, audit_path, source_root, ("memory_kv",))

    assert report["summary"]["memory_capable_no_activation_trace_count"] == 1
    assert report["summary"]["clean_source_control_candidate_count"] == 1
    candidate = report["recommended_clean_control_candidates"][0]
    assert candidate["stage_status"] == {
        "baseline_no_memory_activation": "pass",
        "exact_bfcl_mapping": "pass",
        "no_explicit_obligation": "pass",
        "no_hidden_state_dependency": "pass",
        "uniqueness": "pass",
    }


def test_hidden_state_dependency_blocks_source_candidate(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    trace = "memory_rec_sum/baseline/traces/hidden.json"
    _write_trace(source_root / trace, _message_output())
    protocol_path = tmp_path / "protocol.json"
    audit_path = tmp_path / "audit.json"
    protocol_path.write_text(json.dumps(_protocol([])), encoding="utf-8")
    audit_path.write_text(
        json.dumps(
            _audit(
                [
                    {
                        "source_audit_record_id": "src-hidden",
                        "trace_relative_path": trace,
                        "category": "memory_rec_sum",
                        "operation": None,
                        "rejection_reason": "no_memory_operation_intent",
                        "memory_witness_strength": "weak_lookup_witness",
                        "memory_postcondition_witness_present": True,
                        "memory_postcondition_witnesses": ["memory_lookup_needed"],
                        "recommended_tools": [],
                        "called_memory_tools": [],
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        diag,
        "_map_record",
        lambda item, _source_root, _record_type: {
            "bfcl_case_id": "memory_rec_sum_1",
            "prompt_match_count": 1,
            "mapping_status": "exact_current_user_prompt_match",
            "dependency_closure_ready": True,
            "generation_case_ids": ["memory_rec_sum_1"],
            "missing_dependency_ids": [],
        },
    )

    report = diag.evaluate(protocol_path, audit_path, source_root, ("memory_rec_sum",))

    assert report["summary"]["clean_source_control_candidate_count"] == 0
    row = report["source_no_activation_candidates"][0]
    assert row["stage_status"]["no_hidden_state_dependency"] == "fail"
    assert "no_hidden_state_dependency_fail" in row["clean_control_rejection_reasons"]


def test_duplicate_bfcl_mapping_blocks_uniqueness(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    traces = ["memory_kv/baseline/traces/a.json", "memory_kv/baseline/traces/b.json"]
    for trace in traces:
        _write_trace(source_root / trace, _message_output())
    protocol_path = tmp_path / "protocol.json"
    audit_path = tmp_path / "audit.json"
    protocol_path.write_text(json.dumps(_protocol([])), encoding="utf-8")
    audit_path.write_text(
        json.dumps(
            _audit(
                [
                    {
                        "source_audit_record_id": f"src-{idx}",
                        "trace_relative_path": trace,
                        "category": "memory_kv",
                        "operation": None,
                        "rejection_reason": "no_memory_operation_intent",
                        "memory_witness_strength": "no_witness",
                        "memory_postcondition_witness_present": False,
                        "memory_postcondition_witnesses": [],
                        "recommended_tools": [],
                        "called_memory_tools": [],
                    }
                    for idx, trace in enumerate(traces)
                ]
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        diag,
        "_map_record",
        lambda item, _source_root, _record_type: {
            "bfcl_case_id": "memory_kv_duplicate",
            "prompt_match_count": 1,
            "mapping_status": "exact_current_user_prompt_match",
            "dependency_closure_ready": True,
            "generation_case_ids": ["memory_kv_duplicate"],
            "missing_dependency_ids": [],
        },
    )

    report = diag.evaluate(protocol_path, audit_path, source_root, ("memory_kv",))

    assert report["summary"]["clean_source_control_candidate_count"] == 0
    assert report["summary"]["no_activation_stage_counts"]["uniqueness"]["fail"] == 2
    assert report["summary"]["no_activation_rejection_reason_counts"]["uniqueness_fail_bfcl_case_id"] == 2


def test_cli_writes_json_and_markdown(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    trace = "memory_kv/baseline/traces/clean.json"
    _write_trace(source_root / trace, _message_output())
    protocol_path = tmp_path / "protocol.json"
    audit_path = tmp_path / "audit.json"
    output = tmp_path / "out.json"
    md = tmp_path / "out.md"
    protocol_path.write_text(json.dumps(_protocol([])), encoding="utf-8")
    audit_path.write_text(json.dumps(_audit([])), encoding="utf-8")
    monkeypatch.setattr(
        diag,
        "_map_record",
        lambda item, _source_root, _record_type: {
            "bfcl_case_id": "memory_kv_1-customer-1",
            "prompt_match_count": 1,
            "mapping_status": "exact_current_user_prompt_match",
            "dependency_closure_ready": True,
            "generation_case_ids": ["memory_kv_1-customer-1"],
            "missing_dependency_ids": [],
        },
    )

    exit_code = diag.main(
        [
            "--protocol",
            str(protocol_path),
            "--memory-audit",
            str(audit_path),
            "--source-root",
            str(source_root),
            "--category",
            "memory_kv",
            "--output",
            str(output),
            "--markdown-output",
            str(md),
        ]
    )

    assert exit_code == 0
    assert output.exists()
    assert md.exists()
    payload = json.loads(output.read_text())
    assert payload["candidate_commands"] == []
    assert payload["scorer_or_model_run"] is False
    assert payload["smoke_ready"] is False
    assert payload["selection_gate_passed"] is False
    assert payload["claim_boundary_acknowledged"] is True
    assert payload["materialized_protocol_control_count"] == 0
    assert payload["materialized_selected_control_count"] == 0
    assert payload["true_control_available_count"] == 0
    assert payload["required_true_control_count"] == 8
    assert payload["clean_selected_control_count"] == 0
    assert "selected_control_count" not in payload
    assert payload["selected_smoke_baseline_control_activation_count"] == 0
    assert payload["source_pool_negative_control_activation_count"] == 0
    assert "does not run BFCL" in md.read_text()


def test_top_level_does_not_alias_materialized_selected_controls(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    trace = "memory_kv/baseline/traces/activated.json"
    _write_trace(source_root / trace, _memory_call_output())
    protocol_path = tmp_path / "protocol.json"
    audit_path = tmp_path / "audit.json"
    protocol_path.write_text(
        json.dumps(
            _protocol(
                [
                    {
                        "audit_case_id": "ctrl-activated",
                        "source_audit_record_id": "src-activated",
                        "category": "memory_kv",
                        "trace_relative_path": trace,
                        "bfcl_case_id": "memory_kv_1-customer-1",
                        "prompt_match_count": 1,
                        "dependency_closure_ready": True,
                        "negative_control_type": "no_memory_operation_intent",
                        "operation": None,
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    audit_path.write_text(json.dumps(_audit([])), encoding="utf-8")
    monkeypatch.setattr(
        diag,
        "_map_record",
        lambda item, _source_root, _record_type: {
            "bfcl_case_id": "memory_kv_1-customer-1",
            "prompt_match_count": 1,
            "mapping_status": "exact_current_user_prompt_match",
            "dependency_closure_ready": True,
            "generation_case_ids": ["memory_kv_1-customer-1"],
            "missing_dependency_ids": [],
        },
    )

    report = diag.evaluate(protocol_path, audit_path, source_root, ("memory_kv",))

    assert "selected_control_count" not in report
    assert report["materialized_protocol_control_count"] == 1
    assert report["materialized_selected_control_count"] == 1
    assert report["clean_selected_control_count"] == 0
    assert report["selection_gate_passed"] is False
    assert report["smoke_ready"] is False
    assert report["next_required_action"] == "transition_to_evidence_grounding_prior_offline_audit"
