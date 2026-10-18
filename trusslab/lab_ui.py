"""Optimization laboratory added as a tab to the existing application."""
from pathlib import Path
import copy,json
from PySide6.QtCore import Qt,QThread,Signal,QTimer
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QComboBox,
    QSpinBox,QLineEdit,QCheckBox,QSplitter,QTableWidget,QTableWidgetItem,QHeaderView,QScrollArea,
    QProgressBar,QFileDialog,QMessageBox,QDialog,QPlainTextEdit,QDialogButtonBox)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
from .widgets import Panel,label,button
from .laboratory import CampaignConfig,run_campaign,load_campaign,winner_model,validate_campaign
from .lab_plots import COLORS,PLOT_TYPES,draw_plot
from .lab_search import METHODS
from .optimization import RunControl


class CampaignWorker(QThread):
    progress=Signal(object);done=Signal(object);failed=Signal(str)
    def __init__(self,function):super().__init__();self.function=function
    def run(self):
        try:self.done.emit(self.function(self.progress.emit))
        except Exception as exc:self.failed.emit(str(exc))


class LaboratoryTab(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.worker=None;self.campaign=None;self.histories={};self.live={};self.active_record=None;self.parameters=CampaignConfig().parameters
        self.control=RunControl();root=QHBoxLayout(self);root.setContentsMargins(10,10,10,10)
        split=QSplitter(Qt.Horizontal);root.addWidget(split)
        config=Panel('Configuración experimental');config.setMinimumWidth(280);config.setMaximumWidth(365)
        self.methods={}
        for m in METHODS:
            c=QCheckBox(m+' · multiarranque' if m=='SLSQP' else m);c.setChecked(m in ('ASAM','DE','SLSQP'));config.layout.addWidget(c);self.methods[m]=c
        for m in ['GA · pendiente','PSO · pendiente']:
            c=QCheckBox(m);c.setEnabled(False);config.layout.addWidget(c)
        form=QFormLayout();config.layout.addLayout(form)
        self.engine=QComboBox()
        for text,key in [('FEM Python','FEM'),('SAP por candidato','SAP'),('Híbrido: FEM + SAP','HYBRID')]:self.engine.addItem(text,key)
        form.addRow('Motor',self.engine)
        self.budget=QComboBox();self.budget.setEditable(True);self.budget.addItems(['2000','5000','10000']);form.addRow('Evaluaciones / corrida',self.budget)
        self.runs=QSpinBox();self.runs.setRange(1,1000);self.runs.setValue(5);form.addRow('Corridas / método',self.runs)
        self.seeds=QLineEdit('42,7,17,101,202');self.seeds.setToolTip('Una semilla distinta por corrida. Déjalo vacío para generar una lista determinista.');form.addRow('Semillas',self.seeds)
        self.active_ids=QLineEdit();self.active_ids.setPlaceholderText('Vacío: todas; ejemplo 1,2,5');form.addRow('Barras activas',self.active_ids)
        self.group_ids=QLineEdit();self.group_ids.setPlaceholderText('Ejemplo 1,2;3,4');form.addRow('Grupos de área',self.group_ids)
        self.validation=QComboBox();self.validation.addItem('Mejor por algoritmo','best_per_method');self.validation.addItem('Todos los factibles','all_feasible');self.validation.addItem('Validar después','none');form.addRow('Validación SAP',self.validation)
        params=button('Parámetros y arranques…');params.clicked.connect(self.edit_parameters);config.layout.addWidget(params)
        note=label('Todos comparten geometría, límites, presupuesto y población inicial por semilla. Los gradientes y reinicios consumen presupuesto.','muted');note.setWordWrap(True);config.layout.addWidget(note)
        self.constraints=label('El modelo se toma de la pestaña Modelado al iniciar.','muted');self.constraints.setWordWrap(True);config.layout.addWidget(self.constraints)
        self.start=button('Iniciar campaña','play');self.start.clicked.connect(self.start_campaign);config.layout.addWidget(self.start)
        row=QHBoxLayout();self.pause=button('Pausar');self.pause.setCheckable(True);self.pause.toggled.connect(self.toggle_pause);row.addWidget(self.pause)
        self.stop=button('Detener');self.stop.clicked.connect(self.cancel);row.addWidget(self.stop);config.layout.addLayout(row)
        self.progress=QProgressBar();config.layout.addWidget(self.progress)
        self.status=label('Listo. Las validaciones SAP no abren ni modifican sesiones del usuario.','muted');self.status.setWordWrap(True);config.layout.addWidget(self.status)
        open_button=button('Abrir campaña guardada');open_button.clicked.connect(self.open_campaign);config.layout.addWidget(open_button)
        repeat_button=button('Repetir configuración guardada');repeat_button.clicked.connect(self.repeat_campaign);config.layout.addWidget(repeat_button)
        config.layout.addStretch()
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(config);split.addWidget(scroll)
        center=QWidget();cl=QVBoxLayout(center);cl.setContentsMargins(0,0,0,0)
        title=label('LABORATORIO DE OPTIMIZACIÓN','panelTitle');cl.addWidget(title)
        controls=QHBoxLayout();self.plot_type=QComboBox()
        for key,text in PLOT_TYPES.items():self.plot_type.addItem(text,key)
        self.plot_type.currentIndexChanged.connect(self.redraw);controls.addWidget(self.plot_type)
        self.seed_filter=QComboBox();self.seed_filter.addItem('Todas las semillas',None);self.seed_filter.currentIndexChanged.connect(self.redraw);controls.addWidget(self.seed_filter)
        export=button('Exportar gráfica');export.clicked.connect(self.export_plot);controls.addWidget(export)
        report=button('Informe / Excel');report.clicked.connect(self.export_report);controls.addWidget(report);cl.addLayout(controls)
        self.figure=Figure(figsize=(8,5),facecolor='#f8fbfe');self.canvas=FigureCanvasQTAgg(self.figure);cl.addWidget(NavigationToolbar2QT(self.canvas,self));cl.addWidget(self.canvas,1)
        self.table=QTableWidget(0,8);self.table.setHorizontalHeaderLabels(['Algoritmo','Semilla','Estado','Peso (lb)','Análisis','Caché','Tiempo (s)','SAP'])
        self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self.show_selection);cl.addWidget(self.table,1);split.addWidget(center)
        right=Panel('Indicadores de campaña');right.setMinimumWidth(230);right.setMaximumWidth(310)
        self.criterion=QComboBox();self.criterion.addItem('Menor peso observado','best_lb');self.criterion.addItem('Menor media factible','mean_lb');self.criterion.addItem('Mayor tasa de factibilidad','feasibility_rate');self.criterion.addItem('Menor tiempo medio','mean_seconds')
        self.criterion.currentIndexChanged.connect(self.update_metrics);right.layout.addWidget(self.criterion)
        self.metrics=QLabel('No hay resultados.');self.metrics.setWordWrap(True);self.metrics.setTextInteractionFlags(Qt.TextSelectableByMouse);right.layout.addWidget(self.metrics)
        self.selection=QLabel('Selecciona una corrida para consultar su diseño.');self.selection.setWordWrap(True);right.layout.addWidget(self.selection)
        use=button('Cargar diseño en Modelado');use.clicked.connect(self.use_winner);right.layout.addWidget(use)
        verify=button('Verificar mejores en SAP2000');verify.clicked.connect(self.verify);right.layout.addWidget(verify)
        caution=label('La clasificación describe esta campaña. Con pocas muestras no demuestra superioridad estadística.','muted');caution.setWordWrap(True);right.layout.addWidget(caution);right.layout.addStretch();split.addWidget(right)
        split.setSizes([300,960,260]);self.timer=QTimer(self);self.timer.setInterval(650);self.timer.timeout.connect(self.redraw)
        self.pause.setEnabled(False);self.stop.setEnabled(False);self.redraw()

    @property
    def running(self):return self.worker is not None
    def edit_parameters(self):
        if self.running:return
        d=QDialog(self);d.setWindowTitle('Parámetros inmutables de la campaña');d.resize(650,620);layout=QVBoxLayout(d)
        note=QLabel('Cada configuración se guarda íntegra. ASAM puro y los refinamientos híbridos se identifican por separado.');note.setWordWrap(True);layout.addWidget(note)
        editor=QPlainTextEdit(json.dumps(self.parameters,indent=2));layout.addWidget(editor)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);layout.addWidget(buttons)
        if d.exec():
            try:self.parameters=json.loads(editor.toPlainText())
            except ValueError as exc:QMessageBox.warning(self,'Parámetros inválidos',str(exc))
    def configuration(self):
        seeds=[int(v.strip()) for v in self.seeds.text().split(',')] if self.seeds.text().strip() else list(range(42,42+self.runs.value()))
        if len(seeds)!=self.runs.value():raise ValueError('Indica exactamente una semilla por corrida, o deja el campo vacío.')
        self.seeds.setText(','.join(map(str,seeds)))
        c=CampaignConfig(algorithms=[m for m,v in self.methods.items() if v.isChecked()],seeds=seeds,budget=int(self.budget.currentText()),
            engine=self.engine.currentData(),parameters=copy.deepcopy(self.parameters),sap_validation=self.validation.currentData(),
            active_ids=[int(v.strip()) for v in self.active_ids.text().split(',')] if self.active_ids.text().strip() else None,
            groups=[[int(v.strip()) for v in group.split(',')] for group in self.group_ids.text().split(';')] if self.group_ids.text().strip() else None)
        c.validate();return c
    def launch(self,function):
        self.control=RunControl();self.worker=CampaignWorker(function)
        self.worker.progress.connect(self.on_progress);self.worker.done.connect(self.accept_campaign);self.worker.failed.connect(self.error)
        self.worker.finished.connect(self.finish);self.start.setEnabled(False);self.pause.setEnabled(True);self.stop.setEnabled(True);self.timer.start();self.worker.start()
        for control in [*self.methods.values(),self.engine,self.budget,self.runs,self.seeds,self.validation,self.active_ids,self.group_ids]:control.setEnabled(False)
    def start_campaign(self):
        if self.running:return
        try:
            config=self.configuration();snapshot=self.owner.model.clone();self.begin(snapshot,config)
        except Exception as exc:self.error(str(exc))
    def begin(self,snapshot,config):
        snapshot.validate()
        from .design_space import DesignSpace
        DesignSpace(snapshot,config.active_ids,config.groups)
        self.histories={};self.live={};self.active_record=None;self.campaign={'runs':[],'configuration':{'algorithms':config.algorithms,'seeds':config.seeds},'statistics':[],'model':snapshot.to_dict()};self.table.setRowCount(0)
        self.progress.setRange(0,len(config.algorithms)*len(config.seeds));self.progress.setValue(0)
        self.constraints.setText(f'{len(snapshot.members)} barras · A {snapshot.area_min:g}–{snapshot.area_max:g} in²\nσ ±{snapshot.stress_limit:g} ksi · u ±{snapshot.displacement_limit:g} in\nHuella: {snapshot.fingerprint()[:16]}')
        self.launch(lambda notify:run_campaign(snapshot,config,Path(__file__).resolve().parents[1]/'data'/'campaigns',control=self.control,progress=notify))
    def on_progress(self,item):
        kind=item.get('type')
        if kind=='evaluation':
            self.campaign['_directory']=item['campaign_directory']
            self.live.setdefault(item['run_id'],[]).append(item)
            self.active_record={'id':item['run_id'],'algorithm':item['algorithm'],'seed':item['seed'],'status':'running','trace':''}
            self.status.setText(f'{item["algorithm"]} · semilla {item["seed"]}\n{item["evaluations"]} análisis · {item["cache_hits"]} caché · {item["elapsed_seconds"]:.1f} s\nMejor factible: {item["best_feasible_lb"]}')
        elif kind=='run_completed':
            r=item['run'];self.active_record=None;self.live.pop(r['id'],None);self.histories.pop(r['id'],None);self.progress.setValue(item['completed_runs'])
            if self.campaign is None:self.campaign={'runs':[],'configuration':{'algorithms':list(self.methods),'seeds':[]},'statistics':[],'model':self.owner.model.to_dict()}
            self.campaign['runs'].append(r);self.populate()
        else:self.status.setText(item.get('message','Validando…'))
    def accept_campaign(self,campaign):
        self.campaign=campaign;self.histories={};self.live={};self.active_record=None;self.populate();self.redraw()
        self.status.setText(f'{campaign["status"]} · {campaign.get("elapsed_seconds",0):.1f} s\n{campaign.get("_directory","")}')
    def finish(self):
        worker=self.worker;self.worker=None;self.timer.stop();self.start.setEnabled(True);self.pause.setEnabled(False);self.pause.setChecked(False);self.stop.setEnabled(False)
        if worker:worker.deleteLater()
        for control in [*self.methods.values(),self.engine,self.budget,self.runs,self.seeds,self.validation,self.active_ids,self.group_ids]:control.setEnabled(True)
    def toggle_pause(self,value):self.control.pause(value);self.pause.setText('Reanudar' if value else 'Pausar')
    def cancel(self):self.control.cancel();self.status.setText('Detención solicitada. Esperando al análisis actual…')
    def error(self,message):QMessageBox.warning(self,'Laboratorio',message)
    def populate(self):
        if not self.campaign:return
        self.table.setRowCount(len(self.campaign['runs']))
        for i,r in enumerate(self.campaign['runs']):
            values=[r['algorithm'],r['seed'],r['status'],f'{r["result"]["weight_lb"]:.6f}' if r.get('result') else '—',r['metrics']['evaluations'],r['metrics']['cache_hits'],f'{r["metrics"]["elapsed_seconds"]:.2f}',r['sap_validation']['status']]
            for j,value in enumerate(values):self.table.setItem(i,j,QTableWidgetItem(str(value)))
        current=self.seed_filter.currentData();self.seed_filter.blockSignals(True);self.seed_filter.clear();self.seed_filter.addItem('Todas las semillas',None)
        for seed in sorted({r['seed'] for r in self.campaign['runs']}):self.seed_filter.addItem(str(seed),seed)
        index=self.seed_filter.findData(current);self.seed_filter.setCurrentIndex(max(0,index));self.seed_filter.blockSignals(False);self.update_metrics()
    def redraw(self,*args):
        campaign=self.campaign
        if campaign and self.active_record:
            campaign={**campaign,'runs':campaign['runs']+[self.active_record]}
            self.histories[self.active_record['id']]=self.live[self.active_record['id']]
        draw_plot(self.figure,campaign,self.plot_type.currentData(),histories=self.histories,seed=self.seed_filter.currentData());self.canvas.draw_idle()
    def update_metrics(self,*args):
        if not self.campaign:return
        stats=self.campaign.get('statistics',[]);eligible=[s for s in stats if s['n_valid']>0 and s.get(self.criterion.currentData()) is not None]
        if not eligible:
            self.metrics.setText('Estadísticas disponibles al terminar las corridas.');return
        key=self.criterion.currentData();winner=(max if key=='feasibility_rate' else min)(eligible,key=lambda s:s[key])
        self.metrics.setText(f'Según {self.criterion.currentText().lower()}:\n{winner["algorithm"]}\n\nMejor peso: {winner["best_lb"]:,.6f} lb\nMedia: {winner["mean_lb"]:,.6f} lb\nMediana: {winner["median_lb"]:,.6f} lb\nDesviación muestral: {winner["sample_std_lb"]}\nFactibilidad: {winner["n_valid"]}/{winner["n_completed"]}\nTiempo medio: {winner["mean_seconds"]:.2f} s\n\nMuestras limitadas (<20): {"sí" if winner["limited_sample"] else "no"}')
    def selected_record(self):
        index=self.table.currentRow()
        return self.campaign['runs'][index] if self.campaign and 0<=index<len(self.campaign['runs']) else None
    def show_selection(self):
        r=self.selected_record()
        if r:self.selection.setText(f'{r["algorithm"]} · semilla {r["seed"]}\nσ máxima: {r.get("max_abs_stress_ksi","—")} ksi\nu XYZ: {r.get("max_displacement_components_in","—")} in\nSAP: {r["sap_validation"]["status"]}')
    def use_winner(self):
        r=self.selected_record()
        if not r or not r.get('result'):self.error('Selecciona una corrida con diseño factible.');return
        if self.owner.job or not self.owner.confirm_unsaved():return
        self.owner.model=winner_model(self.campaign,r);self.owner.result=copy.deepcopy(r['result']);self.owner.history=[]
        self.owner.selected=('member',self.owner.model.members[0].id);self.owner.dirty=True;self.owner.project_path=None;self.owner.refresh(True);self.owner.main_tabs.setCurrentIndex(0)
    def open_campaign(self):
        if self.running:return
        path,_=QFileDialog.getOpenFileName(self,'Abrir campaña','', 'Campaña (campaign.json)')
        if path:
            try:self.accept_campaign(load_campaign(path))
            except Exception as exc:self.error(str(exc))
    def repeat_campaign(self):
        if self.running or not self.campaign or 'model' not in self.campaign or 'parameters' not in self.campaign.get('configuration',{}):return
        try:
            from .core import Model
            self.begin(Model.from_dict(self.campaign['model']),CampaignConfig(**copy.deepcopy(self.campaign['configuration'])))
        except Exception as exc:self.error(str(exc))
    def verify(self):
        if self.running or not self.campaign or '_directory' not in self.campaign:return
        campaign=copy.deepcopy(self.campaign)
        mode=self.validation.currentData() if self.validation.currentData()!='none' else 'best_per_method'
        self.launch(lambda notify:validate_campaign(campaign,campaign['_directory'],mode,control=self.control,progress=notify))
    def export_plot(self):
        path,_=QFileDialog.getSaveFileName(self,'Exportar gráfica','comparacion.png','PNG (*.png);;SVG (*.svg);;PDF (*.pdf)')
        if path:self.figure.savefig(path,dpi=180,bbox_inches='tight')
    def export_report(self):
        if not self.campaign or self.running:return
        directory=QFileDialog.getExistingDirectory(self,'Exportar informe científico')
        if directory:
            try:
                from .lab_report import export_report
                export_report(self.campaign,directory);self.status.setText('Informe exportado: '+directory)
            except Exception as exc:self.error(str(exc))
