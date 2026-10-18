# Validación ejecutada — etapas 2, 3 y 4

Se amplió el proyecto existente; recuperación previa: commit `2053846`, etiqueta `pre-phase3-20261017`. La base pasó 18 pruebas con una integración opcional omitida. La suite ampliada terminó con **32 pruebas aprobadas y 2 integraciones opcionales omitidas**, registradas en `data/phase3_verification/unit_tests.xml`. Los ensayos reales siguientes se ejecutaron mediante scripts independientes; no son simulaciones de API.

## SAP2000 real 26.3.0

Se probaron tres candidatos de áreas uniformes 35, 30 y 25 in² en **la misma sesión propia**: pesos 14687.636354, 12589.402589 y 10491.168825 lb. Todos aprobaron la comparación FEM, equilibrio y estado final CASE_I=4. La sesión se cerró al terminar. El ensayo se repitió durante la corrección de la restauración del ganador.

La búsqueda SAP limitada a cuatro evaluaciones completó 4 análisis SAP y 0 evaluaciones del optimizador FEM. Fue una prueba de integración y presupuesto; no una optimización convergida.

La búsqueda híbrida completó 33 análisis FEM y 3 SAP: dos candidatos distintos verificados y una restauración del ganador. Se comprobó que la última huella del registro SAP coincide con el diseño final y con su SDB. No se tocó la sesión SAP previa del usuario.

Evidencia: [verification.json](../data/phase3_verification/verification.json). Cada carpeta allí referenciada conserva auditoría, SDB, comparación y registro de candidatos. `scripts/verify_phase3_sap.py` reproduce el ensayo. `TRUSSLAB_RUN_SAP_BATCH=1` habilita además la prueba pytest de integración oculta; no se habilita de forma predeterminada.

## Interfaz Qt/VTK

El panel utilizó resultados auténticos guardados del Caso I. Se probaron modos de geometría/esfuerzo/fuerza, amplificación, espesor visual, cargas, reacciones, desplazamientos y selección numérica. Se compararon copias profundas del resultado y la huella del modelo antes y después: no cambiaron. Se capturó el panel renderizado.

La búsqueda se ejecutó en QThread mientras un temporizador de la interfaz registró 32 pulsos. El contador permaneció estable durante la pausa y volvió a avanzar al reanudar. La detención finalizó con 310 evaluaciones y conservó un diseño factible; motivo: `cancelled`. No hubo errores reportados por la ventana. Se desactivó el renderizado perpetuo de geometría estática y se agruparon inserciones de mallas. Los cambios rápidos del panel se agrupan mediante temporizador.

Evidencia: [verification.json](../data/phase3_ui/verification.json), [panel SAP](../data/phase3_ui/resultados_sap.png), [configuración](../data/phase3_ui/configuracion.png). Ensayo: `scripts/verify_phase3_ui.py`. Estas pruebas operan únicamente ventanas creadas por el propio ensayo; no activan capas manuales de SAP.

## ASAM: verificación y límites del resultado

Mismos parámetros por corrida: Ti=0.05, Tf=1e-6, enfriamiento=0.96, 100 puntos preliminares, R0=17.45 in², reducción de radio=0.96, 50 propuestas por temperatura, máximo 300 ciclos y 16000 evaluaciones, estancamiento desactivado. Todas usan el benchmark de 25 ksi. No se inicia desde las áreas publicadas ni se impone un peso objetivo.

| Semilla | Peso factible (lb) | Máx. σ/admisible | Máx. u/límite | Evaluaciones | Terminación |
|---:|---:|---:|---:|---:|---|
| 42 | 5114.493884 | 0.981160736 | 0.999999603 | 13400 | temperature_final |
| 7 | 5097.238503 | 0.969169471 | 0.999999476 | 13400 | temperature_final |
| 17 | 5082.111427 | 0.999648772 | 0.999997716 | 13400 | temperature_final |
| 42 | 5114.493884 | 0.981160736 | 0.999999603 | 13400 | temperature_final |

La repetición de semilla 42 produjo exactamente las mismas áreas. Todas las soluciones se recalcularon con FEM; pasaron factibilidad y residuo de equilibrio menor que 1e-8 kip. Los mecanismos logísticos, uniformes, reducción de radio, límites y conservación del mejor factible tienen pruebas específicas. Las corridas de esta tabla siguen **pendientes de validación SAP individual**; las pruebas SAP anteriores verifican el funcionamiento del motor con otros candidatos.

Estos ensayos no reproducen todavía el mejor peso ASAM publicado de 5060.877 lb y no prueban un óptimo global. Tampoco comparan eficiencia entre algoritmos: el laboratorio de campañas y estadísticas es la etapa 5, aún pendiente.

Al recalcular las áreas publicadas redondeadas a tres decimales, el peso es 5060.871666808 lb y la relación máxima de desplazamiento 1.000001759846. Supera 1+1e-6 y se clasifica **infactible bajo la tolerancia del programa**. Esto no demuestra que las áreas originales sin redondear fueran inadmisibles; se necesita su precisión original para verificarlo.

La solución anterior archivada se recalculó: 5060.855730008 lb, relación de esfuerzo 0.999998394997 y desplazamiento 0.999999990000. La diferencia frente a 5060.877 lb es -0.021269992 lb. Una diferencia de ese tamaño puede deberse a redondeo y tolerancias, pero no se atribuye una causa única sin los datos originales ni se afirma superioridad.

Datos: [verification.json](../data/phase3_asam/verification.json), [corridas CSV](../data/phase3_asam/runs.csv), [gráfico PNG](../data/phase3_asam/convergencia_semilla42.png), [gráfico SVG](../data/phase3_asam/convergencia_semilla42.svg). `scripts/verify_phase3_asam.py` reproduce los ensayos; `scripts/summarize_phase3.py` regenera este informe sin análisis nuevos.

## Limitaciones antes de continuar

La pausa/detención espera a que retorne la llamada COM en curso. Un bloqueo externo de SAP no se resuelve matando instancias del usuario. Si una operación falla, se registran los errores y se libera la sesión propia; no hay sustitución silenciosa del motor. No se ha forzado un bloqueo real o un fallo de licencia de SAP durante estas pruebas; la ruta de fallo y cierre se prueba con dobles unitarios identificados.

La OAPI pública inspeccionada no ofrece selectores de todos los diagramas; el panel equivalente usa resultados recuperados de SAP. Se mantiene el uso manual de vistas SAP. El laboratorio comparativo, GA/PSO, campañas integrales, Excel/informe académico completo y generalización a materiales/patrones múltiples quedan pendientes, conforme al punto de parada solicitado.

El fundamento, decisiones ASAM y referencias verificables están en [ASAM_Y_MOTORES.md](ASAM_Y_MOTORES.md).
