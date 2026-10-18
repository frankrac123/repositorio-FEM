"""Geometry prepared once; identical axial formulation to fem.solve."""
from datetime import datetime,timezone
import numpy as np


class PreparedTruss:
    def __init__(self,model):
        model.validate();self.model=model.clone();self.size=3*len(model.nodes)
        self.xyz=np.array([n.xyz for n in model.nodes],float)
        self.loads=np.array([n.load for n in model.nodes],float).ravel()
        self.free=np.flatnonzero(~np.array([n.fixed for n in model.nodes],bool).ravel())
        if not len(self.free):raise ValueError('El modelo no tiene grados de libertad libres.')
        lookup={n.id:i for i,n in enumerate(model.nodes)}
        dofs=[];directions=[];lengths=[]
        for b in model.members:
            i,j=lookup[b.start],lookup[b.end];delta=self.xyz[j]-self.xyz[i];length=np.linalg.norm(delta)
            lengths.append(length);directions.append(np.r_[-delta/length,delta/length])
            dofs.append(np.r_[np.arange(3*i,3*i+3),np.arange(3*j,3*j+3)])
        self.dofs=np.array(dofs);self.t=np.array(directions);self.lengths=np.array(lengths)
        self.unit=(model.elastic_modulus/self.lengths)[:,None,None]*self.t[:,:,None]*self.t[:,None,:]
        self.rows=np.broadcast_to(self.dofs[:,:,None],self.unit.shape).ravel()
        self.cols=np.broadcast_to(self.dofs[:,None,:],self.unit.shape).ravel()

    def solve(self,areas):
        m=self.model;areas=np.asarray(areas,float)
        if areas.shape!=(len(m.members),) or not np.isfinite(areas).all() or np.any(areas<m.area_min) or np.any(areas>m.area_max):
            raise ValueError('Áreas fuera de los límites del modelo preparado.')
        K=np.zeros((self.size,self.size));np.add.at(K,(self.rows,self.cols),(areas[:,None,None]*self.unit).ravel())
        reduced=K[np.ix_(self.free,self.free)];condition=float(np.linalg.cond(reduced))
        if not np.isfinite(condition) or condition>1e13:raise ValueError('Estructura inestable o mal condicionada.')
        u=np.zeros(self.size);u[self.free]=np.linalg.solve(reduced,self.loads[self.free]);reactions=K@u-self.loads
        stress=m.elastic_modulus/self.lengths*np.einsum('ij,ij->i',self.t,u[self.dofs])
        sr=float(np.max(abs(stress))/m.stress_limit);dr=float(np.max(abs(u[self.free]))/m.displacement_limit)
        balance=reactions.reshape(-1,3)+self.loads.reshape(-1,3)
        residual=float(max(abs(reactions[self.free])));net=balance.sum(axis=0)
        moment=np.cross(self.xyz-self.xyz.mean(axis=0),balance).sum(axis=0)
        if not np.isfinite(u).all() or not np.isfinite(stress).all() or residual>1e-6 or max(abs(net))>1e-6 or max(abs(moment))>1e-3:
            raise ValueError('La solución no cumple finitud, residuo o equilibrio.')
        return {'engine':'FEM · NumPy (geometría preparada)','timestamp':datetime.now(timezone.utc).isoformat(),
            'analysis_status':'solved','weight_lb':float(np.dot(areas,self.lengths)*m.density),
            'members':[{'id':b.id,'force':float(stress[i]*areas[i]),'stress':float(stress[i]),'ratio':float(abs(stress[i])/m.stress_limit),
                'length':float(self.lengths[i]),'area':float(areas[i])} for i,b in enumerate(m.members)],
            'displacements':{str(n.id):u[3*i:3*i+3].tolist() for i,n in enumerate(m.nodes)},
            'reactions':{str(n.id):reactions[3*i:3*i+3].tolist() for i,n in enumerate(m.nodes)},
            'stress_ratio':sr,'displacement_ratio':dr,'feasible':bool(sr<=1+1e-6 and dr<=1+1e-6),
            'residual_kip':residual,'condition_number':condition,'equilibrium':{'net_force_kip':net.tolist(),'net_moment_kip_in':moment.tolist(),'passed':True}}
