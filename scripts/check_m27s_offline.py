#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
DEFAULT_ROOT=Path('outputs/artifacts/bfcl_ctspc_subset30_v1'); DEFAULT_HOLDOUT=Path('outputs/artifacts/bfcl_ctspc_holdout30_v1'); DEFAULT_OUTPUT=DEFAULT_ROOT/'m27s_offline_summary.json'; DEFAULT_MD=DEFAULT_ROOT/'m27s_offline_summary.md'
def _j(p:Path, default:Any=None):
    if not p.exists():
        if default is not None: return default
        raise FileNotFoundError(p)
    return json.loads(p.read_text())
def _w(p:Path,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
def evaluate(root:Path=DEFAULT_ROOT, holdout:Path=DEFAULT_HOLDOUT)->dict[str,Any]:
    a=_j(root/'m27s_activation_recall.json',{}); t=_j(root/'m27s_tool_ranking.json',{}); ar=_j(root/'m27s_arg_realization_readiness.json',{}); h=_j(holdout/'holdout_manifest.json',{})
    checks={'m27s_activation_recall_passed':bool(a.get('m27s_activation_recall_passed')),'m27s_tool_ranking_passed':bool(t.get('m27s_tool_ranking_passed')),'m27s_arg_realization_passed':bool(ar.get('m27s_arg_realization_passed')),'m27s_holdout_manifest_ready':bool(h.get('m27s_holdout_manifest_ready'))}
    return {'report_scope':'m2_7s_offline_summary','artifact_root':str(root),'holdout_root':str(holdout),**checks,'m2_7s_offline_passed':all(checks.values()),'activation_recall':{k:a.get(k) for k in ['actionable_false_negative_count','classification_distribution']},'tool_ranking':{k:t.get(k) for k in ['tool_mismatch_before_arg_realization_count','offline_recommended_tool_match_proxy','dominant_selected_next_tool_rate']},'arg_realization':{k:ar.get(k) for k in ['raw_arg_match_rate_proxy','emitted_arg_wrong_or_guidance_not_followed_count']},'holdout':{k:h.get(k) for k in ['selected_case_count','candidate_generatable_count','overlap_with_dev_case_ids']},'diagnostic':{'offline_readiness_only':True,'bfcl_performance_evidence':False,'no_bfcl_rerun':True,'next_experiment_requires_explicit_request':True}}
def md(r):
    lines=['# M2.7s Offline Summary','',f"- Passed: `{r['m2_7s_offline_passed']}`",'','| Check | Passed |','| --- | ---: |']
    for k in ['m27s_activation_recall_passed','m27s_tool_ranking_passed','m27s_arg_realization_passed','m27s_holdout_manifest_ready']: lines.append(f"| `{k}` | `{r[k]}` |")
    return '\n'.join(lines)+'\n'
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=DEFAULT_ROOT); ap.add_argument('--holdout-root',type=Path,default=DEFAULT_HOLDOUT); ap.add_argument('--output',type=Path,default=DEFAULT_OUTPUT); ap.add_argument('--markdown-output',type=Path,default=DEFAULT_MD); ap.add_argument('--compact',action='store_true'); args=ap.parse_args(); r=evaluate(args.root,args.holdout_root); _w(args.output,r); args.markdown_output.write_text(md(r));
    if args.compact: print(json.dumps({k:r.get(k) for k in ['m2_7s_offline_passed','m27s_activation_recall_passed','m27s_tool_ranking_passed','m27s_arg_realization_passed','m27s_holdout_manifest_ready']},indent=2,sort_keys=True))
if __name__=='__main__': main()
