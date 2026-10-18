"""Opt-in real Windows Qt/VTK interactions; never attach to a user's window."""
import os
from pathlib import Path
import pytest
pytestmark=pytest.mark.skipif(os.environ.get('TRUSSLAB_RUN_QT')!='1',reason='Explicit desktop Qt test run required')

@pytest.fixture
def window():
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from trusslab.ui import MainWindow
    from trusslab.widgets import STYLE
    app=QApplication.instance() or QApplication([]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
    w=MainWindow();w.showMaximized();QTest.qWait(350)
    errors=[];w.error=errors.append;w.test_errors=errors
    yield w
    w.dirty=False;w.close();app.processEvents()

def type_number(field,text,confirm=False):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    field.setFocus();field.selectAll();QTest.keyClicks(field,str(text))
    if confirm:QTest.keyClick(field,Qt.Key_Return)

def test_windows_modeler_from_empty_document(window,tmp_path):
    from PySide6.QtCore import Qt,QTimer,QPoint
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QComboBox,QDialogButtonBox
    from trusslab.editor_properties import NumberEdit
    from trusslab.editor_commands import Tool
    from trusslab.core import save_project,load_project
    from trusslab.fem import solve
    w=window
    def choose_new():
        d=QApplication.activeModalWidget();d.findChild(QComboBox,'project_type').setCurrentIndex(1)
        QTest.mouseClick(d.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
    QTimer.singleShot(60,choose_new);w.new_project()
    assert w.model.structure_type=='3D' and not w.model.nodes and not w.model.members and w.result is None
    coordinates=[[0,0,0],[100,0,0],[0,75,0],[25,25,100]]
    for xyz in coordinates:
        def fill_node(xyz=xyz):
            d=QApplication.activeModalWidget()
            for axis,value in zip('xyz',xyz):type_number(d.findChild(NumberEdit,axis),value)
            QTest.mouseClick(d.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
        QTimer.singleShot(60,fill_node);w.add_node()
    assert [n.xyz for n in w.model.nodes]==coordinates and not w.model.members
    assert all(n.fixed==[False]*3 for n in w.model.nodes)
    w.select('node',4);QTest.qWait(50);field=w.property_editor.fields['xyz_X']
    assert field.lineEdit().isVisible() and field.lineEdit().width()>35 and field.lineEdit().height()>=15
    assert field.lineEdit().text()=='25.000000'
    type_number(field,'-25,75',True);QApplication.processEvents()
    assert w.model.node(4).xyz[0]==-25.75
    assert w.scene.node_positions[4][0]==-25.75
    assert w.property_editor.fields['xyz_X'] is field  # no reconstruction during commit
    w.select('node',2);w.select('node',4)
    assert w.property_editor.fields['xyz_X'].value()==-25.75
    w.scene.plotter.camera_position=[(280,-380,260),(35,25,45),(0,0,1)];w.scene.fit()
    w.tool_combo.setCurrentIndex(list(Tool).index(Tool.MEMBER))
    for base in (1,2,3):
        for id in (base,4):
            pos=w.scene.project(w.model.node(id).xyz).toPoint()
            QTest.mouseClick(w.scene.plotter.interactor,Qt.LeftButton,Qt.NoModifier,pos);QApplication.processEvents()
    assert [(b.start,b.end) for b in w.model.members]==[(1,4),(2,4),(3,4)]
    assert w.scene.member_connectivity=={1:(1,4),2:(2,4),3:(3,4)}
    w.set_tool(Tool.SELECT);w.select('node',4)
    type_number(w.property_editor.fields['load_Z'],'-10.5',True)
    assert w.model.pattern_load(4,'LC1')==[0.,0.,-10.5]
    tail,head=w.scene.load_arrows()[4]
    assert head[2]-tail[2]<0 and head[:2]==tail[:2]
    for id in (1,2,3):
        w.select('node',id);QApplication.processEvents()
        for check in w.property_editor.checks.values():
            w.property_scroll.ensureWidgetVisible(check);QApplication.processEvents()
            QTest.mouseClick(check,Qt.LeftButton,Qt.NoModifier,QPoint(8,check.height()//2))
        w.property_scroll.ensureWidgetVisible(w.property_editor.apply_button)
        QApplication.processEvents()
        QTest.mouseClick(w.property_editor.apply_button,Qt.LeftButton)
        assert w.model.node(id).fixed==[True]*3
    assert w.model.node(4).fixed==[False]*3
    assert w.result is None
    w.run_fem();assert w.result and w.result['residual_kip']<1e-8
    assert w.result['model_fingerprint']==w.model.fingerprint()
    w.select('node',4);type_number(w.property_editor.fields['xyz_Z'],'110',True)
    assert w.result is None
    w.undo();assert w.model.node(4).xyz[2]==100 and w.result is not None
    w.redo();assert w.model.node(4).xyz[2]==110 and w.result is None
    path=tmp_path/'draft.trusslab.json';save_project(path,w.model,w.result)
    before=w.model.to_dict();w.load_document(path)
    assert w.model.to_dict()==before and w.result is None
    assert not w.test_errors
    Path('data/modeler').mkdir(exist_ok=True)
    w.select('node',4);QTest.qWait(100)
    w.grab().save('data/modeler/qt_editor.png')

def test_mouse_node_creation_uses_camera_ray_and_work_plane(window):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from trusslab.editor_commands import Tool
    from trusslab.core import Model
    w=window;w.set_document(Model.empty('3D'));w.scene.set_view('Frontal')
    w.tool_combo.setCurrentIndex(list(Tool).index(Tool.NODE))
    pos=w.scene.project([25,0,25]).toPoint()
    QTest.mouseClick(w.scene.plotter.interactor,Qt.LeftButton,Qt.NoModifier,pos);QApplication.processEvents()
    assert len(w.model.nodes)==1 and w.model.node(1).xyz==pytest.approx([25,0,25])
    assert not any(w.model.node(1).fixed)
    # Change elevation and create on a different XZ plane, actual ray intersection.
    type_number(w.elevation,'50');w.change_work_plane()
    assert w.model.work_elevation==50
    pos=w.scene.project([-25,50,-25]).toPoint()
    QTest.mouseClick(w.scene.plotter.interactor,Qt.LeftButton,Qt.NoModifier,pos);QApplication.processEvents()
    assert w.model.node(2).xyz==pytest.approx([-25,50,-25])
    w.set_tool(Tool.SELECT);w.create_node_command([10000.,0.,10000.])
    assert w.scene.rect().contains(w.scene.project(w.model.node(3).xyz).toPoint())
    assert not w.test_errors

def test_material_section_pattern_and_multiple_support_editors(window,tmp_path):
    from PySide6.QtCore import Qt,QPoint
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QDialogButtonBox,QPushButton
    from trusslab.examples import triangle
    from trusslab.editor_libraries import LibraryDialog,LoadsDialog
    from trusslab.core import save_project,load_project
    w=window;w.set_document(triangle())
    def edit_cell(table,row,col,value):
        table.setCurrentCell(row,col);QTest.keyClick(table,Qt.Key_F2);QApplication.processEvents()
        editor=QApplication.focusWidget();QTest.keyClick(editor,Qt.Key_A,Qt.ControlModifier);QTest.keyClicks(editor,str(value));QTest.keyClick(editor,Qt.Key_Return)
    def click_text(dialog,text):
        b=next(b for b in dialog.findChildren(QPushButton) if b.text()==text)
        QTest.mouseClick(b,Qt.LeftButton);QApplication.processEvents()
    d=LibraryDialog(w);d.show();QTest.qWait(70)
    edit_cell(d.materials,1,2,12000);edit_cell(d.materials,1,3,.12)
    d.sections.parentWidget().parentWidget().setCurrentIndex(1)
    edit_cell(d.sections,0,2,2.5)
    QTest.mouseClick(d.findChild(QDialogButtonBox).button(QDialogButtonBox.Apply),Qt.LeftButton)
    assert w.model.materials[1].elastic_modulus==12000 and w.model.materials[1].density==.12
    assert w.model.members[0].area==2.5 and w.model.sections[0].area==2.5
    d.close()
    w.select('member',1);QApplication.processEvents();editor=w.property_editor
    QTest.keyClick(editor.fields['material'],Qt.Key_End)
    QTest.keyClicks(editor.fields['group'],'grupo_usuario');type_number(editor.fields['area'],'3.25',True)
    assert w.model.members[0].material_id=='M2' and w.model.members[0].area==3.25 and w.model.members[0].group=='basegrupo_usuario'
    d=LoadsDialog(w);d.show();QTest.qWait(70)
    click_text(d,'Crear patrón');edit_cell(d.patterns,2,1,'Carga nueva')
    click_text(d,'Añadir caso');edit_cell(d.cases,3,2,'LC3=1')
    click_text(d,'Guardar patrones y casos')
    QTest.keyClick(d.pattern,Qt.Key_End);QTest.keyClicks(d.nodes,'3');type_number(d.forces[2],'-7.25')
    click_text(d,'Asignar fuerzas a los nodos')
    assert w.model.pattern_load(3,'LC3')==[0.,0.,-7.25]
    assert w.model.pattern_load(3,'LC1')==[0.,0.,-10.]
    d.close()
    # Multi-selection support assignment must preserve different nodal loads.
    w.select('node',2);w.select('node',3,additive=True);QApplication.processEvents()
    c=w.property_editor.checks['X'];w.property_scroll.ensureWidgetVisible(c);QApplication.processEvents()
    QTest.mouseClick(c,Qt.LeftButton,Qt.NoModifier,QPoint(8,c.height()//2))
    b=w.property_editor.findChild(QPushButton,'apply_supports');w.property_scroll.ensureWidgetVisible(b);QApplication.processEvents();QTest.mouseClick(b,Qt.LeftButton)
    assert w.model.node(2).fixed[0] and w.model.node(3).fixed[0]
    assert not w.model.node(2).fixed[1] and not w.model.node(3).fixed[1]
    assert w.model.pattern_load(3,'LC3')==[0.,0.,-7.25] and w.model.pattern_load(2,'LC3')==[0.,0.,0.]
    path=tmp_path/'libraries.json';save_project(path,w.model);restored,_,_=load_project(path)
    assert restored.to_dict()==w.model.to_dict()
    assert not w.test_errors

def test_property_apply_preserves_full_precision(window):
    from trusslab.examples import triangle
    from trusslab.fem import solve
    w=window;w.model=triangle();w.model.members[0].area=1.123456789123
    w.result=solve(w.model);w.refresh();w.select('member',1)
    editor=w.property_editor;editor.fields['group'].setText('changed');editor.apply()
    assert w.model.members[0].area==1.123456789123
    assert w.result is None

def test_equal_numeric_edit_and_external_mutation_guard(window):
    from trusslab.examples import triangle
    from trusslab.fem import solve
    w=window;w.model=triangle();w.model.nodes[0].xyz=[0,0,0]
    w.result=solve(w.model);fp=w.model.fingerprint()
    w.edit(lambda:setattr(w.model.nodes[0],'xyz',[0.,0.,0.]))
    assert w.model.fingerprint()==fp and w.result is not None
    w.model.members[0].area*=2.;w.refresh()
    assert w.result is None

def test_save_open_validate_and_exports_use_current_model(window,tmp_path,monkeypatch):
    import json,csv
    from PySide6.QtWidgets import QFileDialog
    from trusslab.examples import triangle
    w=window;w.set_document(triangle());w.validate_document()
    assert w.checked_fingerprint==w.model.fingerprint()
    w.run_fem();assert w.result
    target=tmp_path/'ui_project.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,**kwargs:(str(target),''))
    assert w.save_project() and target.exists()
    expected=w.model.fingerprint();w.model.name='changed';w.dirty=False
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args,**kwargs:(str(target),''))
    w.open_project();assert w.model.fingerprint()==expected and w.result
    target=tmp_path/'ui_results.csv';w.export_csv()
    with target.open(encoding='utf-8-sig',newline='') as f:assert len(list(csv.DictReader(f)))==len(w.model.members)
    target=tmp_path/'ui_report.json';w.export_report();assert json.loads(target.read_text(encoding='utf-8'))
    target=tmp_path/'ui_view.png';w.export_image();assert target.stat().st_size>1000
    assert not w.test_errors

def test_deleting_loads_and_renaming_pattern_preserves_assignments(window):
    from PySide6.QtCore import Qt
    from trusslab.editor_libraries import LoadsDialog
    from trusslab.examples import triangle
    w=window;w.set_document(triangle());d=LoadsDialog(w)
    d.patterns.item(0,0).setText('D')
    d.cases.item(0,2).setText('D=1');d.cases.item(2,2).setText('D=1.2; LC2=1.6')
    d.apply_definitions();assert w.model.pattern_load(3,'D')==[0.,0.,-10.]
    d.patterns.setRowCount(0);d.cases.setRowCount(0);d.apply_definitions()
    assert not w.model.load_patterns and not any(any(v) for v in w.model.nodal_loads().values())
    assert w.model.analysis_issues()
    d.close();assert not w.test_errors

def test_optimize_action_runs_worker_and_updates_model(window):
    import time
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtWidgets import QApplication,QDialogButtonBox
    from PySide6.QtTest import QTest
    from trusslab.examples import triangle
    w=window;w.set_document(triangle());initial=w.model.weight()
    def accept_configuration():
        d=QApplication.activeModalWidget();d.iterations.setValue(60);d.budget.setValue(150)
        QTest.mouseClick(d.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
    QTimer.singleShot(80,accept_configuration);w.optimize_dialog()
    deadline=time.monotonic()+90
    while w.job and time.monotonic()<deadline:QTest.qWait(50)
    assert w.job is None and not w.test_errors
    assert w.result['feasible'] and w.model.weight()<initial
    assert w.result['model_fingerprint']==w.model.fingerprint() and w.history
