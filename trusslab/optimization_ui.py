"""Incremental configuration and responsive controls for stages 3 and 4."""
from dataclasses import fields
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QComboBox,QSpinBox,QDoubleSpinBox,
    QLabel,QDialogButtonBox,QGroupBox,QProgressBar,QHBoxLayout,QPushButton,QLineEdit,QMessageBox)
from .asam import ASAMOptions
from .editor_properties import NumberEdit
from .analysis import design_cases


class OptimizationDialog(QDialog):
    def __init__(self,model,parent=None):
        super().__init__(parent);self.model=model
        self.setWindowTitle('Optimización de tamaño');self.resize(620,750)
        layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.method=QComboBox()
        for label,value in [('SLSQP · búsqueda local','SLSQP'),('DE · evolución diferencial','DE'),('ASAM · Millán-Páramo et al.','ASAM')]:self.method.addItem(label,value)
        form.addRow('Algoritmo',self.method)
        self.engine=QComboBox()
        for label,value in [('FEM Python','FEM'),('SAP2000 · cada candidato','SAP'),('Híbrido · FEM + verificación SAP','HYBRID')]:self.engine.addItem(label,value)
        form.addRow('Motor estructural',self.engine)
        self.iterations=self.integer(1,100000,250);form.addRow('Máximo de iteraciones',self.iterations)
        self.budget=self.integer(2,10000000,10000);form.addRow('Máximo de evaluaciones',self.budget)
        self.seed=self.integer(0,2147483647,42);form.addRow('Semilla',self.seed)
        self.topk=self.integer(1,1000,3);form.addRow('Diseños a verificar en híbrido',self.topk)
        self.active=QLineEdit();self.active.setPlaceholderText('Vacío = todas; ejemplo: 1,2,5');form.addRow('Barras optimizables (ID)',self.active)
        self.groups=QLineEdit();self.groups.setPlaceholderText('Ejemplo: 1,2;3,4 · resto individuales');form.addRow('Grupos de área compartida',self.groups)
        form.addRow('Casos verificados',QLabel(', '.join(design_cases(model))))
        form.addRow('Límites del modelo',QLabel(f'A: {model.area_min:g}–{model.area_max:g} in² · σ: ±{model.stress_limit:g} ksi · u: ±{model.displacement_limit:g} in'))
        self.asam=QGroupBox('ASAM · parámetros científicos');af=QFormLayout(self.asam);layout.addWidget(self.asam)
        labels={'temperature_initial':'Temperatura inicial (energía normalizada)','temperature_final':'Temperatura final',
            'cooling':'Coeficiente de enfriamiento','initial_points':'Candidatos de exploración preliminar',
            'radius_initial':'Radio inicial (in²)','radius_reduction':'Reducción del radio',
            'proposals_per_temperature':'Propuestas por temperatura','convergence_tolerance':'Tolerancia de estancamiento (0: desactivada)',
            'convergence_patience':'Temperaturas sin mejora para terminar'}
        self.parameters={};defaults=ASAMOptions()
        for field in fields(defaults):
            value=getattr(defaults,field.name)
            if isinstance(value,int):control=self.integer(1,1000000,value)
            else:
                control=NumberEdit(value,0.,100000.,9)
            self.parameters[field.name]=control;af.addRow(labels[field.name],control)
        note=QLabel('ASAM: exploración uniforme, radio decreciente y aceptación logística.\nEl motor SAP usa una sesión propia; no cambia al FEM si falla. Los grupos y los casos marcados en Cargas se toman del modelo actual.');note.setWordWrap(True);layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('Iniciar búsqueda');buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.method.currentIndexChanged.connect(self.refresh);self.engine.currentIndexChanged.connect(self.refresh);self.refresh()

    @staticmethod
    def integer(lo,hi,value):
        control=QSpinBox();control.setRange(lo,hi);control.setValue(value);return control
    def refresh(self):
        self.asam.setEnabled(self.method.currentData()=='ASAM');self.topk.setEnabled(self.engine.currentData()=='HYBRID')
    def configuration(self):
        active=[int(v.strip()) for v in self.active.text().split(',')] if self.active.text().strip() else None
        groups=[[int(v.strip()) for v in group.split(',')] for group in self.groups.text().split(';')] if self.groups.text().strip() else None
        return {'method':self.method.currentData(),'engine':self.engine.currentData(),
            'iterations':self.iterations.value(),'seed':self.seed.value(),'max_evaluations':self.budget.value(),
            'hybrid_validations':self.topk.value(),'asam_options':ASAMOptions(**{k:v.value() for k,v in self.parameters.items()}),
            'active_ids':active,'groups':groups}
    def validate(self):
        try:
            from .design_space import DesignSpace
            config=self.configuration();DesignSpace(self.model,config['active_ids'],config['groups'])
            if config['method']=='ASAM':
                config['asam_options'].validate()
                if config['asam_options'].initial_points>=config['max_evaluations']:raise ValueError('El presupuesto debe superar la exploración inicial.')
            if config['engine']=='HYBRID' and config['max_evaluations']<config['hybrid_validations']+2:raise ValueError('Aumenta el presupuesto para incluir la verificación SAP.')
            self.accept()
        except ValueError as error:QMessageBox.warning(self,'Configuración',str(error))


class OptimizationProgress(QDialog):
    def __init__(self,control,budget,parent=None):
        super().__init__(parent);self.control=control;self.finished_run=False
        self.setWindowTitle('Búsqueda estructural en curso');self.resize(540,240)
        layout=QVBoxLayout(self);self.details=QLabel('Preparando análisis…');self.details.setWordWrap(True);layout.addWidget(self.details)
        self.bar=QProgressBar();self.bar.setRange(0,budget);layout.addWidget(self.bar)
        self.status=QLabel('La pausa y la detención se aplican entre análisis estructurales.');self.status.setWordWrap(True);layout.addWidget(self.status)
        row=QHBoxLayout();layout.addLayout(row);self.pause_button=QPushButton('Pausar');self.pause_button.setCheckable(True);self.pause_button.toggled.connect(self.pause);row.addWidget(self.pause_button)
        self.stop_button=QPushButton('Detener');self.stop_button.clicked.connect(self.stop);row.addWidget(self.stop_button)
        self.hide_button=QPushButton('Ocultar');self.hide_button.clicked.connect(self.hide);row.addWidget(self.hide_button)
    def pause(self,value):
        self.control.pause(value);self.pause_button.setText('Reanudar' if value else 'Pausar')
        self.status.setText('Pausa solicitada; espera al análisis actual.' if value else 'Búsqueda reanudada.')
    def stop(self):
        self.control.cancel();self.stop_button.setEnabled(False);self.pause_button.setEnabled(False)
        self.status.setText('Detención solicitada; se conserva el mejor candidato factible calculado. Esperando al análisis actual…')
    def update_progress(self,item):
        if isinstance(item,str):self.status.setText(item);return
        self.bar.setValue(item['evaluations']);best=item.get('best_feasible_lb');best='ninguno' if best is None else f'{best:,.3f} lb'
        self.details.setText(f'Iteraciones: {item["iteration"]} · Evaluaciones: {item["evaluations"]}\nFEM: {item["fem_evaluations"]} · SAP: {item["sap_evaluations"]}\nTiempo: {item["elapsed_seconds"]:.1f} s · Mejor factible: {best}\nSAP2000: {item["sap_status"]} · Verificación: {item["external_validation"]}')
    def finish(self):
        self.finished_run=True;self.close()
    def reject(self):
        if self.finished_run:super().reject()
        else:self.hide()
