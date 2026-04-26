#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
DEFAULT_ROOT=Path('outputs/artifacts/bfcl_ctspc_subset30_v1')
DEFAULT_OUTPUT=DEFAULT_ROOT/'m27s_arg_realization_readiness.json'
DEFAULT_MD=DEFAULT_ROOT/'m27s_arg_realization_readiness.md'
def _j(p:Path, default:Any=None):
    if not p.exists():
        if default is not None: return default
        raise FileNotFoundError(p)
    return json.loads(p.read_text())
def _jl(p:Path): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def _serializable(v):
    try: json.dumps(v); return True
    except Exception: return False
def _w(p:Path,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
def evaluate_arg_realization(root:Path=DEFAULT_ROOT)->dict[str,Any]:
    summary=_j(root/'subset_summary.json',{}); arg=_j(root/'m27r_arg_realization.json',{})
    cases=arg.get('cases') or []
    emitted_wrong=sum(1 for c in cases if c.get('failure_reason')=='emitted_arg_wrong_or_guidance_not_followed')
    serializable=sum(1 for c in cases if _serializable(c.get('candidate_args') or {}))
    raw=float(summary.get('raw_normalized_arg_match_rate_among_activated') or 0.0)
    report={'report_scope':'m2_7s_arg_realization','artifact_root':str(root),'raw_arg_match_rate_proxy':raw,'min_raw_arg_match_rate_proxy':0.6,'emitted_arg_wrong_or_guidance_not_followed_count':emitted_wrong,'max_emitted_arg_wrong_or_guidance_not_followed':1,'candidate_args_serializable_count':serializable,'candidate_args_serializable_rate':serializable/len(cases) if cases else 1.0,'cases':cases,'m27s_arg_realization_passed':raw>=0.6 and emitted_wrong<=1 and (serializable==len(cases)),'diagnostic':{'offline_only':True,'guidance_only_no_exact_tool_choice':True}}
    return report
def md(r): return '\n'.join(['# M2.7s Arg Realization','',f"- Passed: `{r['m27s_arg_realization_passed']}`",f"- Raw arg match proxy: `{r['raw_arg_match_rate_proxy']}`",f"- Emitted arg wrong count: `{r['emitted_arg_wrong_or_guidance_not_followed_count']}`",''])
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=DEFAULT_ROOT); ap.add_argument('--output',type=Path,default=DEFAULT_OUTPUT); ap.add_argument('--markdown-output',type=Path,default=DEFAULT_MD); ap.add_argument('--compact',action='store_true'); a=ap.parse_args(); r=evaluate_arg_realization(a.root); _w(a.output,r); a.markdown_output.write_text(md(r));
    if a.compact: print(json.dumps({k:r.get(k) for k in ['raw_arg_match_rate_proxy','emitted_arg_wrong_or_guidance_not_followed_count','candidate_args_serializable_rate','m27s_arg_realization_passed']},indent=2,sort_keys=True))
if __name__=='__main__': main()
