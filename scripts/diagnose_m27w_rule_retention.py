#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path
from typing import Any
DEFAULT_ROOT=Path('outputs/artifacts/bfcl_ctspc_subset30_v1'); DEFAULT_HOLDOUT=Path('outputs/artifacts/bfcl_ctspc_holdout30_v1'); OUT=DEFAULT_ROOT/'m27w_rule_retention.json'; MD=DEFAULT_ROOT/'m27w_rule_retention.md'
def _j(p:Path, default:Any=None):
    if not p.exists():
        if default is not None: return default
        raise FileNotFoundError(p)
    return json.loads(p.read_text())
def _w(p:Path,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
def decide(rule, holdout_ready:bool):
    net=int(rule.get('net_case_gain') or 0); reg=int(rule.get('regressed_count') or 0); tool=float(rule.get('tool_match_rate') or 0); arg=float(rule.get('arg_match_rate') or 0); traj=int(rule.get('trajectory_fail_count') or 0); fixed=int(rule.get('fixed_count') or 0)
    if net>0 and reg==0 and tool>=0.6 and arg>=0.6 and traj<=fixed and holdout_ready: return 'retain','positive_dev_and_holdout_evidence'
    if net>=0 and reg==0 and (tool>=0.6 or arg>=0.6): return 'demote','dev_only_or_partial_alignment_signal_requires_holdout'
    return 'reject','no_positive_retention_signal'
def evaluate(root:Path=DEFAULT_ROOT,holdout_root:Path=DEFAULT_HOLDOUT)->dict[str,Any]:
    base=_j(root/'m27r_rule_retention.json',{}); hold=_j(holdout_root/'holdout_manifest.json',{}); hold_ready=bool(hold.get('m27tw_holdout_manifest_ready') or hold.get('m27s_holdout_manifest_ready'))
    rules=[]; dist=Counter()
    for r in base.get('rules') or []:
        d,reason=decide(r,hold_ready); item={**r,'decision':d,'reason':reason,'holdout_evidence_available':hold_ready}; rules.append(item); dist[d]+=1
    report={'report_scope':'m2_7w_rule_retention','artifact_root':str(root),'holdout_root':str(holdout_root),'holdout_evidence_available':hold_ready,'rule_count':len(rules),'rules':rules,'decision_distribution':{k:dist.get(k,0) for k in ['retain','demote','reject']},'m27w_rule_retention_passed':(dist.get('retain',0)+dist.get('demote',0))>=1 and hold_ready,'diagnostic':{'dev_only_cannot_promote_to_retained_memory':True}}
    return report
def md(r): return '\n'.join(['# M2.7w Rule Retention','',f"- Passed: `{r['m27w_rule_retention_passed']}`",f"- Holdout evidence: `{r['holdout_evidence_available']}`",f"- Decisions: `{r['decision_distribution']}`",''])
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=DEFAULT_ROOT); ap.add_argument('--holdout-root',type=Path,default=DEFAULT_HOLDOUT); ap.add_argument('--output',type=Path,default=OUT); ap.add_argument('--markdown-output',type=Path,default=MD); ap.add_argument('--compact',action='store_true'); a=ap.parse_args(); r=evaluate(a.root,a.holdout_root); _w(a.output,r); a.markdown_output.write_text(md(r));
    if a.compact: print(json.dumps({k:r.get(k) for k in ['holdout_evidence_available','decision_distribution','m27w_rule_retention_passed']},indent=2,sort_keys=True))
if __name__=='__main__': main()
