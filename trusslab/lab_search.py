"""Pure and explicitly named hybrid drivers share one counted evaluator."""
from dataclasses import asdict
import hashlib
import numpy as np
from scipy.optimize import minimize,differential_evolution,NonlinearConstraint
from .asam import ASAMOptions,preliminary_points,quality,run_asam
from .lab_evaluation import BudgetReached
from .optimization import Cancelled

METHODS=('ASAM','DE','SLSQP','ASAM+SLSQP','DE+SLSQP')


def search(evaluator,method,seed,parameters):
    if method not in METHODS:raise ValueError('Método de laboratorio no implementado.')
    ev=evaluator;p=parameters;options=ASAMOptions(**p.get('asam',{}));options.validate()
    bounds=list(zip(ev.space.lower,ev.space.upper));scale=ev.model.weight()
    population=preliminary_points(np.random.default_rng(seed),options.initial_points,ev.space.lower,ev.space.upper)
    signature=hashlib.sha256(population.tobytes()).hexdigest()
    info={'message':'max_iterations','converged':False,'iterations':0,'initial_population_sha256':signature,
          'initial_policy':'shared_uniform_population','starts':[],'hybrid': '+' in method}
    last_limit=ev.budget-1  # One real, counted safety evaluation if needed.
    primary_limit=int(last_limit*p.get('global_fraction',.7)) if '+' in method else last_limit
    minimum=options.initial_points*(2 if ev.sap else 1)+2
    if primary_limit<minimum:raise ValueError('El presupuesto no alcanza para la población inicial y búsqueda configuradas.')
    pool=[]
    def evaluate(x,metadata=None,limit=primary_limit):return ev.evaluate(x,metadata,limit=limit)
    def callback(x,*args):ev.iteration+=1;ev.control.checkpoint()
    def slsqp(x,limit,phase):
        ev.phase=phase
        before=ev.evaluations
        info['starts'].append({'variables_in2':np.asarray(x).tolist(),'start_evaluation':before,'phase':phase,'limit':limit})
        try:
            result=minimize(lambda v:ev.evaluate(v,limit=limit)['weight_lb']/scale,x,method='SLSQP',bounds=bounds,
                constraints=[{'type':'ineq','fun':lambda v:ev.margins(v,limit)}],callback=callback,
                options={'maxiter':p.get('iterations',10000),'ftol':p.get('slsqp_ftol',1e-10)})
            info['starts'][-1].update(message=str(result.message),iterations=int(result.nit),converged=bool(result.success))
            return result
        except BudgetReached:
            info['starts'][-1]['message']='stage_budget';return None
        finally:info['starts'][-1]['evaluations']=ev.evaluations-before
    try:
        ev.phase='common_preliminary'
        for x in population:pool.append((x,evaluate(x)))
        base=method.split('+')[0];ev.phase='global_search'
        if base=='ASAM':
            outcome=run_asam(evaluate,ev.space.lower,ev.space.upper,options,p.get('iterations',10000),seed,scale,
                ev.control.checkpoint,initial_population=population,
                constraint_policy=p.get('asam_constraint_policy','feasible_first'),penalty_coefficient=p.get('penalty_coefficient',100.))
            info.update(message=outcome['message'],converged=outcome['converged'],iterations=outcome['iterations'])
        elif base=='DE':
            result=differential_evolution(lambda x:evaluate(x)['weight_lb']/scale,bounds,
                constraints=(NonlinearConstraint(lambda x:ev.margins(x,primary_limit),0,np.inf),),
                init=population,seed=seed,maxiter=p.get('iterations',10000),callback=callback,polish=False,
                mutation=tuple(p.get('de_mutation',[.5,1.])),recombination=p.get('de_recombination',.7),
                tol=p.get('de_tolerance',1e-6),workers=1)
            info.update(message=str(result.message),converged=bool(result.success),iterations=int(result.nit))
        else:
            # Same evaluated pool as ASAM/DE; rank it, then choose spatially
            # separated starts. No archived design or hand-picked optimum.
            ordered=sorted(pool,key=lambda pair:quality(pair[1],scale));starts=[ordered[0][0]]
            remaining=[x for x,_ in ordered[1:]]
            for _ in range(min(p.get('slsqp_starts',5),len(population))-1):
                x=max(remaining,key=lambda v:min(np.linalg.norm((v-s)/(ev.space.upper-ev.space.lower)) for s in starts))
                starts.append(x);remaining=[v for v in remaining if not np.array_equal(v,x)]
            successes=[]
            for i,x in enumerate(starts):
                ev.control.checkpoint();limit=ev.evaluations+max(0,(primary_limit-ev.evaluations)//(len(starts)-i))
                result=slsqp(x,limit,'slsqp_multistart')
                if result is not None:successes.append(bool(result.success))
            info.update(message='multistart_completed',converged=any(successes))
    except BudgetReached:info.update(message='max_evaluations',converged=False)
    except Cancelled:info.update(message='cancelled',converged=False)
    if '+' in method and info['message']!='cancelled' and ev.best is not None:
        before_weight=ev.best[1]['weight_lb'];info['global_weight_lb']=before_weight
        try:
            slsqp(ev.best[0],last_limit,'local_refinement')
            info['refinement_improved']=ev.best[1]['weight_lb']<before_weight
            info['message']='hybrid_completed'
        except Cancelled:info['message']='cancelled'
    # Do not silently replace the best with a worse repaired candidate.
    if ev.best is not None and info['message']!='cancelled':
        x,r=ev.best;ratio=max(r['stress_ratio'],r['displacement_ratio'])
        if ratio>1-1e-8:
            ev.phase='roundoff_safety';candidate=np.minimum(ev.space.upper,x*max(1.,ratio)*(1+1e-8))
            try:ev.evaluate(candidate,limit=ev.budget)
            except BudgetReached:pass
            except Cancelled:info['message']='cancelled'
    info['iterations']=max(info['iterations'],ev.iteration,max((h.get('iteration',0) for h in ev.history),default=0))
    return info
