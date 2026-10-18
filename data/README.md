# Datos y evidencias conservadas

El repositorio conserva resultados científicos y ejemplos necesarios para revisar el programa. Los archivos nuevos de ejecución se generan localmente bajo `data/` y quedan excluidos por `.gitignore` salvo selección explícita.

| Ruta | Contenido |
|---|---|
| `sap_case_i.trusslab.json` | Proyecto SAP histórico comprobado por las pruebas físicas |
| `automatic_final/sap_case_i.trusslab.json` | Análisis automático del ejemplo de aproximadamente 5060.856 lb |
| `visible_verification/sap_20261017_211826_49123b/` | SDB final visible, datos transferidos, auditoría y comparación FEM–SAP |
| `phase3_asam/` | Resumen de corridas, CSV y gráficos de ASAM |
| `phase3_ui/` | Capturas del programa y resultados de la prueba Qt |
| `phase3_verification/` | Resumen de pruebas SAP y resultado pytest histórico |
| `evidence/asam/seed42`, `seed7`, `seed17` | Configuraciones y trazas completas por evaluación, comprimidas con gzip |
| `evidence/sap/` | Ensayos persistente, SAP por candidato e híbrido: modelos, API y resultados |
| `evidence/manifest.json` | Origen, ubicación publicada, tamaño y SHA-256 de los archivos archivados |

Los diseños ASAM finales también se incluyen en `examples/ASAM_CasoI_semilla*.trusslab.json`, sin duplicar el historial completo en cada proyecto. Sus resultados numéricos se conservan; los historiales íntegros están en los archivos `evaluations.jsonl.gz`. La repetición de semilla 42 dio las mismas áreas y está documentada en el resumen; se conserva una traza de esa secuencia de diseños, cuyos tiempos de ejecución pueden variar entre repeticiones.

## Lectura de trazas

Gzip se lee con la biblioteca estándar de Python:

```python
import gzip
import json

with gzip.open('data/evidence/asam/seed42/evaluations.jsonl.gz', 'rt', encoding='utf-8') as stream:
    records = [json.loads(line) for line in stream]
```

Desde la raíz, `python scripts/summarize_phase3.py` regenera el informe y el gráfico de semilla 42 utilizando la evidencia comprimida cuando el historial local original no está en este clon. No ejecuta análisis nuevos. Requiere el entorno de escritorio, que incluye Matplotlib.

Los campos históricos `run_directory` y `sap_model` de los informes originales conservan las rutas de Windows donde se realizó la prueba. Son procedencia de la evidencia; las ubicaciones publicadas y sus huellas están en el manifiesto. No es necesario recrear esas rutas para abrir los ejemplos, ejecutar las pruebas o regenerar el informe.

## Alcance

- Las trazas ASAM contienen datos FEM; la verificación SAP individual de esas tres corridas sigue pendiente.
- En una sesión persistente, el SDB compartido conserva el modelo final, mientras el registro por candidato conserva los resultados históricos de cada evaluación. `best.trusslab.json` identifica al ganador de una búsqueda.
- No se publican la instalación ni licencias de SAP2000, entornos Python, inventarios del escritorio, cachés, archivos del solucionador recuperables, corridas incompletas o pruebas redundantes de desarrollo.
- El XML pytest y los resúmenes publicados son evidencia histórica local. El resultado de GitHub Actions se consulta por separado en la pestaña Actions.

Consulta [la validación de etapas 2–4](../docs/VALIDACION_FASE3.md) para interpretar los resultados y las tolerancias.
