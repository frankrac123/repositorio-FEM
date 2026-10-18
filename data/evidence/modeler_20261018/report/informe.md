# Informe de comparación estructural

Modelo: Triángulo 2D · materiales y cargas
Huella: 3ec34d736344db763e685f893e0898c94ea8d56884bc7d4c5d2b1b1c38daf7a5
Estado: completed
Configuración: 1 corridas por método; presupuesto 180 por corrida; motor FEM.

## Problema y formulación
Áreas 0.1 a 35.0 in². Propiedades por barra: B1: E=29000 ksi, gamma=0.283 lb/in³; B2: E=10000 ksi, gamma=0.1 lb/in³; B3: E=29000 ksi, gamma=0.283 lb/in³
Esfuerzos admisibles ±25.0 ksi; desplazamientos ±2.0 in por componente libre.
Minimizar W = suma(gamma A L), en lb. Rigidez axial EA/L; solución Kff uf = Ff y reacciones Ku - F. El peso propio solicitado se concentra por mitades en los nodos extremos para conservar la formulación axial.
Patrones: [{"id": "LC1", "name": "Vertical y peso propio", "load_type": "Dead", "nodal_loads": {"3": [0.0, 0.0, -10.0]}, "self_weight": 1.0}, {"id": "LC2", "name": "Horizontal", "load_type": "Wind", "nodal_loads": {"3": [4.0, 0.0, -2.0]}, "self_weight": 0.0}]
Casos verificados en cada candidato: C1, C2, ULS
Tolerancia de factibilidad: 1e-6 en las relaciones normalizadas. Estabilidad: condición <= 1e13. Equilibrio: 1e-6 kip y 1e-3 kip in.

## Métodos y configuración experimental
ASAM usa exploración uniforme, radio geométrico y aceptación logística. Las direcciones simétricas, reflexión de límites, normalización y tratamiento de restricciones son decisiones del proyecto.
DE utiliza SciPy con restricciones explícitas y sin pulido oculto. SLSQP es determinista con varios arranques obtenidos de la misma población común; las semillas cambian los arranques.
Los métodos que incluyen +SLSQP contabilizan el refinamiento dentro del presupuesto y se presentan por separado de los puros.
Cada método recibe la misma población inicial por semilla. Se registran análisis nuevos, auditorías FEM del motor SAP, aciertos de caché, reinicios y gradientes.
La verificación externa posterior no alimenta la búsqueda y tiene costes separados. No se introducen diseños publicados como puntos de arranque.
Parámetros inmutables: {"asam": {"temperature_initial": 0.05, "temperature_final": 1e-06, "cooling": 0.96, "initial_points": 10, "radius_initial": 17.45, "radius_reduction": 0.96, "proposals_per_temperature": 50, "convergence_tolerance": 0.0, "convergence_patience": 30}, "iterations": 10000, "slsqp_starts": 2, "slsqp_ftol": 1e-10, "de_mutation": [0.5, 1.0], "de_recombination": 0.7, "de_tolerance": 1e-06, "asam_constraint_policy": "feasible_first", "penalty_coefficient": 100.0, "global_fraction": 0.7}
Semillas: 42
Versiones: {"trusslab": "0.1.0", "python": "3.11.9", "numpy": "2.4.6", "scipy": "1.17.1", "platform": "Windows-10-10.0.26300-SP0", "source_sha256": "47642515b51874ac245903bd3f50ff0f30ccf4d029c80db0bfad6fcb29d86233"}

## Resultados descriptivos
| Método | n factibles/completadas | Mejor (lb) | Media (lb) | Mediana (lb) | Desviación muestral (lb) |
|---|---:|---:|---:|---:|---:|
| ASAM | 1/1 | 79.544886 | 79.544886 | 79.544886 | No disponible |
| DE | 1/1 | 46.760562 | 46.760562 | 46.760562 | No disponible |
| SLSQP | 1/1 | 34.834439 | 34.834439 | 34.834439 | No disponible |

Tasa de factibilidad = corridas completas con diseño factible / corridas completas, incluyendo fallos y excluyendo canceladas. La desviación es muestral (n-1); no se define con una sola muestra.
Con menos de 20 corridas factibles por método, la muestra es limitada. Estas estadísticas no prueban diferencias significativas ni superioridad universal.

## Validación SAP2000
ASAM, semilla 42: pending
DE, semilla 42: pending
SLSQP, semilla 42: pending

## Restricciones activas
Se consideran próximas al límite con tolerancia relativa 1e-4; esto no modifica la tolerancia de factibilidad 1e-6.
ASAM, semilla 42: 
DE, semilla 42: 
SLSQP, semilla 42: Esfuerzo B1 · ULS, Esfuerzo B3 · ULS
Coste de validación externa: {"sap_analyses": 0, "independent_fem_audits": 0}
Los SDB archivados son copias del modelo guardado del candidato verificado; los resultados numéricos y la comparación se conservan en JSON. Al abrir una copia aislada en SAP puede ser necesario volver a analizar para reconstruir sus archivos auxiliares.

## Discusión y conclusiones
El menor peso observado en esta campaña fue 34.834439 lb con SLSQP. El criterio es descriptivo y depende del presupuesto y los arranques documentados.
No se sustituye una solución infactible o un análisis fallido por valores estructurales inventados. Los pendientes SAP no se presentan como validados.
Los tiempos incluyen pausas y dependen del equipo y de la carga del sistema. Los métodos pueden finalizar antes del límite; se comparan también sus consumos reales.
Referencias del Caso I: 5060.855730008 lb (diseño anterior), y aproximadamente 5060.877 lb (artículo). Solo son comparables si geometría, cargas, material y límites coinciden con el benchmark de 25 ksi; no son objetivos impuestos.

## Referencias
Millán-Páramo, Matoski y Mazer (2017). DOI: https://doi.org/10.18845/tm.v30i2.3209
SciPy: https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.differential_evolution.html
SciPy: https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html
