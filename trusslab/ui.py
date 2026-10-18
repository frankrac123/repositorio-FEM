from __future__ import annotations
import csv
import json
import sys
import traceback
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer
from PySide6.QtGui import QAction, QFont, QKeySequence, QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,
    QTreeWidget,QTreeWidgetItem,QTableWidget,QTableWidgetItem,QHeaderView,QSplitter,QComboBox,QDoubleSpinBox,
    QFormLayout,QScrollArea,QCheckBox,QLineEdit,QFileDialog,QMessageBox,QDialog,QDialogButtonBox,QSpinBox,QMenu,
    QInputDialog,QPlainTextEdit,QProgressBar,QAbstractItemView)
from .core import benchmark,Node,Member,save_project,load_project
from .fem import solve
from .scene import ModelScene
from .widgets import Panel,Metric,Convergence,label,button,STYLE
from .icons import icon

ROOT=Path(__file__).resolve().parents[1]


class Job(QThread):
    progress=Signal(object)
    done=Signal(object)
    failed=Signal(str)

    def __init__(self,function):
        super().__init__()
        self.function=function

    def run(self):
        try:self.done.emit(self.function(self))
        except Exception as e:self.failed.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('TrussLab 3D — Optimización estructural')
        self.setWindowIcon(icon('cube','#247df2',48))
        self.resize(1660,960)
        self.setMinimumSize(1160,720)
        self.model=benchmark()
        self.result=solve(self.model)
        self.history=[]
        self.project_path=None
        self.dirty=False
        self.selected=('member',5)
        self.job=None
        from .sap import VisibleSapSessions
        self.sap_sessions=VisibleSapSessions()
        self.sap_session_id=None
        self.last_sap_result=None
        sample=ROOT/'examples'/'Caso_I_calculado.trusslab.json'
        if sample.exists():
            try:self.model,self.result,self.history=load_project(sample)
            except Exception:pass
        root=QWidget();root.setObjectName('root');self.setCentralWidget(root)
        main=QVBoxLayout(root);main.setContentsMargins(0,0,0,0);main.setSpacing(0)
        main.addWidget(self.make_toolbar())
        body=QHBoxLayout();body.setContentsMargins(10,9,10,8);body.setSpacing(8)
        main.addLayout(body,1)
        self.explorer=self.make_explorer()
        self.explorer.setMinimumWidth(225);self.explorer.setMaximumWidth(290)
        self.properties=self.make_properties();self.properties.setMinimumWidth(277);self.properties.setMaximumWidth(345)
        self.summary=self.make_summary()
        self.scene=ModelScene();self.scene.selected_entity.connect(self.select)
        self.model_panel=self.make_model_panel()
        self.chart=Convergence()
        self.chart_panel=Panel('Convergencia de optimización')
        self.chart_panel.layout.addWidget(self.chart,1)
        self.chart_note=label('SLSQP · cálculo matricial independiente','muted');self.chart_panel.layout.addWidget(self.chart_note)
        self.table_panel=self.make_table()
        middle=QSplitter(Qt.Vertical)
        middle.setHandleWidth(8)
        middle.addWidget(self.model_panel)
        bottom=QSplitter(Qt.Horizontal);bottom.setHandleWidth(8)
        bottom.addWidget(self.chart_panel);bottom.addWidget(self.table_panel);bottom.setSizes([360,570])
        bottom.setMinimumHeight(258)
        middle.addWidget(bottom);middle.setSizes([510,280]);middle.setStretchFactor(0,3);middle.setStretchFactor(1,1)
        right=QSplitter(Qt.Vertical);right.setHandleWidth(8)
        self.summary.setMinimumHeight(258)
        right.addWidget(self.properties);right.addWidget(self.summary);right.setSizes([510,280]);right.setMinimumWidth(277);right.setMaximumWidth(345)
        allpanels=QSplitter(Qt.Horizontal);allpanels.setHandleWidth(8)
        allpanels.addWidget(self.explorer);allpanels.addWidget(middle);allpanels.addWidget(right)
        allpanels.setSizes([262,1030,322]);allpanels.setStretchFactor(1,1)
        body.addWidget(allpanels)
        self.statusBar().showMessage('Listo')
        self.status_units=label('kip · in · ksi   |   Plano XZ   |   6 nodos · 10 barras','muted')
        self.statusBar().addPermanentWidget(self.status_units)
        self.setup_shortcuts()
        self.refresh(reset=True)
        QTimer.singleShot(500,self.scene.fit)

    def make_toolbar(self):
        toolbar=QFrame();toolbar.setObjectName('toolbar');toolbar.setFixedHeight(83)
        l=QHBoxLayout(toolbar);l.setContentsMargins(20,7,18,7);l.setSpacing(17)
        logo=QLabel();logo.setPixmap(icon('cube','#267be4',43).pixmap(43,43));l.addWidget(logo)
        brand=QVBoxLayout();brand.setSpacing(0)
        brand.addWidget(label('TrussLab 3D','brand'))
        brand.addWidget(label('Modela  ·  Analiza  ·  Optimiza  ·  Conecta con SAP2000','subtitle'))
        l.addLayout(brand);l.addStretch(1)
        def group(items):
            g=QFrame();g.setObjectName('toolGroup');gl=QHBoxLayout(g);gl.setContentsMargins(5,2,5,2);gl.setSpacing(2)
            for text,glyph,color,callback in items:
                b=QPushButton();b.setObjectName('toolbarButton');b.setCursor(Qt.PointingHandCursor);b.setFixedSize(65,58)
                bl=QVBoxLayout(b);bl.setContentsMargins(9,4,9,4);bl.setSpacing(2)
                im=QLabel();im.setPixmap(icon(glyph,color,24).pixmap(24,24));im.setAlignment(Qt.AlignCenter);im.setAttribute(Qt.WA_TransparentForMouseEvents)
                tx=label(text);tx.setAlignment(Qt.AlignCenter);tx.setAttribute(Qt.WA_TransparentForMouseEvents)
                bl.addWidget(im);bl.addWidget(tx);b.clicked.connect(callback);gl.addWidget(b)
                b.setAccessibleName(text)
                if glyph=='play':self.analyze_button=b
                if glyph=='settings':self.optimize_button=b
            l.addWidget(g)
        group([('Nuevo','file','#536a8a',self.new_project),('Abrir','folder','#536a8a',self.open_project),('Guardar','save','#536a8a',self.save_project)])
        group([('Analizar','play','#257eff',self.analyze_menu),('Optimizar','settings','#10aa76',self.optimize_dialog)])
        group([('Exportar','export','#536a8a',self.export_menu)])
        l.addStretch(1)
        script=button('Python\nScripting  ⌄','code');script.clicked.connect(self.export_script);script.setMinimumHeight(48);l.addWidget(script)
        self.open_sap_button=button('ABRIR EN SAP2000','link','#ffffff')
        self.open_sap_button.setObjectName('primary');self.open_sap_button.setMinimumHeight(48)
        self.open_sap_button.setToolTip('Transferir el diseño actual, analizarlo y dejar SAP2000 abierto')
        self.open_sap_button.clicked.connect(self.open_in_sap);l.addWidget(self.open_sap_button)
        self.sap_button=button('⌄');self.sap_button.setToolTip('Actualizar, validar y consultar la integración SAP2000')
        self.sap_button.clicked.connect(self.sap_menu);self.sap_button.setFixedSize(29,48);l.addWidget(self.sap_button)
        return toolbar

    def make_explorer(self):
        p=Panel('Explorador del modelo')
        search=button('','search');search.setFixedSize(27,27);search.setToolTip('Buscar nodo o barra');search.clicked.connect(self.search_entity);p.header.addWidget(search)
        self.tree=QTreeWidget();self.tree.setHeaderHidden(True);self.tree.setIndentation(15);self.tree.setUniformRowHeights(True)
        self.tree.itemClicked.connect(self.tree_selected)
        self.tree.itemDoubleClicked.connect(self.tree_edit)
        p.layout.addWidget(self.tree,1)
        h=QHBoxLayout();h.setSpacing(5)
        add=button('Nodo','addnode');add.clicked.connect(self.add_node);h.addWidget(add)
        add=button('Barra','bar');add.clicked.connect(self.add_member);h.addWidget(add)
        remove=button('','trash');remove.setToolTip('Eliminar selección');remove.clicked.connect(self.delete_selected);h.addWidget(remove)
        p.layout.addLayout(h)
        return p

    def populate_tree(self):
        self.tree.clear()
        def item(parent,text,glyph=None,data=None):
            q=QTreeWidgetItem(parent,[text])
            if glyph:q.setIcon(0,icon(glyph,'#5c7da6',15))
            if data:q.setData(0,Qt.UserRole,data)
            return q
        project=item(self.tree,'Proyecto 1','cube')
        nodes=item(project,f'Nodos ({len(self.model.nodes)})','folder')
        for n in self.model.nodes:
            x,y,z=n.xyz
            q=item(nodes,f'●  {n.id}    ({x:g}, {y:g}, {z:g})',data=('node',n.id))
            q.setForeground(0,QColor('#607997'))
        bars=item(project,f'Barras ({len(self.model.members)})','folder')
        for m in self.model.members:item(bars,f'{m.id}     ({m.start} – {m.end})','bar',('member',m.id))
        material=item(project,'Material (1)','folder',('material',0))
        item(material,'Material del benchmark','settings',('material',0))
        item(material,f'E = {self.model.elastic_modulus:,.0f} ksi')
        cases=item(project,'Casos de carga (1)','folder')
        case=item(cases,'LC1 · Carga vertical','load',('loads',0))
        item(case,'Sin peso propio · Caso I')
        for n in self.model.nodes:
            if any(n.load):item(case,f'Nodo {n.id}: Fz = {n.load[2]:g} kips',data=('node',n.id))
        opt=item(project,'Configuración de optimización','settings',('settings',0))
        item(opt,f'Variables: {len(self.model.members)} áreas','weight',('settings',0))
        item(opt,'Objetivo: minimizar peso','chart',('settings',0))
        lim=item(opt,'Restricciones','check',('settings',0))
        item(lim,f'Esfuerzo ≤ ±{self.model.stress_limit:g} ksi')
        item(lim,f'Desplazamiento ≤ ±{self.model.displacement_limit:g} in')
        self.tree.expandAll()
        iterator=self.tree.findItems('',Qt.MatchContains|Qt.MatchRecursive)
        for q in iterator:
            if q.data(0,Qt.UserRole)==self.selected:self.tree.setCurrentItem(q);break

    def make_model_panel(self):
        p=Panel('Vista del modelo 3D')
        p.layout.setContentsMargins(2,8,2,2)
        p.header.setContentsMargins(11,0,10,0)
        views=QFrame();vl=QHBoxLayout(views);vl.setContentsMargins(0,0,0,0);vl.setSpacing(0)
        self.view_buttons={}
        for name in ['Isométrica','Frontal','Superior','Lateral']:
            b=button(name);b.setCheckable(True);b.setChecked(name=='Isométrica');b.setMinimumWidth(68)
            b.clicked.connect(lambda _,n=name:self.set_view(n));vl.addWidget(b);self.view_buttons[name]=b
        p.header.addWidget(views)
        for glyph,tooltip,action in [('cursor','Selecciona nodos y barras en la escena',lambda:self.statusBar().showMessage('Haz clic sobre un nodo o una barra. Arrastra para orbitar.')),
                ('fit','Ajustar modelo a la vista',self.scene.fit),('image','Guardar imagen de la vista',self.export_image)]:
            b=button('',glyph,'#267eff' if glyph=='cursor' else '#526783');b.setToolTip(tooltip);b.setFixedSize(30,29);b.clicked.connect(action);p.header.addWidget(b)
        self.scene.setMinimumHeight(290)
        p.layout.addWidget(self.scene,1)
        options=QHBoxLayout();options.setContentsMargins(12,0,10,3);options.setSpacing(16)
        self.checks={}
        for text,key,value in [('Numeración','labels',True),('Deformada','deformed',True),('Tracción / compresión','stress_colors',False),('Cotas','dimensions',True)]:
            c=QCheckBox(text);c.setChecked(value);c.toggled.connect(lambda v,k=key:self.scene_option(k,v));options.addWidget(c);self.checks[key]=c
        options.addStretch()
        options.addWidget(label('Orbitar: arrastrar  ·  Zoom: rueda','muted'))
        p.layout.addLayout(options)
        return p

    def make_properties(self):
        self.entity_combo=QComboBox();self.entity_combo.addItems(['Barra','Nodo']);self.entity_combo.setFixedWidth(83)
        self.entity_combo.currentIndexChanged.connect(self.entity_type_changed)
        p=Panel('Propiedades',self.entity_combo)
        self.prop_heading=label('Barra 5 (Nodo 3 – Nodo 4)','panelTitle');self.prop_heading.setStyleSheet('font-size:12px; background:#eef4fc; padding:7px; border:1px solid #d6e2ef; border-radius:5px;')
        p.layout.addWidget(self.prop_heading)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.property_body=QWidget();self.property_layout=QVBoxLayout(self.property_body);self.property_layout.setContentsMargins(2,2,2,0);self.property_layout.setSpacing(8)
        scroll.setWidget(self.property_body);p.layout.addWidget(scroll,1)
        return p

    def clear_properties(self):
        while self.property_layout.count():
            item=self.property_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()

    def show_properties(self):
        if not hasattr(self,'property_layout'):return
        self.clear_properties()
        kind,id=self.selected
        self.entity_combo.blockSignals(True);self.entity_combo.setCurrentIndex(0 if kind=='member' else 1);self.entity_combo.blockSignals(False)
        form=QFormLayout();form.setContentsMargins(0,0,0,0);form.setHorizontalSpacing(9);form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        container=QWidget();container.setLayout(form);self.property_layout.addWidget(container)
        def row(name,value,unit='',editable=False,callback=None,minimum=-1e8,maximum=1e8,decimals=3):
            wrap=QWidget();h=QHBoxLayout(wrap);h.setContentsMargins(0,0,0,0);h.setSpacing(6)
            if editable:
                field=QDoubleSpinBox();field.setRange(minimum,maximum);field.setDecimals(decimals);field.setValue(float(value));field.setKeyboardTracking(False);field.setButtonSymbols(QDoubleSpinBox.NoButtons)
                if callback:field.editingFinished.connect(lambda:callback(field.value()))
            else:
                field=QLineEdit(str(value));field.setReadOnly(True)
            field.setMinimumWidth(50);field.setMaximumWidth(160);h.addWidget(field,1)
            if unit:
                u=label(unit,'muted');u.setFixedWidth(24);h.addWidget(u)
            caption=label(name);caption.setWordWrap(True);caption.setFixedWidth(112)
            form.addRow(caption,wrap)
            return field
        if kind=='member':
            m=next((m for m in self.model.members if m.id==id),self.model.members[0])
            self.prop_heading.setText(f'Barra {m.id} (Nodo {m.start} – Nodo {m.end})')
            row('ID de barra',m.id)
            row('Nodo inicial',m.start);row('Nodo final',m.end)
            row('Longitud',f'{self.model.length(m):.2f}','in')
            row('Área (A)',m.area,'in²',True,lambda v:self.change_area(m.id,v),self.model.area_min,self.model.area_max,4)
            mat=button('Benchmark  ⌄');mat.clicked.connect(self.material_dialog);mat.setMaximumWidth(160);form.addRow('Material',mat)
            row('Módulo elástico (E)',f'{self.model.elastic_modulus:g}','ksi')
            if self.result:
                r=next(r for r in self.result['members'] if r['id']==m.id)
                row('Fuerza axial (P)',f'{r["force"]:+.3f}','kips')
                row('Esfuerzo (σ)',f'{r["stress"]:+.3f}','ksi')
                self.ratio_row(form,'Relación de esfuerzo',r['ratio'])
                row('Límite de despl.',f'{self.model.displacement_limit:.2f}','in')
                # Report end displacement magnitude and component-based constraint separately.
                u=max(sum(x*x for x in self.result['displacements'][str(n)])**.5 for n in (m.start,m.end))
                row('Máx. |u| extremos',f'{u:.3f}','in')
                rr=max(abs(x)/self.model.displacement_limit for n in (m.start,m.end) for x in self.result['displacements'][str(n)])
                self.ratio_row(form,'Relación por componente',rr)
        else:
            n=self.model.node(id)
            self.prop_heading.setText(f'Nodo {n.id} · Coordenadas y cargas')
            row('ID de nodo',n.id)
            for d,axis in enumerate('XYZ'):
                row(f'Coordenada {axis}',n.xyz[d],'in',True,lambda v,d=d:self.change_node(n.id,'xyz',d,v))
            for d,axis in enumerate('XYZ'):
                row(f'Fuerza {axis}',n.load[d],'kips',True,lambda v,d=d:self.change_node(n.id,'load',d,v))
            for d,axis in enumerate('XYZ'):
                check=QCheckBox(f'Restringir {axis}');check.setChecked(n.fixed[d]);check.toggled.connect(lambda v,d=d:self.change_node(n.id,'fixed',d,v));form.addRow('',check)
            if self.result:
                for d,axis in enumerate('XYZ'):row(f'Desplazamiento {axis}',f'{self.result["displacements"][str(n.id)][d]:+.5f}','in')
        self.property_layout.addStretch()
        note=label('Tracción (+)  ·  Compresión (−)\nUnidades del modelo: kip, in, ksi','muted');note.setWordWrap(True);self.property_layout.addWidget(note)

    def ratio_row(self,form,title,ratio):
        w=QWidget();l=QVBoxLayout(w);l.setContentsMargins(0,0,0,0);l.setSpacing(4)
        good=ratio<=1+1e-6
        text=label(f'{ratio:.3f}');text.setStyleSheet('color:'+('#0ba875' if good else '#e44b63'));l.addWidget(text)
        bar=QProgressBar();bar.setRange(0,1000);bar.setValue(min(1000,int(ratio*1000)));bar.setTextVisible(False);bar.setFixedHeight(6)
        if not good:bar.setStyleSheet('QProgressBar::chunk {background:#ec6379;}')
        l.addWidget(bar);form.addRow(title,w)

    def make_summary(self):
        p=Panel('Resumen')
        h=QHBoxLayout();h.setSpacing(10)
        self.summary_symbol=label('✓');self.summary_symbol.setStyleSheet('color:white; background:#25b982; border-radius:15px; font-size:22px; font-weight:600;');self.summary_symbol.setAlignment(Qt.AlignCenter);self.summary_symbol.setFixedSize(30,30);h.addWidget(self.summary_symbol)
        text=QVBoxLayout();text.setSpacing(2)
        self.summary_title=label('Diseño factible','success');self.summary_subtitle=label('Análisis estructural completado','muted');self.summary_subtitle.setWordWrap(True)
        text.addWidget(self.summary_title);text.addWidget(self.summary_subtitle);h.addLayout(text,1);p.layout.addLayout(h)
        cards=QHBoxLayout();cards.setSpacing(6)
        self.metric_weight=Metric('Función objetivo\nPeso','weight','lb')
        self.metric_stress=Metric('Máx. relación\nde esfuerzo','chart','Límite: 25 ksi')
        self.metric_displ=Metric('Máx. relación\nde despl.','move','Límite: 2 in')
        for m in [self.metric_weight,self.metric_stress,self.metric_displ]:cards.addWidget(m,1)
        p.layout.addLayout(cards,1)
        self.engine_label=label('Motor: FEM · NumPy','muted');self.engine_label.setWordWrap(True);p.layout.addWidget(self.engine_label)
        return p

    def make_table(self):
        p=Panel('Resultados por barra')
        self.results_export=button('','export');self.results_export.setFixedSize(26,25);self.results_export.setToolTip('Exportar resultados CSV');self.results_export.clicked.connect(self.export_csv);p.header.addWidget(self.results_export)
        self.table=QTableWidget(0,8);self.table.setHorizontalHeaderLabels(['ID','Nodos','Longitud\n(in)','Área\n(in²)','Fuerza axial\n(kips)','Esfuerzo\n(ksi)','Relación\nσ / σadm','|u| máx.\n(in)'])
        self.table.verticalHeader().hide();self.table.setAlternatingRowColors(True);self.table.setShowGrid(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(30);self.table.verticalHeader().setMinimumSectionSize(17);self.table.verticalHeader().setDefaultSectionSize(18)
        self.table.cellClicked.connect(lambda row,col:self.select('member',self.model.members[row].id))
        self.table.cellDoubleClicked.connect(lambda row,col:self.area_dialog(self.model.members[row].id))
        p.layout.addWidget(self.table,1)
        return p

    def refresh(self,reset=False):
        self.populate_tree();self.show_properties()
        self.scene.selected=self.selected;self.scene.set_model(self.model,self.result,reset)
        self.chart.history=self.history;self.chart.update()
        self.table.setRowCount(len(self.model.members))
        for i,m in enumerate(self.model.members):
            r=next((r for r in (self.result or {}).get('members',[]) if r['id']==m.id),None)
            u=max(sum(v*v for v in self.result['displacements'][str(n)])**.5 for n in (m.start,m.end)) if r else None
            values=[str(m.id),f'{m.start} – {m.end}',f'{self.model.length(m):.1f}',f'{m.area:.4f}',
                    f'{r["force"]:+.3f}' if r else '—',f'{r["stress"]:+.3f}' if r else '—',f'{r["ratio"]:.3f}' if r else '—',f'{u:.3f}' if u is not None else '—']
            for j,v in enumerate(values):
                q=QTableWidgetItem(v);q.setTextAlignment(Qt.AlignCenter)
                if r and j==6:q.setForeground(QColor('#159b70') if r['ratio']<=1+1e-6 else QColor('#dc4a63'))
                self.table.setItem(i,j,q)
            if self.selected==('member',m.id):self.table.selectRow(i)
        self.status_units.setText(f'kip · in · ksi   |   {len(self.model.nodes)} nodos · {len(self.model.members)} barras')
        if self.result:
            r=self.result;feasible=r['feasible'];opt=r.get('optimization')
            self.summary_title.setText('Diseño factible' if feasible else 'Restricciones excedidas')
            self.summary_title.setStyleSheet('color:'+('#0ba875' if feasible else '#df5168'))
            self.summary_symbol.setText('✓' if feasible else '!')
            self.summary_symbol.setStyleSheet(f'color:white; background:{"#25b982" if feasible else "#e76b80"};border-radius:15px;font-size:22px;')
            sub=f'{opt["method"]} · {opt["iterations"]} iteraciones' if opt else 'Análisis lineal completado'
            if opt and not opt['converged']:sub+=' · '+str(opt.get('message','límite alcanzado'))
            if r.get('external_validation')=='pending':sub+=' · pendiente de SAP2000'
            self.summary_subtitle.setText(sub)
            self.metric_weight.value.setText(f'{r["weight_lb"]:,.1f}')
            if opt:
                gain=100*(1-r['weight_lb']/opt['initial_weight_lb']);self.metric_weight.note.setText(f'lb   ↓ {gain:.1f}%');self.metric_weight.bar.setValue(int(gain*10))
            else:self.metric_weight.note.setText('lb');self.metric_weight.bar.setValue(0)
            self.metric_stress.value.setText(f'{r["stress_ratio"]:.3f}');self.metric_stress.note.setText(f'±{self.model.stress_limit:g} ksi');self.metric_stress.bar.setValue(min(1000,int(r['stress_ratio']*1000)))
            self.metric_displ.value.setText(f'{r["displacement_ratio"]:.3f}');self.metric_displ.note.setText(f'±{self.model.displacement_limit:g} in');self.metric_displ.bar.setValue(min(1000,int(r['displacement_ratio']*1000)))
            self.engine_label.setText('Motor: '+r['engine']+('  ·  FEM coincide ✓' if r.get('comparison',{}).get('passed') else ''))
        else:
            self.summary_title.setText('Modelo sin analizar');self.summary_subtitle.setText('Revisa geometría y apoyos')
            self.engine_label.setText('Sin resultados válidos para este modelo')
            for m in [self.metric_weight,self.metric_stress,self.metric_displ]:m.value.setText('—');m.bar.setValue(0)
        self.setWindowTitle(('● ' if self.dirty else '')+'TrussLab 3D — '+self.model.name)

    def select(self,kind,id):
        if self.job:return
        self.selected=(kind,id);self.scene.selected=self.selected;self.show_properties()
        self.scene.set_model(self.model,self.result)
        if kind=='member':
            for i,m in enumerate(self.model.members):
                if m.id==id:self.table.selectRow(i);break

    def tree_selected(self,item,column):
        data=item.data(0,Qt.UserRole)
        if not data:return
        kind,id=data
        if kind in ('node','member'):self.select(kind,id)
        elif kind=='material':self.material_dialog()
        elif kind=='settings':self.optimize_dialog()
        elif kind=='loads':self.select('node',next((n.id for n in self.model.nodes if any(n.load)),self.model.nodes[0].id))

    def tree_edit(self,item,column):
        data=item.data(0,Qt.UserRole)
        if data and data[0]=='member':self.area_dialog(data[1])

    def entity_type_changed(self,index):
        if not hasattr(self,'scene'):return
        self.select('member' if index==0 else 'node',self.model.members[0].id if index==0 else self.model.nodes[0].id)

    def set_view(self,name):
        for n,b in self.view_buttons.items():b.setChecked(n==name)
        self.scene.set_view(name)

    def scene_option(self,key,value):
        setattr(self.scene,key,value);self.scene.set_model(self.model,self.result)

    def edit(self,mutation):
        if self.job:return
        old=self.model.clone()
        try:
            mutation();self.model.validate()
        except Exception as e:
            self.model=old;self.error(str(e));self.show_properties();return
        self.dirty=True;self.history=[]
        try:self.result=solve(self.model);self.statusBar().showMessage('Modelo actualizado · resultados FEM recalculados',6000)
        except Exception as e:self.result=None;self.statusBar().showMessage(str(e))
        self.refresh()

    def change_area(self,id,value):
        m=next(m for m in self.model.members if m.id==id)
        if abs(m.area-value)>1e-10:self.edit(lambda:setattr(m,'area',value))

    def change_node(self,id,kind,d,value):
        n=self.model.node(id)
        if getattr(n,kind)[d]!=value:self.edit(lambda:getattr(n,kind).__setitem__(d,value))

    def area_dialog(self,id):
        m=next(m for m in self.model.members if m.id==id)
        value,ok=QInputDialog.getDouble(self,'Área de barra',f'Barra {id} · Área (in²)',m.area,self.model.area_min,self.model.area_max,4)
        if ok:self.change_area(id,value)

    def dialog(self,title,fields):
        d=QDialog(self);d.setWindowTitle(title);d.setMinimumWidth(350)
        l=QVBoxLayout(d);form=QFormLayout();l.addLayout(form);widgets={}
        for key,caption,value,low,high,dec in fields:
            w=QDoubleSpinBox();w.setRange(low,high);w.setDecimals(dec);w.setValue(value);form.addRow(caption,w);widgets[key]=w
        boxes=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);boxes.accepted.connect(d.accept);boxes.rejected.connect(d.reject);l.addWidget(boxes)
        return {k:w.value() for k,w in widgets.items()} if d.exec() else None

    def material_dialog(self):
        v=self.dialog('Material y límites del modelo',[
            ('E','Módulo E (ksi)',self.model.elastic_modulus,1,1e8,1),('rho','Peso específico (lb/in³)',self.model.density,.000001,10,6),
            ('stress','Esfuerzo admisible ± (ksi)',self.model.stress_limit,.01,1e5,2),('displ','Desplazamiento ± (in)',self.model.displacement_limit,.0001,1e5,4)])
        if v:
            def change():
                self.model.elastic_modulus=v['E'];self.model.density=v['rho'];self.model.stress_limit=v['stress'];self.model.displacement_limit=v['displ']
            self.edit(change)

    def add_node(self):
        if self.job:return
        v=self.dialog('Crear nodo y conectarlo',[
            ('x','Coordenada X (in)',900,-1e6,1e6,3),('y','Coordenada Y (in)',0,-1e6,1e6,3),('z','Coordenada Z (in)',180,-1e6,1e6,3),
            ('to','Conectar a nodo ID',self.model.nodes[0].id,1,1e8,0),('area','Área de la barra (in²)',10,self.model.area_min,self.model.area_max,4)])
        if not v:return
        def change():
            self.model.node(int(v['to']))
            id=max(n.id for n in self.model.nodes)+1
            self.model.nodes.append(Node(id,[v['x'],v['y'],v['z']],[False,abs(v['y'])<1e-10,False]))
            self.model.members.append(Member(max(m.id for m in self.model.members)+1,int(v['to']),id,v['area']))
            self.selected=('node',id)
        self.edit(change)

    def add_member(self):
        if self.job:return
        v=self.dialog('Crear barra entre nodos existentes',[
            ('start','Nodo inicial ID',self.model.nodes[0].id,1,1e8,0),('end','Nodo final ID',self.model.nodes[1].id,1,1e8,0),
            ('area','Área (in²)',10,self.model.area_min,self.model.area_max,4)])
        if v:
            def change():
                id=max(m.id for m in self.model.members)+1
                self.model.members.append(Member(id,int(v['start']),int(v['end']),v['area']));self.selected=('member',id)
            self.edit(change)

    def delete_selected(self):
        if self.job:return
        kind,id=self.selected
        if QMessageBox.question(self,'Eliminar elemento',f'¿Eliminar {"la barra" if kind=="member" else "el nodo"} {id}?\nAl eliminar un nodo también se eliminan sus barras.')!=QMessageBox.Yes:return
        def change():
            if kind=='member':self.model.members=[m for m in self.model.members if m.id!=id]
            else:
                self.model.nodes=[n for n in self.model.nodes if n.id!=id]
                self.model.members=[m for m in self.model.members if id not in (m.start,m.end)]
            if self.model.members:self.selected=('member',self.model.members[0].id)
        self.edit(change)

    def search_entity(self):
        value,ok=QInputDialog.getText(self,'Buscar','Escribe N3 para nodo 3, o B5 para barra 5:')
        if ok:
            try:
                kind='node' if value.strip().upper().startswith('N') else 'member';id=int(value.strip()[1:])
                exists=any(x.id==id for x in (self.model.nodes if kind=='node' else self.model.members))
                if not exists:raise ValueError()
                self.select(kind,id)
            except Exception:self.error('No se encontró ese nodo o barra.')

    def start_job(self,function,done):
        if self.job:return
        self.job=Job(function);self.analyze_button.setEnabled(False);self.optimize_button.setEnabled(False)
        self.open_sap_button.setEnabled(False);self.sap_button.setEnabled(False)
        self.properties.setEnabled(False);self.explorer.setEnabled(False)
        self.job.progress.connect(self.job_progress)
        self.job.done.connect(done)
        self.job.failed.connect(self.job_error)
        self.job.finished.connect(self.finish_job)
        self.job.start()

    def finish_job(self):
        if getattr(self,"optimization_progress",None):
            self.optimization_progress.finish();self.optimization_progress=None
        if getattr(self,'show_progress_button',None):
            self.statusBar().removeWidget(self.show_progress_button);self.show_progress_button.deleteLater();self.show_progress_button=None
        job=self.job;self.job=None
        if job:job.deleteLater()
        self.analyze_button.setEnabled(True);self.optimize_button.setEnabled(True);self.properties.setEnabled(True);self.explorer.setEnabled(True)
        self.open_sap_button.setEnabled(True);self.sap_button.setEnabled(True)

    def job_progress(self,item):
        if getattr(self,"optimization_progress",None):self.optimization_progress.update_progress(item)
        if isinstance(item,str):self.statusBar().showMessage(item)
        else:
            self.history.append(item);self.chart.history=self.history;self.chart.update()
            self.statusBar().showMessage(f'Optimizando · iteración {item["iteration"]} · {item["weight_lb"]:,.2f} lb · {item["evaluations"]} evaluaciones')

    def job_error(self,message):
        self.statusBar().showMessage('La operación no se completó')
        self.error(message)

    def analyze_menu(self):
        menu=QMenu(self)
        menu.addAction(icon('play','#287ff5'),'Analizar con FEM independiente',self.run_fem)
        menu.addAction(icon('link','#287ff5'),'Analizar con SAP2000 y comparar',self.run_sap)
        menu.exec(self.analyze_button.mapToGlobal(self.analyze_button.rect().bottomLeft()))

    def run_fem(self):
        if self.job:return
        try:
            self.result=solve(self.model);self.dirty=True;self.refresh();self.statusBar().showMessage('Análisis FEM completado · equilibrio verificado',7000)
        except Exception as e:self.error(str(e))

    def run_sap(self):
        if self.job:return
        from .sap import analyze
        snapshot=self.model.clone()
        self.start_job(lambda job:analyze(snapshot,ROOT/'data',progress=job.progress.emit),self.accept_sap_result)

    def open_in_sap(self):
        self.transfer_to_visible_sap(update=False)

    def update_in_sap(self):
        self.transfer_to_visible_sap(update=True)

    def transfer_to_visible_sap(self,update=False):
        if self.job:return
        try:
            snapshot=self.model.clone();snapshot.validate();solve(snapshot)
        except Exception as exc:
            self.error(str(exc));return
        previous=self.sap_session_id if update else None
        self.statusBar().showMessage('Actualizando en una copia nueva; la sesión anterior se conserva…' if update else 'Abriendo SAP2000 con el diseño actual…')
        self.start_job(lambda job:self.sap_sessions.open(snapshot,ROOT/'data',job.progress.emit,previous).result(),self.accept_sap_result)

    def accept_sap_result(self,result):
        if result.get('model_fingerprint')!=self.model.fingerprint():
            self.last_sap_result=result
            self.error('El modelo cambió durante la transferencia. El informe pertenece a la instantánea enviada.');return
        if self.result and 'optimization' in self.result:
            result['optimization']=self.result['optimization']
        self.result=result;self.last_sap_result=result;self.dirty=True
        if result.get('session'):self.sap_session_id=result['session']['id']
        self.refresh()
        valid=result.get('validation',{}).get('passed',result['comparison']['passed'])
        visible=result.get('mode')=='visible_persistent'
        self.statusBar().showMessage(('SAP2000 permanece abierto · ' if visible else 'Análisis automático completado · ')+('comparación y equilibrio aprobados' if valid else 'VALIDACIÓN CON DIFERENCIAS'))
        if not valid:
            self.error('Hay diferencias fuera de tolerancia, un desequilibrio o una acción no axial. Revisa la comparación. La sesión visible queda abierta para inspección.')
        elif not result['feasible']:
            self.error('SAP2000 y FEM coinciden, pero el diseño excede los límites de esfuerzo o desplazamiento.')
        if visible:self.show_comparison()

    def sap_menu(self):
        menu=QMenu(self)
        menu.addAction('Abrir diseño actual y dejar SAP2000 abierto',self.open_in_sap)
        menu.addAction('Actualizar modelo en SAP2000 (nueva copia)',self.update_in_sap)
        menu.addSeparator()
        menu.addAction('Diagnóstico de conexión',self.diagnose_sap)
        menu.addAction('Análisis automático en segundo plano',self.run_sap)
        menu.addAction('Ver comparación numérica',self.show_comparison)
        menu.addAction('RESULTADOS ESTRUCTURALES — SAP2000',self.show_sap_results)
        menu.addAction('Cómo consultar vistas y resultados en SAP2000',self.show_sap_views)
        menu.exec(self.sap_button.mapToGlobal(self.sap_button.rect().bottomLeft()))

    def diagnose_sap(self):
        from .sap import diagnose
        self.show_text('Diagnóstico SAP2000',json.dumps(diagnose(),indent=2,ensure_ascii=False))

    def show_comparison(self):
        result=self.result if self.result and 'comparison' in self.result else self.last_sap_result
        if not result:
            self.show_text('Validación SAP2000 / FEM','Este modelo aún no tiene una comparación SAP2000.\nPulsa ABRIR EN SAP2000 o Analizar → SAP2000.');return
        d=QDialog(self);d.setWindowTitle('Comparación FEM / SAP2000');d.resize(1060,640)
        layout=QVBoxLayout(d)
        validation=result.get('validation',{})
        passed=validation.get('passed',result['comparison']['passed'])
        heading=label('Comparación y equilibrio: APROBADOS' if passed else 'ADVERTENCIA: validación con diferencias','panelTitle')
        heading.setStyleSheet('color:'+('#0ba875' if passed else '#d84a61'));layout.addWidget(heading)
        if result.get('model_fingerprint')!=self.model.fingerprint():
            layout.addWidget(label('Informe de una transferencia anterior: el modelo actual cambió. Actualiza SAP2000 para volver a comparar.'))
        feasible=validation.get('design_feasible',result.get('feasible'))
        note=f'Diseño: {"cumple los límites" if feasible else "EXCEDE LOS LÍMITES"} · Esfuerzo: {result["stress_ratio"]:.6f} · Desplazamiento: {result["displacement_ratio"]:.6f}'
        layout.addWidget(label(note))
        balance=validation.get('equilibrium',{}).get('sap',{})
        if balance:
            layout.addWidget(label(f'Equilibrio SAP: ΣF = {balance["net_force_kip"]} kip · ΣM = {balance["net_moment_kip_in"]} kip·in','muted'))
        rows=result['comparison'].get('rows',[])
        table=QTableWidget(len(rows),9);table.setHorizontalHeaderLabels(['Magnitud','Elemento','Comp.','FEM','SAP2000','Diferencia abs.','Error relativo','Tolerancia abs.','Estado'])
        names={'displacement':'Desplazamiento','reaction':'Reacción','force':'Fuerza axial','stress':'Esfuerzo','weight':'Peso'}
        def number(value):return '—' if value is None else f'{value:.8g}'
        for i,row in enumerate(rows):
            values=[names.get(row['quantity'],row['quantity']),row['entity'],row['component'],number(row['fem']),number(row['sap']),
                    number(row['absolute_error'])+' '+row['unit'],'—' if row['relative_error'] is None else f'{row["relative_error"]:.3e}',
                    number(row['tolerance'])+' '+row['unit'],'OK' if row['passed'] else 'REVISAR']
            for col,text in enumerate(values):
                item=QTableWidgetItem(text)
                if col==8:item.setForeground(QColor('#159b70' if row['passed'] else '#d84a61'))
                table.setItem(i,col,item)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.setAlternatingRowColors(True)
        table.verticalHeader().hide();table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(table,1)
        relative_note=label('Error relativo = |SAP − FEM| / |FEM|. Se omite cuando |FEM| ≤ 10⁻¹². El estado usa la tolerancia absoluta.','muted');relative_note.setWordWrap(True);layout.addWidget(relative_note)
        path=label('SDB e informes JSON/CSV: '+result.get('run_directory','sin ruta'),'muted');path.setWordWrap(True);path.setTextInteractionFlags(Qt.TextSelectableByMouse);layout.addWidget(path)
        actions=QHBoxLayout();guide=button('Vistas en SAP2000');guide.clicked.connect(self.show_sap_views);actions.addWidget(guide)
        actions.addStretch();close=button('Cerrar');close.clicked.connect(d.accept);actions.addWidget(close);layout.addLayout(actions)
        self.comparison_dialog=d
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def show_sap_views(self):
        from .sap import MANUAL_VIEWS
        self.show_text('Vistas y resultados en SAP2000','SAP2000 queda visible con la geometría ajustada a la ventana.\nLa OAPI instalada permite refrescar y ajustar el zoom; las capas y vistas de resultados se activan manualmente:\n\n'+'\n\n'.join(MANUAL_VIEWS))

    def show_sap_results(self):
        result=self.result if self.result and self.result.get('engine','').startswith('SAP2000') else self.last_sap_result
        if not result or result.get('model_fingerprint')!=self.model.fingerprint():
            self.error('Analiza o abre el diseño actual en SAP2000 antes de consultar sus resultados estructurales.');return
        from .results_ui import StructuralResultsDialog
        dialog=StructuralResultsDialog(self.model,result,self);dialog.exec()

    def optimize_dialog(self):
        if self.job:return
        from .optimization_ui import OptimizationDialog,OptimizationProgress
        from .optimization import optimize,RunControl
        d=OptimizationDialog(self.model,self)
        if not d.exec():return
        config=d.configuration();snapshot=self.model.clone()
        self.history=[];self.chart.history=[];self.chart.update()
        self.chart_note.setText(f'{config["method"]} · {config["engine"]} · semilla {config["seed"]}')
        self.optimization_control=RunControl()
        self.optimization_progress=OptimizationProgress(self.optimization_control,config['max_evaluations'],self)
        self.show_progress_button=button('Ver ejecución')
        self.show_progress_button.clicked.connect(lambda:self.optimization_progress.show())
        self.statusBar().addPermanentWidget(self.show_progress_button)
        self.optimization_progress.show()
        def done(data):
            self.model,self.result,self.history=data;self.dirty=True;self.refresh()
            metadata=self.result['optimization']
            self.statusBar().showMessage(f'Búsqueda terminada: {metadata["message"]} · {metadata["evaluations"]} evaluaciones · {self.result["external_validation"]}')
        self.start_job(lambda job:optimize(snapshot,progress=job.progress.emit,
            cancelled=job.isInterruptionRequested,control=self.optimization_control,
            output_dir=ROOT/'data',**config),done)

    def confirm_unsaved(self):
        if not self.dirty:return True
        r=QMessageBox.question(self,'Proyecto modificado','¿Guardar los cambios del proyecto?',QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
        if r==QMessageBox.Cancel:return False
        if r==QMessageBox.Save:return self.save_project()
        return True

    def new_project(self):
        if self.job or not self.confirm_unsaved():return
        self.model=benchmark();self.result=solve(self.model);self.history=[];self.selected=('member',5);self.project_path=None;self.dirty=False;self.refresh(True)

    def open_project(self):
        if self.job or not self.confirm_unsaved():return
        path,_=QFileDialog.getOpenFileName(self,'Abrir proyecto',str(ROOT/'examples'),'TrussLab (*.json)')
        if path:
            try:
                m,r,h=load_project(path)
                # Recompute rather than trust cached values for a changed or external project.
                fresh=solve(m)
                if r and r.get('engine','').startswith('SAP2000'):
                    from .fem import compare
                    if not compare(m,fresh,r)['passed']:raise ValueError('Los resultados guardados no corresponden al modelo.')
                    from .validation import validation_report
                    r['validation']=validation_report(m,fresh,r)
                    r['comparison']=r['validation']['comparison']
                    r['model_fingerprint']=m.fingerprint()
                else:
                    if r and 'optimization' in r:fresh['optimization']=r['optimization']
                    r=fresh
                self.model,self.result,self.history=m,r,h;self.project_path=path;self.selected=('member',m.members[0].id);self.dirty=False;self.refresh(True)
            except Exception as e:self.error(str(e))

    def save_project(self):
        path=self.project_path
        if not path:path,_=QFileDialog.getSaveFileName(self,'Guardar proyecto',str(ROOT/'data'/'Mi_proyecto.trusslab.json'),'TrussLab (*.json)')
        if not path:return False
        try:
            save_project(path,self.model,self.result,self.history);self.project_path=path;self.dirty=False;self.setWindowTitle('TrussLab 3D — '+self.model.name);self.statusBar().showMessage('Proyecto guardado',5000);return True
        except Exception as e:self.error(str(e));return False

    def export_menu(self):
        menu=QMenu(self);menu.addAction('Resultados por barra (CSV)',self.export_csv);menu.addAction('Vista del modelo (PNG)',self.export_image);menu.addAction('Informe numérico (JSON)',self.export_report);menu.addAction('Modelo como script Python',self.export_script)
        menu.exec(self.mapToGlobal(self.centralWidget().rect().topLeft())+self.analyze_button.pos())

    def export_csv(self):
        if not self.result:self.error('Primero analiza el modelo.');return
        path,_=QFileDialog.getSaveFileName(self,'Exportar resultados',str(ROOT/'data'/'resultados.csv'),'CSV (*.csv)')
        if path:
            with open(path,'w',newline='',encoding='utf-8-sig') as file:
                rows=self.result['members'];writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            self.statusBar().showMessage('Resultados CSV exportados',5000)

    def export_image(self):
        path,_=QFileDialog.getSaveFileName(self,'Guardar vista',str(ROOT/'data'/'modelo.png'),'Imagen PNG (*.png)')
        if path:self.scene.grab().save(path);self.statusBar().showMessage('Vista guardada',5000)

    def export_report(self):
        path,_=QFileDialog.getSaveFileName(self,'Exportar informe',str(ROOT/'data'/'informe.json'),'JSON (*.json)')
        if path:save_project(path,self.model,self.result,self.history);self.statusBar().showMessage('Informe numérico exportado',5000)

    def export_script(self):
        path,_=QFileDialog.getSaveFileName(self,'Exportar modelo como Python',str(ROOT/'data'/'mi_modelo.py'),'Python (*.py)')
        if path:
            source='from trusslab.core import Model\nfrom trusslab.fem import solve\n\nmodel = Model.from_dict('+repr(self.model.to_dict())+')\nprint(solve(model))\n'
            Path(path).write_text(source,encoding='utf-8');self.statusBar().showMessage('Script exportado · ejecutar con el entorno de TrussLab',5000)

    def show_text(self,title,text):
        d=QDialog(self);d.setWindowTitle(title);d.resize(680,440);l=QVBoxLayout(d);body=QPlainTextEdit();body.setReadOnly(True);body.setPlainText(text);l.addWidget(body);b=QDialogButtonBox(QDialogButtonBox.Close);b.rejected.connect(d.reject);l.addWidget(b);d.exec()

    def setup_shortcuts(self):
        for shortcut,action in [('Ctrl+N',self.new_project),('Ctrl+O',self.open_project),('Ctrl+S',self.save_project),('F5',self.run_fem),('F6',self.run_sap),('Delete',self.delete_selected)]:
            a=QAction(self);a.setShortcut(QKeySequence(shortcut));a.triggered.connect(action);self.addAction(a)

    def error(self,message):
        QMessageBox.warning(self,'TrussLab 3D',message)

    def closeEvent(self,event):
        if self.job:
            self.error('Hay una operación en curso. Espera a que termine antes de cerrar.');event.ignore();return
        if not self.confirm_unsaved():event.ignore();return
        if not self.sap_sessions.shutdown():
            self.error('La sesión SAP todavía está liberando sus referencias. Intenta cerrar en un momento.');event.ignore();return
        self.scene.plotter.close();event.accept()


def main():
    app=QApplication(sys.argv)
    app.setStyle('Fusion');app.setFont(QFont('Segoe UI',9));app.setStyleSheet(STYLE)
    app.setApplicationName('TrussLab 3D')
    window=MainWindow();window.showMaximized()
    return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
