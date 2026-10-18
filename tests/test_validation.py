import copy
import math
import threading
import pytest
from trusslab.core import benchmark
from trusslab.fem import solve,compare
from trusslab.validation import validation_report
from trusslab.sap import _ManagedSession


def test_comparison_aligns_ids_and_rejects_missing_results():
    m=benchmark();fem=solve(m);sap=copy.deepcopy(fem)
    sap['members'].reverse()
    assert compare(m,fem,sap)['passed']
    sap['members'].pop()
    assert not compare(m,fem,sap)['passed']


def test_comparison_rejects_nonfinite_missing_components_and_weight():
    m=benchmark();fem=solve(m)
    for field in ['nan','missing','weight']:
        sap=copy.deepcopy(fem)
        if field=='nan':sap['members'][0]['stress']=math.nan
        elif field=='missing':sap['displacements']['1']=[]
        else:sap['weight_lb']+=1
        report=compare(m,fem,sap)
        assert not report['passed']
        assert any(not row['passed'] for row in report['rows'])


def test_relative_error_omitted_at_zero_and_mismatch_detected():
    m=benchmark();fem=solve(m);sap=copy.deepcopy(fem)
    report=compare(m,fem,sap)
    zeros=[r for r in report['rows'] if r['fem']==0]
    assert zeros and all(r['relative_error'] is None for r in zeros)
    sap['displacements']['2'][2]+=.01
    assert not compare(m,fem,sap)['passed']


def test_equilibrium_and_feasibility_are_separate_from_agreement():
    m=benchmark()
    for bar in m.members:bar.area=1
    fem=solve(m);sap=copy.deepcopy(fem)
    report=validation_report(m,fem,sap)
    assert report['passed']
    assert not report['design_feasible']
    sap['reactions']['5'][0]+=.001
    assert not validation_report(m,fem,sap)['equilibrium']['sap']['passed']


def test_input_audit_and_nonaxial_action_cannot_validate():
    m=benchmark();fem=solve(m);sap=copy.deepcopy(fem)
    sap['input_audit']={'passed':False}
    assert not validation_report(m,fem,sap)['passed']
    sap['input_audit']['passed']=True;sap['max_nonaxial_component']=.5
    assert not validation_report(m,fem,sap)['passed']


def test_fingerprint_changes_for_every_transferred_input():
    m=benchmark();initial=m.fingerprint()
    mutations=[lambda w:setattr(w.members[0],'area',20),lambda w:w.nodes[1].load.__setitem__(2,-90),
               lambda w:w.nodes[0].xyz.__setitem__(0,730),lambda w:w.nodes[0].fixed.__setitem__(0,True)]
    for mutate in mutations:
        w=m.clone();mutate(w)
        assert w.fingerprint()!=initial
    assert m.fingerprint()==initial


def test_managed_com_references_are_confined_to_owner_thread():
    session=_ManagedSession();session.assert_owner();errors=[]
    def foreign():
        try:session.detach()
        except RuntimeError as exc:errors.append(str(exc))
    thread=threading.Thread(target=foreign);thread.start();thread.join()
    assert errors
    session.detach()
