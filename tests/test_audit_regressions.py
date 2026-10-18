import pytest
import numpy as np
from trusslab.examples import triangle
from trusslab.fem import solve
from trusslab.prepared_fem import PreparedTruss
from trusslab.core import Material,save_project,load_project
from trusslab.sap_mapping import transfer_definition

def test_prepared_rejects_unknown_case():
    m=triangle()
    with pytest.raises(ValueError):PreparedTruss(m).solve_case([b.area for b in m.members],'missing')

def test_fixed_member_outside_design_bounds_is_analyzable():
    m=triangle();m.members[0].area=50.
    a=solve(m);b=PreparedTruss(m).solve_case([x.area for x in m.members],m.active_case)
    assert np.allclose(a['displacements']['3'],b['displacements']['3'])

def test_explicit_case_independent_of_active_case():
    m=triangle();m.load_patterns[0].nodal_loads['3'][1]=1.
    solve(m,case='C2')

def test_deleted_patterns_do_not_resurrect_legacy_loads():
    m=triangle();m.set_nodal_load(3,'LC1',[0.,0.,-13.]);m.load_patterns=[];m.analysis_cases=[]
    assert not any(any(v) for v in m.nodal_loads().values())

def test_sap_global_material_and_explicit_legacy_are_distinct():
    m=triangle();m.members[0].material_id=None
    m.materials.append(Material('legacy','Different',12345.,.12));m.members[1].material_id='legacy'
    mapping,materials,_,_=transfer_definition(m)
    assert len(materials)==3
    assert len(set(mapping['materials'].values()))==3

def test_stale_save_discards_history(tmp_path):
    m=triangle();r=solve(m);m.members[0].area*=2
    p=tmp_path/'stale.json';save_project(p,m,r,[{'old':True}])
    _,r,h=load_project(p)
    assert r is None and h==[]

def test_units_self_weight_and_closed_form():
    from trusslab.units import lb_to_kip,kip_to_lb
    from trusslab.core import Model,Node,Member,LoadPattern,AnalysisCase
    assert kip_to_lb(lb_to_kip(283.))==pytest.approx(283.)
    m=Model('vertical',[Node(1,[0.,0.,0.],[True]*3),Node(2,[0.,0.,100.],[True,True,False])],[Member(1,1,2,2.)],elastic_modulus=20000.,density=.25)
    m.load_storage='patterns';m.load_patterns=[LoadPattern('D','Dead',self_weight=1.)];m.analysis_cases=[AnalysisCase('C','C',{'D':1.})];m.active_case='C'
    r=solve(m)
    assert r['weight_lb']==pytest.approx(50.)
    assert r['reactions']['1'][2]==pytest.approx(.05)
    assert r['displacements']['2'][2]==pytest.approx(-.025*100/(20000*2))
    areas=[4.];p=PreparedTruss(m).solve_case(areas,'C')
    assert p['weight_lb']==pytest.approx(100.)
    assert p['displacements']['2'][2]==pytest.approx(r['displacements']['2'][2])

def test_cache_with_matching_fingerprint_but_corrupt_values_rejected(tmp_path):
    import json
    m=triangle();r=solve(m);p=tmp_path/'corrupt.json';save_project(p,m,r,[{'old':True}])
    d=json.loads(p.read_text(encoding="utf-8"));d['results']['displacements']['3'][2]+=1.;p.write_text(json.dumps(d))
    with pytest.warns(RuntimeWarning):_,r,h=load_project(p)
    assert r is None and not h

def test_multiple_cases_include_governing_nonactive_case():
    from trusslab.analysis import solve_design,constraint_margins
    m=triangle();m.optimization_config['load_cases']=['C1','C2','ULS']
    r=solve_design(m)
    assert set(r['case_results'])=={'C1','C2','ULS'}
    assert r['stress_ratio']==max(x['stress_ratio'] for x in r['case_results'].values())
    assert len(constraint_margins(m,r))==3*(3+3)

def test_fully_restrained_truss_has_zero_motion_and_balanced_reactions():
    m=triangle()
    for n in m.nodes:n.fixed=[True]*3
    r=solve(m)
    assert r['displacement_ratio']==0 and all(u==[0.,0.,0.] for u in r['displacements'].values())
    assert all(b['force']==0 for b in r['members']) and r['equilibrium']['passed']

def test_campaign_retains_best_on_later_failure(tmp_path,monkeypatch):
    import trusslab.laboratory as lab
    def failure(ev,*args):
        ev.evaluate(ev.space.initial)
        raise RuntimeError('deliberate audit failure')
    monkeypatch.setattr(lab,'search',failure)
    m=triangle();c=lab.CampaignConfig(algorithms=['SLSQP'],seeds=[42],budget=110,sap_validation='none')
    result=lab.run_campaign(m,c,tmp_path)
    record=result['runs'][0]
    assert record['status']=='failed' and record['best_before_failure']['result']['feasible']
    assert ( __import__('pathlib').Path(result['_directory'])/'runs'/record['id']/'best_before_failure.trusslab.json').exists()

def test_runtime_counts_failure_and_retains_best(tmp_path,monkeypatch):
    import trusslab.optimization_runtime as runtime
    original=runtime.solve;calls=0
    def fail_after_first(model):
        nonlocal calls
        calls+=1
        if calls>1:raise RuntimeError('deliberate analysis failure')
        return original(model)
    monkeypatch.setattr(runtime,'solve',fail_after_first)
    with pytest.raises(RuntimeError):runtime.optimize(triangle(),output_dir=tmp_path)
    directory=next(tmp_path.iterdir())
    import json
    d=json.loads((directory/'termination.json').read_text())
    assert d['status']=='failed' and d['evaluations']==2 and d['best_feasible_lb']>0
    assert (directory/'best_before_failure.trusslab.json').exists()

def test_copy_retains_global_material_and_individual_section():
    from trusslab.editor_commands import copy_entities
    m=triangle();b=m.members[0];b.material_id=None;b.section_id=None
    copy_entities(m,{('member',b.id)},[0.,0.,200.])
    copied=m.members[-1]
    assert copied.material_id is None and copied.section_id is None and copied.area==b.area
    assert m.member_material(copied).elastic_modulus==m.elastic_modulus

def test_corrupt_multicase_envelope_rejected(tmp_path):
    import json
    from trusslab.analysis import solve_design
    m=triangle();m.optimization_config['load_cases']=['C1','C2','ULS']
    p=tmp_path/'envelope.json';save_project(p,m,solve_design(m))
    d=json.loads(p.read_text(encoding='utf-8'));d['results']['stress_ratio']=99.;p.write_text(json.dumps(d))
    with pytest.warns(RuntimeWarning):_,r,h=load_project(p)
    assert r is None and not h

def test_overflow_of_finite_load_factors_is_not_a_solution():
    m=triangle()
    for n in m.nodes:n.fixed=[True]*3
    m.load_patterns[0].nodal_loads['3'][2]=-1e308
    m.analysis_cases[0].factors={'LC1':1e308}
    with np.errstate(over='ignore',invalid='ignore'):
        with pytest.raises(ValueError,match='finita'):solve(m)
