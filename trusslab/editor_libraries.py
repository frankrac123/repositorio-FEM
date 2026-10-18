from PySide6.QtCore import Qt
"""Editable structural libraries, load patterns and analysis combinations."""
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QTabWidget,QTableWidget,
    QTableWidgetItem,QPushButton,QDialogButtonBox,QFormLayout,QLineEdit,QComboBox,QLabel,QWidget)
from .core import Material,Section,LoadPattern,AnalysisCase
from .editor_properties import NumberEdit

def table(headers,rows):
    w=QTableWidget(len(rows),len(headers));w.setHorizontalHeaderLabels(headers)
    for i,row in enumerate(rows):
        for j,value in enumerate(row):w.setItem(i,j,QTableWidgetItem(str(value)))
    w.horizontalHeader().setStretchLastSection(True);return w

def rows(w):
    return [[w.item(i,j).text().strip() if w.item(i,j) else '' for j in range(w.columnCount())] for i in range(w.rowCount())]

def add_row(w,values):
    i=w.rowCount();w.insertRow(i)
    for j,value in enumerate(values):w.setItem(i,j,QTableWidgetItem(str(value)))

class LibraryDialog(QDialog):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.setWindowTitle('Materiales, secciones y límites');self.resize(780,570)
        layout=QVBoxLayout(self);tabs=QTabWidget();layout.addWidget(tabs)
        m=owner.model
        materials=m.materials or [Material('legacy',m.material_name,m.elastic_modulus,m.density)]
        self.materials=table(['ID','Nombre','E (ksi)','Peso específico (lb/in³)'],[[x.id,x.name,x.elastic_modulus,x.density] for x in materials])
        self.sections=table(['ID','Nombre','Área (in²)'],[[x.id,x.name,x.area] for x in m.sections])
        for name,w,defaults in [('Materiales',self.materials,lambda:['M'+str(self.materials.rowCount()+1),'Nuevo material',29000,.283]),
                                ('Secciones',self.sections,lambda:['S'+str(self.sections.rowCount()+1),'Nueva sección',1.])]:
            page=QWidget();l=QVBoxLayout(page);l.addWidget(w);h=QHBoxLayout();l.addLayout(h)
            add=QPushButton('Añadir');add.clicked.connect(lambda _,w=w,values=defaults:add_row(w,values()));h.addWidget(add)
            remove=QPushButton('Eliminar fila');remove.clicked.connect(lambda _,w=w:w.removeRow(w.currentRow()) if w.currentRow()>=0 else None);h.addWidget(remove)
            tabs.addTab(page,name)
        page=QWidget();f=QFormLayout(page);self.limits={}
        for key,title in [('area_min','Área mínima (in²)'),('area_max','Área máxima (in²)'),('stress_limit','Esfuerzo admisible ± (ksi)'),('displacement_limit','Desplazamiento ± (in)')]:
            field=NumberEdit(getattr(m,key),1e-8,1e9);self.limits[key]=field;f.addRow(title,field)
        tabs.addTab(page,'Límites de diseño')
        note=QLabel('Las áreas de sección se aplican a todas sus barras asignadas. El área individual puede ajustarse en Propiedades. El material histórico conserva E = 10,000 ksi.');note.setWordWrap(True);layout.addWidget(note)
        boxes=QDialogButtonBox(QDialogButtonBox.Apply|QDialogButtonBox.Close);boxes.button(QDialogButtonBox.Apply).clicked.connect(self.apply);boxes.rejected.connect(self.reject);layout.addWidget(boxes)
        for button in self.findChildren(QPushButton):button.setAutoDefault(False);button.setDefault(False)
    def apply(self):
        try:
            mats=[Material(id,name,float(e.replace(',','.')),float(r.replace(',','.'))) for id,name,e,r in rows(self.materials)]
            secs=[Section(id,name,float(a.replace(',','.'))) for id,name,a in rows(self.sections)]
        except ValueError:self.owner.error('Introduce números válidos en materiales y secciones.');return
        def change():
            m=self.owner.model;previous={s.id:s.area for s in m.sections};m.materials=mats;m.sections=secs
            for s in secs:
                if previous.get(s.id)!=s.area:
                    for b in m.members:
                        if b.section_id==s.id:b.area=s.area
            for mat in mats:
                if mat.id=='legacy':m.elastic_modulus=mat.elastic_modulus;m.density=mat.density;m.material_name=mat.name
            for key,field in self.limits.items():setattr(m,key,field.value())
        self.owner.edit(change)

class LoadsDialog(QDialog):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.setWindowTitle('CARGAS · patrones, fuerzas y casos');self.resize(800,650)
        layout=QVBoxLayout(self);m=owner.model
        patterns=m.load_patterns or [LoadPattern('LC1','Carga histórica',nodal_loads={str(n.id):n.load for n in m.nodes if any(n.load)})]
        self.pattern_data={p.id:p for p in patterns}
        self.patterns=table(['ID','Nombre','Tipo (Dead/Live/Wind/Other)','Multiplicador peso propio'],[[p.id,p.name,p.load_type,p.self_weight] for p in patterns]);layout.addWidget(self.patterns)
        h=QHBoxLayout();layout.addLayout(h)
        add=QPushButton('Crear patrón');add.clicked.connect(lambda:add_row(self.patterns,['LC'+str(self.patterns.rowCount()+1),'Nueva carga','Other',0.]));h.addWidget(add)
        remove=QPushButton('Eliminar patrón');remove.clicked.connect(lambda:self.patterns.removeRow(self.patterns.currentRow()) if self.patterns.currentRow()>=0 else None);h.addWidget(remove)
        apply=QPushButton('Guardar patrones y casos');apply.clicked.connect(self.apply_definitions);h.addWidget(apply)
        layout.addWidget(QLabel('Casos / combinaciones lineales. Factores: LC1=1; LC2=-1'))
        cases=m.analysis_cases or [AnalysisCase('LC1','Caso 1',{'LC1':1.})]
        self.cases=table(['ID','Nombre','Factores','Optimizar'],[[c.id,c.name,'; '.join(f'{k}={v:g}' for k,v in c.factors.items()),''] for c in cases]);layout.addWidget(self.cases)
        selected=m.optimization_config.get('load_cases') or [m.active_case]
        for i,c in enumerate(cases):self.cases.item(i,3).setCheckState(Qt.Checked if c.id in selected else Qt.Unchecked)
        h=QHBoxLayout();layout.addLayout(h)
        add=QPushButton('Añadir caso');add.clicked.connect(self.add_case);h.addWidget(add)
        remove=QPushButton('Eliminar caso');remove.clicked.connect(lambda:self.cases.removeRow(self.cases.currentRow()) if self.cases.currentRow()>=0 else None);h.addWidget(remove)
        f=QFormLayout();layout.addLayout(f)
        self.pattern=QComboBox();self.pattern.setObjectName('assign_pattern')
        for p in patterns:self.pattern.addItem(p.name,p.id)
        f.addRow('Patrón a editar',self.pattern)
        self.nodes=QLineEdit(','.join(str(id) for kind,id in owner.selection if kind=='node'));self.nodes.setObjectName('load_nodes');f.addRow('Nodos (ID separados por coma)',self.nodes)
        self.forces=[NumberEdit() for _ in range(3)]
        for a,w in zip('XYZ',self.forces):w.setObjectName('assign_F'+a);f.addRow('F'+a+' (kip)',w)
        assign=QPushButton('Asignar fuerzas a los nodos');assign.clicked.connect(self.assign);layout.addWidget(assign)
        self.active=QComboBox();self.active.setObjectName('active_case')
        for c in cases:self.active.addItem(c.name,c.id)
        self.active.setCurrentIndex(max(0,self.active.findData(m.active_case)));f.addRow('Caso para análisis / vista',self.active)
        self.active.currentIndexChanged.connect(self.change_case)
        close=QPushButton('Cerrar');close.clicked.connect(self.accept);layout.addWidget(close)
        for button in self.findChildren(QPushButton):button.setAutoDefault(False);button.setDefault(False)
    def add_case(self):
        add_row(self.cases,['C'+str(self.cases.rowCount()+1),'Combinación','LC1=1',''])
        self.cases.item(self.cases.rowCount()-1,3).setCheckState(Qt.Unchecked)
    def apply_definitions(self):
        try:
            patterns=[LoadPattern(id,name,kind,self.pattern_data[id].nodal_loads.copy() if id in self.pattern_data else {},float(weight.replace(',','.'))) for id,name,kind,weight in rows(self.patterns)]
            cases=[AnalysisCase(id,name,{key.strip():float(value.replace(',','.')) for key,value in (item.split('=') for item in text.split(';'))}) for id,name,text,_ in rows(self.cases)]
        except (ValueError,TypeError):self.owner.error('Comprueba números, identificadores y factores de carga.');return
        def change():
            m=self.owner.model;m.load_patterns=patterns;m.analysis_cases=cases
            m.optimization_config['load_cases']=[c.id for i,c in enumerate(cases) if self.cases.item(i,3).checkState()==Qt.Checked]
            if cases and m.active_case not in {c.id for c in cases}:m.active_case=cases[0].id
        if self.owner.edit(change):
            self.pattern_data={p.id:p for p in patterns};self.pattern.clear();self.active.blockSignals(True);self.active.clear()
            for p in patterns:self.pattern.addItem(p.name,p.id)
            for c in cases:self.active.addItem(c.name,c.id)
            self.active.setCurrentIndex(max(0,self.active.findData(self.owner.model.active_case)));self.active.blockSignals(False)
    def assign(self):
        try:ids=[int(x.strip()) for x in self.nodes.text().split(',') if x.strip()]
        except ValueError:self.owner.error('Utiliza identificadores enteros de nodo.');return
        if not ids or not self.pattern.currentData():self.owner.error('Selecciona nodos y un patrón guardado.');return
        def change():
            for id in ids:self.owner.model.set_nodal_load(id,self.pattern.currentData(),[w.value() for w in self.forces])
        self.owner.display_pattern=self.pattern.currentData();self.owner.scene.load_pattern=self.pattern.currentData();self.owner.edit(change)
    def change_case(self):
        id=self.active.currentData()
        if id:self.owner.edit(lambda:setattr(self.owner.model,'active_case',id));self.owner.scene.load_pattern=None;self.owner.scene.overlay.update()
