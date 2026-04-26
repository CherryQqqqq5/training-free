#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path
from typing import Any
DEFAULT_ROOT=Path('outputs/artifacts/bfcl_ctspc_subset30_v1')
DEFAULT_OUTPUT=DEFAULT_ROOT/'m27s_tool_ranking.json'
DEFAULT_MD=DEFAULT_ROOT/'m27s_tool_ranking.md'
def _j(p:Path, default:Any=None):
    if not p.exists():
        if default is not None: return default
        raise FileNotFoundError(p)
    return json.loads(p.read_text())
def _jl(p:Path): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def _w(p:Path,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
def evaluate_tool_ranking(root:Path=DEFAULT_ROOT)->dict[str,Any]:
    rows=_jl(root/'subset_case_report.jsonl'); arg=_j(root/'m27r_arg_realization.json',{})
    active=[r for r in rows if r.get('policy_plan_activated')]
    dist=Counter(str(r.get('selected_next_tool') or 'none') for r in active)
    mismatches=[c for c in arg.get('cases') or [] if c.get('failure_reason')=='tool_mismatch_before_arg_realization']
    total=len(active); match=sum(1 for r in active if r.get('recommended_tool_match'))
    dominant=max(dist.values())/sum(dist.values()) if dist else 0.0
    report={'report_scope':'m2_7s_tool_ranking','artifact_root':str(root),'activated_case_count':total,'selected_next_tool_distribution':dict(sorted(dist.items())),'dominant_selected_next_tool_rate':dominant,'tool_mismatch_before_arg_realization_count':len(mismatches),'max_tool_mismatch_before_arg_realization_count':2,'offline_recommended_tool_match_proxy':match/total if total else 0.0,'m27s_tool_ranking_passed':len(mismatches)<=2 and (match/total if total else 0.0)>=0.7 and dominant<=0.8,'cases':mismatches,'diagnostic':{'offline_only':True}}
    return report
def md(r):
    return '\n'.join(['# M2.7s Tool Ranking','',f"- Passed: `{r['m27s_tool_ranking_passed']}`",f"- Tool mismatch before arg realization: `{r['tool_mismatch_before_arg_realization_count']}`",f"- Offline tool match proxy: `{r['offline_recommended_tool_match_proxy']}`",f"- Distribution: `{r['selected_next_tool_distribution']}`",''])
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=DEFAULT_ROOT); ap.add_argument('--output',type=Path,default=DEFAULT_OUTPUT); ap.add_argument('--markdown-output',type=Path,default=DEFAULT_MD); ap.add_argument('--compact',action='store_true'); a=ap.parse_args(); r=evaluate_tool_ranking(a.root); _w(a.output,r); a.markdown_output.write_text(md(r));
    if a.compact: print(json.dumps({k:r.get(k) for k in ['tool_mismatch_before_arg_realization_count','offline_recommended_tool_match_proxy','dominant_selected_next_tool_rate','m27s_tool_ranking_passed']},indent=2,sort_keys=True))
if __name__=='__main__': main()
