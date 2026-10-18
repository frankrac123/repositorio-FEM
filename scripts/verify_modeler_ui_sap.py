import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from trusslab.ui import MainWindow
from trusslab.examples import triangle
from trusslab.widgets import STYLE
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
w=MainWindow();errors=[];w.error=errors.append;w.laboratory.error=errors.append
m=triangle();m.optimization_config['load_cases']=['C1','C2','ULS'];w.set_document(m);w.showMaximized();QTest.qWait(300)
lab=w.laboratory;w.main_tabs.setCurrentIndex(1)
lab.parameters['asam']['initial_points']=10;lab.parameters['slsqp_starts']=2
lab.budget.setCurrentText('180');lab.runs.setValue(1);lab.seeds.setText('42');lab.validation.setCurrentIndex(lab.validation.findData('none'))
fingerprint=w.model.fingerprint();QTest.mouseClick(lab.start,Qt.LeftButton)
deadline=time.monotonic()+120
while lab.running and time.monotonic()<deadline:QTest.qWait(100)
assert not lab.running and not errors,errors
assert lab.campaign['status']=='completed' and len(lab.campaign['runs'])==3
assert all(r['status']=='feasible' and set(r['result']['case_results'])=={'C1','C2','ULS'} for r in lab.campaign['runs'])
assert w.model.fingerprint()==fingerprint
lab.table.selectRow(2);lab.use_winner();assert w.result['feasible'];w.scene.load_pattern=None;w.select('member',1);QTest.qWait(100)
Path('data/modeler').mkdir(exist_ok=True)
w.grab().save('data/modeler/laboratory_winner.png')
# Real UI button opens a controlled visible copy for manual inspection.
assert w.history and all('weight_lb' in row for row in w.history)
if '--skip-sap' in sys.argv:
    Path('data/modeler/qt_laboratory.json').write_text(json.dumps({'passed':True,'campaign':lab.campaign['_directory'],'methods':[r['algorithm'] for r in lab.campaign['runs']],'history_rows':len(w.history)},indent=2),encoding='utf-8')
    w.dirty=False;w.close();app.processEvents();print('PASSED QT LABORATORY + HISTORY',flush=True);raise SystemExit(0)
print('OPEN VISIBLE SAP FROM QT BUTTON',flush=True)
QTest.mouseClick(w.open_sap_button,Qt.LeftButton)
deadline=time.monotonic()+180
while w.job and time.monotonic()<deadline:QTest.qWait(100)
assert w.job is None and not errors,errors
assert w.result['engine'].startswith('SAP2000') and w.result['validation']['passed'] and w.result['feasible']
status=w.sap_sessions.inspect(w.sap_session_id).result(timeout=30)
assert status['visible'] and status['analysis_locked']
proof={'passed':True,'campaign':lab.campaign['_directory'],'methods':[r['algorithm'] for r in lab.campaign['runs']],
 'visible_session':status,'sap_model':w.result['sap_model'],'model_fingerprint':w.model.fingerprint(),'validation':w.result['validation']}
if '--audit-update' in sys.argv:
    import hashlib
    first_path=Path(w.result['sap_model']);first_hash=hashlib.sha256(first_path.read_bytes()).hexdigest()
    w.edit(lambda:setattr(w.model.members[0],'area',w.model.members[0].area*1.1))
    if hasattr(w,'comparison_dialog'):w.comparison_dialog.close()
    w.update_in_sap();deadline=time.monotonic()+180
    while w.job and time.monotonic()<deadline:QTest.qWait(100)
    assert w.job is None and not errors,errors
    assert w.result['validation']['passed'] and w.result['model_fingerprint']==w.model.fingerprint()
    assert w.result['sap_model']!=str(first_path) and hashlib.sha256(first_path.read_bytes()).hexdigest()==first_hash
    proof['update']={'passed':True,'result':w.result,'original_sdb_unchanged':True}
Path('data/modeler/qt_laboratory_sap.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
if hasattr(w,'comparison_dialog'):w.comparison_dialog.close()
w.dirty=False;w.close();app.processEvents()
print('PASSED QT LABORATORY + VISIBLE SAP (left open)',flush=True)
