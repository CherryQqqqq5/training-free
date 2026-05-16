from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from scripts.build_abhe_v0_bfcl_fresh_dev_slice import build_plan as build_fresh_slice_plan
from scripts.build_abhe_v0_candidate_materialization_plan import build_plan as build_candidate_plan
from scripts.check_abhe_v0_bfcl_dev_feedback import validate_feedback
from scripts.check_abhe_v0_bfcl_execution_readiness import build_report as build_execution_readiness
from scripts.check_abhe_v0_candidate_materialization_plan import validate_plan as validate_candidate_plan
from scripts.plan_abhe_v0_bfcl_archive_transition import build_plan as build_transition_plan

def test_fresh_slice_materialized_but_execution_readiness_stays_false() -> None:
    plan=build_fresh_slice_plan(); assert plan['fresh_dev_slice_materialized'] is True
    readiness=build_execution_readiness(); assert readiness['execution_readiness_check_passed'] is True; assert readiness['abhe_v0_bfcl_execution_ready'] is False; assert 'bfcl_fresh_dev_slice_not_materialized' not in readiness['blockers']; assert 'dev_smoke_approval_missing' in readiness['blockers']; assert 'scorer_authorization_false' in readiness['blockers']

def test_runner_cannot_execute_without_approval_packet() -> None:
    result=subprocess.run([sys.executable,'scripts/run_abhe_v0_bfcl_dev_smoke.py','--execute-approved','--approval-packet','outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_packet.json','--arm','baseline','--compact-only'], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode != 0; payload=json.loads(result.stdout); assert payload['execution_started'] is False; assert payload['provider_calls_made'] is False; assert payload['bfcl_generate_called'] is False; assert payload['bfcl_evaluate_called'] is False; assert payload['scorer_called'] is False

def test_dry_run_runner_does_not_call_provider_bfcl_or_scorer(tmp_path: Path) -> None:
    manifest_path=tmp_path/'manifest.json'; result=subprocess.run([sys.executable,'scripts/run_abhe_v0_bfcl_dev_smoke.py','--dry-run','--arm','baseline','--compact-only','--manifest-output',str(manifest_path)], check=True, text=True, stdout=subprocess.PIPE)
    payload=json.loads(result.stdout); assert payload['provider_calls_made'] is False; assert payload['bfcl_generate_called'] is False; assert payload['bfcl_evaluate_called'] is False; assert payload['scorer_called'] is False; assert payload['candidate_generated'] is False; assert manifest_path.exists()

def test_candidate_materialization_unapproved_generates_no_rule_yaml_or_jsonl() -> None:
    plan=build_candidate_plan(); assert validate_candidate_plan(plan)==[]; assert plan['candidate_rule_generated'] is False; assert plan['candidate_yaml_generated'] is False; assert plan['candidate_jsonl_generated'] is False; assert plan['candidate_materialized'] is False

def valid_feedback() -> dict:
    row={'entry_id':'state_tracking_v0','case_list_hash':'hash_placeholder','baseline_accuracy':0.2,'candidate_accuracy':0.4,'target_bucket_reduction':2,'fixed_count':3,'regressed_count':1,'net_fixed':2,'non_target_regression_count':0,'false_abstain_count':0,'valid_tool_call_suppression_count':0,'activation_precision':0.8,'activation_recall':0.7,'cost_delta_pct':1.0,'latency_delta_pct':1.0,'leakage_count':0,'boundary_violation_count':0,'provider_model_protocol_match':True,'fresh_slice_hash_match':True,'candidate_approved':True,'raw_material_absent':True,'holdout_touched':False,'full_suite_touched':False,'performance_claim_authorized':False}
    return {'artifact_kind':'abhe_v0_bfcl_dev_feedback','schema_version':'abhe_v0_bfcl_dev_feedback_v0','bounded_dev_smoke_only':True,'performance_evidence':False,'feedback_rows':[row]}

def test_dev_feedback_schema_rejects_holdout_full_suite_or_performance_claim() -> None:
    feedback=valid_feedback(); feedback['feedback_rows'][0]['holdout_touched']=True; assert 'row_0_holdout_touched_not_false' in validate_feedback(feedback)
    feedback=valid_feedback(); feedback['feedback_rows'][0]['full_suite_touched']=True; assert 'row_0_full_suite_touched_not_false' in validate_feedback(feedback)
    feedback=valid_feedback(); feedback['feedback_rows'][0]['performance_claim_authorized']=True; assert 'row_0_performance_claim_authorized_not_false' in validate_feedback(feedback)

def test_archive_transition_plan_defaults_to_no_archive_update() -> None:
    plan=build_transition_plan(valid_feedback(), synthetic_fixture_only=True); assert plan['abhe_v0_bfcl_archive_transition_plan_passed'] is True; assert plan['archive_updated'] is False; assert plan['does_not_update_archive'] is True

def test_positive_fake_feedback_transitions_to_dev_passed() -> None:
    plan=build_transition_plan(valid_feedback(), synthetic_fixture_only=True); assert plan['planned_transitions'][0]['to_status']=='dev_passed'

def test_leakage_fake_feedback_transitions_to_rejected_boundary_failure() -> None:
    feedback=valid_feedback(); feedback['feedback_rows'][0]['leakage_count']=1; plan=build_transition_plan(feedback, synthetic_fixture_only=True); assert plan['planned_transitions'][0]['to_status']=='rejected_boundary_failure'
