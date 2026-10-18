"""Authentic SAP result browser, using the existing model scene and result schema."""
import csv
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QDoubleSpinBox,QCheckBox,
    QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QTabWidget,QPushButton,QFileDialog,QSplitter,QWidget)
from .scene import ModelScene


class StructuralResultsDialog(QDialog):
    def __init__(self,model,result,parent=None):
        super().__init__(parent)
        if not result.get('engine','').startswith('SAP2000'):
            raise ValueError('Este módulo requiere resultados auténticos de SAP2000.')
        if result.get('model_fingerprint')!=model.fingerprint():
            raise ValueError('Los resultados SAP no corresponden al modelo actual.')
        self.model=model.clone();self.result=result
        self.setWindowTitle('RESULTADOS ESTRUCTURALES — SAP2000');self.resize(1250,820)
        layout=QVBoxLayout(self)
        title=QLabel('RESULTADOS ESTRUCTURALES — SAP2000');title.setObjectName('panelTitle');layout.addWidget(title)
        layout.addWidget(QLabel(f'{result["engine"]} · {model.name} · peso {result["weight_lb"]:,.3f} lb'))
        controls=QHBoxLayout();layout.addLayout(controls)
        self.mode=QComboBox();self.mode.addItem('Geometría original','geometry');self.mode.addItem('Esfuerzo axial (ksi)','stress');self.mode.addItem('Fuerza axial (kip)','force')
        controls.addWidget(self.mode)
        self.deformed=QCheckBox('Original + deformada');self.deformed.setChecked(True);controls.addWidget(self.deformed)
        controls.addWidget(QLabel('Amplificación visual ×'))
        self.amplification=QDoubleSpinBox();self.amplification.setRange(0,10000);self.amplification.setValue(12);controls.addWidget(self.amplification)
        controls.addWidget(QLabel('Escala de sección'))
        self.thickness=QDoubleSpinBox();self.thickness.setRange(.1,50);self.thickness.setValue(1.5);controls.addWidget(self.thickness)
        self.scene=ModelScene();self.scene.setMinimumHeight(300)
        splitter=QSplitter(Qt.Vertical);layout.addWidget(splitter,1);splitter.addWidget(self.scene)
        bottom=QWidget();bl=QVBoxLayout(bottom);splitter.addWidget(bottom);splitter.setSizes([440,260])
        checks=QHBoxLayout();bl.addLayout(checks)
        for title,attribute,default in [('Cargas','loads',True),('Reacciones','reactions',False),('Desplazamientos uz','displacement_labels',False),('Barras críticas ≥ 0.95','critical',True)]:
            check=QCheckBox(title);check.setChecked(default);setattr(self.scene,attribute,default)
            check.toggled.connect(lambda value,attr=attribute:self.set_scene(attr,value));checks.addWidget(check)
        self.selection=QLabel('Selecciona una barra o un nodo para consultar valores reales y unidades.');self.selection.setWordWrap(True);bl.addWidget(self.selection)
        self.tabs=QTabWidget();bl.addWidget(self.tabs,1)
        members=[]
        for m in model.members:
            r=next(r for r in result['members'] if r['id']==m.id)
            members.append([m.id,m.start,m.end,m.area,r['force'],r['stress'],model.stress_limit,r['ratio'],'CRÍTICA' if r['ratio']>=.95 else ''])
        self.add_table('Barras',['ID','Inicio','Final','A (in²)','P (kip)','σ calculado (ksi)','σ admisible ± (ksi)','Utilización','Estado'],members)
        nodes=[];reactions=[];loads=[]
        for n in model.nodes:
            u=result['displacements'][str(n.id)];r=result['reactions'][str(n.id)]
            nodes.append([n.id,*u,model.displacement_limit,max(abs(v)/model.displacement_limit for v in u)])
            if any(self.model.restraints(n)):reactions.append([n.id,*r])
            loads.append([n.id,*model.nodal_loads(result.get('analysis_case'))[str(n.id)]])
        self.add_table('Desplazamientos',['Nodo','ux (in)','uy (in)','uz (in)','Límite ± (in)','Utilización'],nodes)
        self.add_table('Reacciones',['Nodo','Rx (kip)','Ry (kip)','Rz (kip)'],reactions)
        self.add_table('Cargas',['Nodo','Fx (kip)','Fy (kip)','Fz (kip)'],loads)
        legend=QLabel('Azul: tracción (+) · Rojo: compresión (−) · Intensidad relativa al máximo mostrado. La escala de deformación y de sección es solo visual.');legend.setWordWrap(True);layout.addWidget(legend)
        footer=QHBoxLayout();layout.addLayout(footer)
        export=QPushButton('Exportar tabla CSV');export.clicked.connect(self.export_table);footer.addWidget(export)
        footer.addStretch();close=QPushButton('Cerrar');close.clicked.connect(self.accept);footer.addWidget(close)
        self.update_timer=QTimer(self);self.update_timer.setSingleShot(True);self.update_timer.setInterval(80)
        self.update_timer.timeout.connect(self.update_scene)
        self.mode.currentIndexChanged.connect(self.request_update);self.deformed.toggled.connect(self.request_update)
        self.amplification.valueChanged.connect(self.request_update);self.thickness.valueChanged.connect(self.request_update)
        self.scene.selected_entity.connect(self.select)
        self.update_scene(reset=True)

    def add_table(self,title,columns,rows):
        table=QTableWidget(len(rows),len(columns));table.setHorizontalHeaderLabels(columns);table.verticalHeader().hide()
        table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.setAlternatingRowColors(True);table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for i,row in enumerate(rows):
            for j,value in enumerate(row):table.setItem(i,j,QTableWidgetItem(f'{value:.6g}' if isinstance(value,float) else str(value)))
        self.tabs.addTab(table,title)

    def set_scene(self,attribute,value):
        setattr(self.scene,attribute,value);self.scene.overlay.update()

    def request_update(self,*args):self.update_timer.start()

    def update_scene(self,*args,reset=False):
        self.scene.stress_colors=self.mode.currentData()!='geometry';self.scene.result_quantity=self.mode.currentData()
        self.scene.deformed=self.deformed.isChecked();self.scene.deform_scale=self.amplification.value();self.scene.section_scale=self.thickness.value()
        self.scene.set_model(self.model,self.result,reset)

    def select(self,kind,id):
        if kind=='member':
            r=next(r for r in self.result['members'] if r['id']==id)
            self.selection.setText(f'Barra {id}: A = {r["area"]:.6g} in² · P = {r["force"]:+.6g} kip · σ calculado = {r["stress"]:+.6g} ksi · admisible ±{self.model.stress_limit:g} ksi · utilización = {r["ratio"]:.6f}')
        else:
            u=self.result['displacements'][str(id)];r=self.result['reactions'][str(id)]
            self.selection.setText(f'Nodo {id}: u XYZ = {u} in · R XYZ = {r} kip')
        self.scene.selected=(kind,id);self.scene.overlay.update()
        if self.mode.currentData()=='geometry':self.request_update()

    def export_table(self):
        path,_=QFileDialog.getSaveFileName(self,'Exportar tabla SAP2000','resultados_sap.csv','CSV (*.csv)')
        if not path:return
        table=self.tabs.currentWidget()
        with Path(path).open('w',newline='',encoding='utf-8-sig') as out:
            writer=csv.writer(out);writer.writerow([table.horizontalHeaderItem(j).text() for j in range(table.columnCount())])
            for i in range(table.rowCount()):writer.writerow([table.item(i,j).text() for j in range(table.columnCount())])

    def done(self,result):
        self.update_timer.stop();self.scene.timer.stop();self.scene.plotter.close();super().done(result)
