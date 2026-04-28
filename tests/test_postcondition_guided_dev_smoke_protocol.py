from __future__ import annotations

import json
from pathlib import Path

import scripts.build_postcondition_guided_dev_smoke_protocol as protocol


def _write_runtime(runtime_dir: Path, *, ready: bool = True) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "rule.yaml").write_text("patch_id: postcondition_guided_runtime_smoke_adapter\n", encoding="utf-8")


def _write_manifest(path: Path, rows: list[dict], *, commands: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"candidate_records": rows, "candidate_commands": commands or [], "planned_commands": []}), encoding="utf-8")


def _write_audit(path: Path, trace_root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"trace_root": str(trace_root)}), encoding="utf-8")


def _write_trace(trace_root: Path, rel: str, text: str = "read report") -> None:
    path = trace_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"request": {"messages": [{"role": "user", "content": text}], "tools": []}}), encoding="utf-8")


def _always_activated_plan(runtime_dir: Path, request_payload: dict) -> dict:
    return {"activated": True, "selected_tool": "cat", "blocked_reason": "activated"}


def _row(index: int, gap: str = "read_content") -> dict:
    return {
        "candidate_id": f"pc_{index}",
        "run_name": "required_target" if index < 4 else "soft_target",
        "trace_relative_path": f"required_target/traces/{index}.json",
        "postcondition_gap": gap,
        "recommended_tools": ["cat"] if gap == "read_content" else ["grep", "find"],
        "failure_labels": ["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
        "request_predicates": ["tools_available", "prior_tool_outputs_present"],
        "intervention_strength": "guidance_only",
        "exact_tool_choice": False,
        "runtime_enabled": False,
        "low_risk_dry_run_review_eligible": True,
        "ambiguity_flags": [],
    }


def test_postcondition_guided_protocol_freezes_nine_low_risk_cases(tmp_path: Path, monkeypatch) -> None:
    runtime = tmp_path / "runtime"
    manifest = tmp_path / "manifest.json"
    audit = tmp_path / "audit.json"
    trace_root = tmp_path / "traces"
    rows = [_row(i, "search_or_find" if i in {0, 1, 4} else "read_content") for i in range(9)]
    for row in rows:
        _write_trace(trace_root, row["trace_relative_path"])
    _write_runtime(runtime)
    _write_manifest(manifest, rows)
    _write_audit(audit, trace_root)
    monkeypatch.setattr(protocol.readiness, "evaluate", lambda runtime_dir: {
        "postcondition_guided_runtime_smoke_ready": True,
        "synthetic_final_answer_negative_control_activated": False,
        "synthetic_no_prior_tool_output_negative_control_activated": False,
        "synthetic_missing_capability_negative_control_activated": False,
    })
    monkeypatch.setattr(protocol, "_runtime_plan", _always_activated_plan)

    report = protocol.evaluate(manifest, audit, runtime)

    assert report["smoke_protocol_ready_for_review"] is True
    assert report["provider_required"] == "novacode"
    assert report["selected_case_count"] == 9
    assert report["capability_distribution"] == {"search_or_find": 3, "read_content": 6}
    assert report["runtime_replay_activation_count"] == 9
    assert report["runtime_replay_inactive_case_count"] == 0
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["does_not_authorize_scorer"] is True
    assert report["baseline_command"] is None
    assert report["candidate_command"] is None
    assert report["pre_registered_stop_loss"]["case_regressed_count_eq_0"] is True
    assert report["pre_registered_stop_loss"]["control_activation_count_eq_0"] is True
    assert report["control_lane"]["required_control_activation_count"] == 0
    assert report["control_lane"]["synthetic_final_answer_negative_control_activated"] is False
    assert report["hard_pins"] == ["provider_required", "selected_case_list_hash", "runtime_rule_sha256"]
    assert "activation_without_prior_tool_output" in report["invalidity_clauses"]


def test_postcondition_guided_protocol_rejects_commands(tmp_path: Path, monkeypatch) -> None:
    runtime = tmp_path / "runtime"
    manifest = tmp_path / "manifest.json"
    audit = tmp_path / "audit.json"
    trace_root = tmp_path / "traces"
    rows = [_row(i) for i in range(9)]
    for row in rows:
        _write_trace(trace_root, row["trace_relative_path"])
    _write_runtime(runtime)
    _write_manifest(manifest, rows, commands=["bash run_bfcl.sh"])
    _write_audit(audit, trace_root)
    monkeypatch.setattr(protocol.readiness, "evaluate", lambda runtime_dir: {"postcondition_guided_runtime_smoke_ready": True})
    monkeypatch.setattr(protocol, "_runtime_plan", _always_activated_plan)

    report = protocol.evaluate(manifest, audit, runtime)

    assert report["smoke_protocol_ready_for_review"] is False
    assert report["first_failure"]["check"] == "manifest_has_no_candidate_commands"


def test_postcondition_guided_protocol_rejects_ambiguous_or_non_low_risk_rows(tmp_path: Path, monkeypatch) -> None:
    runtime = tmp_path / "runtime"
    manifest = tmp_path / "manifest.json"
    audit = tmp_path / "audit.json"
    trace_root = tmp_path / "traces"
    rows = [_row(i) for i in range(8)] + [{**_row(8), "ambiguity_flags": ["multi_step_required"]}]
    for row in rows:
        _write_trace(trace_root, row["trace_relative_path"])
    _write_runtime(runtime)
    _write_manifest(manifest, rows)
    _write_audit(audit, trace_root)
    monkeypatch.setattr(protocol.readiness, "evaluate", lambda runtime_dir: {"postcondition_guided_runtime_smoke_ready": True})
    monkeypatch.setattr(protocol, "_runtime_plan", _always_activated_plan)

    report = protocol.evaluate(manifest, audit, runtime)

    assert report["smoke_protocol_ready_for_review"] is False
    assert report["first_failure"]["check"] == "selected_low_risk_case_count"


def test_postcondition_guided_protocol_rejects_forbidden_gap(tmp_path: Path, monkeypatch) -> None:
    runtime = tmp_path / "runtime"
    manifest = tmp_path / "manifest.json"
    audit = tmp_path / "audit.json"
    trace_root = tmp_path / "traces"
    rows = [_row(i) for i in range(8)] + [_row(8, "write_content")]
    for row in rows:
        _write_trace(trace_root, row["trace_relative_path"])
    _write_runtime(runtime)
    _write_manifest(manifest, rows)
    _write_audit(audit, trace_root)
    monkeypatch.setattr(protocol.readiness, "evaluate", lambda runtime_dir: {"postcondition_guided_runtime_smoke_ready": True})
    monkeypatch.setattr(protocol, "_runtime_plan", _always_activated_plan)

    report = protocol.evaluate(manifest, audit, runtime)

    assert report["smoke_protocol_ready_for_review"] is False
    assert any(item["check"] == "allowed_postcondition_gap" for item in report["failures"])
