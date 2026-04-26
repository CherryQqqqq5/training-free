#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path
from typing import Any
DEFAULT_ROOT=Path('outputs/artifacts/bfcl_ctspc_subset30_v1'); OUT=DEFAULT_ROOT/'m27u_tool_ranking.json'; MD=DEFAULT_ROOT/'m27u_tool_ranking.md'
def _j(p:Path, default:Any=None):
    if not p.exists():
        if default is not None: return default
        raise FileNotFoundError(p)
    return json.loads(p.read_text())
def _jl(p:Path): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def _w(p:Path,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
def _guard(root):
    d=_j(root/'m27i_guard_preflight.json',{}); return {str(r.get('case_id')):r for r in d.get('cases') or [] if r.get('case_id')}
def _goal(cand):
    pc=cand.get('postcondition') if isinstance(cand.get('postcondition'),dict) else {}; return {'file_content':'read_content','file_exists':'create_file','directory_exists':'create_directory','matches':'search','target_path_changed':'move_or_copy','content_written':'write_content','comparison_result':'compare'}.get(str(pc.get('kind') or ''),'unknown')
def evaluate(root:Path=DEFAULT_ROOT)->dict[str,Any]:
    rows=_jl(root/'subset_case_report.jsonl'); guards=_guard(root); active=[r for r in rows if r.get('policy_plan_activated')]; dist=Counter(str(r.get('selected_next_tool') or 'none') for r in active); cases=[]
    for row in active:
        g=guards.get(str(row.get('case_id')),{}); plan=g.get('after_guard_plan') if isinstance(g.get('after_guard_plan'),dict) else {}; cand=plan.get('selected_action_candidate') if isinstance(plan.get('selected_action_candidate'),dict) else {}; scores=plan.get('selected_candidate_rank_scores') if isinstance(plan.get('selected_candidate_rank_scores'),dict) else {}
        if row.get('recommended_tool_match') is not True:
            rejected=plan.get('rejected_action_candidates') or []
            better=rejected[0] if rejected else None
            cases.append({'case_id':row.get('case_id'),'selected_tool':row.get('selected_next_tool'),'expected_or_proxy_goal':scores.get('request_pending_goal_family') or cand.get('pending_goal_family') or _goal(cand),'postcondition_goal_family':scores.get('postcondition_goal_family') or _goal(cand),'better_rejected_candidate':better,'why_selected_tool_won':scores,'failure_reason':'tool_mismatch_before_arg_realization'})
    match=sum(1 for r in active if r.get('recommended_tool_match')); total=len(active); dominant=max(dist.values())/sum(dist.values()) if dist else 0.0
    report={'report_scope':'m2_7u_tool_ranking','artifact_root':str(root),'activated_case_count':total,'selected_next_tool_distribution':dict(sorted(dist.items())),'dominant_selected_next_tool_rate':dominant,'tool_mismatch_before_arg_realization_count':len(cases),'offline_recommended_tool_match_proxy':match/total if total else 0.0,'cases':cases,'m27u_tool_ranking_passed':len(cases)<=2 and (match/total if total else 0)>=0.7 and dominant<=0.8,'diagnostic':{'offline_only':True}}
    return report
def md(r): return '\n'.join(['# M2.7u Tool Ranking','',f"- Passed: `{r['m27u_tool_ranking_passed']}`",f"- Mismatches: `{r['tool_mismatch_before_arg_realization_count']}`",f"- Match proxy: `{r['offline_recommended_tool_match_proxy']}`",''])
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=DEFAULT_ROOT); ap.add_argument('--output',type=Path,default=OUT); ap.add_argument('--markdown-output',type=Path,default=MD); ap.add_argument('--compact',action='store_true'); a=ap.parse_args(); r=evaluate(a.root); _w(a.output,r); a.markdown_output.write_text(md(r));
    if a.compact: print(json.dumps({k:r.get(k) for k in ['tool_mismatch_before_arg_realization_count','offline_recommended_tool_match_proxy','dominant_selected_next_tool_rate','m27u_tool_ranking_passed']},indent=2,sort_keys=True))
if __name__=='__main__': main()
