import numpy as np
import pytest
from trusslab.asam import ASAMOptions,acceptance_probability,preliminary_points,reflect_into_bounds,run_asam
from trusslab.core import benchmark
from trusslab.fem import solve
from trusslab.optimization import optimize,RunControl
from trusslab.design_space import DesignSpace


def test_logistic_rule_not_metropolis():
    assert acceptance_probability(0,1)==.5
    assert acceptance_probability(1,1)==pytest.approx(1/(1+np.e))
    assert acceptance_probability(1000,.001)==0
    assert acceptance_probability(2,.1)<acceptance_probability(2,1)<.5
    for args in [(-1,1),(1,0),(float('nan'),1)]:
        with pytest.raises(ValueError):acceptance_probability(*args)


def test_uniform_preliminary_reflection_and_seed():
    lower=np.array([.1,.2]);upper=np.array([35.,40.])
    x=preliminary_points(np.random.default_rng(9),10000,lower,upper)
    assert np.all(x>=lower) and np.all(x<=upper)
    assert np.mean(x,axis=0)==pytest.approx((lower+upper)/2,abs=.3)
    assert np.array_equal(x,preliminary_points(np.random.default_rng(9),10000,lower,upper))
    reflected=reflect_into_bounds(np.array([-400.,700.]),lower,upper)
    assert np.all(reflected>=lower) and np.all(reflected<=upper)


def test_asam_three_mechanisms_and_feasible_priority():
    trace=[]
    def evaluate(x,meta):
        trace.append((x.copy(),meta.copy()))
        # Infeasible values have a deceptively smaller objective.
        feasible=x[0]>=.5
        return {'feasible':feasible,'weight_lb':float(x[0]),'members':[{'ratio':1 if feasible else 2}], 'displacement_ratio':0}
    options=ASAMOptions(initial_points=10,proposals_per_temperature=4,radius_initial=.5,radius_reduction=.5,cooling=.8)
    run_asam(evaluate,np.array([.1]),np.array([1.]),options,3,42,1.)
    assert len(trace)==22
    assert all(t[1]['phase']=='preliminary' for t in trace[:10])
    assert [trace[i][1]['radius'] for i in [10,14,18]]==[.5,.25,.125]
    assert [trace[i][1]['temperature'] for i in [10,14,18]]==pytest.approx([.05,.04,.032])
    assert all(.1<=t[0][0]<=1 for t in trace)


def test_groups_and_fixed_members():
    m=benchmark();space=DesignSpace(m,active_ids=[1,2,3],groups=[[1,2]])
    candidate=space.expand([12,15])
    assert [b.area for b in candidate.members[:4]]==[12,12,15,35]
    assert all(b.area==35 for b in m.members)
    with pytest.raises(ValueError):DesignSpace(m,groups=[[1,2],[2,3]])


def test_asam_budget_seed_and_best_is_genuinely_feasible():
    opts=ASAMOptions(initial_points=30,proposals_per_temperature=10)
    runs=[optimize(benchmark(),'ASAM',20,17,max_evaluations=150,asam_options=opts) for _ in range(2)]
    a,r,h=runs[0];b,s,j=runs[1]
    assert [m.area for m in a.members]==[m.area for m in b.members]
    assert [(i['weight_lb'],i['feasible']) for i in h]==[(i['weight_lb'],i['feasible']) for i in j]
    assert len(h)==r['optimization']['evaluations']<=150
    assert r['optimization']['message']=='max_evaluations'
    assert r['feasible'] and solve(a)['feasible']
    best=[i['best_feasible_lb'] for i in h if i['best_feasible_lb'] is not None]
    assert all(y<=x for x,y in zip(best,best[1:]))


def test_controlled_cancel_keeps_best_and_input():
    model=benchmark();control=RunControl();seen=[]
    def progress(item):
        if isinstance(item,dict):
            seen.append(item)
            if item['evaluations']==8:control.cancel()
    candidate,result,history=optimize(model,max_evaluations=50,control=control,progress=progress)
    assert len(history)==8 and result['optimization']['message']=='cancelled'
    assert solve(candidate)['feasible'] and all(b.area==35 for b in model.members)


def test_pause_can_be_cancelled_safely():
    import threading,time
    from trusslab.optimization import Cancelled
    c=RunControl();c.pause();done=[]
    def worker():
        try:c.checkpoint()
        except Cancelled:done.append(True)
    thread=threading.Thread(target=worker);thread.start();time.sleep(.06)
    assert thread.is_alive();c.cancel();thread.join(1)
    assert done==[True]


def test_hybrid_provenance_lifecycle_and_no_fallback(tmp_path):
    # Test double only; real SAP has a separate opt-in integration test.
    created=[]
    class Batch:
        def __init__(self,path):created.append(self);self.count=0;self.closed=False
        def __enter__(self):return self
        def __exit__(self,*args):self.closed=True
        def evaluate(self,m):
            self.count+=1;self.last_fingerprint=m.fingerprint()
            r=solve(m);r['engine']='SAP2000 TEST DOUBLE';return r
    m,r,h=optimize(benchmark(),iterations=2,engine='HYBRID',max_evaluations=80,
        hybrid_validations=2,output_dir=tmp_path,batch_factory=Batch)
    assert len(created)==1 and created[0].closed and 2<=created[0].count<=3
    assert created[0].last_fingerprint==m.fingerprint() and r['sap_file_matches_result']
    assert r['external_validation']=='verified' and 2<=r['optimization']['sap_evaluations']<=3
    assert any(i['external_validation']=='pending' for i in h)
    assert r['optimization']['evaluations']<=80
    class Broken(Batch):
        def evaluate(self,m):raise RuntimeError('SAP unavailable')
    with pytest.raises(RuntimeError,match='SAP unavailable'):
        optimize(benchmark(),engine='SAP',output_dir=tmp_path,batch_factory=Broken)
    assert created[-1].closed


def test_cancelled_hybrid_never_claims_external_validation(tmp_path):
    control=RunControl()
    def progress(item):
        if isinstance(item,dict) and item['evaluations']==5:control.cancel()
    class Forbidden:
        def __init__(self,path):raise AssertionError('SAP must not start after cancellation')
    model,result,history=optimize(benchmark(),engine='HYBRID',control=control,
        progress=progress,output_dir=tmp_path,batch_factory=Forbidden)
    assert result['external_validation']=='pending'
    assert result['optimization']['message']=='cancelled' and result['optimization']['sap_evaluations']==0


def test_no_feasible_candidate_is_never_reported_as_optimum(tmp_path):
    m=benchmark();m.displacement_limit=1e-10
    with pytest.raises(ValueError,match='No se encontró un diseño factible'):
        optimize(m,'ASAM',2,42,max_evaluations=30,asam_options=ASAMOptions(initial_points=10),output_dir=tmp_path)
    assert not list(tmp_path.rglob('best.trusslab.json'))
    assert all(b.area==35 for b in m.members)


def test_sap_winner_restoration_is_counted_within_budget(tmp_path):
    instances=[]
    class Batch:
        def __init__(self,path):instances.append(self);self.calls=0
        def __enter__(self):return self
        def __exit__(self,*exc):self.closed=True
        def evaluate(self,m):
            self.calls+=1;self.last_fingerprint=m.fingerprint()
            r=solve(m);r['engine']='SAP2000 TEST DOUBLE';return r
    m,r,h=optimize(benchmark(),engine='SAP',max_evaluations=4,output_dir=tmp_path,batch_factory=Batch)
    assert instances[0].calls==4 and instances[0].closed
    assert r['optimization']['evaluations']==4 and h[-1]['phase']=='restore_winner'
    assert r['sap_file_matches_result'] and instances[0].last_fingerprint==m.fingerprint()
