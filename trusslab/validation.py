"""Finite, ID-aligned comparisons and independent equilibrium/limit checks."""
import csv
import math
from pathlib import Path
import numpy as np

TOLERANCES = {'displacement': 1e-5, 'force': 1e-4, 'stress': 1e-5,
              'reaction': 1e-4, 'weight': 1e-8, 'equilibrium_force': 1e-6,
              'equilibrium_moment': 1e-3, 'relative_zero': 1e-12}


def detailed_compare(model, reference, candidate):
    rows=[]
    issues=[]
    def row(kind, entity, component, a, b, unit):
        def scalar(value):
            try:
                number=float(value)
                return number if math.isfinite(number) else None
            except (TypeError,ValueError):return None
        a,b=scalar(a),scalar(b)
        finite=a is not None and b is not None
        diff=abs(a-b) if finite else None
        relative=diff/abs(a) if finite and abs(a)>TOLERANCES['relative_zero'] else None
        tolerance=TOLERANCES[kind]
        rows.append({'quantity':kind,'entity':entity,'component':component,'unit':unit,
                     'fem':a,'sap':b,
                     'absolute_error':diff,'relative_error':relative,'tolerance':tolerance,
                     'passed':bool(finite and diff<=tolerance)})
    for n in model.nodes:
        for field,kind,unit in [('displacements','displacement','in'),('reactions','reaction','kip')]:
            a=reference.get(field,{}).get(str(n.id),[])
            b=candidate.get(field,{}).get(str(n.id),[])
            for d,axis in enumerate('XYZ'):
                row(kind,f'N{n.id}',axis,a[d] if len(a)>d else None,b[d] if len(b)>d else None,unit)
    def members(result):
        values=result.get('members',[])
        ids=[r['id'] for r in values]
        if len(set(ids))!=len(ids) or set(ids)!={m.id for m in model.members}:
            issues.append('Identificadores de barras faltantes, duplicados o inesperados.')
        return {r['id']:r for r in values}
    fa,sa=members(reference),members(candidate)
    for m in model.members:
        for field,kind,unit in [('force','force','kip'),('stress','stress','ksi')]:
            row(kind,f'B{m.id}','axial',fa.get(m.id,{}).get(field),sa.get(m.id,{}).get(field),unit)
    row('weight','Modelo','W',reference.get('weight_lb'),candidate.get('weight_lb'),'lb')
    def maximum(kind):
        values=[r['absolute_error'] for r in rows if r['quantity']==kind]
        return max(values) if values and all(x is not None for x in values) else None
    return {'max_displacement_error_in':maximum('displacement'),'max_force_error_kip':maximum('force'),
            'max_stress_error_ksi':maximum('stress'),'max_reaction_error_kip':maximum('reaction'),
            'weight_error_lb':maximum('weight'),'passed':not issues and all(r['passed'] for r in rows),
            'issues':issues,'rows':rows,'tolerances':dict(TOLERANCES)}


def equilibrium(model,result):
    forces=np.array([result['reactions'][str(n.id)] for n in model.nodes],dtype=float)+np.array([n.load for n in model.nodes],dtype=float)
    net=forces.sum(axis=0)
    # Center coordinates to avoid excessive cancellation for offset models.
    xyz=np.array([n.xyz for n in model.nodes],dtype=float)
    moment=np.cross(xyz-xyz.mean(axis=0),forces).sum(axis=0)
    finite=bool(np.isfinite(forces).all() and np.isfinite(moment).all())
    return {'net_force_kip':net.tolist(),'net_moment_kip_in':moment.tolist(),
            'force_tolerance_kip':TOLERANCES['equilibrium_force'],
            'moment_tolerance_kip_in':TOLERANCES['equilibrium_moment'],
            'passed':finite and bool(max(abs(net))<=TOLERANCES['equilibrium_force'] and max(abs(moment))<=TOLERANCES['equilibrium_moment'])}


def limits(model,result):
    stress=max(abs(r['stress'])/model.stress_limit for r in result['members'])
    displacement=max(abs(result['displacements'][str(n.id)][d])/model.displacement_limit
                     for n in model.nodes for d in range(3) if not n.fixed[d])
    return {'stress_ratio':stress,'displacement_ratio':displacement,
            'stress_passed':bool(math.isfinite(stress) and stress<=1+1e-6),
            'displacement_passed':bool(math.isfinite(displacement) and displacement<=1+1e-6)}


def validation_report(model,reference,candidate):
    comparison=detailed_compare(model,reference,candidate)
    balance={'fem':equilibrium(model,reference),'sap':equilibrium(model,candidate)}
    constraints={'fem':limits(model,reference),'sap':limits(model,candidate)}
    audit=candidate.get('input_audit',{})
    axial=candidate.get('max_nonaxial_component',0.)
    passed=bool(comparison['passed'] and all(b['passed'] for b in balance.values())
                and audit.get('passed',True) and math.isfinite(axial) and axial<=1e-5)
    return {'passed':passed,'comparison':comparison,'equilibrium':balance,'constraints':constraints,
            'input_audit_passed':audit.get('passed'), 'axial_only_passed':math.isfinite(axial) and axial<=1e-5,
            'design_feasible':all(c['stress_passed'] and c['displacement_passed'] for c in constraints.values())}


def write_comparison_csv(path,comparison):
    with Path(path).open('w',newline='',encoding='utf-8-sig') as out:
        columns=['quantity','entity','component','unit','fem','sap','absolute_error','relative_error','tolerance','passed']
        writer=csv.DictWriter(out,fieldnames=columns);writer.writeheader();writer.writerows(comparison['rows'])
