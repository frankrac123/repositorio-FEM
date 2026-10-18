"""Single axial stiffness kernel shared by direct analysis and optimization."""
from datetime import datetime,timezone
import numpy as np
from .analysis import design_cases,combine_cases


class TrussKernel:
    def __init__(self,model):
        model.validate(check_case=False);self.model=model.clone();self.size=3*len(model.nodes)
        self.xyz=np.array([n.xyz for n in model.nodes],float)
        self.loads=np.array([model.nodal_loads()[str(n.id)] for n in model.nodes],float).ravel()
        self.free=np.flatnonzero(~np.array([model.restraints(n) for n in model.nodes],bool).ravel())
        self.elastic=np.array([model.member_material(b).elastic_modulus for b in model.members])
        self.densities=np.array([model.member_material(b).density for b in model.members])
        lookup={n.id:i for i,n in enumerate(model.nodes)}
        dofs=[];directions=[];lengths=[]
        for b in model.members:
            i,j=lookup[b.start],lookup[b.end];delta=self.xyz[j]-self.xyz[i];length=np.linalg.norm(delta)
            lengths.append(length);directions.append(np.r_[-delta/length,delta/length])
            dofs.append(np.r_[np.arange(3*i,3*i+3),np.arange(3*j,3*j+3)])
        self.dofs=np.array(dofs);self.t=np.array(directions);self.lengths=np.array(lengths)
        self.unit=(self.elastic/self.lengths)[:,None,None]*self.t[:,:,None]*self.t[:,None,:]
        self.rows=np.broadcast_to(self.dofs[:,:,None],self.unit.shape).ravel()
        self.cols=np.broadcast_to(self.dofs[:,None,:],self.unit.shape).ravel()

    def candidate_fingerprint(self,areas):
        candidate=self.model.clone()
        for b,a in zip(candidate.members,areas):b.area=float(a)
        return candidate.fingerprint()

    def solve(self,areas):
        return combine_cases(self.model,{case:self.solve_case(areas,case) for case in design_cases(self.model)})

    def solve_case(self,areas,case):
        m=self.model;areas=np.asarray(areas,float)
        if areas.shape!=(len(m.members),) or not np.isfinite(areas).all() or np.any(areas<=0):
            raise ValueError('Se requiere un área positiva y finita por barra.')
        if case not in m.available_cases():raise ValueError('Caso de carga inexistente: '+str(case))
        K=np.zeros((self.size,self.size));np.add.at(K,(self.rows,self.cols),(areas[:,None,None]*self.unit).ravel())
        if not np.isfinite(K).all():raise ValueError('Rigidez no finita; revise las escalas del modelo.')
        reduced=K[np.ix_(self.free,self.free)];condition=float(np.linalg.cond(reduced)) if len(self.free) else 1.
        if not np.isfinite(condition) or condition>1e13:raise ValueError('Estructura inestable o mal condicionada.')
        force_map=m.nodal_loads(case,areas=areas)
        if m.structure_type=='2D' and any(abs(v[m.normal_axis])>1e-10 for v in force_map.values()):raise ValueError('Carga fuera del plano.')
        loads=np.array([force_map[str(n.id)] for n in m.nodes],float).ravel()
        if not np.isfinite(loads).all():raise ValueError('Carga resultante no finita.')
        u=np.zeros(self.size);u[self.free]=np.linalg.solve(reduced,loads[self.free]) if len(self.free) else [];reactions=K@u-loads
        stress=self.elastic/self.lengths*np.einsum('ij,ij->i',self.t,u[self.dofs])
        sr=float(np.max(abs(stress))/m.stress_limit);dr=float(np.max(abs(u[self.free]),initial=0.)/m.displacement_limit)
        balance=reactions.reshape(-1,3)+loads.reshape(-1,3)
        residual=float(np.max(abs(reactions[self.free]),initial=0.));net=balance.sum(axis=0)
        moment=np.cross(self.xyz-self.xyz.mean(axis=0),balance).sum(axis=0)
        if not np.isfinite(u).all() or not np.isfinite(reactions).all() or not np.isfinite(net).all() or not np.isfinite(moment).all() or not np.isfinite(stress).all() or residual>1e-6 or max(abs(net))>1e-6 or max(abs(moment))>1e-3:
            raise ValueError('La solución no cumple finitud, residuo o equilibrio.')
        return {'engine':'FEM · NumPy (geometría preparada)','timestamp':datetime.now(timezone.utc).isoformat(),
            'model_id':m.project_id,'model_fingerprint':self.candidate_fingerprint(areas),'analysis_status':'solved','analysis_case':case,'weight_lb':float(np.dot(areas,self.lengths*self.densities)),
            'members':[{'id':b.id,'force':float(stress[i]*areas[i]),'stress':float(stress[i]),'ratio':float(abs(stress[i])/m.stress_limit),
                'length':float(self.lengths[i]),'area':float(areas[i])} for i,b in enumerate(m.members)],
            'displacements':{str(n.id):u[3*i:3*i+3].tolist() for i,n in enumerate(m.nodes)},
            'reactions':{str(n.id):reactions[3*i:3*i+3].tolist() for i,n in enumerate(m.nodes)},
            'stress_ratio':sr,'displacement_ratio':dr,'strict_feasible':bool(sr<=1 and dr<=1),'feasibility_tolerance':1e-6,'feasible':bool(sr<=1+1e-6 and dr<=1+1e-6),
            'residual_kip':residual,'condition_number':condition,'equilibrium':{'net_force_kip':net.tolist(),'net_moment_kip_in':moment.tolist(),'passed':True}}
