import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/check_rashe_v0_offline.py")
ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0")


def run_checker(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict", *map(str, args)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def write_json(path, obj):
    path.write_text(json.dumps(obj))
    return path


def trace(signals, **extra):
    data = {
        "schema_version": "rashe_step_trace_v0",
        "trace_id": "synthetic-trace",
        "offline_only": True,
        "synthetic_fixture": True,
        "signals": signals,
        "provider_call_count": 0,
        "scorer_call_count": 0,
        "source_collection_call_count": 0,
    }
    data.update(extra)
    return data


def verifier(**extra):
    data = {
        "schema_version": "rashe_verifier_report_v0",
        "offline_only": True,
        "enabled": False,
        "runtime_authorized": False,
        "provider_call_count": 0,
        "scorer_call_count": 0,
        "source_collection_call_count": 0,
        "candidate_generation_authorized": False,
        "forbidden_field_violation_count": 0,
        "verifier_passed": True,
        "reject_reason": None,
    }
    data.update(extra)
    return data


def test_valid_seed_skills_pass_schema_and_checker():
    result = run_checker()
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_v0_offline_passed"] is True
    assert summary["seed_skill_count"] == 4
    assert summary["schema_file_count"] == 4
    assert summary["enabled"] is False
    assert summary["runtime_authorized"] is False
    assert summary["provider_call_count"] == 0
    assert summary["scorer_call_count"] == 0
    assert summary["source_collection_call_count"] == 0
    assert summary["candidate_generation_authorized"] is False


def test_forbidden_field_in_skill_fails(tmp_path):
    root = tmp_path / "rashe_v0"
    subprocess.run(["cp", "-R", str(ROOT), str(root)], check=True)
    skill = root / "seed_skills" / "bfcl_current_turn_focus.json"
    data = json.loads(skill.read_text())
    data["gold"] = "hidden answer"
    skill.write_text(json.dumps(data))
    result = run_checker("--root", root)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert summary["forbidden_field_violation_count"] >= 1
    assert any("skill_bfcl_current_turn_focus_forbidden_fields" in b for b in summary["blockers"])


def test_forbidden_field_in_trace_fails(tmp_path):
    path = write_json(tmp_path / "trace.json", trace(["multi_turn"], expected="hidden"))
    result = run_checker("--trace", path)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert any("trace_forbidden_fields" in b for b in summary["blockers"])


def test_deterministic_router_multi_turn_selects_current_turn_skill(tmp_path):
    path = write_json(tmp_path / "trace.json", trace(["multi_turn"]))
    result = run_checker("--trace", path)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["selected_skill_counts"] == {"bfcl_current_turn_focus": 1}


def test_malformed_no_tool_fixture_selects_format_guard(tmp_path):
    path = write_json(tmp_path / "trace.json", trace(["malformed_tool_call_json", "no_tool_call"]))
    result = run_checker("--trace", path)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["selected_skill_counts"] == {"bfcl_tool_call_format_guard": 1}


def test_ambiguous_fixture_fails_closed(tmp_path):
    path = write_json(tmp_path / "trace.json", trace(["multi_turn", "schema_present"]))
    result = run_checker("--trace", path)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["reject_reason_counts"] == {"ambiguous_skill_match": 1}
    assert summary["selected_skill_counts"] == {}


def test_verifier_rejects_provider_scorer_source_path_indicators(tmp_path):
    path = write_json(tmp_path / "verifier.json", verifier(diagnostic_path="provider://secret/scorer/source_collection"))
    result = run_checker("--verifier-report", path)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert any("verifier_forbidden_fields" in b for b in summary["blockers"])


def test_compact_report_keeps_fail_closed_flags():
    result = run_checker()
    assert result.returncode == 0
    summary = json.loads(result.stdout)
    assert summary["offline_only"] is True
    assert summary["enabled"] is False
    assert summary["runtime_authorized"] is False
    assert summary["candidate_generation_authorized"] is False
    assert summary["provider_call_count"] == 0
    assert summary["scorer_call_count"] == 0
    assert summary["source_collection_call_count"] == 0
