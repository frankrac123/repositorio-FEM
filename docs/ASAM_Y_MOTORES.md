# Optimización de tamaño: etapas 2, 3 y 4

Se continúa el proyecto existente. El punto de recuperación anterior a estas modificaciones es el commit `2053846`, etiqueta `pre-phase3-20261017`. El laboratorio comparativo, GA/PSO y las etapas 5–7 no se presentan como terminados.

## Modelo físico y restricciones

Cada barra axial aporta `EA/L · [[nnᵀ, −nnᵀ], [−nnᵀ, nnᵀ]]` a la matriz global. Se resuelve `Kff uf = Ff`, con desplazamientos restringidos nulos; las reacciones se recuperan de `Ku − F`. La deformación axial determina `N = EA/L · n·(uj−ui)` y `σ=N/A`. No se incorpora rigidez artificial para ocultar mecanismos.

El objetivo es `W = Σ γ A L` en **lb**. Para el Caso I, E = 10000 ksi y γ = 0.10 lb/in³. Se mantienen las diez conectividades, dos cargas verticales de −100 kip (nodos 2 y 4), apoyos 5 y 6 y ausencia de peso propio. Los límites son `0.1 ≤ A ≤ 35 in²`, `|σ| ≤ 25 ksi`, y `|ud| ≤ 2 in` para **cada componente libre**, no para la norma del vector.

La factibilidad admite una tolerancia de `10⁻⁶` en las relaciones esfuerzo/límite y desplazamiento/límite: equivale a 0.000025 ksi y 0.000002 in en este benchmark. Las áreas se validan dentro de sus límites; solo se recorta un exceso de redondeo de hasta `10⁻⁹ in²` en la expansión de variables. Un peso menor con restricciones excedidas nunca se elige como ganador.

El texto del artículo menciona 20 ksi, mientras el benchmark adoptado y confirmado por el usuario usa **25 ksi**. No se ejecuta una mezcla de ambas condiciones. Un futuro ensayo a 20 ksi debe guardarse como problema distinto.

## ASAM: fundamento y decisiones explícitas

Referencia principal: Millán-Páramo, Matoski y Mazer (2017), [DOI 10.18845/tm.v30i2.3209](https://doi.org/10.18845/tm.v30i2.3209), [artículo completo](https://www.scielo.sa.cr/pdf/tem/v30n2/0379-3982-tem-30-02-142.pdf). Se implementan sus tres mecanismos: exploración uniforme `X = Amin + U(Amax−Amin)` (ec. 6), radio `Rk+1 = αR Rk` (ec. 7) y aceptación de empeoramientos `P = 1/(1+exp(Δf/T))` (ec. 8). La última regla alcanza 0.5 para diferencia nula y disminuye al aumentar la diferencia o bajar la temperatura. Se evalúan todos los puntos preliminares antes de elegir el estado inicial, salvo cancelación o agotamiento del presupuesto.

Las siguientes decisiones pertenecen a **esta implementación**, no se atribuyen a los autores:

- La ecuación preliminar se interpreta como replicación del límite inferior en cada fila. Aplicar literalmente una identidad rectangular dejaría componentes fuera de los límites.
- La dirección del paso usa perturbaciones independientes uniformes en `[−R,R]` sobre todo el vector. Los excesos se reflejan periódicamente dentro del intervalo; no se acumulan por recorte en sus extremos.
- El estado inicial se ordena primero por factibilidad. Entre factibles gana menor peso; entre infactibles, menor suma cuadrática de excesos normalizados de las barras y del máximo desplazamiento relativo. Así puede explorarse desde una población inicialmente inadmisible.
- Una vez factible, la trayectoria no acepta estados infactibles. Dentro de la misma clase se aceptan mejoras; los empeoramientos siguen la regla logística. Para factibles se usa energía `W/Winicial`; para infactibles, la medida de violación. Un empate de violación se desempata con peso normalizado.
- Temperatura y radio disminuyen una vez por ciclo de propuestas. Ambos coeficientes se configuran por separado. La semilla corresponde a `numpy.random.default_rng`.
- Hay detención por temperatura final, ciclos máximos, presupuesto, cancelación o estancamiento opcional. La tolerancia de estancamiento mide cambios de energía normalizada del mejor factible; 0 la desactiva. Su paciencia también es configurable.
- Los valores iniciales de temperatura, radio, población y propuestas son parámetros del programa, no una reconstrucción de parámetros desconocidos del código MATLAB original. ASAM no invoca SLSQP ni otro refinador local oculto.

El mejor factible se conserva aunque la trayectoria acepte un empeoramiento. Una reparación opcional de redondeo amplía las variables activas en una proporción mínima y se vuelve a analizar con el mismo motor; aparece como `roundoff_safety` y consume presupuesto. Con barras fijas no se supone que escalar las activas resuelva todas las restricciones: se comprueba el resultado y se conserva el anterior si falla.

Los mecanismos se verifican con probabilidades conocidas, distribución de candidatos, límites, trazas de radio/temperatura y semillas repetidas. La reproducción del peso publicado exige, además, contrastar resultados numéricos; implementar las ecuaciones no demuestra haber reproducido todas las decisiones del programa original.

## Motores y procedencia de los datos

| Modalidad | Exploración | Verificación externa |
|---|---|---|
| FEM | Rigidez matricial NumPy | Cada candidato figura pendiente de SAP |
| SAP | Análisis OAPI real de cada candidato distinto | Resultado recuperado de SAP |
| Híbrido | FEM | Hasta K candidatos factibles de menor peso, distintos, verificados con SAP |

`SapBatchSession` crea una instancia propia y oculta; no se conecta al modelo activo del usuario. Todos sus objetos COM se crean, usan y liberan en el mismo hilo de trabajo, con llamadas serializadas. El primer candidato crea geometría, secciones, cargas y archivos; los siguientes desbloquean el modelo, actualizan las secciones nombradas por proyecto y barra, leen sus áreas, guardan, ejecutan el análisis y recuperan `FrameForce`, `JointDispl` y `JointReact`. El peso se obtiene del modelo transferido; esfuerzos = axial SAP/área verificada. FEM se calcula adicionalmente como control independiente y **no suministra las fuerzas SAP**. Una discrepancia del control detiene la búsqueda.

Se comprueba el estado final `CASE_I=4`. En v26.3 se usa `File.Save()` después del análisis: proporcionar nombre de archivo en ese punto invalida los resultados. Cuando es necesario y queda presupuesto, se vuelve a analizar el ganador para que el SDB final no quede describiendo una perturbación posterior. Este análisis también se registra y cuenta. Al cancelar no se hacen análisis adicionales: el JSON del mejor conserva sus propios datos; `sap_file_matches_result` señala si el SDB coincide o contiene el último candidato evaluado. También se comprueba esta bandera si una reparación rechazada consumió la última evaluación disponible.

El híbrido reserva K evaluaciones externas y una evaluación final de seguridad/restauración. Si existen menos de K candidatos factibles distintos, verifica los disponibles. Los demás registros conservan `external_validation=pending`. La selección final usa exclusivamente los verificados factibles; una cancelación previa puede devolver el mejor FEM explícitamente pendiente. Si SAP falla, se informa el error y se conserva el modelo de la interfaz; no hay sustitución automática por FEM.

## Presupuesto, interfaz y archivos

La API de optimización cuenta intentos de análisis estructural: FEM y SAP suman en híbrido. El laboratorio contabiliza por separado el análisis SAP y su auditoría FEM (dos unidades por candidato SAP); los fallos consumen el intento iniciado. Los presupuestos de ambas interfaces deben interpretarse con esa política explícita. Una comparación FEM independiente del adaptador SAP es un control adicional, identificado aparte de los análisis que solicita el optimizador. Repeticiones exactas del mismo vector y motor se recuperan de una caché acotada a 2048 entradas; no se redondean las claves, para conservar las perturbaciones de diferencias finitas. Una repetición expulsada de la caché se recalcula y vuelve a contar. Se reserva una evaluación final, por lo que una búsqueda puede terminar usando menos que el máximo. Las iteraciones de los algoritmos no equivalen al número de análisis.

SLSQP utiliza restricciones separadas para cada esfuerzo y componente libre; DE utiliza `NonlinearConstraint`, sin pulido automático. Ambos mantienen la API anterior. Documentación oficial: [SLSQP](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html), [DE](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.differential_evolution.html). Esta implementación usa SciPy 1.17.1 y su interfaz instalada.

La configuración permite seleccionar algoritmo, motor, presupuesto, semilla, K, barras activas, grupos de área y parámetros ASAM. La ventana de ejecución informa evaluaciones por motor, iteración, tiempo transcurrido y mejor factible. Pausa y detención actúan **entre análisis**; no interrumpen una llamada COM ya iniciada. La búsqueda vive en QThread y la interfaz recibe señales. Al detener, se devuelve el mejor factible ya calculado; si no existe ninguno se informa y no se cambian las áreas.

Cada ejecución guarda `configuration.json`, `evaluations.jsonl`, `convergence.csv` y, si existe ganador, `best.trusslab.json`. SAP añade auditorías, llamadas y resultados de cada candidato en JSONL; los errores se registran. Se conservan áreas, semilla, restricciones, procedencia y motivo de terminación. El tiempo incluye pausas. El gráfico distingue candidatos factibles azules, infactibles rojos y mejor factible acumulado verde, con consulta mediante el cursor.

## Resultados estructurales SAP

El menú SAP abre **RESULTADOS ESTRUCTURALES — SAP2000** solamente para resultados cuyo motor y huella coincidan con el modelo actual. Muestra tablas de axiales/esfuerzos y admisibles, desplazamientos, reacciones y cargas; las barras críticas se marcan a partir de utilización 0.95. La tabla activa se exporta a CSV.

El visor representa tracción azul, compresión roja e intensidad proporcional al máximo absoluto mostrado. Permite original y deformada simultáneas, amplificación y escala de secciones configurables. El radio de representación es proporcional a `sqrt(A/π)`: el factor visual no cambia áreas ni desplazamientos reales. Se agrupan las inserciones de mallas en un único renderizado por actualización.

Se inspeccionaron la biblioteca de tipos instalada y `CSI_OAPI_Documentation.chm`. `cView` ofrece `RefreshView` y `RefreshWindow`; no expone selectores públicos de todos los diagramas. Por ello se conserva la guía manual SAP existente y se muestran aquí sus valores auténticos. No se presenta el panel como control automático de menús SAP no expuestos.

## Alcance pendiente

La infraestructura admite cualquier número de barras, estructuras planas/espaciales estables, grupos y selección de variables de **tamaño**. El modelo admite varios materiales por barra y múltiples patrones/casos de carga. Las restricciones se verifican en todos los casos seleccionados. Límites independientes por elemento, optimización de geometría/topología, pandeo y perfiles comerciales no están implementados.

Las curvas comparativas, campañas con presupuestos equivalentes, estadísticas entre algoritmos, GA/PSO e informes Excel/académicos completos quedan para etapas posteriores. No se afirma optimalidad global ni superioridad de un algoritmo con los ensayos de estas etapas. Los formatos numéricos CSV/JSON y PNG sirven de base para esos informes.
