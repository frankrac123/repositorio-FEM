from __future__ import annotations
import math
import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtCore import Qt, QPointF, QRectF, QTimer, QEvent, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPolygonF
from PySide6.QtWidgets import QWidget, QVBoxLayout
from .result_styles import signed_color,section_radius


class Overlay(QWidget):
    def __init__(self, scene):
        super().__init__(scene)
        self.scene = scene
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        s = self.scene
        if s.model is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(QFont('Segoe UI', 9))
        if s.labels:
            for m in s.model.members:
                a = np.array(s.model.node(m.start).xyz)
                b = np.array(s.model.node(m.end).xyz)
                mid = s.project((a+b)*.5)
                # Shift diagonal labels apart at crossings, never create a node.
                dx = -18 if (b-a)[0]*(b-a)[2] < 0 else 18
                if abs((b-a)[0]) < 1e-6:
                    dx = 17
                if abs((b-a)[2]) < 1e-6:
                    dx = 0
                rect = QRectF(mid.x()+dx-10, mid.y()-24, 21, 18)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor('#2582ef') if s.selected == ('member', m.id) else QColor(102, 125, 150, 225))
                p.drawRoundedRect(rect, 3, 3)
                p.setPen(QColor('white'))
                p.drawText(rect, Qt.AlignCenter, str(m.id))
            for n in s.model.nodes:
                pos = s.project(n.xyz)
                rect = QRectF(pos.x()+5, pos.y()-35 if n.xyz[2] > s.center[2] else pos.y()+10, 25, 25)
                p.setPen(QPen(QColor('#516783'), 1))
                p.setBrush(QColor(255,255,255,235))
                p.drawEllipse(rect)
                p.setPen(QColor('#152745'))
                p.setFont(QFont('Segoe UI', 10, QFont.DemiBold))
                p.drawText(rect, Qt.AlignCenter, str(n.id))
                p.setFont(QFont('Segoe UI', 9))
        # Loads display their real magnitude and direction from the model.
        for n in s.model.nodes:
            if not s.loads:break
            load = np.array(n.load)
            norm = np.linalg.norm(load)
            if norm < 1e-12:
                continue
            head = s.project(n.xyz)
            end = s.project(np.array(n.xyz) - load/norm*s.span*.105)
            delta = head-end
            length = math.hypot(delta.x(),delta.y()) or 1
            ux,uy = delta.x()/length, delta.y()/length
            p.setPen(QPen(QColor('#ed3d58'), 3.3, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(end, head-QPointF(ux*12,uy*12))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#ed3d58'))
            p.drawPolygon(QPolygonF([head-QPointF(ux*10,uy*10), head-QPointF(ux*25-uy*7,uy*25+ux*7), head-QPointF(ux*25+uy*7,uy*25-ux*7)]))
            p.setPen(QColor('#da2645'))
            p.setFont(QFont('Segoe UI', 10, QFont.DemiBold))
            p.drawText(QRectF(end.x()+10,end.y()-12,100,24), Qt.AlignVCenter, f'{norm:g} kips')
        if s.result and s.reactions:
            for n in s.model.nodes:
                reaction=np.array(s.result['reactions'][str(n.id)])
                norm=np.linalg.norm(reaction)
                if norm<1e-7:continue
                start=s.project(n.xyz)
                end=s.project(np.array(n.xyz)+reaction/norm*s.span*.09)
                p.setPen(QPen(QColor('#8457bb'),2.5));p.drawLine(start,end)
                d=end-start;length=math.hypot(d.x(),d.y()) or 1
                u=QPointF(d.x()/length,d.y()/length);v=QPointF(-u.y(),u.x())
                p.setBrush(QColor('#8457bb'));p.drawPolygon(QPolygonF([end,end-u*10+v*4,end-u*10-v*4]))
                p.drawText(QRectF(end.x()-65,end.y()-22,135,20),Qt.AlignCenter,f'R = {norm:.3f} kip')
        if s.result and s.displacement_labels:
            p.setPen(QColor('#8761a2'));p.setFont(QFont('Segoe UI',8))
            for n in s.model.nodes:
                pos=s.project(n.xyz)
                uz=s.result['displacements'][str(n.id)][2]
                p.drawText(QRectF(pos.x()+12,pos.y()+28,130,20),f'uz = {uz:+.4f} in')
        if s.result and s.critical:
            p.setPen(QColor('#ae741c'));p.setFont(QFont('Segoe UI',9,QFont.Bold))
            for m in s.model.members:
                r=next(r for r in s.result['members'] if r['id']==m.id)
                if r['ratio']>=.95:
                    mid=s.project((np.array(s.model.node(m.start).xyz)+np.array(s.model.node(m.end).xyz))*.5)
                    p.drawText(mid+QPointF(8,16),f'! {r["ratio"]:.3f}')
        if s.dimensions and s.view in ('Frontal','IsomÃ©trica'):
            self.draw_dimensions(p)
        # Triad uses the same XZ convention as the numerical model.
        base = QPointF(43,self.height()-46)
        p.setFont(QFont('Segoe UI',9,QFont.DemiBold))
        for tip, color, text in [(base+QPointF(36,0),'#ee4054','X'),(base+QPointF(0,-37),'#17a95e','Z'),(base+QPointF(-19,17),'#2579ff','Y')]:
            p.setPen(QPen(QColor(color),1.8))
            p.drawLine(base,tip)
            v=base-tip
            norm=math.hypot(v.x(),v.y())
            v=QPointF(v.x()/norm,v.y()/norm)
            ort=QPointF(-v.y(),v.x())
            p.setBrush(QColor(color))
            p.drawPolygon(QPolygonF([tip,tip+v*6+ort*3,tip+v*6-ort*3]))
            p.drawText(tip+QPointF(6,-2),text)
        # Legend kept away from geometry and dimensions.
        bx, by = self.width()-206, self.height()-43
        p.setFont(QFont('Segoe UI',8))
        p.setPen(QPen(QColor('#547c9f'),2))
        p.drawLine(bx,by,bx+30,by)
        p.setPen(QColor('#62758e'))
        p.drawText(bx+40,by+4,'GeometrÃ­a original')
        if s.deformed:
            p.setPen(QPen(QColor('#ef7186'),1.8,Qt.DashLine))
            p.drawLine(bx,by+19,bx+30,by+19)
            p.setPen(QColor('#62758e'))
            p.drawText(bx+40,by+23,f'Deformada Ã—{s.deform_scale:g}')
        p.end()

    def draw_dimensions(self,p):
        s=self.scene
        xs=sorted(set(n.xyz[0] for n in s.model.nodes))
        zmin=min(n.xyz[2] for n in s.model.nodes)
        zmax=max(n.xyz[2] for n in s.model.nodes)
        ymin=min(n.xyz[1] for n in s.model.nodes)
        p.setFont(QFont('Segoe UI',9))
        p.setPen(QPen(QColor('#5f738c'),.8))
        for a,b in zip(xs,xs[1:]):
            if len(xs)>10: break
            pa=s.project([a,ymin,zmin-s.span*.095]); pb=s.project([b,ymin,zmin-s.span*.095])
            p.drawLine(pa,pb)
            for t in (pa,pb): p.drawLine(t+QPointF(0,-8),t+QPointF(0,8))
            p.drawText(QRectF((pa.x()+pb.x())/2-40,(pa.y()+pb.y())/2-22,80,20),Qt.AlignCenter,f'{b-a:g} in')
        if zmax>zmin:
            pa=s.project([xs[-1]+s.span*.075,ymin,zmin]);pb=s.project([xs[-1]+s.span*.075,ymin,zmax])
            p.drawLine(pa,pb)
            p.drawLine(pa+QPointF(-7,0),pa+QPointF(7,0));p.drawLine(pb+QPointF(-7,0),pb+QPointF(7,0))
            p.drawText(QRectF((pa.x()+pb.x())/2+9,(pa.y()+pb.y())/2-10,70,20),Qt.AlignVCenter,f'{zmax-zmin:g} in')


class ModelScene(QWidget):
    selected_entity = Signal(str,int)

    def __init__(self):
        super().__init__()
        self.model=None
        self.result=None
        self.selected=('member',5)
        self.labels=True
        self.dimensions=True
        self.deformed=True
        self.stress_colors=False
        self.result_quantity='stress'
        self.loads=True
        self.reactions=False
        self.displacement_labels=False
        self.critical=False
        self.section_scale=1.5
        self.deform_scale=12.
        self.view='IsomÃ©trica'
        self.center=np.array([360.,0.,180.])
        self.span=720.
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        # Static geometry needs no perpetual render loop; camera interactions
        # and explicit model changes render on demand. Overlay has its own timer.
        self.plotter=QtInteractor(self, auto_update=False)
        layout.addWidget(self.plotter.interactor)
        self.plotter.set_background('#e8f0f7', top='#f8fbff')
        self.plotter.enable_parallel_projection()
        self.plotter.interactor.installEventFilter(self)
        self.overlay=Overlay(self)
        self.overlay.raise_()
        self.timer=QTimer(self)
        self.timer.timeout.connect(self.overlay.update)
        self.timer.start(100)
        self.press_pos=None

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect())

    def project(self, xyz):
        r=self.plotter.renderer
        r.SetWorldPoint(*[float(x) for x in xyz],1.)
        r.WorldToDisplay()
        x,y,_=r.GetDisplayPoint()
        rw,rh=r.GetSize()
        return QPointF(x*self.width()/max(rw,1),(rh-y)*self.height()/max(rh,1))

    def eventFilter(self,obj,event):
        if event.type()==QEvent.MouseButtonPress:
            self.press_pos=event.position()
        elif event.type()==QEvent.MouseButtonRelease and self.press_pos is not None:
            pos=event.position()
            if (pos-self.press_pos).manhattanLength()<5 and event.button()==Qt.LeftButton:
                self.pick(pos)
            self.press_pos=None
        return False

    def pick(self,pos):
        if self.model is None: return
        for n in self.model.nodes:
            if (self.project(n.xyz)-pos).manhattanLength()<20:
                self.selected_entity.emit('node',n.id)
                return
        best=(14,None)
        point=np.array([pos.x(),pos.y()])
        for m in self.model.members:
            a=self.project(self.model.node(m.start).xyz);b=self.project(self.model.node(m.end).xyz)
            a=np.array([a.x(),a.y()]);b=np.array([b.x(),b.y()])
            v=b-a
            dist=np.linalg.norm(point-(a+np.clip(np.dot(point-a,v)/max(np.dot(v,v),1),0,1)*v))
            if dist<best[0]:best=(dist,m.id)
        if best[1] is not None:self.selected_entity.emit('member',best[1])

    def set_model(self,model,result=None,reset=False):
        self.model=model
        self.result=result
        xyz=np.array([n.xyz for n in model.nodes])
        self.center=(xyz.min(axis=0)+xyz.max(axis=0))*.5
        self.span=max(float(np.ptp(xyz,axis=0).max()),1.)
        camera=self.plotter.camera_position if not reset else None
        self.plotter.clear()
        self.plotter.set_background('#e8f0f7',top='#f8fbff')
        radius=self.span*.0055
        forces={r['id']:r for r in result['members']} if result else {}
        quantity=self.result_quantity
        maxvalue=max((abs(r.get(quantity,r['stress'])) for r in forces.values()),default=0.)
        for m in model.members:
            a,b=model.node(m.start).xyz,model.node(m.end).xyz
            color='#5f92bc'
            if self.stress_colors and m.id in forces:
                color=signed_color(forces[m.id].get(quantity,forces[m.id]['stress']),maxvalue)
            if self.selected==('member',m.id) and not self.stress_colors:color='#2385ec'
            tube=pv.Line(a,b).tube(radius=section_radius(m.area,self.section_scale),n_sides=20)
            self.plotter.add_mesh(tube,color=color,smooth_shading=True,specular=.8,specular_power=45,ambient=.22,render=False)
        for n in model.nodes:
            self.plotter.add_mesh(pv.Sphere(radius=radius*2.7,center=n.xyz,theta_resolution=24,phi_resolution=24),
                                  color='#3786c1' if self.selected!=('node',n.id) else '#ffb13f',smooth_shading=True,specular=.9,specular_power=35,ambient=.18,render=False)
            if n.fixed[0] and n.fixed[2]:
                x,y,z=n.xyz
                d=self.span*.046
                support=pv.PolyData(np.array([[x-d,y,z-d*.65],[x-d,y,z+d*.65],[x,y,z]]),faces=[3,0,1,2])
                self.plotter.add_mesh(support,color='#8397ac',show_edges=True,edge_color='#5e728a',ambient=.6,render=False)
                for i in range(6):
                    z0=z-d*.7+i*d*.28
                    self.plotter.add_mesh(pv.Line([x-d*1.3,y,z0-d*.2],[x-d,y,z0+d*.1]),color='#687e95',line_width=1,render=False)
        # A reference grid on the XY plane below the structure.
        floor=float(xyz[:,2].min())-self.span*.045
        step=self.span/12
        cx,cy,_=self.center
        for i in range(-12,13):
            c='#dae4ee' if i%3 else '#cddbe8'
            self.plotter.add_mesh(pv.Line([cx-2*self.span,cy+i*step,floor],[cx+2*self.span,cy+i*step,floor]),color=c,line_width=.6,opacity=.6,render=False)
            self.plotter.add_mesh(pv.Line([cx+i*step,cy-2*self.span,floor],[cx+i*step,cy+2*self.span,floor]),color=c,line_width=.6,opacity=.6,render=False)
        if result and self.deformed:
            for m in model.members:
                a=np.array(model.node(m.start).xyz)+self.deform_scale*np.array(result['displacements'][str(m.start)])
                b=np.array(model.node(m.end).xyz)+self.deform_scale*np.array(result['displacements'][str(m.end)])
                for t in np.arange(0,1,.075):
                    self.plotter.add_mesh(pv.Line(a+(b-a)*t,a+(b-a)*min(t+.04,1)),color='#ef96a4',line_width=1.5,opacity=.85,render=False)
        if camera is None:self.set_view(self.view)
        else:self.plotter.camera_position=camera
        self.plotter.render()
        self.overlay.update()

    def set_view(self,name):
        self.view=name
        c=self.center
        if name=='Frontal':eye=c+np.array([0,-2*self.span,0]);up=(0,0,1)
        elif name=='Superior':eye=c+np.array([0,0,2*self.span]);up=(0,1,0)
        elif name=='Lateral':eye=c+np.array([2*self.span,0,0]);up=(0,0,1)
        else:eye=c+np.array([.09*self.span,-2.2*self.span,.22*self.span]);up=(0,0,1)
        self.plotter.camera_position=[eye.tolist(),c.tolist(),up]
        self.plotter.camera.parallel_projection=True
        self.fit()

    def fit(self):
        aspect=max(self.width(),1)/max(self.height(),1)
        height=max(np.ptp(np.array([n.xyz for n in self.model.nodes]),axis=0)[2],self.span*.3) if self.model else self.span*.5
        self.plotter.camera.parallel_scale=max(height*.71,self.span/(max(aspect,.1)*1.55))
        self.plotter.render()
        self.overlay.update()

    def closeEvent(self,event):
        self.timer.stop()
        self.plotter.close()
        super().closeEvent(event)
