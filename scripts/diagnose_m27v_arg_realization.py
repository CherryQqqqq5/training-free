#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
DEFAULT_ROOT=Path('outputs/artifacts/bfcl_ctspc_subset30_v1'); OUT=DEFAULT_ROOT/'m27v_arg_realization.json'; MD=DEFAULT_ROOT/'m27v_arg_realization.md'
def _j(p:Path, default:Any=None):
    if not p.exists():
        if default is not None: return default
        raise FileNotFoundError(p)
    return json.loads(p.read_text())
def _w(p:Path,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
def _serial(v):
    try: json.dumps(v); return True
    except Exception: return False
def _has_canonical(c):
    cmap=c.get('canonical_arg_map') if isinstance(c.get('canonical_arg_map'),dict) else {}
    args=c.get('candidate_args') if isinstance(c.get('candidate_args'),dict) else c.get('candidate_args') or {}
    return bool(cmap) or isinstance(args,dict)
def evaluate(root:Path=DEFAULT_ROOT)->dict[str,Any]:
    summary=_j(root/'subset_summary.json',{}); arg=_j(root/'m27r_arg_realization.json',{}); cases=arg.get('cases') or []
    emitted=sum(1 for c in cases if c.get('failure_reason')=='emitted_arg_wrong_or_guidance_not_followed'); serial=sum(1 for c in cases if _serial(c.get('candidate_args') or {})); canonical=sum(1 for c in cases if _has_canonical(c)); raw=float(summary.get('raw_normalized_arg_match_rate_among_activated') or 0.0)
    report={'report_scope':'m2_7v_arg_realization','artifact_root':str(root),'raw_arg_match_rate_proxy':raw,'emitted_arg_wrong_or_guidance_not_followed_count':emitted,'candidate_args_serializable_rate':serial/len(cases) if cases else 1.0,'canonical_arg_validation_coverage':canonical/len(cases) if cases else 1.0,'cases':cases,'m27v_arg_realization_passed':raw>=0.6 and emitted<=1 and serial==len(cases) and canonical==len(cases),'diagnostic':{'offline_only':True,'guidance_only':True}}
    return report
def md(r): return '\n'.join(['# M2.7v Arg Realization','',f"- Passed: `{r['m27v_arg_realization_passed']}`",f"- Raw arg match proxy: `{r['raw_arg_match_rate_proxy']}`",f"- Canonical coverage: `{r['canonical_arg_validation_coverage']}`",''])
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=DEFAULT_ROOT); ap.add_argument('--output',type=Path,default=OUT); ap.add_argument('--markdown-output',type=Path,default=MD); ap.add_argument('--compact',action='store_true'); a=ap.parse_args(); r=evaluate(a.root); _w(a.output,r); a.markdown_output.write_text(md(r));
    if a.compact: print(json.dumps({k:r.get(k) for k in ['raw_arg_match_rate_proxy','emitted_arg_wrong_or_guidance_not_followed_count','candidate_args_serializable_rate','canonical_arg_validation_coverage','m27v_arg_realization_passed']},indent=2,sort_keys=True))
if __name__=='__main__': main()
