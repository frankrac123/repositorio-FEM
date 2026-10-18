# Auditoría y estabilización de TrussLab 3D

Fecha: 18 de octubre de 2026. Alcance: aplicación existente de cerchas axiales 2D/3D, análisis estático lineal elástico y optimización de áreas. No se sustituyó la interfaz ni se añadieron algoritmos.

## Recuperación y versión de partida

Repositorio: https://github.com/frankrac123/repositorio-FEM. Punto de partida limpio: `bee4238d9f8aa4c0ba157dc0dbce2168f754a475`. Etiqueta de recuperación creada antes de modificar fuentes: `pre-audit-stabilization-20261018`.

La incompatibilidad sugerida `solve(model)` frente a `solve(model, case=...)` **no persistía** en esa versión: ya aceptaba `case`. Se encontraron inconsistencias reales de validación y dos implementaciones matemáticas. Se corrigieron mediante un núcleo común, no añadiendo solamente un argumento.

## Errores, causas y correcciones

| Hallazgo | Causa | Corrección y archivos |
|---|---|---|
| Caso desconocido aceptado como estructura sin carga | PreparedTruss no validaba el identificador | Validación común de casos en `core.py`, `truss_kernel.py`, interfaces `fem.py` y `prepared_fem.py` |
| Un caso activo inválido impedía analizar otro caso válido solicitado | Validación previa usaba siempre active_case | Validación del caso pedido explícitamente; preparación geométrica separada de cargas |
| Barra fija con área positiva fuera de límites de optimización rechazada por un motor | Se confundían límites de búsqueda con validez física | Núcleo exige áreas positivas/finítas; `DesignSpace` mantiene límites en variables optimizables |
| Cargas eliminadas reaparecían | Al vaciar patrones se utilizaba el caché histórico Node.load | `load_storage` distingue documento histórico de biblioteca vacía; schema 3 conserva versiones 1/2 |
| Material global confundido con material explícito llamado legacy en SAP | Diccionario indexado por un ID sintético coincidente | Espacios separados global/entity en `sap_mapping.py`; creación, lectura y actualización OAPI usan la misma clave |
| Resultados antiguos o alterados podían mostrarse | Migración antigua confiaba en una huella ausente; historial sobrevivía al descarte | Verificación física al abrir resultados guardados, descarte de resultado/historial incompatibles y guardia de huella en UI |
| Aplicar grupo u otra propiedad redondeaba áreas/coordenadas no editadas | QDoubleSpinBox de seis decimales devolvía el valor mostrado | `NumberEdit` conserva el valor completo mientras el usuario no lo edite |
| Operación numéricamente idéntica cambiaba int a float y dejaba huella antigua | Igualdad Python ignoraba la diferencia de serialización | Restaurar la instantánea original en operaciones sin cambio semántico |
| Renombrar patrón perdía fuerzas; una ventana antigua podía restaurar asignaciones viejas | Se buscaba por el nuevo ID en una captura anterior | Conservar ID original por fila y consultar datos actuales del modelo en `editor_libraries.py` |
| Copiar barra con material global asignaba el primer material de biblioteca | Se reutilizaban valores predeterminados de creación | Copia conserva exactamente material, sección y área originales en `editor_commands.py` |
| Editar material explícito legacy modificaba propiedades globales | Se interpretaba todo ID legacy como material sintético | Solo la fila histórica sintética actualiza el material global |
| Cercha totalmente restringida rechazada aunque su respuesta estática es definida | Reducción vacía tratada como error | Desplazamientos nulos, axiales nulos y reacciones opuestas a cargas; no se añaden apoyos |
| Un fallo tardío perdía la evidencia del mejor candidato | Captura de excepción guardaba solo el error | Guardar best_before_failure por separado, contar intento fallido y mantener estado failed en ambos coordinadores |
| Herramienta de selección y mensaje del plano sin acción efectiva | Conexiones UI incompletas | Conectar selección al estado de herramienta y señal de mensaje a barra de estado |
| Documentación describía inicio/Caso I/material único antiguos | README y guía de motores no seguían al modelador | Actualización de README, MODELADOR, ASAM_Y_MOTORES, INDEX y CONTRIBUTING |

Las seis primeras regresiones reproducibles dieron **6 fallos de 6** antes de corregirse (`audit_before.xml`). La suite original dio **53 aprobadas y 5 omitidas** tanto localmente (19.08 s) como en clon limpio (17.22 s). Los registros posteriores indican los conteos realmente ejecutados; no se equiparan pruebas omitidas a aprobadas.

## Arquitectura y flujo de datos

| Entrada/coordinador | Datos y responsabilidades | Destino |
|---|---|---|
| run.py / ui.main / lanzador | Crear ventana existente; documento inicialmente vacío | ui.MainWindow |
| editor_commands, editor_properties, editor_libraries | Mutaciones transaccionales, validación de integridad y deshacer | core.Model |
| core.Model | Nodos, conectividad, área efectiva por barra, materiales E/γ, secciones, apoyos, patrones/casos, unidades/límites y configuración | FEM, optimización y adaptador SAP |
| fem.solve(model, case=...) | Interfaz pública y procedencia de resultado | truss_kernel.TrussKernel |
| prepared_fem.PreparedTruss | Adaptador de geometría preparada; sin segunda formulación | mismo TrussKernel |
| analysis | Casos seleccionados, restricciones de cada componente libre y agregación de máximos sin fabricar envolventes físicas | optimización/laboratorio |
| design_space | Variables según barras activas/grupos y barras fijas conservadas | optimization_runtime / lab_evaluation |
| optimization_runtime | API simple ASAM/DE/SLSQP; motores FEM/SAP/híbrido | solve_design o SapBatchSession |
| lab_search / lab_evaluation / laboratory | Cinco métodos existentes, población por semilla, presupuesto, caché exacta, trazas y campañas | mismo núcleo FEM o SAP con auditoría FEM |
| sap_mapping / sap | Nombres explícitos, transferencia/relectura, sesiones COM propias, recuperación y validación | SAP2000 real |
| scene / results_ui / lab_ui / lab_plots / lab_report | Representar modelo/resultados, exportar e informar | Sin formulación FEM alternativa |

`optimization.py` es una fachada pública usada por GUI, pruebas y scripts; no se eliminó. `prepared_fem.py` es ahora un adaptador real. `cli.py` es una entrada alternativa válida; mantiene el benchmark por defecto y usa nombres generales al recibir --project. `scripts/verify_phase3_*`, `verify_phase4_*` y `reproduce_example.py` conservan experimentos históricos; no alimentan diseños óptimos a la búsqueda actual. Los controles GA/PSO permanecen pendientes y no ejecutan algoritmos simulados.

El inventario AST de todos los Python del proyecto, sus importaciones, definiciones, hashes y referencias al benchmark está en `data/evidence/audit_20261018/source_map.json`, reproducible con `scripts/audit_inventory.py`. Se revisaron fuentes, pruebas, configuración, dependencias fijadas y documentos. Las referencias fijas a seis nodos/diez barras se concentran en benchmark, pruebas y experimentos históricos; los bucles de ensamblaje, dibujo, variables y transferencia usan las listas del documento. Las comparaciones publicadas y pesos 5060.* son referencias descriptivas, no objetivos del algoritmo.

## Formulación física y unidades

Para cada barra: L = ||xj−xi||, d = (xj−xi)/L, t = [−d,d], ke = (EA/L) t⊗t. Se ensambla K, se resuelve Kff uf = Ff, σ = (E/L)t·ue, P = Aσ y R = Ku−F. Se comprueba finitud, residuo, equilibrio de fuerzas y momentos. No hay rigidez artificial. Se detectan mecanismos mediante condición de Kff > 1e13 o singularidad, además de conectividad, apoyos, coordenadas coincidentes, longitudes nulas y referencias/materiales inválidos.

Un borrador incompleto se guarda pero no se etiqueta apto para cálculo. En 2D se elimina únicamente la traslación normal declarada por el plano; en 3D no se deducen apoyos de coordenadas nulas. Las secciones inicializan o actualizan áreas asignadas; el área efectiva de cada barra gobierna FEM, SAP, peso y optimización.

Unidades: in, in², kip, ksi (=kip/in²), E en ksi. `density` significa **peso específico lb/in³**, no densidad de masa. W = ΣγAL en lb. La gravedad se convierte mediante lb/1000 a kip y se reparte mitad por extremo, idénticamente en FEM y SAP; el peso propio distribuido nativo SAP queda en cero para conservar comportamiento axial. No se implementa dinámica ni conversión silenciosa de masa. `units.py` centraliza conversiones verificadas mediante barra vertical cerrada y peso propio dependiente del área.

Tolerancias absolutas FEM/SAP: u 1e-5 in, P 1e-4 kip, σ 1e-5 ksi, reacción 1e-4 kip, peso 1e-8 lb. Equilibrio: 1e-6 kip, 1e-3 kip·in. Factibilidad: razones <=1+1e-6; `strict_feasible` requiere <=1 sin tolerancia. La interfaz y los resultados separan ambos criterios.

## Prueba A — Caso I

Se conservó el proyecto calculado existente y la convención nodal/conectividad. E=10000 ksi, γ=.10 lb/in³, A entre .1 y 35 in², σadm=±25 ksi, uadm=±2 in/componente, −100 kip en N2/N4 Z, apoyos N5/N6. El peso reproducido fue **5060.855730007684 lb**. Frente a 5060.877 lb publicado, diferencia −0.021269992316 lb (~−0.0004203%). Se verifica el diseño guardado; no se afirma que una búsqueda nueva ASAM reproduzca el óptimo publicado.

Máximo desplazamiento ≈1.99999998 in, máxima razón de esfuerzo ≈0.999998395. Reacciones: N5 ≈[−300,0,97.369073] kip y N6 ≈[300,0,102.630927] kip. Las tablas completas de áreas, axiales, esfuerzos, desplazamientos y reacciones se conservan en JSON/CSV; no se deducen de la imagen.

La discrepancia textual 20/25 ksi del artículo de Millán-Páramo, Matoski y Mazer (2017), DOI 10.18845/tm.v30i2.3209, permanece documentada. Se utiliza el benchmark de 25 ksi autorizado y verificado para este proyecto. No se presenta E=10000 ksi como acero A36 ni se fuerza un peso objetivo.

## Pruebas B, C, D y E — modelos independientes

Se variaron además los ejemplos respecto a los ensayos anteriores: triángulo con base 140 in y vértice [55,0,95]; trípode espacial con vértice [37,43,112] y tres apoyos no colineales. Sus datos completos están en los JSON de evidencia. El trípode es no coplanar y recibe fuerzas XYZ. Se usan materiales con E y γ diferentes, incluido un material explícito llamado legacy junto al material global para comprobar la corrección del mapeo SAP.

| Modelo | Peso inicial lb | Casos FEM/SAP | Comparación real |
|---|---:|---|---|
| A Caso I guardado | 5060.855730007684 | LC1 | Aprobada |
| B/D/E triángulo 2D | 171.099223237518 | C1, C2, ULS | Aprobadas |
| C/D/E trípode 3D | 305.397547087414 | C1, C2, ULS | Aprobadas |

Máximos errores observados en este ensayo: desplazamiento 1.11023e-15 in, fuerza/reacción 1.13687e-13 kip, esfuerzo 7.54952e-15 ksi. Cada caso se recuperó independientemente en SAP; las restricciones del optimizador abarcan los tres casos, no solo el activo. Se conservaron CSV por magnitud/componente, modelos JSON y SDB reales. Un SDB copiado sin auxiliares puede necesitar reanálisis al abrirse; los JSON conservan las respuestas efectivamente recuperadas.

## Espera COM reproducida durante la auditoría

La primera suite con todos los indicadores activos terminó con **73 aprobadas y 1 fallida en 331.72 s**: el ensayo visible bloqueaba el STA principal de pytest mediante `Future.result()` después de otras pruebas COM. La operación registrada era Helper.CreateObject; no se atribuyó el fallo al cálculo FEM ni se marcó como aprobado. La espera del ensayo ahora procesa mensajes COM/Qt, como hace la aplicación. El ensayo aislado posterior pasó (**1 aprobada en 114.81 s**), verificando apertura, actualización en otra copia, conservación del SDB anterior, análisis automático independiente y sesiones visibles vivas. Registros before_sta_wait.xml/after_sta_wait.xml. La suite completa corregida se vuelve a ejecutar para comprobar la interacción entre pruebas.

## SAP2000 OAPI y sesiones

SAP2000 26.3.0, Windows, SAP2000v1.Helper. La auditoría relee coordenadas, conectividades, áreas, materiales E/γ, apoyos, liberaciones, DOF, patrones y factores. Crea una sección por barra. Las liberaciones y restricciones rotacionales evitan introducir flexión en la cercha axial. Los resultados se obtienen de JointDispl, FrameForce y JointReact y se contrastan con FEM y equilibrio.

Los nombres se derivan del proyecto/ID. Las instancias COM viven en su hilo propietario y los ensayos usan modelos/directorios únicos. No se cierra una instancia ajena. Abrir/actualizar visible conserva copias anteriores; los modos automáticos cierran únicamente sus instancias propias. Se conserva `File.Save()` sin nombre después del análisis: proporcionar ruta otra vez puede invalidar resultados en SAP 26.3.0. El estado final de análisis se comprueba como 4.

## Algoritmos y presupuesto

ASAM, DE, SLSQP multirrarranque, ASAM+SLSQP y DE+SLSQP utilizan el mismo evaluador del laboratorio. En dos geometrías se ejecutaron semillas 42/17 con presupuesto 240 por método, población común 20, y se repitió toda la campaña: **40 corridas**, con áreas iguales en sus repeticiones. Todos los mejores retenidos cumplieron las restricciones dentro de tolerancia, y ningún método superó el presupuesto. Las áreas/grupos se expanden con DesignSpace; las barras no activas conservan su área incluso fuera del intervalo de búsqueda.

Los CSV conservan pesos y evaluaciones de las 20 corridas originales. Algunos diseños locales/híbridos satisfacen solo la tolerancia 1e-6; el campo strict_feasible evita confundirlos con cumplimiento estricto. Las diferencias de peso o de dos semillas no prueban superioridad estadística. No hay demostración de óptimo global.

La API simple cuenta intentos de motor, incluido intento fallido. El laboratorio cuenta SAP más su auditoría FEM como dos unidades por candidato SAP; la verificación externa posterior se registra por separado. Caché exacta no consume análisis nuevo; diferencias finitas, reinicios y refinamientos sí. Un fallo conserva el mejor previo como best_before_failure y mantiene estado failed.

## Interfaz y documentos

Las pruebas Qt ejecutan acciones sobre ventanas propias: Nuevo vacío, crear nodos numéricamente/con ratón, crear barras, editar coordenadas/áreas/materiales/secciones, fuerzas, apoyos múltiples, validación/análisis, deshacer/rehacer, guardar/abrir/exportar CSV/JSON/PNG, campañas y aplicación del ganador. Se prueba también la acción Optimizar con diálogo y QThread reales. La escritura conserva precisión de campos no editados y no reconstruye el editor durante la confirmación.

La carga de JSON antiguo verifica físicamente resultados existentes; abrir un borrador sin resultados no llama al solucionador. Las ediciones invalidan resultados, y una guardia de huella evita mostrarlos después de una mutación externa.

## Entorno, clon limpio y publicación

Se clonó el repositorio remoto en una carpeta nueva y se creó una .venv nueva, sin system-site-packages. Se instaló `requirements.txt` con `pip --no-cache-dir`; el registro está en `clean_install.txt`. No se copiaron dependencias ni fuentes locales al clon. Entorno comprobado: Python 3.11.9 64 bits, Windows, NumPy 2.4.6, SciPy 1.17.1, PySide6 6.12.0, VTK 9.7.1, PyVista .49.1, comtypes 1.4.17. El inventario contiene versiones completas. No se modificó el lock que ya se pudo instalar desde cero; incluye herramientas de empaquetado y exportación además del núcleo. Otros Python/sistemas no se declaran probados por esta instalación.

El conteo inicial desde GitHub fue 53 aprobadas/5 omitidas. La verificación del commit corregido publicado se registra al finalizar en el manifiesto de reproducción; este informe no considera el ensayo inicial como validación de cambios todavía no publicados.

## Reproducir

```powershell
git clone https://github.com/frankrac123/repositorio-FEM.git
cd repositorio-FEM
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q --junitxml=unit-tests.xml
$env:TRUSSLAB_RUN_QT='1'
.\.venv\Scripts\python.exe -m pytest -q --junitxml=qt-tests.xml
.\.venv\Scripts\python.exe scripts/verify_audit.py --algorithms
.\.venv\Scripts\python.exe scripts/audit_inventory.py
# SAP real solo con instalación y licencia disponibles:
$env:TRUSSLAB_RUN_SAP_BATCH='1'
$env:TRUSSLAB_RUN_SAP_INTEGRATION='1'
.\.venv\Scripts\python.exe -m pytest -q --junitxml=all-tests.xml
.\.venv\Scripts\python.exe scripts/verify_audit.py --sap --algorithms
.\.venv\Scripts\python.exe scripts/verify_modeler_ui_sap.py --audit-update
```

Los indicadores SAP abren instancias reales. Las copias visibles quedan abiertas para consulta. Para congelar una versión, ejecuta `git checkout <SHA del manifiesto>` antes de instalar y probar.

## Limitaciones

Solo cerchas axiales elásticas lineales y unidades kip/in/ksi, no vigas/pórticos, plasticidad, dinámica, pandeo ni diseño normativo. Límite de esfuerzo/desplazamiento global, no admisibles individuales. Gravedad global −Z; en una cercha 2D XY las cargas gravitatorias normales se rechazan. El umbral de condición detecta inestabilidad numérica pero no es una prueba de seguridad estructural. Las pruebas cubren casos definidos, no todas las geometrías posibles ni toda instalación SAP. SAP requiere Windows/licencia/OAPI; Qt requiere una sesión gráfica. El formato conserva documentos anteriores, pero descarta resultados incompatibles en lugar de presentarlos como actuales.

## Archivos y evidencia

Fuentes modificados: core, fem, prepared_fem, nuevo truss_kernel y units, analysis, sap_mapping/sap, editor_commands/editor_properties/editor_libraries, ui, cli, laboratory, optimization_runtime, lab_report. Pruebas: test_audit_regressions, test_modeler_ui y nombre del ensayo de compatibilidad en test_laboratory. Scripts: audit_inventory, verify_audit y extensión opcional audit-update del ensayo UI/SAP. Documentación: README, CONTRIBUTING, guías e informe presente. El diff Git constituye la lista exacta.

Evidencia seleccionada: `data/evidence/audit_20261018/`. Los directorios de ejecución completos permanecen locales; los archivos de evidencia identifican los originales. Los ensayos con dobles COM de la suite son pruebas unitarias del ciclo de vida, no evidencia SAP real. Los SDB/JSON/CSV de esta auditoría proceden de SAP real y están identificados como tales.


La comprobación Qt/SAP con `verify_modeler_ui_sap.py --audit-update` pasó: campaña desde el botón, aplicación del ganador, apertura visible desde el botón, edición de área y actualización en copia nueva; el hash del SDB anterior no cambió. Evidencia `qt_open_update_sap.json`, `qt_initial.sdb` y `qt_updated.sdb`.

El cierre que no se sustituye es el de la aplicación del usuario: ninguna prueba envía entradas a sus ventanas. Las ventanas Qt de prueba y las instancias SAP creadas por ellas son independientes. La habilidad de control de Windows se usó solo para inventariar ventanas durante el diagnóstico, sin modificar modelos.


La siguiente ejecución conjunta terminó con 76 pruebas aprobadas (196.36 s), pero emitió diagnósticos nativos Windows RPC 0x800706ba durante `comtypes.client.PumpEvents`. No se interpretó ese código de salida cero como ausencia de incidencias. Se sustituyó la espera RPC modal del STA ocioso por despacho estándar de mensajes de su propio hilo (`pump_sta_messages`), conservando afinidad y la cola serializada. La espera de integración usa ese mismo despacho. El resultado de la suite posterior y su registro completo se incorporan a la evidencia final. Las dos regresiones finales verifican además la envolvente guardada de casos y el rechazo de desbordamientos aritméticos.


### Cierre local final

La suite completa final aprobó **78/78 pruebas, 0 fallos, 0 omitidas, 187.95 s**, con Qt y ambas integraciones SAP activadas. Registro completo `audit_final_local.txt` y JUnit `audit_final_local.xml`. El despacho STA estándar y la espera con mensajes permiten completar las operaciones; los avisos 0x800706ba **no desaparecieron** y también se observaron dentro de Analyze.RunAnalysis. No se afirma haber corregido su origen en el SDK.

Se verificó que [CPython 3.11.9 faulthandler](https://github.com/python/cpython/blob/v3.11.9/Modules/faulthandler.c#L358-L417) imprime ese encabezado antes de devolver EXCEPTION_CONTINUE_SEARCH; el encabezado por sí solo no demuestra un cierre del proceso. En esta ejecución el proceso continuó, SAP devolvió estados/códigos válidos y se comprobaron respuestas, equilibrio y sesiones. Se conserva el registro sin ocultar avisos y se documenta esta incidencia de diagnóstico nativo como limitación pendiente. No se desactivó faulthandler para maquillar los resultados.


## Reproducción cerrada desde GitHub y SHA del código

**Commit de producción auditado y reproducido: `700bbdf10f6f54888a496f0b3d3f7af9ec4f6ab4`.** Fue descargado mediante fetch/checkout desde el remoto, no copiado desde la carpeta de desarrollo. El manifiesto `published_reproduction.json` registra huella de cada módulo de producción, versiones, ejecutable, sistema y **cero cambios rastreados** en el clon.

Resultado del clon limpio: **78 pruebas, 0 fallos, 0 errores, 0 omitidas; 198.185 s en JUnit** (198.23 s mostrado por pytest). Se activaron las ocho pruebas Qt y las dos integraciones SAP reales. El user site de Python estaba desactivado y el paquete trusslab se importó desde el clon; la generación COM se realizó dentro de su .venv. Pip check no encontró dependencias rotas.

También se repitieron las 40 corridas de los cinco métodos en el clon: 49.17 s para el ensayo numérico, pesos idénticos a la instalación original en las 20 corridas comparadas (máxima diferencia 0.0 lb). Después se ejecutó el experimento completo con SAP real en ese mismo checkout: **aprobado en 174.88 s**, incluyendo A–E y dos sesiones persistentes que verificaron diseño inicial y ganador de las cerchas 2D/3D en C1/C2/ULS. Sus mejores diseños, SDB, campañas completas, repeticiones, resultados, configuraciones y CSV se conservaron en la evidencia clean_planar/clean_spatial. Los algoritmos no recibieron un peso objetivo ni áreas publicadas como arranque.

GitHub Actions aprobó ambos trabajos numéricos, Windows y Ubuntu: https://github.com/frankrac123/repositorio-FEM/actions/runs/39110130233. CI no ejecuta Qt ni SAP; esos ensayos constan separadamente arriba.

Una evaluación presupuestada significa un candidato con todos los casos seleccionados, no cada resolución individual de Kff. Las referencias numéricas del Caso I también aparecen en textos iniciales heredados de UI; refresh reemplaza los contadores/selección con el documento real antes del uso. No gobiernan ensamblaje ni optimización; el inventario conserva las referencias encontradas.

### Ejecutar sin esperar al cierre de copias SAP visibles

Al redirigir salida nativa, PowerShell puede seguir esperando EOF de handles heredados por las ventanas SAP que deliberadamente permanecen abiertas, incluso después de que pytest haya terminado. Se verificó que los procesos Python habían salido; no se cerraron las copias SAP para desbloquear el shell. `scripts/run_audit_tests.py` utiliza archivos directos y espera el handle de pytest; guarda su código de salida, duración y número de diagnósticos nativos. Usar:

```powershell
.\.venv\Scripts\python.exe scripts/run_audit_tests.py --output data/audit/final_process -- -q --junitxml=data/audit/final_tests.xml
```

Los cambios posteriores al SHA de producción anterior añaden este ejecutor de pruebas, documentación y evidencia; no modifican la aplicación. El SHA exacto de entrega se obtiene con git rev-parse HEAD y se registra en el manifiesto que genera scripts/repro_manifest.py después de probar el checkout publicado. El informe entregado fuera del historial Git incorpora ese SHA final sin intentar incluir el hash de un commit dentro de sí mismo.
