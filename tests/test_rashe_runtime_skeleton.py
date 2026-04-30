import json
import subprocess
import sys
from pathlib import Path

from grc.skills.router import SkillRouter
from grc.skills.store import SkillStore
from grc.skills.verifier import load_simple_yaml, verify_runtime_config, verify_trace

SCRIPT = Path("scripts/check_rashe_runtime_skeleton.py")
CONFIG = Path("configs/runtime_bfcl_skills.yaml")
FIXTURES = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/fixtures")


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_runtime_config_default_disabled_and_inert():
    config = load_simple_yaml(CONFIG)
    assert config["enabled"] is False
    assert config["runtime_behavior_authorized"] is False
    assert config["provider_calls_authorized"] is False
    assert config["source_collection_authorized"] is False
    assert config["scorer_authorized"] is False
    assert config["candidate_generation_authorized"] is False
    report = verify_runtime_config(config)
    assert report.verifier_passed is True
    assert report.provider_call_count == 0
    assert report.scorer_call_count == 0
    assert report.source_collection_call_count == 0


def test_skill_store_loads_disabled_seed_skills_only():
    store = SkillStore.load_manifest()
    assert store.blockers == []
    assert set(store.skills) == {
        "bfcl_current_turn_focus",
        "bfcl_schema_reading",
        "bfcl_tool_call_format_guard",
        "bfcl_memory_web_search_discipline",
    }
    for skill in store.skills.values():
        assert skill.enabled is False
        assert skill.offline_only is True
        assert skill.runtime_authorized is False


def test_router_selects_each_seed_skill_deterministically():
    cases = {
        "positive_current_turn_focus.json": "bfcl_current_turn_focus",
        "positive_schema_reading.json": "bfcl_schema_reading",
        "positive_tool_call_format_guard.json": "bfcl_tool_call_format_guard",
        "positive_memory_web_search_discipline.json": "bfcl_memory_web_search_discipline",
    }
    router = SkillRouter()
    for fixture, expected_skill in cases.items():
        decision = router.route(load_fixture(fixture))
        assert decision.decision_status == "selected"
        assert decision.selected_skill_id == expected_skill
        assert decision.provider_call_count == 0
        assert decision.scorer_call_count == 0
        assert decision.source_collection_call_count == 0


def test_router_rejects_ambiguous_fixture():
    decision = SkillRouter().route(load_fixture("reject_ambiguous_routing.json"))
    assert decision.decision_status == "ambiguous_reject"
    assert decision.reject_reason == "ambiguous_skill_match"
    assert decision.selected_skill_id is None


def test_verifier_rejects_forbidden_path_and_raw_case_id_but_allows_case_hash():
    forbidden = verify_trace(load_fixture("reject_forbidden_field.json"))
    assert forbidden.verifier_passed is False
    assert forbidden.forbidden_field_violation_count > 0

    path = verify_trace(load_fixture("reject_path_indicator.json"))
    assert path.verifier_passed is False
    assert path.path_indicator_violation_count > 0

    raw_case_id = verify_trace(load_fixture("reject_raw_case_id.json"))
    assert raw_case_id.verifier_passed is False
    assert raw_case_id.raw_case_id_rejected_count == 1

    case_hash = verify_trace(load_fixture("positive_case_hash_allowed.json"))
    assert case_hash.verifier_passed is True
    assert case_hash.case_hash_allowed_count == 1


def test_skeleton_import_does_not_load_runtime_proxy_modules():
    for name in list(sys.modules):
        if name.startswith("grc.runtime"):
            del sys.modules[name]
    __import__("grc.skills")
    loaded = [name for name in sys.modules if name.startswith("grc.runtime")]
    assert loaded == []


def test_runtime_skeleton_checker_compact_report_passes_fail_closed():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_runtime_skeleton_passed"] is True
    assert summary["enabled"] is False
    assert summary["runtime_behavior_authorized"] is False
    assert summary["provider_call_count"] == 0
    assert summary["scorer_call_count"] == 0
    assert summary["source_collection_call_count"] == 0
    assert summary["candidate_generation_authorized"] is False
    assert summary["ruleengine_proxy_active_path_imported"] is False
    assert summary["forbidden_field_violation_count"] == 0
    assert summary["raw_case_id_rejected_count"] == 1
    assert summary["case_hash_allowed_count"] == 5
