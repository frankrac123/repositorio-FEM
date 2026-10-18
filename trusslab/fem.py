"""Linear axial truss stiffness solver, arbitrary geometry, 3 translations/node.

Units: kip, inch, ksi. Objective weight is lb. Positive axial force is tension.
Only explicitly restrained translations are removed. No artificial stiffness.
"""
from __future__ import annotations
from datetime import datetime, timezone
import numpy as np


def solve(model):
    model.validate()
    count = len(model.nodes)
    lookup = {n.id: i for i, n in enumerate(model.nodes)}
    K = np.zeros((3*count, 3*count))
    F = np.array([n.load for n in model.nodes], dtype=float).reshape(-1)
    free = np.flatnonzero(~np.array([n.fixed for n in model.nodes], dtype=bool).reshape(-1))
    if not len(free):
        raise ValueError("El modelo no tiene grados de libertad libres.")
    elements = []
    for m in model.members:
        i, j = lookup[m.start], lookup[m.end]
        a, b = np.array(model.nodes[i].xyz), np.array(model.nodes[j].xyz)
        L = np.linalg.norm(b-a)
        direction = (b-a)/L
        t = np.r_[-direction, direction]
        dofs = np.r_[np.arange(3*i, 3*i+3), np.arange(3*j, 3*j+3)]
        K[np.ix_(dofs, dofs)] += model.elastic_modulus*m.area/L*np.outer(t, t)
        elements.append((m, dofs, t, L))
    reduced = K[np.ix_(free, free)]
    condition = float(np.linalg.cond(reduced))
    if not np.isfinite(condition) or condition > 1e13:
        raise ValueError("Estructura inestable: mecanismo, apoyos insuficientes o grados libres sin rigidez.")
    u = np.zeros(3*count)
    u[free] = np.linalg.solve(reduced, F[free])
    reactions = K @ u-F
    members = []
    for m, dofs, t, L in elements:
        stress = model.elastic_modulus/L*float(t @ u[dofs])
        members.append({'id': m.id, 'force': stress*m.area, 'stress': stress,
                        'ratio': abs(stress)/model.stress_limit, 'length': float(L), 'area': m.area})
    max_stress = max(r['ratio'] for r in members)
    max_displ = float(max(abs(u[free]))) / model.displacement_limit
    residual = float(max(abs(reactions[free])))
    return {'engine': 'FEM · NumPy', 'timestamp': datetime.now(timezone.utc).isoformat(),
            'weight_lb': model.weight(), 'members': members,
            'displacements': {str(n.id): u[3*i:3*i+3].tolist() for i, n in enumerate(model.nodes)},
            'reactions': {str(n.id): reactions[3*i:3*i+3].tolist() for i, n in enumerate(model.nodes)},
            'stress_ratio': max_stress, 'displacement_ratio': max_displ,
            'feasible': bool(max_stress <= 1+1e-6 and max_displ <= 1+1e-6),
            'residual_kip': residual, 'condition_number': condition}


def compare(model, reference, candidate):
    from .validation import detailed_compare
    return detailed_compare(model,reference,candidate)
