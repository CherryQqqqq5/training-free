import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_candidate_proposer_artifacts import DEFAULT_ROOT, check

CHECKER = Path("scripts/check_rashe_candidate_proposer_artifacts.py")


def copy_root(tmp_path: Path) -> Path:
    root = tmp_path / "rashe_candidate_proposals"
    shutil.copytree(DEFAULT_ROOT, root)
    return root


def load_spec(root: Path, skill: str) -> dict:
    return json.loads((root / skill / "candidate_spec.json").read_text())


def write_spec(root: Path, skill: str, data: dict) -> None:
    (root / skill / "candidate_spec.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_candidate_proposer_artifact_checker_passes_current_artifacts():
    result = subprocess.run([sys.executable, str(CHECKER), "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_candidate_proposer_artifacts_passed"] is True
    assert summary["allowed_seed_skills"] == ["bfcl_multi_turn_state_tracking", "bfcl_hallucination_abstain"]
    assert len(summary["artifact_files"]) == 6
    assert all(not path.endswith(".jsonl") for path in summary["artifact_files"])


def test_artifact_checker_rejects_extra_skill_and_jsonl(tmp_path):
    root = copy_root(tmp_path)
    extra = root / "bfcl_web_search_decomposition"
    extra.mkdir()
    (extra / "candidate_spec.jsonl").write_text("{}\n")

    blockers = check(root)["blockers"]
    joined = "\n".join(blockers)
    assert "bfcl_web_search_decomposition" in joined
    assert "candidate_proposer_jsonl_forbidden" in joined


def test_artifact_checker_rejects_downstream_flags(tmp_path):
    root = copy_root(tmp_path)
    spec = load_spec(root, "bfcl_multi_turn_state_tracking")
    spec["candidate_generation_authorized"] = True
    spec["scorer_authorized"] = True
    spec["performance_evidence"] = True
    write_spec(root, "bfcl_multi_turn_state_tracking", spec)

    blockers = check(root)["blockers"]
    assert "candidate_proposer_spec_bfcl_multi_turn_state_tracking_candidate_generation_authorized_not_false:True" in blockers
    assert "candidate_proposer_spec_bfcl_multi_turn_state_tracking_scorer_authorized_not_false:True" in blockers
    assert "candidate_proposer_spec_bfcl_multi_turn_state_tracking_performance_evidence_not_false:True" in blockers


def test_artifact_checker_rejects_evidence_or_route_drift(tmp_path):
    root = copy_root(tmp_path)
    spec = load_spec(root, "bfcl_hallucination_abstain")
    spec["route_model"] = "gpt-4o"
    spec["compact_evidence"]["irrelevance"]["irrelevant_tool_call"] = 19
    write_spec(root, "bfcl_hallucination_abstain", spec)

    blockers = check(root)["blockers"]
    assert "candidate_proposer_spec_bfcl_hallucination_abstain_route_model_invalid:'gpt-4o'" in blockers
    assert "candidate_proposer_spec_bfcl_hallucination_abstain_compact_evidence_invalid" in blockers


def test_artifact_checker_rejects_forbidden_text_and_secret_like_material(tmp_path):
    root = copy_root(tmp_path)
    skill_md = root / "bfcl_multi_turn_state_tracking" / "SKILL.md"
    skill_md.write_text(skill_md.read_text() + "\ncase_id api_key secret_token\n")

    blockers = check(root)["blockers"]
    joined = "\n".join(blockers)
    assert "case_id" in joined
    assert "api_key" in joined
    assert "secret_token" in joined


def test_artifact_checker_rejects_failed_no_leakage_audit(tmp_path):
    root = copy_root(tmp_path)
    audit_path = root / "bfcl_hallucination_abstain" / "no_leakage_audit.json"
    audit = json.loads(audit_path.read_text())
    audit["audit_passed"] = False
    audit["prompt_material_used"] = True
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")

    blockers = check(root)["blockers"]
    assert "candidate_proposer_audit_bfcl_hallucination_abstain_not_passed:False" in blockers
    assert "candidate_proposer_audit_bfcl_hallucination_abstain_prompt_material_used_not_false:True" in blockers
