"""Explicit internal → SAP names, independent of COM and benchmark labels."""
import re,unicodedata,hashlib
from .core import LoadPattern,AnalysisCase

def slug(text):
    text=unicodedata.normalize('NFKD',str(text)).encode('ascii','ignore').decode()
    return re.sub('[^A-Za-z0-9_]+','_',text).strip('_')[:35] or 'Project'

def token(id):return slug(id)+'_'+hashlib.sha256(str(id).encode()).hexdigest()[:6]

def transfer_definition(model):
    prefix=slug(model.name)+'_'+model.project_id[:8]
    patterns=model.load_patterns or [LoadPattern('LC1','Carga histórica',nodal_loads={str(n.id):list(n.load) for n in model.nodes if any(n.load)})]
    cases={p.id:AnalysisCase(p.id,p.name,{p.id:1.}) for p in patterns}
    cases.update({c.id:c for c in model.analysis_cases})
    materials={model.member_material(b).id:model.member_material(b) for b in model.members}
    mapping={'project':prefix,'materials':{id:prefix+'_M_'+token(id) for id in materials},
             'sections':{b.id:prefix+'_S_'+str(b.id) for b in model.members},
             'patterns':{p.id:prefix+'_P_'+token(p.id) for p in patterns},
             'cases':{id:prefix+'_C_'+token(id) for id in cases}}
    return mapping,materials,patterns,cases

def pattern_forces(model,pattern_id):
    if not model.load_patterns:return {str(n.id):list(n.load) for n in model.nodes}
    clone=model.clone();clone.analysis_cases=[]
    return clone.nodal_loads(pattern_id)

def active_dof(model):
    dof=[True,True,True,False,False,False]
    if model.structure_type=='2D':dof[model.normal_axis]=False
    return dof
