import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/check_rashe_scope_approval.py")


def _base_packet():
    return {
        "report_scope": "scope_change_approval_rashe",
        "scope_change_route": "retrieval_augmented_skill_harness_evolution",
        "short_name": "RASHE",
        "approval_status": "proposed",
        "approved_before_implementation": False,
        "approved_before_source_collection": False,
        "approved_before_candidate_generation": False,
        "approved_before_scorer": False,
        "training_free_claim": True,
        "model_weights_changed": False,
        "bfcl_evaluator_modified": False,
        "same_model_same_provider_required": True,
        "provider": "Chuangzhi/Novacode",
        "provider_profile": "novacode",
        "model": "gpt-5.2",
        "candidate_pool_ready": False,
        "scorer_authorization": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "proposed_only": True,
        "runtime_implementation_authorized": False,
        "source_collection_authorized": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "active_acceptance_path": False,
        "allowed_changes_proposed_only": ["skill packages / SkillBank"],
        "forbidden_changes": ["model weight updates"],
        "no_leakage": {
            "gold_used": False,
            "expected_used": False,
            "scorer_diff_used_for_skill": False,
            "candidate_output_used_for_skill": False,
            "holdout_used_for_skill": False,
            "raw_trace_committed": False,
        },
        "gate_fields": {
            "suite_scope": "full_suite_or_signed_subset",
            "subset_approval_id_required_if_not_full_suite": True,
            "dev_holdout_disjoint_required_before_scorer": True,
            "candidate_pool_gate_required": True,
            "paired_comparison_required": True,
            "cost_gate_required": True,
            "latency_gate_required": True,
            "regression_gate_required": True,
        },
    }


def _run(tmp_path, packet):
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps(packet))
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--approval", str(approval), "--compact", "--strict"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_proposed_fail_closed_packet_passes(tmp_path):
    result = _run(tmp_path, _base_packet())
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_scope_approval_passed"] is True
    assert summary["approval_status"] == "proposed"


def test_approved_packet_fails_closed(tmp_path):
    packet = _base_packet()
    packet["approval_status"] = "approved"
    packet["approved_before_implementation"] = True
    result = _run(tmp_path, packet)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert "approval_status_invalid" in summary["blockers"]
    assert "approved_before_implementation_not_false" in summary["blockers"]


def test_leakage_counter_fails_closed(tmp_path):
    packet = _base_packet()
    packet["no_leakage"]["gold_used"] = True
    result = _run(tmp_path, packet)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert "no_leakage_gold_used_not_false" in summary["blockers"]
