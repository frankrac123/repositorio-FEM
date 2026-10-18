"""Stable property editors. Explicit confirmation commits one document command."""
from PySide6.QtCore import Qt,QLocale
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QFormLayout,QDoubleSpinBox,QLineEdit,
    QComboBox,QCheckBox,QPushButton,QLabel)
from .engineering_types import BoundaryCondition

class NumberEdit(QDoubleSpinBox):
    def __init__(self,value=0.,minimum=-1e9,maximum=1e9,decimals=6,parent=None):
        super().__init__(parent)
        self.setLocale(QLocale.c());self.setRange(minimum,maximum);self.setDecimals(decimals)
        self.setKeyboardTracking(False);self.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.setMinimumHeight(32);self.setMinimumWidth(86);self.setValue(float(value))
        self.lineEdit().textEdited.connect(self.mark_edited)
        self.setStyleSheet('QDoubleSpinBox {color:#152745;background:white;padding:4px 6px;} QDoubleSpinBox QLineEdit {border:0;background:transparent;color:#152745;padding:0;}')
    def mark_edited(self,*args):self._edited=True
    def setValue(self,value):
        super().setValue(float(value))
        self._exact=float(value);self._shown=super().value();self._edited=False
    def value(self):
        self.interpretText()
        return self._exact if not self._edited and super().value()==self._shown else super().value()
    def stepBy(self,steps):
        self._edited=True
        super().stepBy(steps)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.layout_text()
    def showEvent(self,event):
        super().showEvent(event)
        self.layout_text()
    def layout_text(self):
        # Qt 6.12/Fusion + stylesheet + NoButtons can return a 1 px edit field
        # on Windows. Own the text rectangle; no hidden spin-button subcontrols.
        self.lineEdit().setGeometry(7,4,max(1,self.width()-14),max(1,self.height()-8))
    def validate(self,text,pos):return super().validate(text.replace(',','.'),pos)
    def valueFromText(self,text):return super().valueFromText(text.replace(',','.'))

class PropertiesEditor(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.fields={};self.checks={}
        self.selection=tuple(owner.selection);self.entity=owner.selected
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.form=QFormLayout();self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.form.setLabelAlignment(Qt.AlignLeft|Qt.AlignVCenter);layout.addLayout(self.form)
        kind,id=self.entity;m=owner.model
        if kind=='node' and any(n.id==id for n in m.nodes):
            node=m.node(id)
            if len(self.selection)==1:
                for d,axis in enumerate('XYZ'):
                    f=self.number('xyz_'+axis,f'{axis} (in)',node.xyz[d]);f.setEnabled(m.structure_type!='2D' or d!=m.normal_axis)
            self.pattern=QComboBox();self.pattern.setObjectName('load_pattern')
            for p in m.load_patterns:self.pattern.addItem(p.name,p.id)
            if not m.load_patterns and m.load_storage=='legacy':self.pattern.addItem('Carga histórica','LC1')
            index=self.pattern.findData(owner.display_pattern)
            self.pattern.setCurrentIndex(max(index,0));self.form.addRow('Patrón',self.pattern)
            self.pattern.currentIndexChanged.connect(self.load_pattern)
            for d,axis in enumerate('XYZ'):self.number('load_'+axis,f'F{axis} (kip)',m.pattern_load(id,self.pattern.currentData())[d])
            for d,axis in enumerate('XYZ'):
                c=QCheckBox('Restringir '+axis);c.setObjectName('fixed_'+axis);c.setChecked(node.fixed[d]);self.checks[axis]=c
                self.form.addRow(c)
            if m.structure_type=='2D':
                note=QLabel(f'Plano {m.work_plane}: la traslación normal se elimina del análisis; no es un apoyo añadido.');note.setWordWrap(True);layout.addWidget(note)
        elif kind=='member' and any(b.id==id for b in m.members):
            b=next(b for b in m.members if b.id==id)
            self.form.addRow(QLabel(f'Nodos {b.start} → {b.end} · L = {m.length(b):.6g} in'))
            self.number('area','Área (in²)',b.area,1e-8,1e8)
            mat=QComboBox();mat.setObjectName('member_material');mat.addItem(m.material_name,None)
            for material in m.materials:mat.addItem(material.name,material.id)
            mat.setCurrentIndex(max(0,mat.findData(b.material_id)));self.fields['material']=mat;self.form.addRow('Material',mat)
            sec=QComboBox();sec.setObjectName('member_section');sec.addItem('Área individual',None)
            for s in m.sections:sec.addItem(s.name,s.id)
            sec.setCurrentIndex(max(0,sec.findData(b.section_id)));self.fields['section']=sec;self.form.addRow('Sección',sec)
            sec.currentIndexChanged.connect(self.section_changed)
            group=QLineEdit(b.group);group.setObjectName('design_group');self.fields['group']=group;self.form.addRow('Grupo',group)
            material=m.member_material(b);self.form.addRow(QLabel(f'E = {material.elastic_modulus:g} ksi · ρ = {material.density:g} lb/in³'))
        else:
            note=QLabel('Proyecto vacío. Crea nodos con coordenadas o activa Crear nodo y haz clic en el plano de trabajo.');note.setWordWrap(True);layout.addWidget(note);return
        self.apply_button=QPushButton('Aplicar cambios');self.apply_button.setObjectName('apply_properties');layout.addWidget(self.apply_button)
        self.apply_button.clicked.connect(self.apply)
        if kind=='node':
            for text,mode in [('Aplicar solo fuerzas','loads'),('Aplicar solo apoyos','supports')]:
                button=QPushButton(text);button.setObjectName('apply_'+mode)
                button.clicked.connect(lambda _,mode=mode:self.apply(mode));layout.addWidget(button)
        if owner.result:
            if kind=='node':
                u=owner.result['displacements'][str(id)]
                text='Resultados (in):\n'+' · '.join(f'u{a}={v:+.5g}' for a,v in zip('XYZ',u))
            else:
                r=next(r for r in owner.result['members'] if r['id']==id)
                text=f'Resultados: P={r["force"]:+.6g} kip\nσ={r["stress"]:+.6g} ksi · razón={r["ratio"]:.4g}'
            result_label=QLabel(text);result_label.setWordWrap(True);result_label.setStyleSheet('background:#edf2f7;color:#5c708c;padding:6px;');layout.addWidget(result_label)
        # Return commits, focus loss only interprets text. No controls are deleted.
        for field in self.fields.values():
            if isinstance(field,NumberEdit):field.lineEdit().returnPressed.connect(self.apply)
        note=QLabel('Enter o Aplicar para confirmar. Los cambios invalidan el análisis anterior.');note.setWordWrap(True);layout.addWidget(note)
    def number(self,key,caption,value,minimum=-1e9,maximum=1e9):
        f=NumberEdit(value,minimum,maximum);f.setObjectName(key);self.fields[key]=f;self.form.addRow(caption,f);return f
    def load_pattern(self):
        if not all('load_'+a in self.fields for a in 'XYZ'):return
        self.owner.display_pattern=self.pattern.currentData()
        values=self.owner.model.pattern_load(self.entity[1],self.pattern.currentData())
        for d,a in enumerate('XYZ'):self.fields['load_'+a].setValue(values[d])
        self.owner.scene.load_pattern=self.pattern.currentData();self.owner.scene.overlay.update()
    def section_changed(self):
        id=self.fields['section'].currentData()
        sec=next((s for s in self.owner.model.sections if s.id==id),None)
        if sec:self.fields['area'].setValue(sec.area)
    def apply(self,mode='all'):
        if isinstance(mode,bool):mode='all'
        for field in self.fields.values():
            if isinstance(field,NumberEdit):field.interpretText()
        owner=self.owner;kind,id=self.entity
        def change():
            if kind=='node':
                if mode=='all' and 'xyz_X' in self.fields:owner.model.node(id).xyz=[self.fields['xyz_'+a].value() for a in 'XYZ']
                for k,i in self.selection:
                    if k!='node':continue
                    if mode in ('all','supports'):owner.model.set_support(BoundaryCondition(i,[self.checks[a].isChecked() for a in 'XYZ']))
                    if mode in ('all','loads'):owner.model.set_nodal_load(i,self.pattern.currentData(),[self.fields['load_'+a].value() for a in 'XYZ'])
            else:
                for k,i in self.selection:
                    if k!='member':continue
                    b=next(b for b in owner.model.members if b.id==i)
                    b.area=self.fields['area'].value();b.material_id=self.fields['material'].currentData()
                    b.section_id=self.fields['section'].currentData();b.group=self.fields['group'].text().strip()
        owner.edit(change,rebuild_properties=False)
