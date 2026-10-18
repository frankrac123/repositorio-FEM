# Verificación del modelador · 18 de octubre de 2026

Resultado local: **57 pruebas aprobadas, 1 omitida**, sin fallos ni errores. Incluye tres pruebas Qt reales y una prueba SAP persistente real. El [JUnit](../data/evidence/modeler_20261018/final_tests.xml) identifica cada caso.

Además se ejecutaron scripts de integración reales, separados de pytest. Las instancias SAP ocultas pertenecían a las pruebas; la copia abierta mediante el botón de la interfaz quedó visible para inspección.

| Flujo solicitado | Comprobación ejecutada |
|---|---|
| 1. Proyecto 3D vacío | Diálogo Nuevo mediante QTest; sin nodos, barras ni resultados |
| 2. Cuatro nodos aislados | Entrada XYZ con teclado Qt y confirmación en el diálogo |
| 3. Modificar coordenadas | Negativo con coma decimal, Enter, cambio de selección, persistencia y coordenadas del visor |
| 4. Conectar gráficamente | Clics Qt en los nodos proyectados; conectividad central y del visor verificadas |
| 5. Carga negativa en Z | Escritura Qt, vector persistido y sentido geométrico de la flecha verificados |
| 6. Apoyos | Clics Qt individuales y asignación múltiple; sin Y automática y sin sobrescribir cargas |
| 7. Guardar y recuperar | Borradores y bibliotecas completos, migración JSON e igualdad de los datos recuperados |
| 8. Cercha nueva FEM | Triángulo 2D y trípode 3D, propiedades por barra y equilibrio |
| 9. SAP2000 | Auditoría de entrada, análisis, lectura y comparación real; botón Abrir probado con Qt |
| 10. Optimizar y actualizar SAP | SLSQP en ambos modelos nuevos, tres casos por candidato y actualización real en una sesión propia |
| 11. Caso I | Reapertura del proyecto histórico y nueva comparación SAP del diseño de 5060.855730007684 lb |
| 12. Cercha espacial | Geometría no coplanar, dos patrones y tres casos; FEM/SAP antes y después de optimizar |

Resultados observados de las búsquedas, sin afirmar óptimos globales:

| Modelo | Peso inicial (lb) | Peso factible obtenido (lb) | Evaluaciones de diseño |
|---|---:|---:|---:|
| Triángulo 2D | 127.540000 | 34.834439 | 34 |
| Trípode espacial | 272.971169 | 32.423981 | 77 |

El laboratorio Qt ejecutó ASAM, DE y SLSQP sobre el modelo nuevo con los tres casos; se comprobó que conserva la instantánea original, permite aplicar el diseño elegido y recupera su historial. Sus comprobaciones no se presentan como un estudio estadístico de rendimiento.

La prueba histórica visible que aparece omitida abre varias ventanas adicionales y necesita `TRUSSLAB_RUN_SAP_INTEGRATION=1`. El botón visible del flujo nuevo sí se ejecutó y su estado SAP bloqueado/analizado se registró por separado.

Evidencia: [manifiesto y huellas](../data/evidence/modeler_20261018/manifest.json), [optimización y comparación por caso](../data/evidence/modeler_20261018/optimization_verification.json), [botón Qt y sesión visible](../data/evidence/modeler_20261018/qt_laboratory_sap.json), [referencia histórica](../data/evidence/modeler_20261018/benchmark_reference.json), [captura del editor](../data/evidence/modeler_20261018/qt_editor.png).

Los SDB archivados son copias de modelos reales. SAP puede requerir volver a ejecutar el análisis si se abre una copia sin sus archivos auxiliares; los resultados y comparaciones numéricos completos se conservan en los JSON. Las rutas absolutas dentro de los informes identifican el entorno original de ejecución.

También se exportó una campaña nueva a PDF y Excel: las diez páginas del PDF se renderizaron y revisaron visualmente; Excel conserva esfuerzos y desplazamientos separados por caso. Los archivos están en `data/evidence/modeler_20261018/report`.
