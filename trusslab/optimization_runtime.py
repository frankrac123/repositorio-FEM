"""Size optimization with explicit structural provenance and hard budgets."""
from contextlib import ExitStack
from collections import OrderedDict
from dataclasses import asdict
from pathlib import Path
import csv,json,threading,time,uuid
import numpy as np
from scipy.optimize import minimize,differential_evolution,NonlinearConstraint
from .fem import solve
from .design_space import DesignSpace
from .asam import ASAMOptions,run_asam


class Cancelled(Exception):pass
class EvaluationBudget(Exception):pass


class RunControl:
    """Pause/stop between analyses; never interrupt an in-flight COM call."""
    def __init__(self):
        self.stop=threading.Event();self.paused=threading.Event()
    def cancel(self):self.stop.set();self.paused.clear()
    def pause(self,value=True):self.paused.set() if value else self.paused.clear()
    def checkpoint(self):
        while self.paused.is_set():
            if self.stop.wait(.05):raise Cancelled()
        if self.stop.is_set():raise Cancelled()


def optimize(model,method='SLSQP',iterations=200,seed=42,progress=None,cancelled=None,*,
             engine='FEM',max_evaluations=10000,hybrid_validations=3,asam_options=None,
             control=None,output_dir=None,active_ids=None,groups=None,batch_factory=None):
    """Hybrid reserves K real SAP verifications and one optional safety check.

    Every counted evaluation runs one selected engine. Exact repeats are cached.
    A SAP failure raises; there is no fallback. The input model is never changed.
    """
    if engine not in ('FEM','SAP','HYBRID'):raise ValueError('Motor no implementado.')
    if method not in ('SLSQP','DE','ASAM'):raise ValueError('Algoritmo no implementado.')
    if iterations<1 or max_evaluations<2:raise ValueError('Iteraciones y presupuesto inválidos.')
    reserve=hybrid_validations if engine=='HYBRID' else 0
    if engine=='HYBRID' and (reserve<1 or max_evaluations<reserve+2):raise ValueError('Presupuesto insuficiente para las verificaciones SAP.')
    options=asam_options or ASAMOptions()
    if isinstance(options,dict):options=ASAMOptions(**options)
    if method=='ASAM':options.validate()
    space=DesignSpace(model,active_ids,groups);initial_weight=model.weight()
    control=control or RunControl();started=time.monotonic()
    history=[];cache=OrderedDict();ranked={};best=None;counts={'FEM':0,'SAP':0};iteration=0
    run_dir=None
    if output_dir is not None:
        run_dir=Path(output_dir)/('optimization_'+time.strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6])
        run_dir.mkdir(parents=True,exist_ok=False)
        (run_dir/'configuration.json').write_text(json.dumps({'method':method,'engine':engine,'seed':seed,
            'iterations':iterations,'max_evaluations':max_evaluations,'hybrid_validations':reserve,
            'asam':asdict(options),'design_space':space.descriptor(),'model':model.to_dict()},indent=2),encoding='utf-8')
    def checkpoint():
        control.checkpoint()
        if cancelled and cancelled():raise Cancelled()
    def total():return sum(counts.values())
    with ExitStack() as stack:
        batch=None
        ledger=stack.enter_context((run_dir/'evaluations.jsonl').open('a',encoding='utf-8')) if run_dir else None
        def sap_evaluate(candidate):
            nonlocal batch
            if batch is None:
                if batch_factory is None:
                    from .sap import SapBatchSession
                    factory=SapBatchSession
                else:factory=batch_factory
                if run_dir is None:raise ValueError('El motor SAP requiere output_dir para registrar sus operaciones.')
                if progress:progress('Iniciando sesión SAP2000 propia y persistente…')
                batch=stack.enter_context(factory(run_dir/'sap'))
            return batch.evaluate(candidate)

        def evaluate(x,metadata=None,*,backend=None,limit=None,force=False):
            nonlocal best
            checkpoint();backend=backend or ('SAP' if engine=='SAP' else 'FEM')
            x=np.asarray(x,dtype=float);key=(backend,x.tobytes())
            if key in cache and not force:return cache[key][1]
            if total()>=(max_evaluations-reserve-1 if limit is None else limit):raise EvaluationBudget()
            candidate=space.expand(x)
            result=sap_evaluate(candidate) if backend=='SAP' else solve(candidate)
            counts[backend]+=1
            result['model_fingerprint']=candidate.fingerprint()
            result['external_validation']='verified' if backend=='SAP' else 'pending'
            cache[key]=(candidate,result,x.copy())
            cache.move_to_end(key)
            if len(cache)>2048:cache.popitem(last=False)
            if result['feasible']:
                ranked[key]=cache[key]
                retained=reserve if engine=='HYBRID' else 1
                while len(ranked)>max(1,retained):
                    worst=max(ranked,key=lambda k:ranked[k][1]['weight_lb']);del ranked[worst]
                if best is None or result['weight_lb']<best[1]['weight_lb']:best=cache[key]
            item={'iteration':iteration,'evaluations':total(),'engine':result['engine'],
                  'backend':backend,'fem_evaluations':counts['FEM'],'sap_evaluations':counts['SAP'],
                  'weight_lb':result['weight_lb'],'feasible':result['feasible'],
                  'best_feasible_lb':None if best is None else best[1]['weight_lb'],
                  'stress_ratio':result['stress_ratio'],'displacement_ratio':result['displacement_ratio'],
                  'elapsed_seconds':time.monotonic()-started,'external_validation':result['external_validation'],
                  'sap_status':'sesión persistente activa' if batch is not None else 'sin sesión',
                  'areas_in2':[m.area for m in candidate.members],**(metadata or {})}
            history.append(item)
            if ledger:
                ledger.write(json.dumps(item)+'\n')
                if total()%50==0:ledger.flush()
            if progress:progress(item)
            return result

        def margins(x):
            r=evaluate(x)
            return np.r_[[1-m['ratio'] for m in r['members']],
                [1-abs(r['displacements'][str(n.id)][d])/model.displacement_limit
                 for n in model.nodes for d in range(3) if not n.fixed[d]]]
        def objective(x):return evaluate(x)['weight_lb']/initial_weight
        def callback(x,*args):
            nonlocal iteration
            iteration+=1;checkpoint()
        info={'converged':False,'message':'max_iterations','iterations':0}
        try:
            if method=='ASAM':
                info=run_asam(evaluate,space.lower,space.upper,options,iterations,seed,initial_weight,checkpoint)
            else:
                evaluate(space.initial,{'phase':'initial'})
                bounds=list(zip(space.lower,space.upper))
                if method=='SLSQP':
                    search=minimize(objective,space.initial,method='SLSQP',bounds=bounds,
                        constraints=[{'type':'ineq','fun':margins}],callback=callback,
                        options={'maxiter':iterations,'ftol':1e-10})
                else:
                    search=differential_evolution(objective,bounds,
                        constraints=(NonlinearConstraint(margins,0.,np.inf),),maxiter=iterations,
                        popsize=10,seed=seed,x0=space.initial,callback=callback,polish=False,workers=1,tol=1e-6)
                evaluate(search.x,{'phase':'algorithm_final'})
                info={'converged':bool(search.success),'message':str(search.message),'iterations':int(search.nit)}
        except EvaluationBudget:info.update(message='max_evaluations',converged=False)
        except Cancelled:info.update(message='cancelled',converged=False)
        except Exception as error:
            if run_dir:(run_dir/'error.txt').write_text(str(error),encoding='utf-8')
            raise
        iteration=max(iteration,max((h['iteration'] for h in history),default=0))
        if info['iterations']==0:info['iterations']=iteration
        if best is None:
            if run_dir:
                (run_dir/'termination.json').write_text(json.dumps({**info,'evaluations':total(),
                    'best_feasible_lb':None,'model_unchanged':True},indent=2),encoding='utf-8')
            raise ValueError('No se encontró un diseño factible; el modelo original se conserva. '+str(run_dir or ''))
        verified=[]
        if engine=='HYBRID' and info['message']!='cancelled':
            shortlist=sorted((v for k,v in ranked.items() if k[0]=='FEM'),key=lambda v:v[1]['weight_lb'])[:reserve]
            try:
                for candidate,result,x in shortlist:
                    result=evaluate(x,{'phase':'external_verification'},backend='SAP',limit=max_evaluations-1)
                    if result['feasible']:verified.append((candidate,result,x))
            except Cancelled:info.update(message='cancelled',converged=False)
            if not verified and info['message']!='cancelled':raise ValueError('Ningún candidato verificado por SAP cumple las restricciones.')
        if verified:best=min(verified,key=lambda value:value[1]['weight_lb'])
        final_model,final,x=best
        def final_evaluation(x,phase,backend):
            try:return evaluate(x,{'phase':phase},backend=backend,limit=max_evaluations,force=backend=='SAP')
            except Cancelled:
                info.update(message='cancelled',converged=False)
                return None
        # Count and log numerical repair, with the same engine as the final result.
        ratio=max(final['stress_ratio'],final['displacement_ratio'])
        if ratio>1-1e-8 and info['message']!='cancelled' and total()<max_evaluations:
            corrected=np.minimum(space.upper,x*max(1.,ratio)*(1+1e-8))
            backend='SAP' if final['engine'].startswith('SAP2000') else 'FEM'
            r=final_evaluation(corrected,'roundoff_safety',backend)
            if r is not None and r['feasible']:
                final_model,final,x=cache[(backend,corrected.tobytes())]
        # The SDB shared by a batch must describe the winner rather than the
        # last finite-difference perturbation. This real analysis is counted.
        if (final['engine'].startswith('SAP2000') and info['message']!='cancelled' and total()<max_evaluations
                and getattr(batch,'last_fingerprint',final_model.fingerprint())!=final_model.fingerprint()):
            r=final_evaluation(x,'restore_winner','SAP')
            if r is not None:final=r;final_model=space.expand(x)
        if not final['feasible']:raise ValueError('El diseño seleccionado incumple las restricciones.')
        final=dict(final)
        if final['engine'].startswith('SAP2000'):
            final['sap_file_matches_result']=getattr(batch,'last_fingerprint',final_model.fingerprint())==final_model.fingerprint()
        final['optimization']={'method':method,'engine_mode':engine,'seed':seed,
            'evaluations':total(),'fem_evaluations':counts['FEM'],'sap_evaluations':counts['SAP'],
            'max_evaluations':max_evaluations,'initial_weight_lb':initial_weight,
            'elapsed_seconds':time.monotonic()-started,'feasible_evaluations':sum(h['feasible'] for h in history),
            'global_optimum_proven':False,'design_space':space.descriptor(),
            'run_directory':str(run_dir or ''),'asam':asdict(options) if method=='ASAM' else None,**info}
        if run_dir:
            from .core import save_project
            save_project(run_dir/'best.trusslab.json',final_model,final,history)
            with (run_dir/'convergence.csv').open('w',newline='',encoding='utf-8-sig') as stream:
                keys=['evaluations','iteration','backend','weight_lb','feasible','best_feasible_lb','elapsed_seconds','external_validation']
                writer=csv.DictWriter(stream,fieldnames=keys,extrasaction='ignore');writer.writeheader();writer.writerows(history)
        return final_model,final,history
