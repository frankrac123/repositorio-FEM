"""Structural document: draft integrity, analysis preconditions and JSON migration."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import copy
import json
import math
import hashlib
import uuid
from .engineering_types import BoundaryCondition
from .units import lb_to_kip

@dataclass
class Node:
    id: int
    xyz: list[float]
    fixed: list[bool] = field(default_factory=lambda: [False, False, False])
    load: list[float] = field(default_factory=lambda: [0., 0., 0.])

@dataclass
class Member:
    id: int
    start: int
    end: int
    area: float = 35.
    material_id: str | None = None
    section_id: str | None = None
    group: str = ''
    element_type: str = 'truss'

Element = Member

@dataclass
class Material:
    id: str
    name: str
    elastic_modulus: float
    density: float

@dataclass
class Section:
    id: str
    name: str
    area: float
    section_type: str = 'axial'

@dataclass
class LoadPattern:
    id: str
    name: str
    load_type: str = 'Other'
    nodal_loads: dict[str, list[float]] = field(default_factory=dict)
    self_weight: float = 0.

@dataclass
class AnalysisCase:
    id: str
    name: str
    factors: dict[str, float] = field(default_factory=dict)

@dataclass
class Model:
    name: str
    nodes: list[Node]
    members: list[Member]
    elastic_modulus: float = 10000.
    density: float = .1
    stress_limit: float = 25.
    displacement_limit: float = 2.
    area_min: float = .1
    area_max: float = 35.
    material_name: str = 'Benchmark · E = 10,000 ksi'
    project_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    structure_type: str = '3D'
    units: str = 'kip-in-ksi'
    work_plane: str = 'XZ'
    work_elevation: float = 0.
    grid_step: float = 25.
    materials: list[Material] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    load_patterns: list[LoadPattern] = field(default_factory=list)
    analysis_cases: list[AnalysisCase] = field(default_factory=list)
    active_case: str = 'LC1'
    optimization_config: dict = field(default_factory=dict)
    load_storage: str = 'legacy'

    @classmethod
    def empty(cls, dimension='3D', plane='XZ', name='Nuevo proyecto'):
        return cls(name, [], [], elastic_modulus=29000., density=.283,
                   material_name='Acero · E = 29,000 ksi', structure_type=dimension,
                   work_plane=plane, load_storage='patterns', materials=[Material('M1','Acero',29000.,.283)],
                   sections=[Section('S1','Área 1 in²',1.)],
                   load_patterns=[LoadPattern('LC1','Carga 1')],
                   analysis_cases=[AnalysisCase('LC1','Caso 1',{'LC1':1.})])

    def clone(self):return copy.deepcopy(self)

    def node(self,id):
        try:return next(n for n in self.nodes if n.id==id)
        except StopIteration:raise ValueError(f'No existe el nodo {id}.') from None

    def length(self,member):return math.dist(self.node(member.start).xyz,self.node(member.end).xyz)

    def member_material(self,member):
        if member.material_id is None:return Material('legacy',self.material_name,self.elastic_modulus,self.density)
        try:return next(m for m in self.materials if m.id==member.material_id)
        except StopIteration:raise ValueError(f'Barra {member.id}: material inexistente.') from None

    def weight(self):return sum(self.member_material(m).density*m.area*self.length(m) for m in self.members)

    @property
    def normal_axis(self):return {'XY':2,'XZ':1,'YZ':0}[self.work_plane]

    def restraints(self,node):
        fixed=list(node.fixed)
        if self.structure_type=='2D':fixed[self.normal_axis]=True
        return fixed

    @property
    def supports(self):
        """User supports only; out-of-plane analysis constraints stay separate."""
        return [BoundaryCondition(n.id,list(n.fixed)) for n in self.nodes if any(n.fixed)]

    def set_support(self,condition):
        condition.validate();self.node(condition.node_id).fixed=list(condition.restrained)

    def case_factors(self,case=None):
        case=case or self.active_case
        found=next((c for c in self.analysis_cases if c.id==case),None)
        return found.factors if found else {case:1.}

    def available_cases(self):
        return {c.id for c in self.analysis_cases}|{p.id for p in self.load_patterns} or ({'LC1'} if self.load_storage=='legacy' else set())

    def nodal_loads(self,case=None,areas=None):
        loads={str(n.id):[0.,0.,0.] for n in self.nodes}
        if not self.load_patterns:return {str(n.id):list(n.load) if self.load_storage=='legacy' else [0.,0.,0.] for n in self.nodes}
        factors=self.case_factors(case)
        for p in self.load_patterns:
            factor=factors.get(p.id,0.)
            for id,values in p.nodal_loads.items():
                if id in loads:loads[id]=[a+factor*b for a,b in zip(loads[id],values)]
            if p.self_weight and factor:
                for i,m in enumerate(self.members):
                    weight=lb_to_kip(self.member_material(m).density*(m.area if areas is None else areas[i])*self.length(m))
                    for id in (m.start,m.end):loads[str(id)][2]-=factor*p.self_weight*weight/2
        return loads

    def pattern_load(self,node_id,pattern_id):
        if not self.load_patterns:return list(self.node(node_id).load) if self.load_storage=='legacy' else [0.,0.,0.]
        p=next(p for p in self.load_patterns if p.id==pattern_id)
        return list(p.nodal_loads.get(str(node_id),[0.,0.,0.]))

    def set_nodal_load(self,node_id,pattern_id,vector):
        self.node(node_id)
        if not self.load_patterns and self.load_storage=='legacy':
            self.load_patterns=[LoadPattern('LC1','Carga histórica',nodal_loads={str(n.id):list(n.load) for n in self.nodes if any(n.load)})]
            self.analysis_cases=[AnalysisCase('LC1','Caso 1',{'LC1':1.})]
        self.load_storage='patterns'
        p=next((p for p in self.load_patterns if p.id==pattern_id),None)
        if p is None:raise ValueError('Seleccione un patrón de carga existente.')
        if any(vector):p.nodal_loads[str(node_id)]=list(vector)
        else:p.nodal_loads.pop(str(node_id),None)
        if pattern_id=='LC1':self.node(node_id).load=list(vector)

    def validate_integrity(self):
        if self.load_storage not in ('legacy','patterns'):raise ValueError('Almacenamiento de cargas inválido.')
        ids=[n.id for n in self.nodes]
        if len(set(ids))!=len(ids) or len({m.id for m in self.members})!=len(self.members):raise ValueError('Hay identificadores duplicados.')
        if any(type(i) is not int or i<1 for i in ids+[m.id for m in self.members]):raise ValueError('Los identificadores deben ser enteros positivos.')
        if self.structure_type not in ('2D','3D') or self.work_plane not in ('XY','XZ','YZ'):raise ValueError('Tipo estructural o plano inválido.')
        if self.units!='kip-in-ksi':raise ValueError('Unidades no implementadas; utilice kip, in, ksi.')
        vals=[self.elastic_modulus,self.density,self.stress_limit,self.displacement_limit,self.area_min,self.area_max,self.grid_step]
        if not all(math.isfinite(x) and x>0 for x in vals) or self.area_min>self.area_max or not math.isfinite(self.work_elevation):raise ValueError('Propiedades o límites inválidos.')
        for i,n in enumerate(self.nodes):
            if len(n.xyz)!=3 or len(n.fixed)!=3 or len(n.load)!=3 or not all(type(v) is bool for v in n.fixed) or not all(math.isfinite(v) for v in n.xyz+n.load):raise ValueError('Cada nodo requiere tres coordenadas, restricciones y cargas finitas.')
            if any(math.dist(n.xyz,o.xyz)<1e-8 for o in self.nodes[:i]):raise ValueError('Existen nodos coincidentes.')
            if self.structure_type=='2D' and abs(n.xyz[self.normal_axis]-self.work_elevation)>1e-8:raise ValueError(f'Nodo {n.id} fuera del plano {self.work_plane}.')
        for collection in (self.materials,self.sections,self.load_patterns,self.analysis_cases):
            if any(not isinstance(x.id,str) or not x.id.strip() for x in collection):raise ValueError('La biblioteca requiere identificadores de texto no vacíos.')
            if len({x.id for x in collection})!=len(collection):raise ValueError('Identificadores de biblioteca duplicados.')
        for mat in self.materials:
            if not all(math.isfinite(v) and v>0 for v in (mat.elastic_modulus,mat.density)):raise ValueError('Material inválido.')
        for sec in self.sections:
            if sec.section_type!='axial' or not math.isfinite(sec.area) or sec.area<=0:raise ValueError('Sección axial inválida.')
        edges=set()
        for m in self.members:
            if m.start not in ids or m.end not in ids:raise ValueError(f'Barra {m.id}: nodo inexistente.')
            if m.start==m.end or self.length(m)<1e-8:raise ValueError(f'Barra {m.id}: longitud cero.')
            if not math.isfinite(m.area) or m.area<=0:raise ValueError(f'Barra {m.id}: área no positiva.')
            if m.element_type!='truss':raise ValueError('Solo se implementan elementos axiales de cercha.')
            self.member_material(m)
            if m.section_id and not any(s.id==m.section_id for s in self.sections):raise ValueError('Sección inexistente.')
            edge=tuple(sorted((m.start,m.end)))
            if edge in edges:raise ValueError('Hay barras duplicadas entre los mismos nodos.')
            edges.add(edge)
        for p in self.load_patterns:
            if not math.isfinite(p.self_weight):raise ValueError('Peso propio inválido.')
            for id,vector in p.nodal_loads.items():
                if id not in {str(i) for i in ids} or len(vector)!=3 or not all(math.isfinite(v) for v in vector):raise ValueError('Carga nodal inválida.')
        for c in self.analysis_cases:
            if not c.factors or not set(c.factors)<={p.id for p in self.load_patterns} or not all(math.isfinite(v) for v in c.factors.values()):raise ValueError('Caso de análisis inválido.')

    def analysis_issues(self,case=None,check_case=True):
        self.validate_integrity();issues=[]
        if len(self.nodes)<2:issues.append('Se necesitan al menos dos nodos.')
        if not self.members:issues.append('No hay barras.')
        for n in self.nodes:
            if not any(n.id in (m.start,m.end) for m in self.members):issues.append(f'Nodo {n.id} desconectado.')
        if self.nodes and not any(any(self.restraints(n)) for n in self.nodes):issues.append('No hay restricciones de apoyo.')
        case=case or self.active_case
        if check_case and case not in self.available_cases():issues.append('Seleccione un caso de carga existente.')
        if check_case and self.structure_type=='2D' and any(abs(v[self.normal_axis])>1e-10 for v in self.nodal_loads(case).values()):issues.append('Hay fuerzas fuera del plano de análisis 2D.')
        return issues

    def validate(self,case=None,check_case=True):
        issues=self.analysis_issues(case,check_case)
        if issues:raise ValueError('Modelo incompleto:\n'+'\n'.join(issues))

    def to_dict(self):return asdict(self)

    def fingerprint(self):return hashlib.sha256(json.dumps(self.to_dict(),sort_keys=True,allow_nan=False).encode('utf-8')).hexdigest()

    @classmethod
    def from_dict(cls,data):
        d=copy.deepcopy(data);d['nodes']=[Node(**n) for n in d['nodes']];d['members']=[Member(**m) for m in d['members']]
        for key,entity in [('materials',Material),('sections',Section),('load_patterns',LoadPattern),('analysis_cases',AnalysisCase)]:d[key]=[entity(**v) for v in d.get(key,[])]
        if 'project_id' not in d:d['project_id']=uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(data,sort_keys=True)).hex
        d.setdefault('load_storage','patterns' if d.get('load_patterns') else 'legacy')
        model=cls(**d);model.validate_integrity();return model

StructuralModel=Model

def benchmark():
    nodes=[Node(1,[720.,0.,360.],[False,True,False]),Node(2,[720.,0.,0.],[False,True,False],[0.,0.,-100.]),
           Node(3,[360.,0.,360.],[False,True,False]),Node(4,[360.,0.,0.],[False,True,False],[0.,0.,-100.]),
           Node(5,[0.,0.,360.],[True,True,True]),Node(6,[0.,0.,0.],[True,True,True])]
    pairs=[(5,3),(3,1),(6,4),(4,2),(3,4),(1,2),(5,4),(6,3),(3,2),(4,1)]
    return Model('Cercha de 10 barras · Caso I',nodes,[Member(i+1,*p) for i,p in enumerate(pairs)],project_id='benchmark-case-i')

def save_project(path,model,results=None,history=None):
    model.validate_integrity()
    if results and results.get('model_fingerprint')!=model.fingerprint():results=None;history=[]
    data={'schema':'trusslab/3','model':model.to_dict(),'results':results,'history':history or []}
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def load_project(path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if data.get('schema') not in ('trusslab/1','trusslab/2','trusslab/3'):raise ValueError('Formato de proyecto incompatible.')
    model=Model.from_dict(data['model']);result=data.get('results')
    history=data.get('history',[])
    if result:
        old=hashlib.sha256(json.dumps(data['model'],sort_keys=True,allow_nan=False).encode('utf-8')).hexdigest()
        recorded=result.get('model_fingerprint')
        compatible=recorded==model.fingerprint() or (data['schema']!='trusslab/3' and recorded in (None,old))
        try:
            if not compatible:raise ValueError('La huella del resultado no coincide.')
            from .fem import solve
            from .validation import detailed_compare
            stored=result.get('case_results') or {result.get('analysis_case',model.active_case):result}
            fresh_cases={}
            for case,cached in stored.items():
                fresh=solve(model,case=case);fresh_cases[case]=fresh
                if not detailed_compare(model,fresh,cached)['passed']:raise ValueError('Resultados numéricos obsoletos.')
                for key in ('stress_ratio','displacement_ratio'):
                    if not math.isclose(float(cached[key]),fresh[key],rel_tol=1e-6,abs_tol=1e-8):raise ValueError('Razones de utilización obsoletas.')
                for key in ('stress_ratio','displacement_ratio','feasible','strict_feasible','feasibility_tolerance'):
                    cached[key]=fresh[key]
            from .analysis import combine_cases
            expected=combine_cases(model,fresh_cases)
            if not detailed_compare(model,expected,result)['passed']:raise ValueError('El caso representado no corresponde al resultado.')
            for key in ('stress_ratio','displacement_ratio'):
                if not math.isclose(float(result[key]),expected[key],rel_tol=1e-6,abs_tol=1e-8):raise ValueError('Envolvente obsoleta.')
            for key in ('stress_ratio','displacement_ratio','feasible','strict_feasible','feasibility_tolerance'):
                result[key]=expected[key]
            result['migration_source_fingerprint']=recorded or old
            result['model_fingerprint']=model.fingerprint()
            for cached in result.get('case_results',{}).values():cached['model_fingerprint']=model.fingerprint()
        except (ValueError,KeyError,TypeError,IndexError):
            import warnings
            warnings.warn('Se descartaron resultados e historial obsoletos o incompatibles.',RuntimeWarning)
            result=None;history=[]
    return model,result,history
