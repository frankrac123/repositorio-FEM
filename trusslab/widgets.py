import math
from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath, QLinearGradient
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QSizePolicy
from .icons import icon


def label(text, name=None):
    x=QLabel(text)
    if name:x.setObjectName(name)
    return x


def button(text, name=None, color='#526783', toolbar=False):
    b=QPushButton(text)
    if name:b.setIcon(icon(name,color))
    b.setCursor(Qt.PointingHandCursor)
    b.setIconSize(QSize(21,21))
    if toolbar:b.setObjectName('toolbarButton')
    return b


class Panel(QFrame):
    def __init__(self,title='',extra=None):
        super().__init__()
        self.setObjectName('panel')
        self.layout=QVBoxLayout(self)
        self.layout.setContentsMargins(12,10,12,10)
        self.layout.setSpacing(8)
        self.header=QHBoxLayout()
        if title:self.header.addWidget(label(title,'panelTitle'))
        self.header.addStretch()
        if extra:self.header.addWidget(extra)
        self.layout.addLayout(self.header)


class Convergence(QFrame):
    def __init__(self):
        super().__init__();self.history=[];self.setMouseTracking(True)
        self.setMinimumHeight(145);self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)

    def mouseMoveEvent(self,event):
        if not self.history:return
        ratio=max(0.,min(1.,(event.position().x()-48)/max(self.width()-63,1)))
        target=ratio*max(h.get('evaluations',i+1) for i,h in enumerate(self.history))
        h=min(self.history,key=lambda h:abs(h.get('evaluations',0)-target))
        best=h.get('best_feasible_lb');best='ninguno' if best is None else f'{best:,.3f} lb'
        self.setToolTip(f'Evaluación {h.get("evaluations",0)} · {h.get("backend","FEM")}\nCandidato: {h["weight_lb"]:,.3f} lb · '+('factible' if h['feasible'] else 'INFACTIBLE')+f'\nMejor factible acumulado: {best}')
        super().mouseMoveEvent(event)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setFont(QFont('Segoe UI',8))
        r=QRectF(48,32,max(self.width()-63,10),max(self.height()-71,10))
        weights=[h['weight_lb'] for h in self.history]
        bests=[h['best_feasible_lb'] for h in self.history if h.get('best_feasible_lb') is not None]
        ymax=max(weights+bests or [15000])*1.04;ymin=min(weights+bests or [5000])*.93
        if ymax-ymin<1:ymax=ymin+1
        xmax=max([h.get('evaluations',i+1) for i,h in enumerate(self.history)] or [1])
        for i in range(6):
            y=r.top()+r.height()*i/5;x=r.left()+r.width()*i/5
            p.setPen(QPen(QColor('#e0e8f0'),.8,Qt.DotLine));p.drawLine(QPointF(r.left(),y),QPointF(r.right(),y));p.drawLine(QPointF(x,r.top()),QPointF(x,r.bottom()))
            p.setPen(QColor('#6b7c94'));p.drawText(QRectF(0,y-9,41,18),Qt.AlignRight|Qt.AlignVCenter,f'{(ymax-(ymax-ymin)*i/5)/1000:.1f}')
            p.drawText(QRectF(x-22,r.bottom()+6,44,18),Qt.AlignCenter,str(round(xmax*i/5)))
        p.setPen(QPen(QColor('#9caec2'),1));p.drawLine(r.bottomLeft(),r.bottomRight());p.drawLine(r.bottomLeft(),r.topLeft())
        p.setPen(QColor('#536a86'));p.drawText(QRectF(r.left(),self.height()-19,r.width(),17),Qt.AlignCenter,'Evaluaciones estructurales')
        p.save();p.translate(12,r.center().y());p.rotate(-90);p.drawText(QRectF(-60,-10,120,18),Qt.AlignCenter,'Peso (×1,000 lb)');p.restore()
        def point(h,w):return QPointF(r.left()+h.get('evaluations',0)/xmax*r.width(),r.bottom()-(w-ymin)/(ymax-ymin)*r.height())
        if weights:
            p.setPen(QPen(QColor('#a6bbd7'),.7));path=QPainterPath(point(self.history[0],weights[0]))
            for h in self.history[1:]:path.lineTo(point(h,h['weight_lb']))
            p.drawPath(path)
            # Red samples are infeasible; the green curve contains only the best
            # feasible weight accumulated at each completed structural evaluation.
            stride=max(1,len(self.history)//450)
            for h in self.history[::stride]+self.history[-1:]:
                p.setBrush(QColor('#2c86f6' if h['feasible'] else '#e47385'));p.setPen(Qt.NoPen);p.drawEllipse(point(h,h['weight_lb']),1.8,1.8)
            bestpath=None
            for h in self.history:
                best=h.get('best_feasible_lb')
                if best is None:continue
                pt=point(h,best)
                if bestpath is None:bestpath=QPainterPath(pt)
                else:bestpath.lineTo(pt)
            if bestpath is not None:p.setPen(QPen(QColor('#17ad76'),2));p.drawPath(bestpath)
        else:p.setPen(QColor('#8b9bb0'));p.drawText(r,Qt.AlignCenter,'Ejecuta una optimización\npara ver la convergencia')
        p.setPen(QColor('#536a86'));p.drawText(48,13,'Azul: factible · Rojo: infactible');p.setPen(QColor('#159d6e'));p.drawText(48,27,'Verde: mejor factible acumulado')
        p.end()


class Metric(QFrame):
    def __init__(self,title,glyph,unit):
        super().__init__()
        self.setObjectName('metric')
        l=QVBoxLayout(self);l.setContentsMargins(9,9,9,9);l.setSpacing(5)
        t=label(title,'metricTitle');t.setWordWrap(True);l.addWidget(t)
        im=QLabel();im.setPixmap(icon(glyph,size=22).pixmap(22,22));l.addWidget(im)
        self.value=label('—','metricValue');l.addWidget(self.value)
        self.note=label(unit,'muted');self.note.setWordWrap(True);l.addWidget(self.note)
        self.bar=QProgressBar();self.bar.setRange(0,1000);self.bar.setTextVisible(False);self.bar.setFixedHeight(6);l.addWidget(self.bar)


STYLE='''
QWidget {font-family: "Segoe UI"; font-size: 12px; color: #182842;}
QMainWindow {background: #e7edf5;}
QWidget#root {background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #f3f7fc,stop:1 #e7eef6);}
QFrame#toolbar {background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #fbfdff,stop:1 #e6effa); border-bottom: 1px solid #cbd9e8;}
QFrame#panel {background: #f9fbfe; border: 1px solid #d6e1ee; border-radius: 10px;}
QLabel {background: transparent; border: none;}
QLabel#brand {font-size: 24px; font-weight: 700; color: #102342;}
QLabel#panelTitle {font-size: 14px; font-weight: 650; color: #162640;}
QLabel#muted {font-size: 11px; color: #6c809c;}
QLabel#subtitle {font-size: 11px; color: #547198;}
QLabel#eyebrow {font-size: 10px; letter-spacing: 1px; color: #8796a9; font-weight: 600;}
QPushButton {background: #f9fbfe; border: 1px solid #d1deec; border-radius: 6px; padding: 6px 10px;}
QPushButton:hover {background: #edf5ff; border-color: #90b7ed;}
QPushButton:pressed {background: #dfecff;}
QPushButton:checked, QPushButton#primary {background: #267ff5; border-color: #267ff5; color: white;}
QPushButton:disabled {color: #9aaac0; background: #f1f4f8; border-color: #e0e7ef;}
QPushButton#toolbarButton {border: none; background: transparent; padding: 6px 12px; font-size: 11px;}
QPushButton#toolbarButton:hover {background: #dfedff;}
QFrame#toolGroup {background: #f4f8fe; border: 1px solid #dce6f1; border-radius: 10px;}
QFrame#divider {background: #cbd9e8; border: none;}
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {background: #fcfdff; border: 1px solid #d0ddec; border-radius: 5px; padding: 5px 7px; selection-background-color: #d4e7ff;}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {border-color: #5d9ff7;}
QLineEdit:read-only {background: #eff3f8; color: #647b9a;}
QComboBox {padding-right: 15px;}
QComboBox::drop-down {border: none; width: 18px;}
QTreeWidget {background: transparent; border: none; outline: 0; show-decoration-selected: 1;}
QTreeWidget::item {height: 25px; border-radius: 4px;}
QTreeWidget::item:selected {background: #e2efff; color: #1672e6;}
QTreeWidget::item:hover {background: #edf4fd;}
QHeaderView::section {background: #eef3f9; border: none; border-right: 1px solid #dce5ef; border-bottom: 1px solid #d4e0ec; padding: 6px 2px; color: #3e5572; font-size: 10px;}
QTableWidget {background: #fcfdff; border: 1px solid #dbe5f0; border-radius: 6px; gridline-color: #e4ebf3; selection-background-color: #d9eaff; selection-color: #0864df; alternate-background-color: #f5f8fc;}
QTableWidget::item {padding: 2px 4px; font-size: 11px;}
QScrollArea {background: transparent; border: none;}
QScrollBar:vertical {background: transparent; width: 5px; margin: 0;}
QScrollBar::handle:vertical {background: #cad8e7; border-radius: 2px; min-height: 25px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height: 0;}
QCheckBox {spacing: 6px; font-size: 11px;}
QCheckBox::indicator {width: 13px; height: 13px; border: 1px solid #bed0e4; border-radius: 3px; background: white;}
QCheckBox::indicator:checked {background: #398cf9; border-color: #398cf9; image: none;}
QProgressBar {border: none; border-radius: 3px; background: #e3eaf2;}
QProgressBar::chunk {border-radius: 3px; background: #28b980;}
QFrame#metric {background: #fcfdff; border: 1px solid #dbe5f0; border-radius: 6px;}
QLabel#metricTitle {font-size: 10px; color: #627792; min-height: 27px;}
QLabel#metricValue {font-size: 18px; font-weight: 700; color: #172942;}
QLabel#success {font-size: 13px; color: #0ea86c; font-weight: 600;}
QLabel#badge {background: #e7f7ef; color: #099768; border-radius: 4px; padding: 4px 7px; font-size: 10px;}
QStatusBar {background: #e5edf6; color: #67809f; font-size: 10px; border-top: 1px solid #d2dfed;}
QSplitter::handle {background: transparent;}
QMenu {background: #fcfdff; border: 1px solid #d6e1ee; padding: 5px;}
QMenu::item {padding: 7px 25px 7px 10px; border-radius: 4px;}
QMenu::item:selected {background: #e4f0ff;}
QDialog {background: #f4f8fd;}
QToolTip {background: #173154; color: white; border: none; border-radius: 4px; padding: 5px;}
'''
