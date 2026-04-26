#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from typing import Any
REPO_ROOT=Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from scripts.scan_bfcl_ctspc_opportunities import scan_opportunities
DEFAULT_DEV_ROOT=Path('outputs/artifacts/bfcl_ctspc_subset30_v1'); DEFAULT_SOURCE_POOL=Path('outputs/artifacts/bfcl_ctspc_source_pool_v1'); DEFAULT_OUT=Path('outputs/artifacts/bfcl_ctspc_holdout30_v1')
CATS=['multi_turn_miss_param','multi_turn_base','multi_turn_miss_func','multi_turn_long_context']; TOOLS={'cat','cd','cp','diff','echo','find','grep','ls','mkdir','mv','sort','tail','touch'}
def _j(p:Path, default:Any=None):
    if not p.exists():
        if default is not None: return default
        raise FileNotFoundError(p)
    return json.loads(p.read_text())
def _w(p:Path,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
def _has_source(root:Path,cat:str)->bool: return bool(list((root/'bfcl').glob(f'**/BFCL_v4_{cat}_score.json')))
def _source_roots(dev:dict[str,Any], source_pool:Path)->list[Path]:
    roots=[Path(str(dev.get('source_run_root') or ''))]
    for p in sorted(source_pool.glob('*/baseline')): roots.append(p)
    return list(dict.fromkeys(roots))
def build_holdout(dev_root:Path=DEFAULT_DEV_ROOT,source_pool:Path=DEFAULT_SOURCE_POOL,out_root:Path=DEFAULT_OUT,max_cases:int=30)->dict[str,Any]:
    dev=_j(dev_root/'paired_subset_manifest.json'); dev_ids={str(x) for x in dev.get('selected_case_ids') or []}; selected=[]; seen=set(); scan=[]
    for root in _source_roots(dev,source_pool):
        for cat in CATS:
            available=_has_source(root,cat); before=len(selected)
            if available:
                try: rows=scan_opportunities(root,cat)
                except Exception: rows=[]
                for row in rows:
                    cid=str(row.get('case_id'))
                    if cid in dev_ids or cid in seen: continue
                    tools=set(str(t) for t in row.get('target_action_tools_present') or [])
                    if row.get('schema_local') and tools & TOOLS:
                        selected.append({**row,'holdout_category':cat,'source_run_root':str(root)}); seen.add(cid)
                        if len(selected)>=max_cases: break
            scan.append({'source_run_root':str(root),'category':cat,'available':available,'selected_count':len(selected)-before})
            if len(selected)>=max_cases: break
        if len(selected)>=max_cases: break
    ids=[str(r['case_id']) for r in selected]; overlap=sorted(set(ids)&dev_ids); generatable=sum(1 for r in selected if r.get('schema_local'))
    return {'report_scope':'m2_7tw_holdout_manifest','artifact_root':str(out_root),'selected_case_count':len(ids),'selected_case_ids':ids,'candidate_generatable_count':generatable,'schema_local_case_count':generatable,'excluded_dev_case_count':len(dev_ids),'overlap_with_dev_case_ids':overlap,'source_scan_summary':scan,'planned_commands':[],'candidate_commands':[],'m27tw_holdout_manifest_ready':len(ids)>=20 and generatable>=15 and not overlap,'diagnostic':{'offline_manifest_only':True,'no_candidate_bfcl_commands':True}}
def md(r):
    lines=['# M2.7tw Holdout Manifest','',f"- Ready: `{r['m27tw_holdout_manifest_ready']}`",f"- Selected: `{r['selected_case_count']}`",f"- Candidate-generatable: `{r['candidate_generatable_count']}`",f"- Dev overlap: `{r['overlap_with_dev_case_ids']}`",'','## Selected Cases']+[f"- `{x}`" for x in r['selected_case_ids']]
    return '\n'.join(lines)+'\n'
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dev-root',type=Path,default=DEFAULT_DEV_ROOT); ap.add_argument('--source-pool-root',type=Path,default=DEFAULT_SOURCE_POOL); ap.add_argument('--out-root',type=Path,default=DEFAULT_OUT); ap.add_argument('--compact',action='store_true'); args=ap.parse_args(); r=build_holdout(args.dev_root,args.source_pool_root,args.out_root); args.out_root.mkdir(parents=True,exist_ok=True); _w(args.out_root/'holdout_manifest.json',r); (args.out_root/'holdout_manifest.md').write_text(md(r));
    if args.compact: print(json.dumps({k:r.get(k) for k in ['selected_case_count','candidate_generatable_count','overlap_with_dev_case_ids','planned_commands','m27tw_holdout_manifest_ready']},indent=2,sort_keys=True))
if __name__=='__main__': main()
