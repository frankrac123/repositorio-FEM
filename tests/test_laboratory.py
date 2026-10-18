import copy,gzip,json
from dataclasses import asdict
import numpy as np
import pytest
from trusslab.core import benchmark,Model,Node,Member
from trusslab.fem import solve,compare
from trusslab.prepared_fem import PreparedTruss
from trusslab.asam import ASAMOptions,quality
from trusslab.lab_evaluation import EvaluationSession,BudgetReached
from trusslab.laboratory import CampaignConfig,run_campaign,load_campaign,statistics
from trusslab.optimization import RunControl


def configuration(methods=None,seeds=None,budget=240):
    c=CampaignConfig(algorithms=methods or ['ASAM','DE','SLSQP'],seeds=seeds or [42],budget=budget,sap_validation='none')
    c.parameters['asam']=asdict(ASAMOptions(initial_points=20,proposals_per_temperature=10))
    return c


def test_prepared_fem_matches_independent_solver_for_varied_areas_and_space():
    spatial=Model('Tetraedro',[Node(1,[0,0,0],[True]*3),Node(2,[120,0,0],[True]*3),Node(3,[0,120,0],[True]*3),
        Node(4,[30,40,120],[False]*3,[5,-3,-20])],[Member(1,1,4,3),Member(2,2,4,4),Member(3,3,4,5)])
    rng=np.random.default_rng(17)
    for model in [benchmark(),spatial]:
        prepared=PreparedTruss(model)
        for _ in range(15):
            areas=rng.uniform(.1,35,len(model.members));candidate=model.clone()
            for b,a in zip(candidate.members,areas):b.area=float(a)
            reference=solve(candidate);actual=prepared.solve(areas)
            assert compare(candidate,reference,actual)['passed']
            assert actual['feasible']==reference['feasible'] and actual['equilibrium']['passed']


def test_real_evaluation_budget_and_cache_are_separate(tmp_path):
    ev=EvaluationSession(benchmark(),2,tmp_path/'trace.gz')
    try:
        a=np.full(10,35.);ev.evaluate(a);ev.evaluate(a)
        assert ev.evaluations==1 and ev.requests==2 and ev.cache_hits==1
        ev.evaluate(np.full(10,30.));ev.evaluate(a)
        with pytest.raises(BudgetReached):ev.evaluate(np.full(10,29.))
        assert ev.evaluations==2 and ev.cache_hits==2
    finally:ev.close()
    with gzip.open(tmp_path/'trace.gz','rt') as stream:assert len(list(stream))==2


def test_failed_analysis_is_not_an_infeasible_physical_solution(tmp_path):
    model=benchmark();model.nodes[0].fixed[1]=False
    ev=EvaluationSession(model,3,tmp_path/'trace.gz')
    try:
        r=ev.evaluate(np.full(10,20.))
        assert r['analysis_status']=='failed' and not r['feasible'] and not r['members']
        assert ev.best is None and ev.failures==1 and quality(r,1)[0]==2
    finally:ev.close()


def test_campaign_equal_limits_common_pool_persistence_and_original_unchanged(tmp_path):
    model=benchmark();fingerprint=model.fingerprint();c=run_campaign(model,configuration(),tmp_path)
    assert model.fingerprint()==fingerprint and c['status']=='completed'
    assert len(c['runs'])==3 and len({r['search']['initial_population_sha256'] for r in c['runs']})==1
    assert all(20<=r['metrics']['evaluations']<=240 for r in c['runs'])
    assert all(r['metrics']['cache_hits']>0 for r in c['runs'])
    assert all(r['sap_validation']['status']=='pending' for r in c['runs'])
    loaded=load_campaign(c['_directory']);assert loaded['model_fingerprint']==fingerprint
    assert loaded['runs']==c['runs']
    payload=json.loads((__import__('pathlib').Path(c['_directory'])/'campaign.json').read_text(encoding='utf-8'))
    payload['model']['stress_limit']=20
    path=tmp_path/'changed.json';path.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='huella'):load_campaign(path)


def test_same_seed_reproduces_all_algorithms(tmp_path):
    a=run_campaign(benchmark(),configuration(),tmp_path);b=run_campaign(benchmark(),configuration(),tmp_path)
    assert [r.get('areas_in2') for r in a['runs']]==[r.get('areas_in2') for r in b['runs']]
    assert [r['metrics']['evaluations'] for r in a['runs']]==[r['metrics']['evaluations'] for r in b['runs']]


def test_campaign_cancellation_is_saved_without_modifying_model(tmp_path):
    control=RunControl();model=benchmark()
    def progress(item):
        if item['type']=='evaluation':control.cancel()
    c=run_campaign(model,configuration(),tmp_path,control=control,progress=progress)
    assert c['status']=='cancelled' and len(c['runs'])==1 and c['runs'][0]['status']=='cancelled'
    assert load_campaign(c['_directory'])['status']=='cancelled' and all(b.area==35 for b in model.members)


def test_statistics_exclude_infeasible_and_cancelled_weights():
    def record(weight,status):return {'algorithm':'ASAM','status':status,'result':{'weight_lb':weight},
        'metrics':{'elapsed_seconds':2,'best_evaluation':10,'failed_analyses':0}}
    r=statistics([record(100,'feasible'),record(200,'feasible'),record(1,'infeasible'),record(2,'cancelled')],['ASAM'])[0]
    assert r['n_valid']==2 and r['n_completed']==3 and r['mean_lb']==150 and r['median_lb']==150
    assert r['sample_std_lb']==pytest.approx(50*2**.5) and r['feasibility_rate']==pytest.approx(2/3)
    assert r['limited_sample']
    assert statistics([record(100,'feasible')],['ASAM'])[0]['sample_std_lb'] is None
