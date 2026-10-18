# Modelador estructural: guía y arquitectura

La aplicación existente inicia con un documento vacío. El Caso I se conserva como ejemplo y sus proyectos antiguos se abren mediante migración en memoria de `trusslab/1` a `trusslab/2`.

## Construir una cercha

1. Pulsa **Nuevo** y elige cercha 2D o 3D. Define el nombre y, para 2D, el plano XY, XZ o YZ. También puedes elegir un ejemplo independiente.
2. Pulsa **XYZ…** o **Nodo** para introducir coordenadas. Los nodos se crean sin barras, cargas ni apoyos. En 2D se bloquea la coordenada normal al plano.
3. Para dibujar con el ratón selecciona **Crear nodo**, una vista apropiada, el plano y la elevación. El clic intersecta el rayo de cámara con ese plano. Un nodo introducido fuera de la vista provoca un encuadre automático que conserva la dirección de cámara. **Captura** ajusta a la malla y a nodos existentes. Una vista paralela al plano avisa y no inventa profundidad.
4. Usa **Conectar nodos** y haz clic en sus extremos; **Barra…** permite escribir sus ID. El cruce visual entre barras no añade una unión.
5. Selecciona una entidad. Escribe coordenadas, fuerzas o áreas y confirma con **Enter** o **Aplicar cambios**. Los controles permanecen activos durante la escritura; aceptan signo negativo y separadores decimal punto o coma.
6. Marca las restricciones X/Y/Z. **Aplicar solo apoyos** permite asignarlas a varios nodos sin alterar sus fuerzas. Ctrl + clic añade o retira entidades de la selección. **Aplicar solo fuerzas** conserva los apoyos.
7. **Cargas** permite crear patrones, sus tipos y peso propio; asignar fuerzas a uno o varios ID; y definir casos mediante factores, por ejemplo `LC1=1.2; LC2=1.6`. La casilla **Optimizar** selecciona todos los casos cuyas restricciones se comprobarán en cada candidato.
8. **Bibliotecas** permite editar materiales (E y peso específico), secciones (área) y límites de diseño. Propiedades asigna material, sección y grupo por barra. Cambiar el área de una sección actualiza las barras que la utilizan; el área individual y la optimización pueden dar a una barra un área propia.
9. **Mover nodo** usa el plano activo; también puedes mover mediante sus coordenadas exactas. **Copiar** duplica geometría con un desplazamiento; **Grupo** selecciona barras por nombre. **Eliminar**, Ctrl+Z y Ctrl+Y operan sobre el documento real. Las copias de geometría nacen libres, sin duplicar cargas ni apoyos.
10. Guarda el proyecto en cualquier etapa. Los documentos vacíos, con nodos aislados o sin apoyos son borradores válidos.

**Validar** comprueba datos y estabilidad y marca el documento listo para análisis. **Analizar** calcula la respuesta. Editar geometría, apoyos, cargas o propiedades invalida los resultados. No se ejecuta un análisis al escribir un número.

## Análisis y optimización

El FEM utiliza EA/L por barra, su longitud y cosenos directores reales, restricciones explícitas, recuperación axial y reacciones. En 2D la traslación normal se elimina por la definición del sistema; no se guarda como apoyo automático. En 3D se utilizan XYZ. Una coordenada Y=0 no impone una restricción.

Solo están implementadas cerchas lineales axiales en unidades kip/in/ksi. No hay rigidez artificial ni elementos de viga/pórtico. La gravedad actúa en −Z. El peso propio solicitado se reparte por mitades en los extremos de cada barra; se recalcula al cambiar sus áreas. Esta misma equivalencia se utiliza en SAP para evitar que una carga distribuida de frame introduzca cortante o flexión.

ASAM, DE y SLSQP toman el modelo actual. Los grupos de diseño comparten una variable de área; las barras restantes tienen variables independientes. El laboratorio conserva también ASAM+SLSQP y DE+SLSQP. Las restricciones se comprueban en todos los casos seleccionados. Los vectores de fuerzas y desplazamientos guardados pertenecen a casos reales, no a una mezcla de componentes. Los indicadores globales muestran el máximo entre casos y el resultado identifica el caso representado.

## SAP2000

**ABRIR EN SAP2000** valida el documento, crea una instancia propia y un directorio único, transfiere y relee geometría, propiedades, apoyos, patrones y factores, analiza, compara y conserva la ventana visible. **Actualizar** crea otra copia para preservar cualquier modificación manual de una sesión anterior.

Los nombres SAP derivan del proyecto y de los ID. `sap_mapping` conserva la correspondencia explícita para materiales, secciones por barra, patrones y casos; las respuestas incluyen además el mapeo de nodos y barras del informe de entrada. Los SDB tienen un nombre específico del proyecto. Guardar después del análisis utiliza `File.Save()` sin nombre para conservar los resultados de SAP2000 26.3.0.

Las sesiones COM siguen en su hilo propietario. La optimización SAP actualiza áreas y cargas de peso propio dentro de una instancia oculta propia. Las pruebas automáticas solo cierran sus propias instancias ocultas; la prueba de apertura visible deja su copia disponible para inspección.

## Responsabilidades del código

- `core.py`: StructuralModel/Model, Node, Element/Member, Material, Section, LoadPattern y AnalysisCase; integridad de borradores, cargas equivalentes y migración JSON.
- `engineering_types.py`: BoundaryCondition, contrato AnalysisResult y descripción OptimizationProblem. Los apoyos se conservan en `Node.fixed` por compatibilidad; `Model.supports` expone sus entidades y `set_support` valida las asignaciones.
- `editor_commands.py`: creación, copia y eliminación de entidades, estados de herramientas y pila de deshacer/rehacer.
- `editor_properties.py`: controles numéricos y confirmación de propiedades sin reconstrucción durante la edición.
- `editor_libraries.py`: materiales, secciones, patrones, casos y asignaciones.
- `scene.py`: representación del documento, selección, intersección rayo/plano, malla, captura y señales de dibujo.
- `analysis.py`, `fem.py`, `prepared_fem.py`, `validation.py`: estados, casos, restricciones, solución axial y comprobación independiente.
- `sap_mapping.py`, `sap.py`: nombres y adaptación OAPI, auditoría y sesiones COM.
- `design_space.py`, módulos de optimización y laboratorio: variables, algoritmos y experimentos reproducibles.
- `ui.py`: composición de ventanas y coordinación de acciones; delega operaciones de ingeniería a esos módulos.

El problema original de texto invisible se reprodujo en Windows: Qt/Fusion con QSS y controles sin botones dejaba el QLineEdit interno del spinbox con un ancho de 1 píxel. `NumberEdit` controla su rectángulo interno y las pruebas verifican su ancho, texto y edición real. También se retiró la reconstrucción al perder foco y se ocultaron inmediatamente los editores reemplazados al cambiar de selección. En las tablas de biblioteca Enter ya no activa por accidente el botón Añadir.

## Comprobaciones reproducibles

Las pruebas Qt actúan sobre ventanas creadas para la prueba; no envían teclado a otras aplicaciones.

```powershell
$env:TRUSSLAB_RUN_QT='1'
$env:TRUSSLAB_RUN_SAP_BATCH='1'
.\.venv\Scripts\python.exe -m pytest -q --junitxml=data/modeler/final_tests.xml
.\.venv\Scripts\python.exe scripts/verify_modeler_sap.py
.\.venv\Scripts\python.exe scripts/verify_modeler_optimization.py
.\.venv\Scripts\python.exe scripts/verify_modeler_ui_sap.py
```

El último script abre una copia SAP visible deliberadamente. Con `--skip-sap` verifica únicamente el laboratorio, su aplicación al modelador y el historial.

Los informes y capturas conservados están en `data/evidence/modeler_20261018`. El manifiesto identifica lo ejecutado y los archivos originales de la evidencia. La prueba histórica visible de `tests/test_sap_integration.py` requiere un indicador adicional y puede aparecer omitida; el flujo visible nuevo se ejecutó por separado con `verify_modeler_ui_sap.py`.
