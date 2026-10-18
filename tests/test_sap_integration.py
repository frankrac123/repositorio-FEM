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


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('TRUSSLAB_RUN_SAP_INTEGRATION')!='1',reason='Requires explicit opt-in to open real SAP2000')
def test_real_visible_update_and_automatic_are_independent(tmp_path):
    manager=VisibleSapSessions()
    try:
        model=benchmark()
        first=manager.open(model,tmp_path).result(timeout=240)
        assert first['input_audit']['node_count']==6
        assert first['input_audit']['member_count']==10
        assert first['validation']['passed']
        assert first['analysis_case_status']['CASE_I']==4
        path=Path(first['sap_model'])
        original=hashlib.sha256(path.read_bytes()).hexdigest()
        changed=model.clone()
        changed.members[0].area=30.
        changed.node(4).load[2]=-95.
        changed.node(1).xyz[0]+=10
        second=manager.open(changed,tmp_path,previous_id=first['session']['id']).result(timeout=240)
        assert second['validation']['passed']
        assert second['model_fingerprint']==changed.fingerprint()
        assert second['analysis_case_status']['CASE_I']==4
        assert second['sap_model']!=first['sap_model']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==original
        assert manager.inspect(first['session']['id']).result(timeout=30)['visible']
        automatic=analyze(changed,tmp_path)
        assert automatic['mode']=='automatic' and automatic['analysis_case_status']['CASE_I']==4
        assert manager.inspect(second['session']['id']).result(timeout=30)['visible']
    finally:
        assert manager.shutdown(timeout=10)
