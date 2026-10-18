r"""Opt-in real SAP integration: explicitly starts visible SAP instances.

Run only on an interactive Windows installation with SAP available:
    $env:TRUSSLAB_RUN_SAP_INTEGRATION='1'
    .\.venv\Scripts\python.exe -m pytest tests/test_sap_integration.py -q
Visible copies deliberately remain open for manual inspection.
"""
import hashlib
import os
from pathlib import Path
import pytest
from trusslab.core import benchmark
from trusslab.sap import VisibleSapSessions,analyze

def wait_com(future,timeout):
    """An STA caller must pump COM/Qt messages while waiting on the SAP STA.

    The desktop already does this in its event loop. Future.result() on the
    pytest main STA can block Helper.CreateObject after a previous COM test.
    """
    import time
    from trusslab.sap import pump_sta_messages
    deadline=time.monotonic()+timeout
    while not future.done() and time.monotonic()<deadline:
        pump_sta_messages();time.sleep(.01)
        try:
            from PySide6.QtCore import QCoreApplication
            app=QCoreApplication.instance()
            if app:app.processEvents()
        except ImportError:pass
    return future.result(timeout=0)


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('TRUSSLAB_RUN_SAP_BATCH')!='1',reason='Opt-in real hidden persistent SAP session')
def test_real_batch_updates_sections_and_preserves_results(tmp_path):
    from trusslab.sap import SapBatchSession
    with SapBatchSession(tmp_path) as session:
        ids=[]
        for area in [35.,30.,25.]:
            model=benchmark()
            for m in model.members:m.area=area
            result=session.evaluate(model);ids.append(result['batch_session_id'])
            assert result['validation']['passed'] and result['analysis_case_status'][result['sap_analysis_case']]==4
            assert session.last_fingerprint==model.fingerprint()
            assert all(m['area']==area for m in result['members'])
        assert len(set(ids))==1
    assert session.closed and not session.refs


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('TRUSSLAB_RUN_SAP_INTEGRATION')!='1',reason='Requires explicit opt-in to open real SAP2000')
def test_real_visible_update_and_automatic_are_independent(tmp_path):
    manager=VisibleSapSessions()
    try:
        model=benchmark()
        first=wait_com(manager.open(model,tmp_path),240)
        assert first['input_audit']['node_count']==6
        assert first['input_audit']['member_count']==10
        assert first['validation']['passed']
        assert first['analysis_case_status'][first['sap_analysis_case']]==4
        path=Path(first['sap_model'])
        original=hashlib.sha256(path.read_bytes()).hexdigest()
        changed=model.clone()
        changed.members[0].area=30.
        changed.node(4).load[2]=-95.
        changed.node(1).xyz[0]+=10
        second=wait_com(manager.open(changed,tmp_path,previous_id=first['session']['id']),240)
        assert second['validation']['passed']
        assert second['model_fingerprint']==changed.fingerprint()
        assert second['analysis_case_status'][second['sap_analysis_case']]==4
        assert second['sap_model']!=first['sap_model']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==original
        assert wait_com(manager.inspect(first['session']['id']),30)['visible']
        automatic=analyze(changed,tmp_path)
        assert automatic['mode']=='automatic' and automatic['analysis_case_status'][automatic['sap_analysis_case']]==4
        assert wait_com(manager.inspect(second['session']['id']),30)['visible']
    finally:
        assert manager.shutdown(timeout=10)
