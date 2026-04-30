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
        "approval_status": "approved",
        "scope_change_approved": True,
        "scope_change_approval_id": "user_approved_rashe_2026-04-30",
        "scope_change_approval_owner": "project_lead_user",
        "scope_change_approval_timestamp_utc": "2026-04-30T00:00:00Z",
        "approved_before_implementation": False,
        "approved_before_source_collection": False,
        "approved_before_candidate_generation": False,
        "approved_before_scorer": False,
        "training_free_claim": True,
        "model_weights_changed": False,
        "bfcl_evaluator_modified": False,
        "same_model_same_provider_required": True,
        "provider": "Chuangzhi/Novacode",
        "provider_route": "Chuangzhi/Novacode",
        "provider_profile": "novacode",
        "model": "gpt-5.2",
        "bfcl_eval_version": "bfcl-eval==2025.12.17",
        "bfcl_protocol_id": "TBD_requires_approval",
        "baseline_comparator_kind": "same_model_same_provider_baseline",
        "hidden_model_calls_allowed": False,
        "suite_scope": "full_suite_or_signed_subset",
        "subset_approval_id": None,
        "dev_split_manifest": None,
        "holdout_split_manifest": None,
        "dev_holdout_disjoint": False,
        "candidate_pool_ready": False,
        "scorer_authorization": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "runtime_implementation_authorized": False,
        "source_collection_authorized": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "active_acceptance_path": False,
        "execution_authorized": False,
        "allowed_changes_scope_only": ["skill packages / SkillBank"],
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


def test_approved_scope_change_fail_closed_packet_passes(tmp_path):
    result = _run(tmp_path, _base_packet())
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_scope_approval_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["scope_change_approved"] is True
    assert summary["scope_change_approval_id"] == "user_approved_rashe_2026-04-30"


def test_runtime_authorization_fails_closed(tmp_path):
    packet = _base_packet()
    packet["approved_before_implementation"] = True
    packet["runtime_implementation_authorized"] = True
    result = _run(tmp_path, packet)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert "approved_before_implementation_not_false" in summary["blockers"]
    assert "runtime_implementation_authorized_not_false" in summary["blockers"]


def test_leakage_counter_fails_closed(tmp_path):
    packet = _base_packet()
    packet["no_leakage"]["gold_used"] = True
    result = _run(tmp_path, packet)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert "no_leakage_gold_used_not_false" in summary["blockers"]


def test_acceptance_fields_fail_closed_while_proposed(tmp_path):
    packet = _base_packet()
    packet["hidden_model_calls_allowed"] = True
    packet["subset_approval_id"] = "subset-approval"
    packet["dev_split_manifest"] = "dev.json"
    packet["holdout_split_manifest"] = "holdout.json"
    packet["dev_holdout_disjoint"] = True
    packet.pop("bfcl_protocol_id")
    result = _run(tmp_path, packet)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert "hidden_model_calls_allowed_not_false" in summary["blockers"]
    assert "subset_approval_id_not_null" in summary["blockers"]
    assert "dev_split_manifest_not_null" in summary["blockers"]
    assert "holdout_split_manifest_not_null" in summary["blockers"]
    assert "dev_holdout_disjoint_not_false" in summary["blockers"]
    assert "bfcl_protocol_id_invalid" in summary["blockers"]


def test_approval_metadata_required(tmp_path):
    packet = _base_packet()
    packet["scope_change_approved"] = False
    packet["scope_change_approval_id"] = "wrong"
    packet["scope_change_approval_owner"] = ""
    packet.pop("scope_change_approval_timestamp_utc")
    result = _run(tmp_path, packet)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert "scope_change_approved_not_true" in summary["blockers"]
    assert "scope_change_approval_id_invalid" in summary["blockers"]
    assert "scope_change_approval_owner_missing" in summary["blockers"]
    assert "scope_change_approval_owner_invalid" in summary["blockers"]
    assert "scope_change_approval_timestamp_utc_missing" in summary["blockers"]
