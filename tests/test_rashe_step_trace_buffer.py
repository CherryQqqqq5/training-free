import json
import subprocess
import sys
from pathlib import Path

from grc.skills.trace_buffer import REQUIRED_V0_2_TRACE_FIELDS, StepTraceBuffer

SCRIPT = Path("scripts/check_rashe_step_trace_buffer.py")
FIXTURES = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/fixtures/step_trace_buffer")


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_step_trace_buffer_accepts_case_hash_synthetic_trace_with_v0_2_contract():
    trace = load_fixture("step_trace_accept_current_turn.json")
    for field in REQUIRED_V0_2_TRACE_FIELDS:
        assert field in trace
    buffer = StepTraceBuffer()
    record = buffer.append(trace)
    assert record.rejected is False
    assert record.trace_hash == "sha256:trace-buffer-current-turn"
    assert record.case_hash == "sha256:buffer-current-turn"
    assert record.source_scope == "synthetic"
    assert record.category == "synthetic_rashe_fixture"
    assert record.step_index == 0
    summary = buffer.summary()
    assert summary["accepted_trace_count"] == 1
    assert summary["case_hash_allowed_count"] == 1
    assert summary["synthetic_trace_count"] == 1
    assert summary["provider_call_count"] == 0
    assert summary["scorer_call_count"] == 0
    assert summary["source_collection_call_count"] == 0
    assert summary["candidate_generation_authorized"] is False
    assert summary["performance_evidence"] is False


def test_step_trace_buffer_accepts_approved_compact_without_raw_indicators():
    buffer = StepTraceBuffer()
    record = buffer.append(load_fixture("step_trace_accept_approved_compact.json"))
    assert record.rejected is False
    assert record.source_scope == "approved_compact"
    assert buffer.summary()["approved_compact_trace_count"] == 1


def test_step_trace_buffer_rejects_raw_case_id():
    buffer = StepTraceBuffer()
    record = buffer.append(load_fixture("step_trace_reject_raw_case_id.json"))
    assert record.rejected is True
    assert record.reject_reason == "raw_case_id"
    assert buffer.summary()["raw_case_id_rejected_count"] == 1


def test_step_trace_buffer_rejects_forbidden_field_and_path_indicator():
    buffer = StepTraceBuffer()
    forbidden = buffer.append(load_fixture("step_trace_reject_forbidden_field.json"))
    path = buffer.append(load_fixture("step_trace_reject_path_indicator.json"))
    assert forbidden.rejected is True
    assert forbidden.reject_reason == "forbidden_field"
    assert path.rejected is True
    assert path.reject_reason == "path_indicator"
    summary = buffer.summary()
    assert summary["forbidden_field_rejected_count"] == 2
    assert summary["path_indicator_rejected_count"] == 1


def test_step_trace_buffer_rejects_dev_only_future_and_unknown_source_scope():
    buffer = StepTraceBuffer()
    dev_future = buffer.append(load_fixture("step_trace_reject_dev_only_future.json"))
    unknown = buffer.append(load_fixture("step_trace_reject_unknown_source_scope.json"))
    assert dev_future.rejected is True
    assert dev_future.reject_reason == "dev_only_future_scope_disabled"
    assert unknown.rejected is True
    assert unknown.reject_reason == "source_scope_not_allowed"
    assert buffer.summary()["source_scope_rejected_count"] == 2


def test_step_trace_buffer_rejects_missing_v0_2_required_field():
    buffer = StepTraceBuffer()
    trace = load_fixture("step_trace_accept_current_turn.json")
    del trace["trace_hash"]
    record = buffer.append(trace)
    assert record.rejected is True
    assert record.reject_reason == "required_field_missing"
    assert buffer.summary()["required_field_missing_rejected_count"] == 1


def test_step_trace_buffer_rejects_provider_scorer_source_calls():
    buffer = StepTraceBuffer()
    trace = load_fixture("step_trace_accept_current_turn.json")
    trace["provider_call_count"] = 1
    record = buffer.append(trace)
    assert record.rejected is True
    assert record.reject_reason == "call_count_nonzero"
    assert buffer.summary()["provider_call_count"] == 1


def test_step_trace_buffer_checker_compact_report_passes_fail_closed():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["step_trace_buffer_offline_passed"] is True
    assert summary["trace_fixture_count"] == 7
    assert summary["accepted_trace_count"] == 2
    assert summary["rejected_trace_count"] == 5
    assert summary["case_hash_allowed_count"] == 2
    assert summary["raw_case_id_rejected_count"] == 1
    assert summary["forbidden_field_rejected_count"] == 3
    assert summary["path_indicator_rejected_count"] == 1
    assert summary["source_scope_rejected_count"] == 2
    assert summary["synthetic_trace_count"] == 1
    assert summary["approved_compact_trace_count"] == 1
    assert summary["provider_call_count"] == 0
    assert summary["scorer_call_count"] == 0
    assert summary["source_collection_call_count"] == 0
    assert summary["candidate_generation_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["required_v0_2_fields"] == list(REQUIRED_V0_2_TRACE_FIELDS)
    assert summary["ruleengine_proxy_active_path_imported"] is False
