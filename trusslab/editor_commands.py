"""Document commands: geometry and assignments never invoke a solver."""
import copy
from enum import Enum
from .core import Node,Member

class Tool(str,Enum):
    SELECT='Seleccionar'
    NODE='Crear nodo'
    MEMBER='Conectar nodos'
    MOVE='Mover nodo'
    LOAD='Asignar carga'
    SUPPORT='Asignar apoyo'
    MEASURE='Medir'
    DELETE='Eliminar'

class UndoHistory:
    def __init__(self):self.undo_items=[];self.redo_items=[]
    def clear(self):self.undo_items.clear();self.redo_items.clear()
    def record(self,snapshot):
        self.undo_items.append(copy.deepcopy(snapshot));self.undo_items=self.undo_items[-100:];self.redo_items.clear()
    def undo(self,current):
        if not self.undo_items:return None
        self.redo_items.append(copy.deepcopy(current));return self.undo_items.pop()
    def redo(self,current):
        if not self.redo_items:return None
        self.undo_items.append(copy.deepcopy(current));return self.redo_items.pop()

def create_node(model,xyz):
    xyz=list(map(float,xyz))
    if model.structure_type=='2D':xyz[model.normal_axis]=model.work_elevation
    id=max((n.id for n in model.nodes),default=0)+1
    model.nodes.append(Node(id,xyz));return id

def create_member(model,start,end,area=None,material_id=None,section_id=None,group=''):
    model.node(start);model.node(end)
    id=max((m.id for m in model.members),default=0)+1
    if material_id is None and model.materials:material_id=model.materials[0].id
    if section_id is None and model.sections:section_id=model.sections[0].id
    if area is None:area=next((s.area for s in model.sections if s.id==section_id),1.)
    model.members.append(Member(id,start,end,area,material_id,section_id,group));return id

def delete_entities(model,selection):
    nodes={id for kind,id in selection if kind=='node'}
    members={id for kind,id in selection if kind=='member'}
    model.nodes=[n for n in model.nodes if n.id not in nodes]
    model.members=[m for m in model.members if m.id not in members and m.start not in nodes and m.end not in nodes]
    for pattern in model.load_patterns:
        for id in nodes:pattern.nodal_loads.pop(str(id),None)

def copy_entities(model,selection,offset):
    members=[m for m in model.members if ('member',m.id) in selection]
    ids={id for kind,id in selection if kind=='node'}|{i for m in members for i in (m.start,m.end)}
    originals=[copy.deepcopy(model.node(i)) for i in sorted(ids)];mapping={};created=[]
    for node in originals:
        new=create_node(model,[a+b for a,b in zip(node.xyz,offset)]);mapping[node.id]=new;created.append(('node',new))
    for member in members:
        id=create_member(model,mapping[member.start],mapping[member.end],member.area,member.material_id,member.section_id,member.group)
        copied=next(b for b in model.members if b.id==id)
        copied.material_id=member.material_id;copied.section_id=member.section_id
        created.append(('member',id))
    return created
