import json
import subprocess
import sys
from pathlib import Path

from grc.skills.trace_buffer import StepTraceBuffer

SCRIPT = Path("scripts/check_rashe_step_trace_buffer.py")
FIXTURES = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/fixtures/step_trace_buffer")


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_step_trace_buffer_accepts_case_hash_synthetic_trace():
    buffer = StepTraceBuffer()
    record = buffer.append(load_fixture("step_trace_accept_current_turn.json"))
    assert record.rejected is False
    assert record.case_hash == "sha256:buffer-current-turn"
    summary = buffer.summary()
    assert summary["accepted_trace_count"] == 1
    assert summary["case_hash_allowed_count"] == 1
    assert summary["provider_call_count"] == 0
    assert summary["scorer_call_count"] == 0
    assert summary["source_collection_call_count"] == 0
    assert summary["candidate_generation_authorized"] is False


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
    assert summary["trace_fixture_count"] == 5
    assert summary["accepted_trace_count"] == 2
    assert summary["rejected_trace_count"] == 3
    assert summary["case_hash_allowed_count"] == 2
    assert summary["raw_case_id_rejected_count"] == 1
    assert summary["forbidden_field_rejected_count"] == 3
    assert summary["path_indicator_rejected_count"] == 1
    assert summary["provider_call_count"] == 0
    assert summary["scorer_call_count"] == 0
    assert summary["source_collection_call_count"] == 0
    assert summary["candidate_generation_authorized"] is False
    assert summary["ruleengine_proxy_active_path_imported"] is False
