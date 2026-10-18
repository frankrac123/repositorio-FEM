"""Mechanism/reproducibility checks, not a comparative algorithm laboratory."""
from pathlib import Path
import json
import argparse
import numpy as np
from trusslab.core import benchmark,load_project
from trusslab.fem import solve
from trusslab.validation import validation_report
from trusslab.optimization import optimize

root=Path(__file__).resolve().parents[1]/'data'/'phase3_asam'
root.mkdir(parents=True,exist_ok=True)
rows=[];signatures=[]
parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');parser.add_argument('--repeat42',action='store_true')
args=parser.parse_args();completed=[]
if args.resume:
    completed=sorted(root.glob('optimization_*/best.trusslab.json'))
for seed in ([42] if args.repeat42 else [42,7,17,42]):
    match=None
    for path in completed:
        stored=json.loads(path.read_text())
        if stored['results']['optimization']['seed']==seed:match=path;break
    if match:
        model,result,history=load_project(match);completed.remove(match)
    else:model,result,history=optimize(benchmark(),'ASAM',300,seed,max_evaluations=16000,output_dir=root)
    independent=solve(model)
    assert independent['feasible'] and independent['residual_kip']<1e-8
    signatures.append([b.area for b in model.members])
    rows.append({'seed':seed,'weight_lb':result['weight_lb'],'stress_ratio':result['stress_ratio'],
        'displacement_ratio':result['displacement_ratio'],'evaluations':result['optimization']['evaluations'],
        'iterations':result['optimization']['iterations'],'termination':result['optimization']['message'],
        'run_directory':result['optimization']['run_directory'],'areas_in2':signatures[-1]})
if args.repeat42:
    print(json.dumps(rows,indent=2));raise SystemExit(0)
assert signatures[0]==signatures[-1]
published=benchmark()
for member,area in zip(published.members,[30.522,.1,23.263,15.151,.1,.545,7.455,21.052,21.526,.1]):member.area=area
pr=solve(published)
# Recompute the earlier local solution instead of assuming its archived weight.
old_path=Path(__file__).resolve().parents[1]/'data'/'automatic_final'/'sap_case_i.trusslab.json'
previous=None
if old_path.exists():
    old,_,_=load_project(old_path);r=solve(old)
    previous={'weight_lb':r['weight_lb'],'stress_ratio':r['stress_ratio'],'displacement_ratio':r['displacement_ratio'],
        'feasible':r['feasible'],'residual_kip':r['residual_kip']}
report={'runs':rows,'repeat_seed42_identical':True,'constraint_ratio_tolerance':1e-6,
    'published_rounded_areas':{'weight_lb':pr['weight_lb'],'stress_ratio':pr['stress_ratio'],
        'displacement_ratio':pr['displacement_ratio'],'feasible':pr['feasible']},'earlier_solution_recomputed':previous}
(root/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
