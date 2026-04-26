#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path
from typing import Any
DEFAULT_ROOT=Path('outputs/artifacts/bfcl_ctspc_subset30_v1')
DEFAULT_OUTPUT=DEFAULT_ROOT/'m27s_activation_recall.json'
DEFAULT_MD=DEFAULT_ROOT/'m27s_activation_recall.md'

def _j(p:Path, default:Any=None):
    if not p.exists():
        if default is not None: return default
        raise FileNotFoundError(p)
    return json.loads(p.read_text())
def _jl(p:Path):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def _w(p:Path,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
def _guard_cases(root:Path):
    d=_j(root/'m27i_guard_preflight.json',{})
    return {str(r.get('case_id')):r for r in d.get('cases') or [] if isinstance(r,dict) and r.get('case_id')}
def classify_activation_recall(case_row:dict[str,Any], guard_row:dict[str,Any]|None=None)->dict[str,Any]:
    guard_row=guard_row or {}
    before=guard_row.get('before_guard_plan') if isinstance(guard_row.get('before_guard_plan'),dict) else {}
    after=guard_row.get('after_guard_plan') if isinstance(guard_row.get('after_guard_plan'),dict) else {}
    before_active=bool(before.get('activated'))
    after_active=bool(after.get('activated'))
    before_candidate=bool(before.get('selected_action_candidate'))
    after_candidate=bool(after.get('selected_action_candidate'))
    reason=str(guard_row.get('case_final_guard_reason') or guard_row.get('top_candidate_rejection_reason') or case_row.get('blocked_reason') or 'unknown')
    if not before_active or before.get('blocked_reason') in {'no_policy_candidate','recommended_tools_empty'}:
        bucket='no_candidate_generated'
    elif before.get('blocked_reason') in {'request_predicates_unmet','activation_predicates_unmet'}:
        bucket='predicate_unmet'
    elif before.get('blocked_reason')=='recommended_tools_not_in_schema':
        bucket='schema_mismatch'
    elif not after_active and 'trajectory' in reason:
        bucket='trajectory_risk_blocked'
    elif not after_active and ('weak' in reason or 'binding' in reason):
        bucket='weak_binding'
    elif before_candidate and not after_candidate:
        bucket='candidate_rejected_by_guard'
    elif after_active and after_candidate:
        bucket='offline_activation_available_runtime_missed'
    else:
        bucket='unknown'
    actionable_false_negative=bucket in {'no_candidate_generated','predicate_unmet','schema_mismatch','offline_activation_available_runtime_missed'}
    return {'case_id':case_row.get('case_id'),'classification':bucket,'actionable_false_negative':actionable_false_negative,'before_guard_activated':before_active,'after_guard_activated':after_active,'guard_reason':reason,'baseline_success':bool(case_row.get('baseline_success')),'candidate_success':bool(case_row.get('candidate_success'))}
def evaluate_activation_recall(root:Path=DEFAULT_ROOT)->dict[str,Any]:
    rows=_jl(root/'subset_case_report.jsonl'); guards=_guard_cases(root)
    cases=[classify_activation_recall(r,guards.get(str(r.get('case_id')))) for r in rows if not r.get('policy_plan_activated')]
    dist=Counter(c['classification'] for c in cases); reasons=Counter(c['guard_reason'] for c in cases)
    false_count=sum(1 for c in cases if c['actionable_false_negative'])
    report={'report_scope':'m2_7s_activation_recall','artifact_root':str(root),'not_activated_case_count':len(cases),'classification_distribution':dict(sorted(dist.items())),'guard_reason_distribution':dict(sorted(reasons.items())),'actionable_false_negative_count':false_count,'max_actionable_false_negative_count':5,'cases':cases,'m27s_activation_recall_passed':false_count<=5 and len(cases)>0,'diagnostic':{'offline_only':True,'trajectory_risk_blocked_not_relaxed':True}}
    return report
def md(r):
    lines=['# M2.7s Activation Recall','',f"- Passed: `{r['m27s_activation_recall_passed']}`",f"- Actionable false negatives: `{r['actionable_false_negative_count']}`",f"- Distribution: `{r['classification_distribution']}`",'','| Case | Class | Reason | Actionable FN |','| --- | --- | --- | ---: |']
    lines += [f"| `{c['case_id']}` | `{c['classification']}` | `{c['guard_reason']}` | `{c['actionable_false_negative']}` |" for c in r['cases']]
    return '\n'.join(lines)+'\n'
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=DEFAULT_ROOT); ap.add_argument('--output',type=Path,default=DEFAULT_OUTPUT); ap.add_argument('--markdown-output',type=Path,default=DEFAULT_MD); ap.add_argument('--compact',action='store_true'); a=ap.parse_args()
    r=evaluate_activation_recall(a.root); _w(a.output,r); a.markdown_output.write_text(md(r))
    if a.compact: print(json.dumps({k:r.get(k) for k in ['not_activated_case_count','classification_distribution','actionable_false_negative_count','m27s_activation_recall_passed']},indent=2,sort_keys=True))
if __name__=='__main__': main()
