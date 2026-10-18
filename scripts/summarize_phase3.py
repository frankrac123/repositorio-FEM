"""Regenerate the stage report from executed evidence, without running solvers."""
from pathlib import Path
import csv,json
import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
science=json.loads((root/'data/phase3_asam/verification.json').read_text())
sap=json.loads((root/'data/phase3_verification/verification.json').read_text())
ui=json.loads((root/'data/phase3_ui/verification.json').read_text())
suite=ET.parse(root/'data/phase3_verification/unit_tests.xml').getroot().find('testsuite')
skipped=int(suite.attrib['skipped']);passed=int(suite.attrib['tests'])-skipped-int(suite.attrib['failures'])-int(suite.attrib['errors'])
rows=science['runs'];folder=root/'data/phase3_asam'
with (folder/'runs.csv').open('w',newline='',encoding='utf-8-sig') as file:
    keys=['seed','weight_lb','stress_ratio','displacement_ratio','evaluations','iterations','termination']
    writer=csv.DictWriter(file,fieldnames=keys,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
fig,ax=plt.subplots(figsize=(8,4.6),layout='constrained')
history=[json.loads(line) for line in (Path(rows[0]['run_directory'])/'evaluations.jsonl').read_text().splitlines()]
for feasible,color,label in [(True,'#4194ee','Candidato factible'),(False,'#e67b8d','Candidato infactible')]:
    sample=[h for h in history if h['feasible']==feasible]
    ax.scatter([h['evaluations'] for h in sample],[h['weight_lb'] for h in sample],s=2,alpha=.25,color=color,label=label,rasterized=True)
best=[h for h in history if h['best_feasible_lb'] is not None]
ax.plot([h['evaluations'] for h in best],[h['best_feasible_lb'] for h in best],color='#079b6c',lw=1.5,label='Mejor factible acumulado')
ax.set(xlabel='Evaluaciones FEM completadas',ylabel='Peso (lb)',title='ASAM · semilla 42 · Caso I · 25 ksi');ax.grid(alpha=.2);ax.legend()
fig.savefig(folder/'convergencia_semilla42.png',dpi=180);fig.savefig(folder/'convergencia_semilla42.svg');plt.close(fig)
table='\n'.join(f'| {r["seed"]} | {r["weight_lb"]:.6f} | {r["stress_ratio"]:.9f} | {r["displacement_ratio"]:.9f} | {r["evaluations"]} | {r["termination"]} |' for r in rows)
rounded=science['published_rounded_areas'];previous=science['earlier_solution_recomputed']
text=f'''# Validación ejecutada — etapas 2, 3 y 4

Se amplió el proyecto existente; recuperación previa: commit `2053846`, etiqueta `pre-phase3-20261017`. La base pasó 18 pruebas con una integración opcional omitida. La suite ampliada terminó con **{passed} pruebas aprobadas y {skipped} integraciones opcionales omitidas**, registradas en `data/phase3_verification/unit_tests.xml`. Los ensayos reales siguientes se ejecutaron mediante scripts independientes; no son simulaciones de API.

## SAP2000 real 26.3.0

Se probaron tres candidatos de áreas uniformes 35, 30 y 25 in² en **la misma sesión propia**: pesos 14687.636354, 12589.402589 y 10491.168825 lb. Todos aprobaron la comparación FEM, equilibrio y estado final CASE_I=4. La sesión se cerró al terminar. El ensayo se repitió durante la corrección de la restauración del ganador.

La búsqueda SAP limitada a cuatro evaluaciones completó {sap['sap_optimization']['sap_evaluations']} análisis SAP y 0 evaluaciones del optimizador FEM. Fue una prueba de integración y presupuesto; no una optimización convergida.

La búsqueda híbrida completó {sap['hybrid_optimization']['fem_evaluations']} análisis FEM y {sap['hybrid_optimization']['sap_evaluations']} SAP: dos candidatos distintos verificados y una restauración del ganador. Se comprobó que la última huella del registro SAP coincide con el diseño final y con su SDB. No se tocó la sesión SAP previa del usuario.

Evidencia: [verification.json](../data/phase3_verification/verification.json). Cada carpeta allí referenciada conserva auditoría, SDB, comparación y registro de candidatos. `scripts/verify_phase3_sap.py` reproduce el ensayo. `TRUSSLAB_RUN_SAP_BATCH=1` habilita además la prueba pytest de integración oculta; no se habilita de forma predeterminada.

## Interfaz Qt/VTK

El panel utilizó resultados auténticos guardados del Caso I. Se probaron modos de geometría/esfuerzo/fuerza, amplificación, espesor visual, cargas, reacciones, desplazamientos y selección numérica. Se compararon copias profundas del resultado y la huella del modelo antes y después: no cambiaron. Se capturó el panel renderizado.

La búsqueda se ejecutó en QThread mientras un temporizador de la interfaz registró {ui['ticks']} pulsos. El contador permaneció estable durante la pausa y volvió a avanzar al reanudar. La detención finalizó con {ui['result']['evaluations']} evaluaciones y conservó un diseño factible; motivo: `{ui['result']['message']}`. No hubo errores reportados por la ventana. Se desactivó el renderizado perpetuo de geometría estática y se agruparon inserciones de mallas. Los cambios rápidos del panel se agrupan mediante temporizador.

Evidencia: [verification.json](../data/phase3_ui/verification.json), [panel SAP](../data/phase3_ui/resultados_sap.png), [configuración](../data/phase3_ui/configuracion.png). Ensayo: `scripts/verify_phase3_ui.py`. Estas pruebas operan únicamente ventanas creadas por el propio ensayo; no activan capas manuales de SAP.

## ASAM: verificación y límites del resultado

Mismos parámetros por corrida: Ti=0.05, Tf=1e-6, enfriamiento=0.96, 100 puntos preliminares, R0=17.45 in², reducción de radio=0.96, 50 propuestas por temperatura, máximo 300 ciclos y 16000 evaluaciones, estancamiento desactivado. Todas usan el benchmark de 25 ksi. No se inicia desde las áreas publicadas ni se impone un peso objetivo.

| Semilla | Peso factible (lb) | Máx. σ/admisible | Máx. u/límite | Evaluaciones | Terminación |
|---:|---:|---:|---:|---:|---|
{table}

La repetición de semilla 42 produjo exactamente las mismas áreas. Todas las soluciones se recalcularon con FEM; pasaron factibilidad y residuo de equilibrio menor que 1e-8 kip. Los mecanismos logísticos, uniformes, reducción de radio, límites y conservación del mejor factible tienen pruebas específicas. Las corridas de esta tabla siguen **pendientes de validación SAP individual**; las pruebas SAP anteriores verifican el funcionamiento del motor con otros candidatos.

Estos ensayos no reproducen todavía el mejor peso ASAM publicado de 5060.877 lb y no prueban un óptimo global. Tampoco comparan eficiencia entre algoritmos: el laboratorio de campañas y estadísticas es la etapa 5, aún pendiente.

Al recalcular las áreas publicadas redondeadas a tres decimales, el peso es {rounded['weight_lb']:.9f} lb y la relación máxima de desplazamiento {rounded['displacement_ratio']:.12f}. Supera 1+1e-6 y se clasifica **infactible bajo la tolerancia del programa**. Esto no demuestra que las áreas originales sin redondear fueran inadmisibles; se necesita su precisión original para verificarlo.

La solución anterior archivada se recalculó: {previous['weight_lb']:.9f} lb, relación de esfuerzo {previous['stress_ratio']:.12f} y desplazamiento {previous['displacement_ratio']:.12f}. La diferencia frente a 5060.877 lb es {previous['weight_lb']-5060.877:.9f} lb. Una diferencia de ese tamaño puede deberse a redondeo y tolerancias, pero no se atribuye una causa única sin los datos originales ni se afirma superioridad.

Datos: [verification.json](../data/phase3_asam/verification.json), [corridas CSV](../data/phase3_asam/runs.csv), [gráfico PNG](../data/phase3_asam/convergencia_semilla42.png), [gráfico SVG](../data/phase3_asam/convergencia_semilla42.svg). `scripts/verify_phase3_asam.py` reproduce los ensayos; `scripts/summarize_phase3.py` regenera este informe sin análisis nuevos.

## Limitaciones antes de continuar

La pausa/detención espera a que retorne la llamada COM en curso. Un bloqueo externo de SAP no se resuelve matando instancias del usuario. Si una operación falla, se registran los errores y se libera la sesión propia; no hay sustitución silenciosa del motor. No se ha forzado un bloqueo real o un fallo de licencia de SAP durante estas pruebas; la ruta de fallo y cierre se prueba con dobles unitarios identificados.

La OAPI pública inspeccionada no ofrece selectores de todos los diagramas; el panel equivalente usa resultados recuperados de SAP. Se mantiene el uso manual de vistas SAP. El laboratorio comparativo, GA/PSO, campañas integrales, Excel/informe académico completo y generalización a materiales/patrones múltiples quedan pendientes, conforme al punto de parada solicitado.

El fundamento, decisiones ASAM y referencias verificables están en [ASAM_Y_MOTORES.md](ASAM_Y_MOTORES.md).
'''
(root/'docs/VALIDACION_FASE3.md').write_text(text,encoding='utf-8')
print('Informe generado:',root/'docs/VALIDACION_FASE3.md')
