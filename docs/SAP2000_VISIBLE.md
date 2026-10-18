# Abrir y actualizar el diseño en SAP2000

Esta función amplía la aplicación existente. El lanzador `TrussLab3D.exe` sigue siendo el mismo: carga el código Python de esta carpeta. Si TrussLab estaba abierto durante la actualización, ciérralo normalmente y vuelve a abrirlo para cargar los cambios.

## Abrir el diseño actual

1. Modela o abre un proyecto en TrussLab; también puedes optimizarlo.
2. Pulsa **ABRIR EN SAP2000** en la barra superior.
3. Espera a la transferencia y al análisis. La interfaz Qt sigue procesando eventos mientras OAPI trabaja.
4. SAP2000 queda visible con el modelo analizado. TrussLab muestra la tabla de comparación FEM / SAP2000.

Se transfieren las áreas presentes en el modelo, incluidas las procedentes de una optimización. No se sustituye el diseño por las áreas de 35 in² del benchmark inicial. El identificador SHA-256 de la instantánea transferida aparece como `model_fingerprint` en el informe.

## Actualizar después de editar

En el menú **⌄** junto al botón, elige **Actualizar modelo en SAP2000 (nueva copia)**. La operación toma una nueva instantánea de coordenadas, conectividades, áreas, material, apoyos y cargas.

Cada actualización crea **otra instancia y otro SDB**. La sesión anterior permanece abierta y no recibe ninguna orden de modificación, guardado o cierre. Esta política protege cambios manuales, incluidos los que todavía no se hayan guardado. No utiliza la instancia activa del usuario como destino. Puedes cerrar manualmente las copias que ya no necesites.

## Dos ciclos de vida

| Operación | Visibilidad | Al terminar |
|---|---|---|
| Analizar → SAP2000 y comparar | Segundo plano | Guarda y cierra solamente la instancia creada por esa operación |
| ABRIR EN SAP2000 / Actualizar | Visible | Conserva la aplicación y el modelo abiertos |

La clase `VisibleSapSessions` mantiene una cola de comandos y un hilo STA de larga duración. Los objetos `helper`, `app` y `SapModel` se crean, usan y liberan exclusivamente en ese hilo. El hilo procesa mensajes COM mientras está inactivo. La interfaz recibe únicamente diccionarios de resultados mediante señales Qt y `Future`; nunca recibe un puntero COM.

Cerrar TrussLab libera las referencias de sus sesiones visibles en el hilo propietario, sin llamar a `ApplicationExit`, guardar cambios manuales ni cerrar SAP. Los errores de transferencia/análisis tampoco cierran las sesiones visibles: quedan disponibles para diagnóstico. El modo automático conserva su cierre mediante `ApplicationExit(False)` sobre la instancia que él mismo creó.

## Comprobación de la transferencia

Antes del análisis, OAPI vuelve a leer los datos efectivamente presentes en SAP:

- Número y nombres de nodos y barras.
- Coordenadas y conectividades exactas.
- Área real de cada sección y material asignado.
- Módulo elástico, peso específico y peso propio desactivado.
- Apoyos, articulaciones, automallado desactivado y grados de libertad globales.
- Cargas de cada nodo, incluidas las dos cargas de −100 kips del Caso I.

Si los datos leídos difieren, se detiene la operación y queda el diagnóstico. Todos los códigos de retorno se comprueban y se registran. La versión instalada devuelve `GLOBAL` en las cargas: se compara el nombre sin distinguir mayúsculas. `Unhide` solo se llama si `Visible()` indica que SAP está oculto; volver a mostrar una instancia ya visible devuelve código 1 en esta instalación.

## Comparación, equilibrio y límites

La tabla contiene FEM, SAP2000, diferencia absoluta, error relativo, tolerancia y estado para cada desplazamiento, reacción, fuerza axial, esfuerzo y peso. El Caso I genera **57 filas**. Las filas de barras se alinean por identificador; no se comparan listas por posición. Los resultados incompletos, duplicados o no finitos no pueden validar.

Se usa error relativo `|SAP − FEM| / |FEM|` cuando `|FEM| > 10⁻¹²`; para valores próximos a cero se omite. La aceptación de cada fila depende de su tolerancia absoluta:

| Magnitud | Tolerancia |
|---|---:|
| Desplazamiento | 10⁻⁵ in |
| Fuerza axial / reacción | 10⁻⁴ kip |
| Esfuerzo | 10⁻⁵ ksi |
| Peso | 10⁻⁸ lb |
| Equilibrio global de fuerzas | 10⁻⁶ kip |
| Equilibrio global de momentos | 10⁻³ kip·in |

Además se verifica que SAP solo presente acción axial, y se comprueban ±25 ksi y ±2 in por componente libre. La coincidencia entre motores y la factibilidad son estados distintos: un modelo que incumple límites puede producir resultados coincidentes, pero no se presenta como un diseño factible.

## Visualización dentro de SAP

La biblioteca de tipos `SAP2000v1` instalada expone `View.RefreshView` y `View.RefreshWindow`; no expone un método para elegir por código el plano XZ ni todas las capas de resultados. Antes del análisis se reconstruye la vista y se restaura el encuadre predeterminado con `RefreshView(0, False)`; después se usa `RefreshWindow(0)`. El argumento `False` restablece el zoom; `True` conservaría el zoom anterior. SAP conserva su vista inicial; si necesitas una vista frontal del benchmark, selecciona el plano X-Z con Y = 0 desde los controles de vista de SAP.

La opción **Cómo consultar vistas y resultados en SAP2000** del menú de TrussLab y el archivo `VISTAS_EN_SAP2000.txt` explican las visualizaciones manuales:

- Numeración y apoyos: opciones de visualización de objetos.
- Secciones: asignaciones de elementos Frame, secciones `TL_A<ID>`.
- Cargas nodales: patrón `CASE_I`.
- Deformada: caso `CASE_I`.
- Fuerzas de barras: componente axial del caso `CASE_I`.
- Reacciones y desplazamientos: resultados de nodos y consulta con clic derecho.

No se afirma que esas capas se activen automáticamente. El modelo, las asignaciones y los resultados necesarios quedan disponibles dentro de SAP.

## Archivos de cada operación

Bajo `data/sap_FECHA_ID/` se guardan `TrussLab_CaseI.sdb`, `transferred.trusslab.json`, `results.json`, `input_audit.json`, `comparison.json`, `comparison.csv`, `api_calls.json`, `operation.json` y la guía de vistas. Las pruebas de integración pueden usar subcarpetas de `data/` para separar sus evidencias.

`operation.json` identifica la llamada en curso; `api_calls.json` conserva los retornos recibidos. Una sesión persistente inspeccionada mediante el gestor genera `session_status.json`, con visibilidad, archivo activo y estado de los casos. La existencia del bloqueo de edición no se usa como prueba de análisis: el estado de caso 4 indica que el análisis terminó.

El primer guardado utiliza una ruta nueva. Después del análisis se llama a `File.Save()` **sin pasar otra vez la ruta**. Se comprobó en esta instalación que `File.Save(ruta)` al terminar desbloqueaba el modelo y cambiaba `CASE_I` de estado 4 a 1; `File.Save()` conserva el análisis. La operación ahora comprueba nuevamente el estado del caso después de guardar y falla explícitamente si deja de estar terminado.

Las pruebas unitarias no abren SAP. La prueba real repetible está en `tests/test_sap_integration.py` y requiere activar expresamente `TRUSSLAB_RUN_SAP_INTEGRATION=1`; deja abiertas sus copias visibles para inspección.

La documentación de prueba y sus rutas concretas se recogen en `VALIDACION_SAP_VISIBLE.md` cuando finaliza la verificación real.
