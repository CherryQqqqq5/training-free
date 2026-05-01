import subprocess
import sys

from scripts.check_rashe_source_diagnostic_interpretation import check


def test_source_diagnostic_interpretation_checker_passes_current_doc():
    result = subprocess.run([sys.executable, "scripts/check_rashe_source_diagnostic_interpretation.py", "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert check()["blockers"] == []


def test_source_diagnostic_interpretation_checker_rejects_threshold_drift(tmp_path):
    doc = tmp_path / "interpretation.md"
    text = """
# Test
bfcl_web_search_decomposition search_query_too_broad fetch_missing_after_search wrong_first_tool
bfcl_memory_retrieve_before_answer memory_not_retrieved memory_update_when_should_search
bfcl_multi_turn_state_tracking multi_turn_state_lost invalid_tool_call_format
bfcl_parser_feedback_retry parser_schema_failure final_answer_before_tool
bfcl_hallucination_abstain unsupported_hallucinated_answer answered_without_tool irrelevant_tool_call
raw prompts raw case IDs gold expected reference scorer diff provider raw payload performance evidence +3pp claims Huawei acceptance
"""
    doc.write_text(text)
    blockers = check(doc)["blockers"]
    assert any("interpretation_threshold_wording_missing" in blocker for blocker in blockers)
