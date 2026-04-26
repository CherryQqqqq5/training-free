#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
DEFAULT_DEV_ROOT=Path('outputs/artifacts/bfcl_ctspc_subset30_v1')
DEFAULT_OUT_ROOT=Path('outputs/artifacts/bfcl_ctspc_source_pool_v1')
CATEGORIES=['multi_turn_base','multi_turn_miss_func','multi_turn_long_context']
MODEL='gpt-4o-mini-2024-07-18-FC'
def _j(p:Path, default:Any=None):
    if not p.exists():
        if default is not None: return default
        raise FileNotFoundError(p)
    return json.loads(p.read_text())
def _w(p:Path,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
def _has_source(root:Path,cat:str)->bool: return bool(list((root/'bfcl').glob(f'**/BFCL_v4_{cat}_score.json')) and list((root/'bfcl').glob(f'**/BFCL_v4_{cat}_result.json')))
def _baseline_command(repo:Path,out_root:Path,cat:str,port:int,runtime:Path)->str:
    return ' '.join(['bash',str(repo/'scripts/run_bfcl_v4_baseline.sh'),MODEL,str(out_root/cat/'baseline'),str(port),cat,str(runtime)])
def build_source_pool_manifest(dev_root:Path=DEFAULT_DEV_ROOT,out_root:Path=DEFAULT_OUT_ROOT,repo_root:Path=Path.cwd(),categories:list[str]|None=None)->dict[str,Any]:
    dev=_j(dev_root/'paired_subset_manifest.json')
    existing_roots=[Path(str(dev.get('source_run_root') or ''))]
    cats=categories or CATEGORIES
    runtime=Path(str(dev.get('runtime_config') or 'configs/runtime_bfcl_structured.yaml'))
    if not runtime.is_absolute(): runtime=repo_root/runtime
    rows=[]; commands=[]
    for i,cat in enumerate(cats):
        existing=[str(root) for root in existing_roots if _has_source(root,cat)]
        ready=bool(existing)
        cmd=None
        if not ready:
            cmd=_baseline_command(repo_root,out_root,cat,8070+i,runtime)
            commands.append(cmd)
        rows.append({'category':cat,'source_artifacts_available':ready,'existing_source_roots':existing,'baseline_source_collection_required':not ready,'planned_source_collection_command':cmd})
    report={'report_scope':'m2_7t_source_pool_manifest','artifact_root':str(out_root),'dev_subset_root':str(dev_root),'categories':cats,'category_status':rows,'planned_source_collection_commands':commands,'planned_commands':commands,'candidate_commands':[],'source_collection_only':True,'m27t_source_pool_ready':all(r['source_artifacts_available'] for r in rows),'diagnostic':{'baseline_only':True,'no_candidate_rules':True,'not_performance_evidence':True,'do_not_run_without_explicit_request':True}}
    return report
def md(r):
    lines=['# M2.7t Source Pool Manifest','',f"- Ready: `{r['m27t_source_pool_ready']}`",f"- Source collection commands: `{len(r['planned_source_collection_commands'])}`",'','| Category | Available | Needs Collection |','| --- | ---: | ---: |']
    for x in r['category_status']: lines.append(f"| `{x['category']}` | `{x['source_artifacts_available']}` | `{x['baseline_source_collection_required']}` |")
    lines+=['','## Planned Baseline-Only Commands']+[f"```bash\n{cmd}\n```" for cmd in r['planned_source_collection_commands']]
    return '\n'.join(lines)+'\n'
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dev-root',type=Path,default=DEFAULT_DEV_ROOT); ap.add_argument('--out-root',type=Path,default=DEFAULT_OUT_ROOT); ap.add_argument('--repo-root',type=Path,default=Path.cwd()); ap.add_argument('--compact',action='store_true'); a=ap.parse_args(); r=build_source_pool_manifest(a.dev_root,a.out_root,a.repo_root); a.out_root.mkdir(parents=True,exist_ok=True); _w(a.out_root/'source_collection_manifest.json',r); (a.out_root/'source_collection_manifest.md').write_text(md(r));
    if a.compact: print(json.dumps({k:r.get(k) for k in ['m27t_source_pool_ready','planned_source_collection_commands','candidate_commands']},indent=2,sort_keys=True))
if __name__=='__main__': main()
