"""Shared, counted structural evaluation for every laboratory algorithm."""
from collections import OrderedDict
from pathlib import Path
import gzip,json,time
import numpy as np
from .design_space import DesignSpace
from .prepared_fem import PreparedTruss
from .optimization import RunControl,Cancelled


class BudgetReached(Exception):pass


class EvaluationSession:
    def __init__(self,model,budget,trace_path,control=None,progress=None,sap=None,active_ids=None,groups=None):
        self.space=DesignSpace(model,active_ids,groups);self.model=self.space.model
        self.prepared=PreparedTruss(self.model);self.budget=budget;self.control=control or RunControl()
        self.progress=progress;self.sap=sap;self.cache=OrderedDict();self.history=[];self.best=None
        self.evaluations=0;self.cache_hits=0;self.requests=0;self.budget_rejections=0;self.failures=0;self.fem_evaluations=0;self.sap_evaluations=0;self.audit_evaluations=0
        self.started=time.perf_counter();self.last_emit=0.;self.phase='preliminary';self.iteration=0;self.best_evaluation=None
        self.trace_path=Path(trace_path);self.trace_path.parent.mkdir(parents=True,exist_ok=True)
        self.stream=gzip.open(self.trace_path,'wt',encoding='utf-8')
        by_id={m.id:i for i,m in enumerate(self.model.members)}
        self.indices=[[by_id[id] for id in group] for group in self.space.groups]
        self.original_areas=np.array([m.area for m in self.model.members])
        self.constraint_count=len(self.model.members)+len(self.prepared.free)

    def close(self):self.stream.close()
    def areas(self,x):
        x=np.asarray(x,float)
        if x.shape!=self.space.initial.shape or not np.isfinite(x).all() or np.any(x<self.space.lower-1e-9) or np.any(x>self.space.upper+1e-9):raise ValueError('Variables de diseño inválidas.')
        areas=self.original_areas.copy()
        for value,indices in zip(np.clip(x,self.space.lower,self.space.upper),self.indices):areas[indices]=value
        return areas

    def evaluate(self,x,metadata=None,*,limit=None):
        self.control.checkpoint();self.requests+=1;x=np.asarray(x,float);key=x.tobytes()
        if key in self.cache:
            self.cache_hits+=1;self.cache.move_to_end(key);return self.cache[key]
        cost=2 if self.sap else 1
        if self.evaluations+cost>min(self.budget,limit if limit is not None else self.budget):
            self.budget_rejections+=1;raise BudgetReached()
        areas=self.areas(x);self.evaluations+=1
        if self.sap:self.sap_evaluations+=1
        else:self.fem_evaluations+=1
        try:
            if self.sap:
                candidate=self.space.expand(x);r=self.sap.evaluate(candidate)
                self.evaluations+=1;self.audit_evaluations+=1
                r['analysis_status']='solved';r['external_validation']='verified'
            else:
                r=self.prepared.solve(areas);r['external_validation']='pending'
        except (ValueError,np.linalg.LinAlgError) as exc:
            self.failures+=1
            r={'weight_lb':float(np.dot(areas,self.prepared.lengths)*self.model.density),'analysis_status':'failed',
               'feasible':False,'members':[],'error':str(exc),'external_validation':'pending'}
        except Exception:
            # SAP errors are not replaced by FEM or artificial physical values.
            self.failures+=1;raise
        self.cache[key]=r
        if len(self.cache)>2048:self.cache.popitem(last=False)
        improved=r['feasible'] and (self.best is None or r['weight_lb']<self.best[1]['weight_lb'])
        if improved:self.best=(x.copy(),r);self.best_evaluation=self.evaluations
        if r['analysis_status']=='solved':
            margins=self.margins_from_result(r)
            excess=np.maximum(-margins-1e-6,0.)
            r['constraint_violation']=float(np.dot(excess,excess))
        else:r['constraint_violation']=None
        item={'evaluations':self.evaluations,'requests':self.requests,'cache_hits':self.cache_hits,
            'phase':self.phase,'iteration':self.iteration,'weight_lb':r['weight_lb'],'feasible':r['feasible'],
            'analysis_status':r['analysis_status'],'constraint_violation':r['constraint_violation'],
            'best_feasible_lb':None if self.best is None else self.best[1]['weight_lb'],
            'elapsed_seconds':time.perf_counter()-self.started,'variables_in2':x.tolist(),'areas_in2':areas.tolist(),
            'stress_ratio':r.get('stress_ratio'),'displacement_ratio':r.get('displacement_ratio'),
            'external_validation':r['external_validation'],**(metadata or {})}
        if r['analysis_status']=='solved':
            item['axial_kip']=[m['force'] for m in r['members']];item['stress_ksi']=[m['stress'] for m in r['members']]
            item['displacements_in']=r['displacements'];item['reactions_kip']=r['reactions']
        else:item['error']=r['error']
        self.history.append(item);self.stream.write(json.dumps(item,allow_nan=False)+'\n')
        now=time.perf_counter()
        if self.progress and (now-self.last_emit>=.1 or len(self.history)==1):self.progress(item);self.last_emit=now
        return r

    def margins_from_result(self,r):
        if r['analysis_status']!='solved':return np.full(self.constraint_count,-1e6)  # Algorithm penalty, not structural results.
        return np.r_[[1-m['ratio'] for m in r['members']],
            [1-abs(r['displacements'][str(n.id)][d])/self.model.displacement_limit for n in self.model.nodes for d in range(3) if not n.fixed[d]]]

    def margins(self,x,limit=None):return self.margins_from_result(self.evaluate(x,limit=limit))
    def metrics(self):
        return {'evaluations':self.evaluations,'budget':self.budget,'requests':self.requests,'cache_hits':self.cache_hits,'budget_rejections':self.budget_rejections,
            'failed_analyses':self.failures,'fem_evaluations':self.fem_evaluations,'sap_evaluations':self.sap_evaluations,
            'independent_fem_audits':self.audit_evaluations,'best_evaluation':self.best_evaluation,
            'feasible_candidates':sum(h['feasible'] for h in self.history),'elapsed_seconds':time.perf_counter()-self.started}
