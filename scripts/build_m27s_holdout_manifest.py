#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from typing import Any
REPO_ROOT=Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from scripts.scan_bfcl_ctspc_opportunities import scan_opportunities, summarize_opportunities
DEFAULT_DEV_ROOT=Path('outputs/artifacts/bfcl_ctspc_subset30_v1')
DEFAULT_OUT_ROOT=Path('outputs/artifacts/bfcl_ctspc_holdout30_v1')
DEFAULT_CATEGORIES=['multi_turn_miss_param','multi_turn_base','multi_turn_miss_func','multi_turn_long_context']
FILE_PATH_TOOLS={'cat','cd','cp','diff','echo','find','grep','ls','mkdir','mv','sort','tail','touch'}
def _j(p:Path, default:Any=None):
    if not p.exists():
        if default is not None: return default
        raise FileNotFoundError(p)
    return json.loads(p.read_text())
def _w(p:Path,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
def _category_available(root:Path, cat:str)->bool: return bool(list((root/'bfcl').glob(f'**/BFCL_v4_{cat}_score.json')))
def build_holdout(dev_root:Path=DEFAULT_DEV_ROOT,out_root:Path=DEFAULT_OUT_ROOT,categories:list[str]|None=None,max_cases:int=30)->dict[str,Any]:
    dev=_j(dev_root/'paired_subset_manifest.json'); source=Path(str(dev.get('source_run_root') or '')); dev_ids={str(x) for x in dev.get('selected_case_ids') or []}; cats=categories or DEFAULT_CATEGORIES
    selected=[]; scanned=[]
    for cat in cats:
        available=_category_available(source,cat); count_before=len(selected)
        if available:
            try: rows=scan_opportunities(source,cat)
            except Exception: rows=[]
            for r in rows:
                cid=str(r.get('case_id'))
                if cid in dev_ids or cid in {str(x.get('case_id')) for x in selected}: continue
                tools=set(str(t) for t in r.get('target_action_tools_present') or [])
                if r.get('schema_local') and tools & FILE_PATH_TOOLS:
                    selected.append({**r,'holdout_category':cat})
                    if len(selected)>=max_cases: break
        scanned.append({'category':cat,'available':available,'selected_count':len(selected)-count_before})
        if len(selected)>=max_cases: break
    ids=[str(r.get('case_id')) for r in selected]; overlap=sorted(dev_ids.intersection(ids)); generatable=sum(1 for r in selected if r.get('schema_local'))
    report={'report_scope':'m2_7s_holdout_manifest','holdout_subset_id':out_root.name,'source_run_root':str(source),'categories':cats,'category_scan_summary':scanned,'selected_case_count':len(ids),'selected_case_ids':ids,'excluded_dev_case_count':len(dev_ids),'overlap_with_dev_case_ids':overlap,'schema_local_case_count':generatable,'candidate_generatable_count':generatable,'planned_commands':[],'selection_criteria':{'cross_category_fallback':True,'exclude_dev_subset':True,'require_schema_local':True,'require_file_path_tool':True},'m27s_holdout_manifest_ready':len(ids)>=20 and not overlap and generatable>=15,'diagnostic':{'offline_only':True,'no_bfcl_planned_commands':True}}
    return report
def md(r):
    lines=['# M2.7s Holdout Manifest','',f"- Ready: `{r['m27s_holdout_manifest_ready']}`",f"- Selected: `{r['selected_case_count']}`",f"- Overlap: `{r['overlap_with_dev_case_ids']}`",'','## Category Scan']
    lines += [f"- `{x['category']}` available=`{x['available']}` selected=`{x['selected_count']}`" for x in r['category_scan_summary']]
    lines += ['','## Selected Cases']+[f"- `{x}`" for x in r['selected_case_ids']]
    return '\n'.join(lines)+'\n'
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dev-root',type=Path,default=DEFAULT_DEV_ROOT); ap.add_argument('--out-root',type=Path,default=DEFAULT_OUT_ROOT); ap.add_argument('--max-cases',type=int,default=30); ap.add_argument('--compact',action='store_true'); a=ap.parse_args(); r=build_holdout(a.dev_root,a.out_root,max_cases=a.max_cases); a.out_root.mkdir(parents=True,exist_ok=True); _w(a.out_root/'holdout_manifest.json',r); (a.out_root/'holdout_manifest.md').write_text(md(r));
    if a.compact: print(json.dumps({k:r.get(k) for k in ['selected_case_count','candidate_generatable_count','overlap_with_dev_case_ids','planned_commands','m27s_holdout_manifest_ready']},indent=2,sort_keys=True))
if __name__=='__main__': main()
