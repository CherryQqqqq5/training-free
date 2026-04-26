from __future__ import annotations
import json
from pathlib import Path
from grc.compiler.action_candidates import generate_action_candidates
from grc.compiler.tool_state import ToolState
from grc.runtime.engine import RuleEngine
from scripts.diagnose_m27s_activation_recall import classify_activation_recall
from scripts.diagnose_m27s_arg_realization import evaluate_arg_realization
from scripts.diagnose_m27s_tool_ranking import evaluate_tool_ranking
from scripts.check_m27s_offline import evaluate

def _wj(p:Path,d:dict): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d)+"\n")
def _wjl(p:Path,rows:list[dict]): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(''.join(json.dumps(r)+'\n' for r in rows))

def test_activation_recall_classifies_guard_rejection_reason():
    case={'case_id':'a','baseline_success':False,'candidate_success':False,'blocked_reason':'activation_predicates_unmet'}
    guard={'before_guard_plan':{'activated':True,'selected_action_candidate':{'tool':'cat'}},'after_guard_plan':{'activated':False},'case_final_guard_reason':'weak_arg_binding_evidence'}
    out=classify_activation_recall(case,guard)
    assert out['classification']=='weak_binding'
    assert out['actionable_false_negative'] is False

def test_pending_goal_tool_family_enforcement():
    move=ToolState(available_tools=['cat','mv'], tool_schemas={'cat':{'properties':{'file_name':{}},'required':['file_name']}, 'mv':{'properties':{'source':{},'destination':{}},'required':['source','destination']}}, latest_user_text="Move 'a.txt' to 'b.txt'", explicit_literals=['a.txt','b.txt'], user_intent_family='move_or_copy', pending_goal_family='move_or_copy')
    cs=generate_action_candidates(move)
    assert cs and cs[0].tool=='mv'
    read=ToolState(available_tools=['cat'], tool_schemas={'cat':{'properties':{'file_name':{}},'required':['file_name']}}, latest_user_text="Read 'a.txt'", explicit_literals=['a.txt'], user_intent_family='read_file_content', pending_goal_family='read_content')
    assert generate_action_candidates(read)[0].tool=='cat'

def test_runtime_guidance_uses_exact_json_without_tool_choice():
    engine=RuleEngine('/tmp/no-rules', runtime_policy={'exact_next_tool_choice_mode':'guidance_only'})
    frag=engine._recommended_policy_tool_fragments({'tools':[{'function':{'name':'cat'}}]}, {'activated':True,'selected_tool':'cat','selected_action_candidate':{'tool':'cat','args':{'file_name':'a.txt'},'arg_bindings':{'file_name':{'source':'explicit_literal'}}},'recommended_tools':['cat']})[0]
    assert 'Use this exact argument JSON' in frag
    assert '{"file_name": "a.txt"}' in frag
    assert 'Do not rename JSON keys or values' in frag

def test_canonical_arg_validation_records_key_mismatch():
    candidate={'args':{'file_name':'a.txt'},'arg_bindings':{'file_name':{'source':'explicit_literal','value':'a.txt'}}}
    rows=RuleEngine._validate_action_candidate_args(candidate, {'path':'a.txt'})
    assert rows['file_name']['match'] is True
    assert rows['file_name']['key_mismatch'] is True
    assert rows['file_name']['observed_field']=='path'

def test_tool_and_arg_gates_fail_on_bad_counts(tmp_path:Path):
    root=tmp_path/'subset'
    _wjl(root/'subset_case_report.jsonl',[{'case_id':'a','policy_plan_activated':True,'selected_next_tool':'cat','recommended_tool_match':False,'raw_normalized_arg_match':False},{'case_id':'b','policy_plan_activated':True,'selected_next_tool':'cat','recommended_tool_match':True,'raw_normalized_arg_match':False}])
    _wj(root/'m27r_arg_realization.json',{'cases':[{'failure_reason':'tool_mismatch_before_arg_realization'},{'failure_reason':'emitted_arg_wrong_or_guidance_not_followed','candidate_args':{'file_name':'x'}}]})
    _wj(root/'subset_summary.json',{'raw_normalized_arg_match_rate_among_activated':0.0})
    assert evaluate_tool_ranking(root)['m27s_tool_ranking_passed'] is False
    assert evaluate_arg_realization(root)['m27s_arg_realization_passed'] is False

def test_offline_summary_aggregates_gates(tmp_path:Path):
    root=tmp_path/'subset'; hold=tmp_path/'holdout'
    _wj(root/'m27s_activation_recall.json',{'m27s_activation_recall_passed':True})
    _wj(root/'m27s_tool_ranking.json',{'m27s_tool_ranking_passed':True})
    _wj(root/'m27s_arg_realization_readiness.json',{'m27s_arg_realization_passed':True})
    _wj(hold/'holdout_manifest.json',{'m27s_holdout_manifest_ready':False,'selected_case_count':4})
    out=evaluate(root,hold)
    assert out['m2_7s_offline_passed'] is False
    assert out['m27s_holdout_manifest_ready'] is False
