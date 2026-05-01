import subprocess
import sys

from scripts.check_rashe_source_diagnostic_interpretation import SEED_SKILLS, check


def test_source_diagnostic_interpretation_checker_passes_current_doc():
    result = subprocess.run([sys.executable, "scripts/check_rashe_source_diagnostic_interpretation.py", "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert check()["blockers"] == []


def test_source_diagnostic_interpretation_checker_rejects_threshold_drift(tmp_path):
    doc = tmp_path / "interpretation.md"
    lines = ["# Test", "## Frozen Skill Primary Bucket Mapping"]
    for skill, buckets in SEED_SKILLS.items():
        lines.append(f"- `{skill}`: " + ", ".join(f"`{bucket}`" for bucket in buckets))
    lines.append("raw prompts raw case IDs gold expected reference scorer diff provider raw payload performance evidence +3pp claims Huawei acceptance")
    doc.write_text("\n".join(lines))
    blockers = check(doc)["blockers"]
    assert any("interpretation_threshold_wording_missing" in blocker for blocker in blockers)


def test_source_diagnostic_interpretation_checker_rejects_mapping_drift(tmp_path):
    doc = tmp_path / "interpretation.md"
    text = """
# Test
- `bfcl_web_search_decomposition`: `answered_without_tool`, `wrong_first_tool`, `search_query_too_broad`, `fetch_missing_after_search`, `memory_not_retrieved`
- `bfcl_memory_retrieve_before_answer`: `memory_not_retrieved`, `memory_update_when_should_search`, `final_answer_before_tool`
- `bfcl_multi_turn_state_tracking`: `multi_turn_state_lost`, `wrong_first_tool`, `final_answer_before_tool`
- `bfcl_parser_feedback_retry`: `invalid_tool_call_format`, `parser_schema_failure`
- `bfcl_hallucination_abstain`: `unsupported_hallucinated_answer`
skill-level aggregate count across that skill's frozen primary buckets at least `12/160` across the 160 signed source cases cover at least `2` signed categories not a single-bucket threshold every skill-level aggregate is below `12` skill design review
raw prompts raw case IDs gold expected reference scorer diff provider raw payload performance evidence +3pp claims Huawei acceptance
"""
    doc.write_text(text)
    blockers = check(doc)["blockers"]
    assert any("interpretation_bucket_extra:bfcl_web_search_decomposition:memory_not_retrieved" in blocker for blocker in blockers)
    assert any("interpretation_bucket_missing:bfcl_hallucination_abstain:irrelevant_tool_call" in blocker for blocker in blockers)
