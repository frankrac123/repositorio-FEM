# Desarrollo y pruebas

El código de producción está en `trusslab/`; los scripts de experimentación en `scripts/`, y las pruebas en `tests/`. Mantén separados los resultados FEM, SAP2000 y los pendientes de verificación externa.

## Preparar el entorno en Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Para trabajar exclusivamente en el núcleo numérico, sin interfaz ni SAP, basta instalar `numpy`, `scipy` y `pytest`. Las pruebas unitarias de colas y ciclo de vida utilizan un doble COM limitado a esas pruebas; las integraciones opcionales conservan COM real. GitHub Actions ejecuta las pruebas unitarias en Windows y Linux. No valida automáticamente la interfaz gráfica ni una instalación real de SAP2000.

## Pruebas de integración explícitas

La suite habitual no inicia SAP. Los siguientes comandos necesitan Windows, SAP2000 disponible y su OAPI registrada:

```powershell
# Una sesión oculta propia: actualiza áreas y la cierra al finalizar.
$env:TRUSSLAB_RUN_SAP_BATCH='1'
.\.venv\Scripts\python.exe -m pytest tests/test_sap_integration.py -q
Remove-Item Env:TRUSSLAB_RUN_SAP_BATCH

# Copias visibles independientes; quedan abiertas para inspección manual.
$env:TRUSSLAB_RUN_SAP_INTEGRATION='1'
.\.venv\Scripts\python.exe -m pytest tests/test_sap_integration.py -q
Remove-Item Env:TRUSSLAB_RUN_SAP_INTEGRATION
```

Los scripts de `scripts/verify_phase3_*.py` también documentan los ensayos reales. Desde la raíz, configura `$env:PYTHONPATH=(Get-Location).Path` antes de ejecutarlos. Consulta el alcance de cada ensayo en [la validación](docs/VALIDACION_FASE3.md).

## Publicación de cambios

- Añade fuentes, configuración, documentación, pruebas y ejemplos pertinentes.
- Conserva unidades, conectividades y restricciones del benchmark de 25 ksi.
- Comprueba `git diff --check` y las pruebas correspondientes al cambio.
- `.gitignore` excluye entornos, dependencias instaladas, cachés y datos de ejecución no seleccionados. Las evidencias conservadas se explican en [data/README.md](data/README.md).
- No introduzcas credenciales, licencias de SAP ni copias del software comercial.

Las corridas grandes se conservan en formato comprimido cuando se necesitan para revisión. Un resultado debe incluir su procedencia, parámetros y restricciones; una simulación de API de una prueba unitaria nunca debe presentarse como un análisis real de SAP.
