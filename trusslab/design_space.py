"""Size variables, optional groups and fixed members; independent of geometry."""
import numpy as np


class DesignSpace:
    def __init__(self,model,active_ids=None,groups=None):
        self.model=model.clone();self.model.validate()
        if model.area_min==model.area_max:raise ValueError('Los límites de área son iguales; no existe intervalo para optimizar.')
        ids={m.id for m in model.members};active=ids if active_ids is None else set(active_ids)
        if not active or not active<=ids:raise ValueError('La selección de barras optimizables no es válida.')
        self.groups=[];seen=set()
        for group in groups or []:
            group=list(group)
            if not group or not set(group)<=active or seen.intersection(group) or len(set(group))!=len(group):
                raise ValueError('Los grupos deben ser disjuntos y contener barras optimizables existentes.')
            self.groups.append(group);seen.update(group)
        self.groups.extend([[m.id] for m in model.members if m.id in active-seen])
        by_id={m.id:m for m in model.members}
        self.initial=np.array([np.mean([by_id[i].area for i in group]) for group in self.groups])
        self.lower=np.full(len(self.groups),model.area_min);self.upper=np.full(len(self.groups),model.area_max)
        self.fixed_ids=sorted(ids-active)

    def expand(self,variables):
        x=np.asarray(variables,dtype=float)
        if x.shape!=self.initial.shape or not np.isfinite(x).all():raise ValueError('Vector de áreas inválido.')
        if np.any(x<self.lower-1e-9) or np.any(x>self.upper+1e-9):raise ValueError('Áreas fuera de los límites de diseño.')
        x=np.clip(x,self.lower,self.upper)
        m=self.model.clone();lookup={b.id:b for b in m.members}
        for value,group in zip(x,self.groups):
            for id in group:lookup[id].area=float(value)
        return m

    def descriptor(self):
        return {'type':'size','groups':self.groups,'fixed_member_ids':self.fixed_ids,
                'lower':self.lower.tolist(),'upper':self.upper.tolist()}
