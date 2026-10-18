"""ASAM mechanisms from Millán-Páramo et al. (2017), Eqs. 6, 7 and 8.

Underspecified choices (symmetric directions, reflection, feasible-first ranking,
normalized energy, proposals per temperature) are explicit project decisions.
No local optimizer is invoked or hidden inside ASAM.
"""
from dataclasses import dataclass,asdict
import math
import numpy as np
from scipy.special import expit


@dataclass
class ASAMOptions:
    temperature_initial: float=.05
    temperature_final: float=1e-6
    cooling: float=.96
    initial_points: int=100
    radius_initial: float=17.45  # in² in the benchmark; configurable for other models
    radius_reduction: float=.96
    proposals_per_temperature: int=50
    convergence_tolerance: float=0.0  # 0 disables early stagnation termination
    convergence_patience: int=30

    def validate(self):
        if not (math.isfinite(self.temperature_initial) and math.isfinite(self.temperature_final) and 0<self.temperature_final<self.temperature_initial):raise ValueError('Temperaturas ASAM inválidas.')
        if not (0<self.cooling<1 and 0<self.radius_reduction<1):raise ValueError('Los coeficientes ASAM deben estar entre 0 y 1.')
        if self.initial_points<1 or self.proposals_per_temperature<1 or self.convergence_patience<1:raise ValueError('Los conteos ASAM deben ser positivos.')
        if not math.isfinite(self.radius_initial) or self.radius_initial<=0:raise ValueError('El radio ASAM debe ser positivo.')
        if not math.isfinite(self.convergence_tolerance) or self.convergence_tolerance<0:raise ValueError('Tolerancia ASAM inválida.')


def acceptance_probability(delta,temperature):
    if not math.isfinite(delta) or not math.isfinite(temperature) or delta<0 or temperature<=0:
        raise ValueError('La regla logística requiere Δ ≥ 0 y T > 0 finitos.')
    return float(expit(-delta/temperature))


def preliminary_points(rng,count,lower,upper):
    return np.asarray(lower)+(np.asarray(upper)-np.asarray(lower))*rng.random((count,len(lower)))


def reflect_into_bounds(x,lower,upper):
    width=np.asarray(upper)-np.asarray(lower)
    y=np.mod(np.asarray(x)-lower,2*width)
    return lower+np.where(y<=width,y,2*width-y)


def violation(result):
    if result.get('analysis_status')=='failed':return float('inf')
    if result.get('constraint_violation') is not None:return result['constraint_violation']
    return float(sum(max(0.,r['ratio']-1.-1e-6)**2 for r in result['members'])
                 +max(0.,result['displacement_ratio']-1.-1e-6)**2)


def quality(result,weight_scale,policy='feasible_first',penalty_coefficient=100.):
    if result.get('analysis_status')=='failed':return (2,float('inf'),result['weight_lb']/weight_scale)
    if policy=='penalty':return (0,result['weight_lb']/weight_scale+penalty_coefficient*violation(result),result['weight_lb']/weight_scale)
    return (0 if result['feasible'] else 1,
            result['weight_lb']/weight_scale if result['feasible'] else violation(result),
            result['weight_lb']/weight_scale)


def run_asam(evaluate,lower,upper,options,iterations,seed,weight_scale,checkpoint=lambda:None,*,
             initial_population=None,constraint_policy='feasible_first',penalty_coefficient=100.):
    if constraint_policy not in ('feasible_first','penalty') or penalty_coefficient<=0:raise ValueError('Política de restricciones ASAM inválida.')
    options.validate();rng=np.random.default_rng(seed)
    generated=preliminary_points(rng,options.initial_points,lower,upper)
    points=generated if initial_population is None else np.asarray(initial_population)
    if points.shape!=generated.shape or not np.isfinite(points).all() or np.any(points<lower) or np.any(points>upper):raise ValueError('Exploración preliminar ASAM inválida.')
    score=lambda r:quality(r,weight_scale,constraint_policy,penalty_coefficient)
    current=None;current_r=None
    for x in points:
        checkpoint();r=evaluate(x,{'phase':'preliminary','iteration':0})
        if current_r is None or score(r)<score(current_r):current,current_r=x.copy(),r
    temperature=options.temperature_initial;radius=options.radius_initial
    best_score=score(current_r);stagnant=0
    for iteration in range(1,iterations+1):
        if temperature<=options.temperature_final:return {'converged':True,'message':'temperature_final','iterations':iteration-1,'options':asdict(options)}
        previous=best_score
        for _ in range(options.proposals_per_temperature):
            checkpoint()
            x=reflect_into_bounds(current+rng.uniform(-radius,radius,len(current)),lower,upper)
            r=evaluate(x,{'phase':'search','iteration':iteration,'temperature':temperature,'radius':radius})
            q,old=score(r),score(current_r)
            if q[0]<old[0]:accept=True
            elif q[0]>old[0]:accept=False  # Never leave a feasible state for an infeasible one.
            elif not math.isfinite(q[1]):accept=False
            else:
                delta=q[1]-old[1]
                if delta==0:delta=q[2]-old[2]
                accept=delta<=0 or rng.random()<acceptance_probability(delta,temperature)
            if accept:current,current_r=x,r
            best_score=min(best_score,q)
        if options.convergence_tolerance and best_score[0]==0 and previous[0]==0 and abs(best_score[1]-previous[1])<=options.convergence_tolerance:
            stagnant+=1
        else:stagnant=0
        if stagnant>=options.convergence_patience:return {'converged':True,'message':'stagnation_tolerance','iterations':iteration,'options':asdict(options)}
        temperature*=options.cooling;radius*=options.radius_reduction
    return {'converged':False,'message':'max_iterations','iterations':iterations,'options':asdict(options)}
