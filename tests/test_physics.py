import json
import numpy as np
import pytest
from trusslab.core import Model,Node,Member,benchmark,save_project,load_project
from trusslab.fem import solve,compare
from trusslab.optimization import optimize


def test_axial_bar_matches_closed_form():
    m=Model('Barra', [Node(1,[0,0,0],[True]*3),Node(2,[120,0,0],[False,True,True],[15,0,0])], [Member(1,1,2,3)])
    r=solve(m)
    assert r['displacements']['2'][0]==pytest.approx(15*120/(10000*3))
    assert r['members'][0]['stress']==pytest.approx(5)
    assert r['reactions']['1'][0]==pytest.approx(-15)
    assert r['weight_lb']==pytest.approx(.1*3*120)


def test_spatial_bar_matches_axial_solution():
    a=np.array([30.,40.,120.]);d=a/np.linalg.norm(a)
    # Two free translations would be mechanisms; orient an axial bar along Z,
    # then validate a non-axis-aligned tetrahedron through a rigid rotation below.
    m=Model('Tetraedro', [Node(1,[0,0,0],[True]*3),Node(2,[120,0,0],[True]*3),Node(3,[0,120,0],[True]*3),Node(4,[30,40,120],[False]*3,[5,-3,-20])],
            [Member(1,1,4,3),Member(2,2,4,4),Member(3,3,4,5)])
    r=solve(m)
    force=sum((np.array(v) for v in r['reactions'].values()),np.zeros(3))+np.array([5,-3,-20])
    assert max(abs(force))<1e-10
    theta=.57
    R=np.array([[np.cos(theta),-np.sin(theta),0],[np.sin(theta),np.cos(theta),0],[0,0,1]])
    rotated=m.clone()
    for n in rotated.nodes:n.xyz=(R@np.array(n.xyz)).tolist();n.load=(R@np.array(n.load)).tolist()
    s=solve(rotated)
    assert np.array(s['displacements']['4'])==pytest.approx(R@np.array(r['displacements']['4']))
    assert [v['force'] for v in s['members']]==pytest.approx([v['force'] for v in r['members']])


def test_case_i_loads_supports_connectivity():
    m=benchmark()
    assert len(m.nodes)==6 and len(m.members)==10
    assert [n.id for n in m.nodes if n.load[2]==-100]==[2,4]
    assert all(n.xyz[1]==0 and n.fixed[1] for n in m.nodes)
    assert {(b.start,b.end) for b in m.members}=={(5,3),(3,1),(6,4),(4,2),(3,4),(1,2),(5,4),(6,3),(3,2),(4,1)}
    r=solve(m)
    total=np.sum(list(r['reactions'].values()),axis=0)+np.sum([n.load for n in m.nodes],axis=0)
    assert max(abs(total))<1e-10
    assert r['residual_kip']<1e-10
    moment=np.sum([np.cross(n.xyz,np.array(r['reactions'][str(n.id)])+n.load) for n in m.nodes],axis=0)
    assert max(abs(moment))<1e-8


def test_area_scaling_and_load_linearity():
    m=benchmark()
    for b in m.members:b.area=10
    a=solve(m)
    for b in m.members:b.area*=2
    b=solve(m)
    assert b['weight_lb']==pytest.approx(2*a['weight_lb'])
    assert np.array(list(b['displacements'].values()))==pytest.approx(np.array(list(a['displacements'].values()))/2)
    assert [x['force'] for x in b['members']]==pytest.approx([x['force'] for x in a['members']])
    for n in m.nodes:n.load=[2*x for x in n.load]
    c=solve(m)
    assert np.array(list(c['displacements'].values()))==pytest.approx(np.array(list(b['displacements'].values()))*2)


def test_invalid_structures_rejected():
    m=benchmark();m.members[0].end=m.members[0].start
    with pytest.raises(ValueError,match='longitud cero'):solve(m)
    m=benchmark();m.nodes[0].xyz=m.nodes[1].xyz.copy()
    with pytest.raises(ValueError,match='coincidentes'):solve(m)
    m=benchmark();m.nodes[0].fixed[1]=False
    with pytest.raises(ValueError,match='inestable'):solve(m)
    m=benchmark();m.members[0].area=float('nan')
    with pytest.raises(ValueError):solve(m)


def test_project_round_trip_and_no_prefixed_results(tmp_path):
    m=benchmark();r=solve(m)
    path=tmp_path/'project.json';save_project(path,m,r)
    n,s,h=load_project(path)
    assert n.to_dict()==m.to_dict()
    assert compare(n,solve(n),s)['passed']
    n.nodes[1].load[2]=-50
    assert not compare(n,solve(n),s)['passed']


def test_optimizer_returns_recomputed_feasible_design():
    m=benchmark()
    w,r,h=optimize(m,iterations=150)
    assert r['feasible']
    assert r['stress_ratio']<=1+1e-8 and r['displacement_ratio']<=1+1e-8
    assert r['weight_lb']<m.weight()*.5
    assert r['weight_lb']==pytest.approx(solve(w)['weight_lb'])
    assert len(h)>2 and all('evaluations' in i for i in h)
    assert all(b.area==35 for b in m.members)


def test_de_finite_candidate_and_feasibility():
    m=benchmark()
    w,r,h=optimize(m,method='DE',iterations=2,seed=123)
    assert r['feasible'] and all(np.isfinite(b.area) for b in w.members)
    assert not r['optimization']['global_optimum_proven']


def test_saved_sap_comparison_is_with_same_model():
    from pathlib import Path
    p=Path(__file__).resolve().parents[1]/'data'/'sap_case_i.trusslab.json'
    if not p.exists():pytest.skip('Integration evidence not present')
    model,r,_=load_project(p)
    assert r['engine'].startswith('SAP2000')
    assert compare(model,solve(model),r)['passed']
    assert r['max_nonaxial_component']<1e-6
