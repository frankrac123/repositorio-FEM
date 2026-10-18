"""Lifecycle unit tests only. These do not claim a real SAP analysis."""
import threading
import sys
import types
import pytest
from trusslab.core import benchmark
from trusslab import sap


@pytest.fixture
def fake_com_runtime(monkeypatch):
    """Queue tests exercise real threading with a scoped COM runtime double.

    This keeps unit tests independent of Windows/comtypes. Opt-in integration
    tests in test_sap_integration.py still use the real COM implementation.
    """
    runtime=types.ModuleType('comtypes');client=types.ModuleType('comtypes.client')
    runtime.COINIT_APARTMENTTHREADED=2
    runtime.CoInitializeEx=lambda mode:None
    runtime.CoUninitialize=lambda:None
    client.PumpEvents=lambda timeout:None
    monkeypatch.setattr(sap,'pump_sta_messages',lambda:None)
    runtime.client=client
    monkeypatch.setitem(sys.modules,'comtypes',runtime)
    monkeypatch.setitem(sys.modules,'comtypes.client',client)


def test_visible_queue_serializes_and_copies_snapshots(monkeypatch,tmp_path,fake_com_runtime):
    calls=[];threads=[];gate=threading.Event()
    def fake_analysis(model,root,visible=False,progress=None,*,_session=None):
        _session.assert_owner();threads.append(threading.get_ident())
        if not calls:gate.wait(2)
        calls.append((model.members[0].area,visible,_session.previous_id))
        return {'session_id':_session.id,'area':model.members[0].area}
    monkeypatch.setattr(sap,'analyze',fake_analysis)
    manager=sap.VisibleSapSessions();model=benchmark()
    a=manager.open(model,tmp_path);model.members[0].area=20
    b=manager.open(model,tmp_path,previous_id='previous-id');model.members[0].area=10
    gate.set()
    assert a.result(timeout=5)['area']==35
    assert b.result(timeout=5)['area']==20
    assert calls==[(35,True,None),(20,True,'previous-id')]
    assert len(set(threads))==1 and threads[0]!=threading.get_ident()
    assert manager.shutdown()


def test_failed_visible_operation_keeps_references_until_shutdown(monkeypatch,tmp_path,fake_com_runtime):
    retained=[];detached=[]
    class Ref:
        def __del__(self):detached.append(threading.get_ident())
    def fake_analysis(model,root,visible=False,progress=None,*,_session=None):
        _session.refs={'app':Ref()};retained.append(_session)
        raise sap.SapError('analysis failure')
    monkeypatch.setattr(sap,'analyze',fake_analysis)
    manager=sap.VisibleSapSessions()
    with pytest.raises(sap.SapError,match='analysis failure'):
        manager.open(benchmark(),tmp_path).result(timeout=5)
    assert retained[0].refs and not detached
    owner=retained[0].owner
    assert manager.shutdown()
    assert not retained[0].refs and detached==[owner]


def test_batch_closes_only_its_owned_reference(tmp_path):
    calls=[]
    class OwnApp:
        def ApplicationExit(self,save):calls.append(save);return 0
    session=sap.SapBatchSession(tmp_path);session.refs={'app':OwnApp()}
    session.__exit__(None,None,None)
    assert calls==[False] and session.closed and not session.refs
