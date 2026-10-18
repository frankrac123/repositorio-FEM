from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import copy
import json
import math
import hashlib


@dataclass
class Node:
    id: int
    xyz: list[float]
    fixed: list[bool] = field(default_factory=lambda: [False, True, False])
    load: list[float] = field(default_factory=lambda: [0., 0., 0.])


@dataclass
class Member:
    id: int
    start: int
    end: int
    area: float = 35.


@dataclass
class Model:
    name: str
    nodes: list[Node]
    members: list[Member]
    elastic_modulus: float = 10000.
    density: float = .1  # lb/in^3; loads and E use kip, in
    stress_limit: float = 25.
    displacement_limit: float = 2.
    area_min: float = .1
    area_max: float = 35.
    material_name: str = "Benchmark · E = 10,000 ksi"

    def clone(self):
        return copy.deepcopy(self)

    def node(self, id):
        return next(n for n in self.nodes if n.id == id)

    def length(self, member):
        return math.dist(self.node(member.start).xyz, self.node(member.end).xyz)

    def weight(self):
        return sum(self.density * m.area * self.length(m) for m in self.members)

    def validate(self):
        if len(self.nodes) < 2 or not self.members:
            raise ValueError("El modelo necesita nodos y barras.")
        ids = [n.id for n in self.nodes]
        if len(set(ids)) != len(ids) or len({m.id for m in self.members}) != len(self.members):
            raise ValueError("Hay identificadores duplicados.")
        if any(len(n.xyz) != 3 or len(n.fixed) != 3 or len(n.load) != 3 for n in self.nodes):
            raise ValueError("Cada nodo debe tener tres coordenadas, apoyos y cargas.")
        vals = [self.elastic_modulus, self.density, self.stress_limit, self.displacement_limit, self.area_min, self.area_max]
        if not all(math.isfinite(x) and x > 0 for x in vals) or self.area_min > self.area_max:
            raise ValueError("Propiedades o límites inválidos.")
        for i, n in enumerate(self.nodes):
            if not all(math.isfinite(v) for v in n.xyz + n.load):
                raise ValueError("Las coordenadas y cargas deben ser finitas.")
            if any(math.dist(n.xyz, other.xyz) < 1e-8 for other in self.nodes[:i]):
                raise ValueError("Existen nodos coincidentes.")
            if not any(n.id in (m.start, m.end) for m in self.members):
                raise ValueError(f"Nodo {n.id} desconectado.")
        edges = set()
        for m in self.members:
            if m.start not in ids or m.end not in ids:
                raise ValueError(f"Barra {m.id}: nodo inexistente.")
            if self.length(m) < 1e-8:
                raise ValueError(f"Barra {m.id}: longitud cero.")
            if not math.isfinite(m.area) or not self.area_min <= m.area <= self.area_max:
                raise ValueError(f"Barra {m.id}: área fuera de límites.")
            edge = tuple(sorted((m.start, m.end)))
            if edge in edges:
                raise ValueError("Hay barras duplicadas entre los mismos nodos.")
            edges.add(edge)

    def to_dict(self):
        return asdict(self)

    def fingerprint(self):
        """Exact snapshot identity for SAP transfers and stale-result detection."""
        return hashlib.sha256(json.dumps(self.to_dict(),sort_keys=True,allow_nan=False).encode('utf-8')).hexdigest()

    @classmethod
    def from_dict(cls, data):
        d = dict(data)
        d['nodes'] = [Node(**n) for n in d['nodes']]
        d['members'] = [Member(**m) for m in d['members']]
        model = cls(**d)
        model.validate()
        return model


def benchmark():
    nodes = [Node(1, [720., 0., 360.]), Node(2, [720., 0., 0.], load=[0., 0., -100.]),
             Node(3, [360., 0., 360.]), Node(4, [360., 0., 0.], load=[0., 0., -100.]),
             Node(5, [0., 0., 360.], [True, True, True]), Node(6, [0., 0., 0.], [True, True, True])]
    pairs = [(5, 3), (3, 1), (6, 4), (4, 2), (3, 4), (1, 2), (5, 4), (6, 3), (3, 2), (4, 1)]
    return Model("Cercha de 10 barras · Caso I", nodes, [Member(i+1, *pair) for i, pair in enumerate(pairs)])


def save_project(path, model, results=None, history=None):
    data = {'schema': 'trusslab/1', 'model': model.to_dict(), 'results': results, 'history': history or []}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def load_project(path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if data.get('schema') != 'trusslab/1':
        raise ValueError("Formato de proyecto incompatible.")
    return Model.from_dict(data['model']), data.get('results'), data.get('history', [])
