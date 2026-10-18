"""Recompute a two-start local SLSQP example; no target weight is used.

The second start deliberately changes A3 to 1 in² to leave the basin of the
first local solution. This is a documented starting design, not a prescribed
optimum. The final design is always obtained from FE constraint evaluations.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trusslab.core import benchmark,save_project
from trusslab.optimization import optimize

root=Path(__file__).resolve().parents[1]
original=benchmark()
first,r1,h1=optimize(original,iterations=300)
start=first.clone()
start.members[2].area=1.
second,r2,h2=optimize(start,iterations=300)
chosen,result=(second,r2) if r2['weight_lb']<r1['weight_lb'] else (first,r1)
history=list(h1)
best=min(x['best_feasible_lb'] for x in h1 if x['best_feasible_lb'] is not None)
for row in h2:
    row=dict(row)
    row['iteration']=len(history)
    row['evaluations']+=h1[-1]['evaluations']
    best=min(best,row['best_feasible_lb'] if row['best_feasible_lb'] is not None else best)
    row['best_feasible_lb']=best
    history.append(row)
result['optimization']['initial_weight_lb']=original.weight()
result['optimization']['iterations']=len(history)-1
result['optimization']['evaluations']=history[-1]['evaluations']
result['optimization']['starts']='Uniform 35 in², then first result with A3 = 1 in²'
root.joinpath('examples').mkdir(exist_ok=True)
save_project(root/'examples'/'Caso_I_calculado.trusslab.json',chosen,result,history)
print(result['weight_lb'],result['stress_ratio'],result['displacement_ratio'])
