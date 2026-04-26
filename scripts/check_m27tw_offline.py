#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
ROOT=Path('outputs/artifacts/bfcl_ctspc_subset30_v1'); HOLD=Path('outputs/artifacts/bfcl_ctspc_holdout30_v1'); SRC=Path('outputs/artifacts/bfcl_ctspc_source_pool_v1'); OUT=ROOT/'m27tw_offline_summary.json'; MD=ROOT/'m27tw_offline_summary.md'
def _j(p:Path, default:Any=None):
    if not p.exists():
        if default is not None: return default
        raise FileNotFoundError(p)
    return json.loads(p.read_text())
def _w(p:Path,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
def evaluate(root:Path=ROOT,holdout:Path=HOLD,source:Path=SRC):
    sp=_j(source/'source_collection_manifest.json',{}); hm=_j(holdout/'holdout_manifest.json',{}); u=_j(root/'m27u_tool_ranking.json',{}); v=_j(root/'m27v_arg_realization.json',{}); w=_j(root/'m27w_rule_retention.json',{})
    checks={'m27t_source_pool_ready':bool(sp.get('m27t_source_pool_ready')),'m27tw_holdout_manifest_ready':bool(hm.get('m27tw_holdout_manifest_ready')),'m27u_tool_ranking_passed':bool(u.get('m27u_tool_ranking_passed')),'m27v_arg_realization_passed':bool(v.get('m27v_arg_realization_passed')),'m27w_rule_retention_passed':bool(w.get('m27w_rule_retention_passed'))}
    return {'report_scope':'m2_7tw_offline_summary',**checks,'m2_7tw_offline_passed':all(checks.values()),'source_pool':{k:sp.get(k) for k in ['planned_source_collection_commands','candidate_commands']},'holdout':{k:hm.get(k) for k in ['selected_case_count','candidate_generatable_count','overlap_with_dev_case_ids']},'tool_ranking':{k:u.get(k) for k in ['tool_mismatch_before_arg_realization_count','offline_recommended_tool_match_proxy','dominant_selected_next_tool_rate']},'arg_realization':{k:v.get(k) for k in ['raw_arg_match_rate_proxy','emitted_arg_wrong_or_guidance_not_followed_count','canonical_arg_validation_coverage']},'rule_retention':{k:w.get(k) for k in ['decision_distribution','holdout_evidence_available']},'diagnostic':{'offline_readiness_only':True,'no_bfcl_rerun':True,'no_100_case':True,'no_m2_8':True,'no_full_bfcl':True}}
def md(r):
    lines=['# M2.7tw Offline Summary','',f"- Passed: `{r['m2_7tw_offline_passed']}`",'','| Check | Passed |','| --- | ---: |']
    for k in ['m27t_source_pool_ready','m27tw_holdout_manifest_ready','m27u_tool_ranking_passed','m27v_arg_realization_passed','m27w_rule_retention_passed']: lines.append(f"| `{k}` | `{r[k]}` |")
    return '\n'.join(lines)+'\n'
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=ROOT); ap.add_argument('--holdout-root',type=Path,default=HOLD); ap.add_argument('--source-pool-root',type=Path,default=SRC); ap.add_argument('--output',type=Path,default=OUT); ap.add_argument('--markdown-output',type=Path,default=MD); ap.add_argument('--compact',action='store_true'); a=ap.parse_args(); r=evaluate(a.root,a.holdout_root,a.source_pool_root); _w(a.output,r); a.markdown_output.write_text(md(r));
    if a.compact: print(json.dumps({k:r.get(k) for k in ['m2_7tw_offline_passed','m27t_source_pool_ready','m27tw_holdout_manifest_ready','m27u_tool_ranking_passed','m27v_arg_realization_passed','m27w_rule_retention_passed']},indent=2,sort_keys=True))
if __name__=='__main__': main()
