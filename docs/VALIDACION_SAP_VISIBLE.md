# Validación de la integración visible — SAP2000 26.3.0

Se realizaron análisis reales con la instalación existente, no con respuestas simuladas. Las sesiones visibles se dejaron abiertas para inspección. No se cerró ni sobrescribió ningún modelo previo del usuario.

## Caso I original: comprobación final

- Diseño actual del ejemplo: **5060.855730008 lb**.
- Se leyeron desde SAP exactamente **6 nodos y 10 barras**.
- Coordenadas y conectividades: comprobadas por lectura independiente.
- Áreas: coinciden individualmente con la instantánea transferida; no se sustituyeron por 35 in².
- Material: E = 10,000 ksi; densidad = 0.0001 kip/in³.
- Cargas: −100 kips en Z en nodos 2 y 4; peso propio desactivado.
- Apoyos en 5 y 6, grados de libertad, articulaciones y automallado: comprobados.
- Visibilidad confirmada por OAPI: **True**.
- Estado final CASE_I después de guardar: **4 (Finished)**.
- El gestor liberó las referencias en su hilo propietario sin llamar a ApplicationExit. La comprobación posterior de procesos confirmó que las ventanas SAP permanecían abiertas; TrussLab respondía.

Archivo del modelo: [TrussLab_CaseI.sdb](../data/visible_verification/sap_20261017_211826_49123b/TrussLab_CaseI.sdb).

Informe: [comparison.json](../data/visible_verification/sap_20261017_211826_49123b/comparison.json); [tabla CSV](../data/visible_verification/sap_20261017_211826_49123b/comparison.csv); [auditoría de entradas](../data/visible_verification/sap_20261017_211826_49123b/input_audit.json).

| Comparación | Error máximo absoluto |
|---|---:|
| Desplazamientos | 6.6613e-16 in |
| Fuerzas | 8.5265e-14 kip |
| Esfuerzos | 1.7764e-14 ksi |
| Reacciones | 1.5365e-13 kip |
| Peso | 0.0000e+00 lb |

Equilibrio FEM y SAP: aprobado. Máxima relación de esfuerzo: 0.999998395. Máxima relación de desplazamiento por componente: 0.999999990. Acción no axial máxima de SAP: 0.0000e+00.

## Transferencia desde los métodos de la interfaz y actualización

Una instancia Qt controlada ejecutó la señal del botón ABRIR EN SAP2000 con el diseño de **5,076.668036816 lb**. Los resultados recibidos, su huella y las 57 filas de comparación coincidieron. Esa prueba permitió descubrir y corregir el guardado posterior que invalidaba el caso, como se explica abajo.

La actualización posterior, con el guardado corregido, cambió deliberadamente:

- Todas las áreas multiplicadas por 1.1, respetando el máximo.
- X del nodo 1 de 720 a 730 in.
- Carga Z del nodo 4 de −100 a −95 kips.
- Restricción X del nodo 3 activada.

El nuevo peso fue **5584.524682454 lb**. La lectura de entradas, la comparación FEM, el equilibrio y el estado Finished pasaron. Se verificaron un SDB nuevo, la referencia a la sesión anterior y el SHA-256 inalterado del archivo anterior. La sesión nueva confirmó visibilidad y CASE_I = 4. La anterior se conservó sin modificar.

La interfaz procesó **474 eventos periódicos de 100 ms** durante esta prueba asíncrona. El botón y la recepción de resultados fueron comprobados mediante componentes Qt de una instancia de prueba; no se inyectó entrada en las ventanas del usuario. La tabla se comprobó por separado: **57 filas, 9 columnas, todos los estados OK**.

Evidencias: [flujo de interfaz y actualización](../data/ui_sap_verification.json) y [tabla Qt](../data/ui_comparison_verified.json). El inventario local de ventanas utilizado durante el desarrollo no se publica en el repositorio.

## Modo automático

Se analizó el mismo ejemplo de **5060.855730008 lb** en una instancia independiente, con lectura de entradas y comparación aprobadas. CASE_I permaneció terminado tras guardar. El registro confirma ApplicationExit con código cero para esa instancia; las sesiones visibles anteriores permanecieron abiertas.

Evidencia: [proyecto y resultados automáticos](../data/automatic_final/sap_case_i.trusslab.json).

## Problemas encontrados y corregidos

1. El nombre del sistema global vuelve como GLOBAL; su comparación ahora ignora mayúsculas.
2. Unhide devuelve código 1 al aplicarse a una instancia ya visible; ahora primero se consulta Visible().
3. El guardado con ruta explícita después del análisis desbloqueaba el modelo y cambiaba CASE_I de 4 a 1. Se observó que el caso seguía terminado después de RefreshView/RefreshWindow y se invalidaba exactamente tras File.Save(ruta). La corrección usa File.Save() sin ruta, verifica el estado después de guardar y conserva los resultados disponibles en SAP.

Las ejecuciones anteriores a estas correcciones se conservaron como diagnóstico y no se presentan como prueba de resultados persistentes. El modelo enlazado en la primera sección corresponde a la comprobación final corregida.

## Pruebas y alcance de la revisión visual

La suite terminó con **18 pruebas aprobadas y 1 omitida**, sin advertencias. La omitida es la prueba OAPI real que requiere activación explícita para no abrir aplicaciones inesperadamente al ejecutar pytest. Los análisis reales descritos arriba se ejecutaron separadamente durante el desarrollo.

Se inspeccionó la ventana TrussLab y se confirmó que el botón era visible. El control de escritorio se detuvo después con Escape. No se verificó visualmente la activación manual de las capas de deformada, fuerzas y reacciones dentro de SAP; esas capas no se activan automáticamente y se documentan en [la guía de uso](SAP2000_VISIBLE.md). Sí se verificaron por OAPI sus resultados numéricos, el archivo activo, la visibilidad y la permanencia de las ventanas.

Si TrussLab ya estaba abierto, hay que volver a iniciarlo para cargar los cambios. El lanzador existente carga directamente las fuentes actualizadas.
