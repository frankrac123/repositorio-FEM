"""Analysis cases and optimization constraints without synthetic force envelopes."""
import numpy as np

def design_cases(model):
    cases=model.optimization_config.get('load_cases') or [model.active_case]
    if len(cases)!=len(set(cases)):raise ValueError('Casos de optimización duplicados.')
    available=model.available_cases()
    if not set(cases)<=available:raise ValueError('Un caso seleccionado para optimización no existe.')
    return list(cases)

def combine_cases(model,results):
    if len(results)==1:return next(iter(results.values()))
    active=model.active_case if model.active_case in results else next(iter(results))
    result=dict(results[active]);result['case_results']=results
    result['display_case']=active
    result['stress_ratio']=max(r['stress_ratio'] for r in results.values())
    result['displacement_ratio']=max(r['displacement_ratio'] for r in results.values())
    result['feasible']=all(r['feasible'] for r in results.values())
    result['strict_feasible']=all(r.get('strict_feasible',r['stress_ratio']<=1 and r['displacement_ratio']<=1) for r in results.values())
    result['feasibility_tolerance']=1e-6
    result['governing_cases']={key:max(results,key=lambda c:results[c][key]) for key in ('stress_ratio','displacement_ratio')}
    excess=np.maximum(-constraint_margins(model,result)-1e-6,0.)
    result['constraint_violation']=float(np.dot(excess,excess))
    return result

def solve_design(model):
    from .fem import solve
    return combine_cases(model,{case:solve(model,case=case) for case in design_cases(model)})

def constraint_margins(model,result):
    cases=result.get('case_results') or {result.get('analysis_case',model.active_case):result}
    return np.concatenate([np.r_[[1-m['ratio'] for m in r['members']],
        [1-abs(r['displacements'][str(n.id)][d])/model.displacement_limit
         for n in model.nodes for d in range(3) if not model.restraints(n)[d]]] for r in cases.values()])

def project_state(model,result=None,checked_fingerprint=None):
    if result and result.get('model_fingerprint')==model.fingerprint():return 'ANALIZADO'
    if checked_fingerprint==model.fingerprint():return 'LISTO PARA ANÁLISIS'
    return 'BORRADOR / MODELADO'
