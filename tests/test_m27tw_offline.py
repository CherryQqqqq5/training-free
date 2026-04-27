from __future__ import annotations
import json
from pathlib import Path
from grc.compiler.action_candidates import generate_action_candidates
from grc.compiler.tool_state import ToolState
from grc.runtime.engine import RuleEngine
from scripts.build_m27t_source_pool_manifest import build_source_pool_manifest, discover_source_categories, _load_category_ids
from scripts.check_m27tw_offline import evaluate as evaluate_tw
from scripts.diagnose_m27w_rule_retention import decide
from grc.compiler.retention_priors import explicit_required_arg_literal_prior

def _wj(p:Path,d:dict): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d)+'\n')

def _retention_prior_rule(**overrides):
    rule={
        'rule_type':'explicit_required_arg_literal_completion',
        'candidate_rules_type':'explicit_required_arg_literal_completion',
        'required_arg':'content',
        'schema_arg_name':'content',
        'literal_value':'hello',
        'literal_source':'current_request',
        'no_next_tool_intervention':True,
        'exact_tool_choice':False,
        'ctspc_v0_action_rule':False,
        'net_case_gain':1,
        'regressed_count':0,
        'tool_match_rate':1.0,
        'arg_match_rate':1.0,
        'trajectory_fail_count':0,
        'fixed_count':1,
    }
    rule.update(overrides)
    rule['retention_prior']=explicit_required_arg_literal_prior(rule)
    return rule
def test_source_pool_manifest_emits_baseline_only_commands_when_missing(tmp_path:Path):
    dev=tmp_path/'dev'; _wj(dev/'paired_subset_manifest.json',{'source_run_root':str(tmp_path/'source'),'runtime_config':'configs/runtime_bfcl_structured.yaml'})
    r=build_source_pool_manifest(dev,tmp_path/'pool',tmp_path/'repo',categories=['multi_turn_base'])
    assert r['m27t_source_pool_ready'] is False
    assert r['candidate_commands']==[]
    assert 'run_bfcl_v4_baseline.sh' in r['planned_source_collection_commands'][0]



def test_source_pool_manifest_discovers_installed_non_live_categories(tmp_path:Path):
    data = tmp_path / 'bfcl_data'
    for category in ['multi_turn_base', 'multi_turn_miss_func', 'multi_turn_long_context', 'simple_python', 'parallel', 'live_simple', 'web_search']:
        rows = [{'id': f'{category}_{i}'} for i in range(3)]
        (data / f'BFCL_v4_{category}.json').parent.mkdir(parents=True, exist_ok=True)
        (data / f'BFCL_v4_{category}.json').write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    categories, diagnostic = discover_source_categories(data_root=data)
    assert 'simple_python' in categories
    assert 'parallel' in categories
    assert 'multi_turn_base' in categories
    assert 'live_simple' not in categories
    assert 'web_search' not in categories
    assert diagnostic['category_discovery_source'] == 'bfcl_runnable_categories_plus_raw_files'

    dev=tmp_path/'dev'; _wj(dev/'paired_subset_manifest.json',{'source_run_root':str(tmp_path/'source'),'runtime_config':'configs/runtime_bfcl_structured.yaml'})
    report = build_source_pool_manifest(dev, tmp_path/'pool', tmp_path/'repo', data_root=data, cases_per_category=2)
    assert report['candidate_commands'] == []
    assert report['source_collection_only'] is True
    assert report['no_candidate_rules'] is True
    assert 'simple_python' in report['missing_source_categories']
    assert all('run_bfcl_v4_baseline.sh' in cmd for cmd in report['planned_source_collection_commands'])
    simple_row = next(row for row in report['category_status'] if row['category'] == 'simple_python')
    assert simple_row['selected_case_count'] == 2
    assert Path(simple_row['test_case_ids_path']).name == 'test_case_ids_to_generate.json'



def test_source_pool_discovery_uses_runnable_memory_backends_not_generic_memory(tmp_path:Path):
    categories, diagnostic = discover_source_categories()
    assert 'memory' not in categories
    assert {'memory_kv', 'memory_vector', 'memory_rec_sum'}.issubset(set(categories))
    assert 'memory' in diagnostic['excluded_categories']
    ids, source = _load_category_ids('memory_kv', 3)
    assert source == 'bfcl_dataset_api'
    assert len(ids) == 3
    assert all(case_id.startswith('memory_kv_') for case_id in ids)

    dev=tmp_path/'dev'; _wj(dev/'paired_subset_manifest.json',{'source_run_root':str(tmp_path/'source'),'runtime_config':'configs/runtime_bfcl_structured.yaml'})
    report = build_source_pool_manifest(dev, tmp_path/'pool', tmp_path/'repo', categories=['memory_kv'], cases_per_category=3)
    row = report['category_status'][0]
    assert row['category'] == 'memory_kv'
    assert row['selected_case_id_source'] == 'bfcl_dataset_api'
    assert row['selected_case_count'] == 3
    assert all(case_id.startswith('memory_kv_') for case_id in row['selected_case_ids'])
    assert report['candidate_commands'] == []
    assert report['source_collection_only'] is True


def test_source_pool_raw_file_fallback_for_fixture_categories(tmp_path:Path):
    data = tmp_path / 'bfcl_data'
    (data / 'BFCL_v4_custom_fixture.json').parent.mkdir(parents=True, exist_ok=True)
    (data / 'BFCL_v4_custom_fixture.json').write_text('\n'.join(json.dumps({'id': f'custom_fixture_{i}'}) for i in range(4)) + '\n', encoding='utf-8')
    ids, source = _load_category_ids('custom_fixture', 2, data_root=data)
    assert source == 'raw_category_file'
    assert ids == ['custom_fixture_0', 'custom_fixture_1']


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

def test_rule_retention_requires_theory_prior_and_holdout_for_demote():
    no_prior={'net_case_gain':1,'regressed_count':0,'tool_match_rate':1.0,'arg_match_rate':1.0,'trajectory_fail_count':0,'fixed_count':1}
    assert decide(no_prior, True, True)[0]=='reject'
    rule=_retention_prior_rule()
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
    rule=_retention_prior_rule()
    decision, reason, extra = decide(rule, True, True)
    assert decision == 'demote'
    assert extra['retain_blocked_by'] == 'missing_holdout_scorer_evidence'
    assert extra['retain_prior_match'] is True

def test_required_pair_validation_blocks_incomplete_cp_candidate():
    candidate={'tool':'cp','args':{'source':'a.txt'},'arg_bindings':{'source':{'source':'explicit_literal','value':'a.txt'}}}
    assert RuleEngine._candidate_required_pair_complete(candidate) is False
    validation = RuleEngine._validate_action_candidate_args(candidate, {'source':'a.txt'})
    assert validation['source']['required_pair_complete'] is False


def test_rule_retention_negative_dev_scorer_blocks_demote_ready():
    rule=_retention_prior_rule()
    decision, reason, extra = decide(rule, True, True, dev_scorer_net_case_gain=-2)
    assert decision == 'reject'
    assert reason == 'negative_scorer_evidence_creates_mismatch_diagnostic'
    assert 'negative_overall_dev_scorer_net_gain' in extra['blockers']
    assert extra['retain_blocked_by'] == 'negative_dev_scorer_mismatch_diagnostic_required'

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
    _wj(root/'m27aa_regression_patterns.json',{'m27aa_regression_patterns_passed':True,'old_regression_unresolved_count':0,'new_regression_pattern_count':0,'regression_pattern_coverage':1.0,'pattern_effective_coverage':1.0,'diagnostic_unsafe_gap_count':0,'scorer_feedback_covers_regression_patterns':True,'scorer_feedback_effective_for_regression_patterns':True})
    _wj(root/'m27m_guidance_only_readiness.json',{'m2_7m_preflight_passed':True,'m2_7m_guidance_only_readiness_passed':True,'plan_activated_count_after_guard':10,'dominant_selected_next_tool_rate_after_guard':0.5,'exact_tool_choice_coverage':0.0})
    _wj(root/'m27i_guard_preflight.json',{'m2_7i_guard_preflight_passed':True,'guard_keeps_fixed_cases':1})
    out=evaluate_tw(root,hold,source)
    assert out['proxy_calibration_passed'] is True
    assert out['pattern_proxy_calibration_passed'] is True
    assert out['m2_7tw_offline_passed'] is True



def test_m27tw_offline_passes_after_scorer_feedback_and_reject_only_retention(tmp_path:Path):
    root=tmp_path/'subset'; hold=tmp_path/'hold'; source=tmp_path/'source'
    _wj(source/'source_collection_manifest.json',{'m27t_source_pool_ready':True})
    _wj(hold/'holdout_manifest.json',{'m27tw_holdout_manifest_ready':True,'selected_case_count':30,'candidate_generatable_count':30,'overlap_with_dev_case_ids':[]})
    _wj(root/'m27u_tool_ranking.json',{'m27u_tool_ranking_passed':True})
    _wj(root/'m27v_arg_realization.json',{'m27v_arg_realization_passed':True})
    _wj(root/'subset_summary.json',{'recommended_tool_match_rate_among_activated':0.63,'raw_normalized_arg_match_rate_among_activated':0.45,'net_case_gain':-2})
    _wj(root/'m27x_scorer_proxy_gap.json',{'m27x_scorer_proxy_gap_explained':True,'fixed_by_code_change':True})
    _wj(root/'m27aa_regression_patterns.json',{'m27aa_regression_patterns_passed':True,'old_regression_unresolved_count':0,'new_regression_pattern_count':0,'regression_pattern_coverage':1.0,'pattern_effective_coverage':1.0,'diagnostic_unsafe_gap_count':0,'scorer_feedback_covers_regression_patterns':True,'scorer_feedback_effective_for_regression_patterns':True})
    _wj(root/'m27m_guidance_only_readiness.json',{'m2_7m_preflight_passed':True,'m2_7m_guidance_only_readiness_passed':True,'plan_activated_count_after_guard':10,'dominant_selected_next_tool_rate_after_guard':0.5,'exact_tool_choice_coverage':0.0})
    _wj(root/'m27i_guard_preflight.json',{'m2_7i_guard_preflight_passed':True,'guard_keeps_fixed_cases':1})
    _wj(root/'m27w_rule_retention.json',{
        'm27w_rule_retention_passed':True,
        'decision_distribution':{'retain':0,'demote':0,'reject':3},
        'm27y_scorer_feedback_ready':True,
        'scorer_feedback_covers_regressions':True,
    })
    out=evaluate_tw(root,hold,source)
    assert out['proxy_calibration_passed'] is True
    assert out['m27w_rule_retention_passed'] is True
    assert out['pattern_proxy_calibration_passed'] is True
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


def test_m27tw_offline_requires_guidance_only_readiness(tmp_path:Path):
    root=tmp_path/'subset'; hold=tmp_path/'hold'; source=tmp_path/'source'
    _wj(source/'source_collection_manifest.json',{'m27t_source_pool_ready':True})
    _wj(hold/'holdout_manifest.json',{'m27tw_holdout_manifest_ready':True,'selected_case_count':30,'candidate_generatable_count':30,'overlap_with_dev_case_ids':[]})
    _wj(root/'m27u_tool_ranking.json',{'m27u_tool_ranking_passed':True})
    _wj(root/'m27v_arg_realization.json',{'m27v_arg_realization_passed':True})
    _wj(root/'m27w_rule_retention.json',{'m27w_rule_retention_passed':True})
    _wj(root/'subset_summary.json',{'recommended_tool_match_rate_among_activated':0.7,'raw_normalized_arg_match_rate_among_activated':0.4})
    _wj(root/'m27x_scorer_proxy_gap.json',{'m27x_scorer_proxy_gap_explained':True,'fixed_by_code_change':True})
    _wj(root/'m27aa_regression_patterns.json',{'m27aa_regression_patterns_passed':True,'old_regression_unresolved_count':0,'new_regression_pattern_count':0,'regression_pattern_coverage':1.0,'pattern_effective_coverage':1.0,'diagnostic_unsafe_gap_count':0,'scorer_feedback_covers_regression_patterns':True,'scorer_feedback_effective_for_regression_patterns':True})
    _wj(root/'m27m_guidance_only_readiness.json',{'m2_7m_preflight_passed':True,'m2_7m_guidance_only_readiness_passed':True,'plan_activated_count_after_guard':10,'dominant_selected_next_tool_rate_after_guard':0.5,'exact_tool_choice_coverage':0.0})
    _wj(root/'m27i_guard_preflight.json',{'m2_7i_guard_preflight_passed':True,'guard_keeps_fixed_cases':1})
    _wj(root/'m27m_guidance_only_readiness.json',{'m2_7m_preflight_passed':False,'m2_7m_guidance_only_readiness_passed':False,'plan_activated_count_after_guard':2,'dominant_selected_next_tool_rate_after_guard':0.5,'exact_tool_choice_coverage':0.0})
    _wj(root/'m27i_guard_preflight.json',{'m2_7i_guard_preflight_passed':False,'guard_keeps_fixed_cases':0})
    out=evaluate_tw(root,hold,source)
    assert out['m27m_guidance_only_readiness_passed'] is False
    assert out['m2_7tw_offline_passed'] is False
    assert out['guidance_only_readiness']['first_failed_criterion'] == 'm2_7m_preflight_passed'
