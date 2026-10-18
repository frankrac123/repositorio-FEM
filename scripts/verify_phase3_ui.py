"""Qt/VTK integration harness; operates only windows created by this script."""
import copy,json
from pathlib import Path
from PySide6.QtWidgets import QApplication,QCheckBox
from PySide6.QtCore import QTimer
from trusslab.core import load_project,benchmark
from trusslab.results_ui import StructuralResultsDialog
from trusslab.optimization_ui import OptimizationDialog,OptimizationProgress
from trusslab.optimization import optimize,RunControl
from trusslab.asam import ASAMOptions
from trusslab.ui import MainWindow
from trusslab.widgets import STYLE

root=Path(__file__).resolve().parents[1];out=root/'data'/'phase3_ui';out.mkdir(parents=True,exist_ok=True)
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
model,result,_=load_project(root/'data'/'visible_verification'/'sap_20261017_211826_49123b'/'transferred.trusslab.json')
before=copy.deepcopy(result);fingerprint=model.fingerprint()
dialog=StructuralResultsDialog(model,result);dialog.show();app.processEvents()
for check in dialog.findChildren(QCheckBox):
    if check.text() in ('Reacciones','Desplazamientos uz'):check.setChecked(True)
    if check.text()=='Cargas':check.setChecked(False);assert not dialog.scene.loads;check.setChecked(True)
for quantity in [1,2,0]:
    dialog.mode.setCurrentIndex(quantity);dialog.amplification.setValue(30+quantity)
    dialog.thickness.setValue(2.5);dialog.select('member',3);dialog.update_scene();app.processEvents()
    assert dialog.scene.result_quantity==dialog.mode.currentData()
assert result==before and model.fingerprint()==fingerprint
assert 'ksi' in dialog.selection.text() and dialog.tabs.count()==4
dialog.mode.setCurrentIndex(1);dialog.update_scene();dialog.grab().save(str(out/'resultados_sap.png'));dialog.accept()
window=MainWindow();window.history=[];window.chart.history=[];window.show();errors=[];window.error=lambda message:errors.append(message)
config=OptimizationDialog(benchmark(),window)
assert config.method.count()==3 and config.engine.count()==3
config.method.setCurrentIndex(2);assert config.asam.isEnabled()
config.grab().save(str(out/'configuracion.png'));config.deleteLater()
control=RunControl();window.optimization_progress=OptimizationProgress(control,100000,window)
window.optimization_progress.show();state={'ticks':0,'done':False,'paused_count':None,'stable':False}
def done(data):
    state['done']=True;state['result']=data[1]['optimization'];state['feasible']=data[1]['feasible']
window.start_job(lambda job:optimize(benchmark(),'ASAM',10000,42,max_evaluations=100000,
    asam_options=ASAMOptions(initial_points=20),control=control,progress=job.progress.emit,output_dir=out),done)
timer=QTimer();timer.setInterval(30)
def tick():
    state['ticks']+=1
    if state['ticks']==5:control.pause()
    if state['ticks']==12:state['paused_count']=len(window.history)
    if state['ticks']==18:
        state['stable']=len(window.history)==state['paused_count'];control.pause(False)
    if state['ticks']==28:control.cancel()
    if state['done'] and window.job is None:
        timer.stop();assert state['stable'] and state['feasible'] and state['result']['message']=='cancelled'
        assert not errors,errors
        window.grab().save(str(out/'interfaz.png'));window.dirty=False;window.close()
        (out/'verification.json').write_text(json.dumps(state,indent=2),encoding='utf-8');print(json.dumps(state));app.quit()
    elif state['ticks']>300:
        control.cancel();raise RuntimeError('Timeout Qt harness')
timer.timeout.connect(tick);timer.start();app.exec()
