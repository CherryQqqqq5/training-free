from __future__ import annotations
import json
from pathlib import Path
from grc.compiler.action_candidates import generate_action_candidates
from grc.compiler.tool_state import ToolState
from grc.runtime.engine import RuleEngine
from scripts.build_m27t_source_pool_manifest import build_source_pool_manifest
from scripts.check_m27tw_offline import evaluate as evaluate_tw
from scripts.diagnose_m27w_rule_retention import decide

def _wj(p:Path,d:dict): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d)+'\n')
def test_source_pool_manifest_emits_baseline_only_commands_when_missing(tmp_path:Path):
    dev=tmp_path/'dev'; _wj(dev/'paired_subset_manifest.json',{'source_run_root':str(tmp_path/'source'),'runtime_config':'configs/runtime_bfcl_structured.yaml'})
    r=build_source_pool_manifest(dev,tmp_path/'pool',tmp_path/'repo',categories=['multi_turn_base'])
    assert r['m27t_source_pool_ready'] is False
    assert r['candidate_commands']==[]
    assert 'run_bfcl_v4_baseline.sh' in r['planned_source_collection_commands'][0]

def test_tool_family_candidates_include_echo_diff_and_reject_cat_for_write_goal():
    write=ToolState(available_tools=['cat','echo'], tool_schemas={'cat':{'properties':{'file_name':{}},'required':['file_name']}, 'echo':{'properties':{'content':{}},'required':['content']}}, latest_user_text="Write 'hello'", explicit_literals=['hello'], user_intent_family='explicit_literal_action', pending_goal_family='write_content')
    assert all(c.tool!='cat' for c in generate_action_candidates(write))
    diff=ToolState(available_tools=['diff'], tool_schemas={'diff':{'properties':{'source':{}},'required':['source']}}, latest_user_text='Compare files', user_intent_family='path_action', pending_goal_family='compare')
    # No fabricated diff args without evidence.
    assert generate_action_candidates(diff)==[]

def test_runtime_validation_alias_and_path_normalized_fields():
    candidate={'args':{'file_name':'/tmp/a.txt'},'arg_bindings':{'file_name':{'source':'explicit_literal','value':'/tmp/a.txt'}}}
    strict=RuleEngine._validate_action_candidate_args(candidate, {'path':'/workspace/a.txt'})
    assert strict['file_name']['key_mismatch'] is True
    assert strict['file_name']['alias_match'] is False
    norm=RuleEngine._validate_action_candidate_args_normalized(candidate, {'path':'/workspace/a.txt'})
    assert norm['file_name']['path_normalized_match'] is True

def test_rule_retention_requires_holdout_for_retain():
    rule={'net_case_gain':1,'regressed_count':0,'tool_match_rate':1.0,'arg_match_rate':1.0,'trajectory_fail_count':0,'fixed_count':1}
    assert decide(rule, False, True)[0]=='reject'
    assert decide(rule, True, True)[0]=='demote'

def test_m27tw_summary_requires_all_gates(tmp_path:Path):
    root=tmp_path/'subset'; hold=tmp_path/'hold'; source=tmp_path/'source'
    _wj(source/'source_collection_manifest.json',{'m27t_source_pool_ready':True})
    _wj(hold/'holdout_manifest.json',{'m27tw_holdout_manifest_ready':True})
    _wj(root/'m27u_tool_ranking.json',{'m27u_tool_ranking_passed':True})
    _wj(root/'m27v_arg_realization.json',{'m27v_arg_realization_passed':False})
    _wj(root/'m27w_rule_retention.json',{'m27w_rule_retention_passed':True})
    out=evaluate_tw(root,hold,source)
    assert out['m2_7tw_offline_passed'] is False


def test_rule_retention_can_mark_demote_ready_after_offline_uv_with_holdout():
    rule={'net_case_gain':1,'regressed_count':0,'tool_match_rate':1.0,'arg_match_rate':1.0,'trajectory_fail_count':0,'fixed_count':1}
    decision, reason, extra = decide(rule, True, True)
    assert decision == 'demote'
    assert extra['retain_blocked_by'] == 'missing_holdout_scorer_evidence'

def test_required_pair_validation_blocks_incomplete_cp_candidate():
    candidate={'tool':'cp','args':{'source':'a.txt'},'arg_bindings':{'source':{'source':'explicit_literal','value':'a.txt'}}}
    assert RuleEngine._candidate_required_pair_complete(candidate) is False
    validation = RuleEngine._validate_action_candidate_args(candidate, {'source':'a.txt'})
    assert validation['source']['required_pair_complete'] is False


def test_rule_retention_negative_dev_scorer_blocks_demote_ready():
    rule={'net_case_gain':1,'regressed_count':0,'tool_match_rate':1.0,'arg_match_rate':1.0,'trajectory_fail_count':0,'fixed_count':1}
    decision, reason, extra = decide(rule, True, True, dev_scorer_net_case_gain=-2)
    assert decision == 'demote'
    assert 'negative_overall_dev_scorer_net_gain' in extra['blockers']
    assert extra['retain_blocked_by'] == 'missing_holdout_scorer_evidence'

def test_m27tw_proxy_calibration_blocks_when_last_scorer_arg_low(tmp_path:Path):
    root=tmp_path/'subset'; hold=tmp_path/'hold'; source=tmp_path/'source'
    _wj(source/'source_collection_manifest.json',{'m27t_source_pool_ready':True})
    _wj(hold/'holdout_manifest.json',{'m27tw_holdout_manifest_ready':True,'selected_case_count':30,'candidate_generatable_count':30,'overlap_with_dev_case_ids':[]})
    _wj(root/'m27u_tool_ranking.json',{'m27u_tool_ranking_passed':True})
    _wj(root/'m27v_arg_realization.json',{'m27v_arg_realization_passed':True})
    _wj(root/'m27w_rule_retention.json',{'m27w_rule_retention_passed':True})
    _wj(root/'subset_summary.json',{'recommended_tool_match_rate_among_activated':0.7,'raw_normalized_arg_match_rate_among_activated':0.4})
    out=evaluate_tw(root,hold,source)
    assert out['proxy_calibration_passed'] is False
    assert out['m2_7tw_offline_passed'] is False

def test_m27tw_proxy_calibration_allows_explicit_gap_fix(tmp_path:Path):
    root=tmp_path/'subset'; hold=tmp_path/'hold'; source=tmp_path/'source'
    _wj(source/'source_collection_manifest.json',{'m27t_source_pool_ready':True})
    _wj(hold/'holdout_manifest.json',{'m27tw_holdout_manifest_ready':True,'selected_case_count':30,'candidate_generatable_count':30,'overlap_with_dev_case_ids':[]})
    _wj(root/'m27u_tool_ranking.json',{'m27u_tool_ranking_passed':True})
    _wj(root/'m27v_arg_realization.json',{'m27v_arg_realization_passed':True})
    _wj(root/'m27w_rule_retention.json',{'m27w_rule_retention_passed':True})
    _wj(root/'subset_summary.json',{'recommended_tool_match_rate_among_activated':0.7,'raw_normalized_arg_match_rate_among_activated':0.4})
    _wj(root/'m27x_scorer_proxy_gap.json',{'m27x_scorer_proxy_gap_explained':True,'fixed_by_code_change':True})
    out=evaluate_tw(root,hold,source)
    assert out['proxy_calibration_passed'] is True
    assert out['m2_7tw_offline_passed'] is True



def test_m27tw_offline_passes_after_scorer_feedback_and_reject_only_retention(tmp_path:Path):
    root=tmp_path/'subset'; hold=tmp_path/'hold'; source=tmp_path/'source'
    _wj(source/'source_collection_manifest.json',{'m27t_source_pool_ready':True})
    _wj(hold/'holdout_manifest.json',{'m27tw_holdout_manifest_ready':True,'selected_case_count':30,'candidate_generatable_count':30,'overlap_with_dev_case_ids':[]})
    _wj(root/'m27u_tool_ranking.json',{'m27u_tool_ranking_passed':True})
    _wj(root/'m27v_arg_realization.json',{'m27v_arg_realization_passed':True})
    _wj(root/'subset_summary.json',{'recommended_tool_match_rate_among_activated':0.63,'raw_normalized_arg_match_rate_among_activated':0.45,'net_case_gain':-2})
    _wj(root/'m27x_scorer_proxy_gap.json',{'m27x_scorer_proxy_gap_explained':True,'fixed_by_code_change':True})
    _wj(root/'m27w_rule_retention.json',{
        'm27w_rule_retention_passed':True,
        'decision_distribution':{'retain':0,'demote':0,'reject':3},
        'm27y_scorer_feedback_ready':True,
        'scorer_feedback_covers_regressions':True,
    })
    out=evaluate_tw(root,hold,source)
    assert out['proxy_calibration_passed'] is True
    assert out['m27w_rule_retention_passed'] is True
    assert out['m2_7tw_offline_passed'] is True


def test_m27tw_offline_remains_blocked_without_scorer_feedback_fix(tmp_path:Path):
    root=tmp_path/'subset'; hold=tmp_path/'hold'; source=tmp_path/'source'
    _wj(source/'source_collection_manifest.json',{'m27t_source_pool_ready':True})
    _wj(hold/'holdout_manifest.json',{'m27tw_holdout_manifest_ready':True,'selected_case_count':30,'candidate_generatable_count':30,'overlap_with_dev_case_ids':[]})
    _wj(root/'m27u_tool_ranking.json',{'m27u_tool_ranking_passed':True})
    _wj(root/'m27v_arg_realization.json',{'m27v_arg_realization_passed':True})
    _wj(root/'m27w_rule_retention.json',{'m27w_rule_retention_passed':True})
    _wj(root/'subset_summary.json',{'recommended_tool_match_rate_among_activated':0.63,'raw_normalized_arg_match_rate_among_activated':0.45})
    _wj(root/'m27x_scorer_proxy_gap.json',{'m27x_scorer_proxy_gap_explained':True,'fixed_by_code_change':False})
    out=evaluate_tw(root,hold,source)
    assert out['proxy_calibration_passed'] is False
    assert out['m2_7tw_offline_passed'] is False
