"""Constrained optimizers. All accepted designs are reanalyzed before reporting."""
import numpy as np
from scipy.optimize import minimize, differential_evolution, NonlinearConstraint
from .fem import solve


class Cancelled(Exception):
    pass


def optimize(model, method='SLSQP', iterations=200, seed=42, progress=None, cancelled=None):
    work = model.clone()
    history = []
    evaluations = 0
    cache_x, cache_r = None, None
    best = None
    initial_weight = model.weight()

    def evaluate(x):
        nonlocal cache_x, cache_r, evaluations, best
        if cancelled and cancelled():
            raise Cancelled()
        if cache_x is not None and np.array_equal(cache_x, x):
            return cache_r
        for m, area in zip(work.members, x):
            m.area = float(np.clip(area, work.area_min, work.area_max))
        cache_r = solve(work)
        cache_x = np.array(x).copy()
        evaluations += 1
        if cache_r['feasible'] and (best is None or cache_r['weight_lb'] < best[0]):
            best = (cache_r['weight_lb'], cache_x.copy())
        return cache_r

    def margins(x):
        r = evaluate(x)
        # Independent member stress constraints and all free translation bounds.
        return np.r_[[1-m['ratio'] for m in r['members']],
                     [1-abs(r['displacements'][str(n.id)][d])/work.displacement_limit
                      for n in work.nodes for d in range(3) if not n.fixed[d]]]

    def objective(x):
        return evaluate(x)['weight_lb']/initial_weight

    def callback(x, *args):
        r = evaluate(x)
        item = {'iteration': len(history), 'weight_lb': r['weight_lb'], 'feasible': r['feasible'],
                'best_feasible_lb': None if best is None else best[0],
                'stress_ratio': r['stress_ratio'], 'displacement_ratio': r['displacement_ratio'], 'evaluations': evaluations}
        history.append(item)
        if progress:
            progress(item)

    x0 = np.array([m.area for m in work.members])
    callback(x0)
    bounds = [(work.area_min, work.area_max)] * len(x0)
    if method == 'SLSQP':
        result = minimize(objective, x0, method='SLSQP', bounds=bounds,
                          constraints=[{'type': 'ineq', 'fun': margins}], callback=callback,
                          options={'maxiter': iterations, 'ftol': 1e-10})
    elif method == 'DE':
        result = differential_evolution(objective, bounds, constraints=(NonlinearConstraint(margins, 0., np.inf),),
                                        maxiter=iterations, popsize=10, seed=seed, callback=callback,
                                        polish=False, workers=1, tol=1e-6)
    else:
        raise ValueError('Algoritmo no implementado.')
    evaluate(result.x)
    callback(result.x)
    if best is None:
        raise ValueError("No se encontró un diseño factible. No se modificaron las áreas.")
    for m, area in zip(work.members, best[1]):
        m.area = float(area)
    final = solve(work)
    # Remove roundoff-level violations instead of rounding them away in tables.
    safety = max(1., final['stress_ratio'], final['displacement_ratio'])*(1+1e-8)
    if safety > 1.:
        for m in work.members:
            m.area = min(work.area_max, m.area*safety)
        final = solve(work)
    if not final['feasible']:
        raise ValueError('El diseño final no cumple las restricciones al recalcularlo.')
    final['optimization'] = {'method': method, 'converged': bool(result.success), 'message': str(result.message),
                             'seed': seed, 'evaluations': evaluations, 'iterations': len(history)-1,
                             'initial_weight_lb': initial_weight, 'global_optimum_proven': False}
    return work, final, history
