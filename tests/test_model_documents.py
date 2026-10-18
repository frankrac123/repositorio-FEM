import json
import numpy as np
import pytest
from trusslab.core import Model,Node,Member,benchmark,save_project,load_project
from trusslab.editor_commands import create_node,create_member,delete_entities,copy_entities
from trusslab.examples import triangle,spatial
from trusslab.fem import solve,compare
from trusslab.analysis import solve_design,constraint_margins,project_state
from trusslab.prepared_fem import PreparedTruss
from trusslab.design_space import DesignSpace
from trusslab.validation import equilibrium

def test_empty_and_isolated_documents_round_trip(tmp_path):
    m=Model.empty('3D');m.validate_integrity()
    for xyz in ([0,0,0],[100,0,0],[0,100,0],[10,20,100]):create_node(m,xyz)
    assert all(n.fixed==[False]*3 for n in m.nodes)
    m.validate_integrity()
    with pytest.raises(ValueError,match='No hay barras'):solve(m)
    path=tmp_path/'draft.json';save_project(path,m);copy,r,h=load_project(path)
    assert copy.to_dict()==m.to_dict() and r is None
    assert project_state(m)=='BORRADOR / MODELADO'

def test_connectivity_and_copy_delete_commands():
    m=Model.empty();create_node(m,[0,0,0]);create_node(m,[100,0,0]);create_member(m,1,2)
    m.validate_integrity();created=copy_entities(m,{('member',1)},[0,50,0]);m.validate_integrity()
    assert len(m.nodes)==4 and len(m.members)==2
    delete_entities(m,{('node',3)});m.validate_integrity();assert len(m.members)==1
    for start,end in [(1,1),(1,99),(2,1)]:
        candidate=m.clone()
        with pytest.raises(ValueError):create_member(candidate,start,end);candidate.validate_integrity()

@pytest.mark.parametrize('plane,normal',[('XZ',1),('XY',2),('YZ',0)])
def test_explicit_plane_not_coordinate_based_support(plane,normal):
    m=Model.empty('2D',plane);axes=[a for a in range(3) if a!=normal]
    end=[0.,0.,0.];end[axes[0]]=100
    fixed=[True]*3;fixed[axes[0]]=False;fixed[normal]=False
    m.nodes=[Node(1,[0.,0.,0.],[True]*3),Node(2,end,fixed)]
    create_member(m,1,2,2.)
    force=[0.,0.,0.];force[axes[0]]=10.;m.set_nodal_load(2,'LC1',force)
    r=solve(m)
    assert r['displacements']['2'][axes[0]]==pytest.approx(10*100/(29000*2))
    assert m.node(2).fixed[normal] is False and m.restraints(m.node(2))[normal] is True
    m.structure_type='3D'
    with pytest.raises(ValueError,match='inestable'):solve(m)

@pytest.mark.parametrize('factory',[triangle,spatial])
def test_materials_patterns_cases_and_prepared_solver(factory):
    m=factory();m.optimization_config['load_cases']=['C1','C2','ULS']
    r=solve_design(m);p=PreparedTruss(m).solve([b.area for b in m.members])
    assert set(r['case_results'])=={'C1','C2','ULS'}
    for case in r['case_results']:
        a,b=r['case_results'][case],p['case_results'][case]
        assert compare(m,a,b)['passed'] and equilibrium(m,a)['passed']
    assert r['feasible']==all(case['feasible'] for case in r['case_results'].values())
    assert len(constraint_margins(m,r))==3*(len(m.members)+sum(not f for n in m.nodes for f in m.restraints(n)))
    assert p['weight_lb']==pytest.approx(m.weight())
    other=m.clone();other.members[0].material_id='M2'
    assert solve(other)['displacements']!=solve(m)['displacements']

def test_case_violation_cannot_be_hidden_by_active_case():
    m=triangle();m.load_patterns[1].nodal_loads['3']=[400.,0.,-200.]
    m.optimization_config['load_cases']=['C1','C2']
    assert solve(m)['feasible']
    r=solve_design(m)
    assert not r['feasible'] and min(constraint_margins(m,r))<0
    assert r['analysis_case']=='C1' and r['case_results']['C2']['stress_ratio']>1

def test_group_variables_follow_document_and_legacy_migration(tmp_path):
    m=triangle();space=DesignSpace(m)
    assert space.groups==[[1],[2,3]] and len(space.initial)==2
    legacy=json.loads((__import__('pathlib').Path(__file__).parents[1]/'examples/Caso_I_calculado.trusslab.json').read_text(encoding='utf-8-sig'))
    path=tmp_path/'old.json';path.write_text(json.dumps(legacy),encoding='utf-8')
    model,r,_=load_project(path)
    assert r and compare(model,solve(model),r)['passed']
    assert r['weight_lb']==pytest.approx(5060.855730008,rel=1e-8)
    save_project(tmp_path/'new.json',model,r)
    reread,result,_=load_project(tmp_path/'new.json');assert reread.to_dict()==model.to_dict() and result is not None
