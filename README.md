# TrussLab 3D

Aplicación de escritorio para modelar cerchas, calcular su respuesta axial y optimizar sus áreas. Interfaz PySide6 con visor PyVista/VTK, inspirada en la imagen proporcionada. La geometría del visor procede de las mismas entidades que utilizan FEM y SAP2000.

## Integración visible con SAP2000

La barra superior incluye **ABRIR EN SAP2000**. Transfiere el diseño actual, lo analiza y conserva SAP abierto. El menú **⌄** incorpora **Actualizar modelo en SAP2000 (nueva copia)**: preserva la sesión anterior y cualquier cambio manual. El modo automático sigue disponible por separado.

Consulta [la guía de uso y ciclo de vida](docs/SAP2000_VISIBLE.md) y [la validación real](docs/VALIDACION_SAP_VISIBLE.md). Si TrussLab ya estaba abierto, vuelve a iniciarlo para cargar el código actualizado.

La ampliación actual incorpora el panel de resultados SAP, motores FEM/SAP/híbrido y ASAM. Consulta [fundamento y uso](docs/ASAM_Y_MOTORES.md) y [resultados de las etapas 2–4](docs/VALIDACION_FASE3.md). El laboratorio comparativo y las etapas posteriores siguen pendientes.

## Abrir en este equipo

Abre **TrussLab3D.exe** en esta carpeta. También puedes usar **Abrir_TrussLab.cmd**. El ejecutable es un lanzador local: requiere conservar juntos el código y la carpeta `.venv`. No es un instalador autónomo ni un ejecutable portable.

El entorno Python 3.11 de 64 bits ya quedó preparado. SAP2000 no se instaló, reinstaló ni modificó.

Para reconstruir el entorno en otro equipo, instala Python 3.11 de 64 bits y ejecuta `Instalar.ps1` desde PowerShell. El archivo `requirements-lock.txt` fija las versiones utilizadas aquí. El lanzador detecta si falta el entorno. Si hay un error al abrir, consulta `data/startup_error.log`.

## Funciones incluidas

- Cámara orbital y zoom, vistas isométrica, frontal, superior y lateral.
- Selección de nodos/barras en la escena, el árbol o la tabla.
- Edición de áreas, coordenadas, apoyos, cargas, módulo elástico y límites.
- Creación de nodos conectados y barras entre nodos existentes; eliminación con confirmación.
- Geometría original y deformada calculada, numeración, cotas y colores de tracción/compresión.
- Análisis matricial de cerchas planas y espaciales con comprobación de estabilidad.
- Diagnóstico OAPI, análisis automático y sesiones SAP2000 visibles y persistentes.
- Actualización mediante copias nuevas, auditoría de datos leídos desde SAP y tabla FEM/SAP con errores, equilibrio y límites.
- ASAM, SLSQP y evolución diferencial con restricciones explícitas, presupuesto y trazabilidad.
- Motores seleccionables FEM, SAP2000 por candidato e híbrido con K verificaciones externas.
- Panel de resultados SAP auténticos, amplificación visual y controles de pausa/detención.
- Guardar/abrir proyectos JSON; exportar CSV, PNG, informe JSON y script Python del modelo.

La opción Python exporta un script; no incluye una consola integrada. La ampliación de etapas 2–4 se describe en [ASAM y motores](docs/ASAM_Y_MOTORES.md). SAP actualiza secciones en una sesión propia persistente durante la optimización. GA/PSO, laboratorio comparativo, pandeo, perfiles comerciales y comprobaciones normativas quedan pendientes.

## Uso

El proyecto de inicio es `examples/Caso_I_calculado.trusslab.json`: contiene un diseño calculado mediante SLSQP y su historial real. **Nuevo** restaura el Caso I con áreas iniciales de 35 in². **Analizar** permite elegir FEM o SAP2000. **Optimizar** configura algoritmo, motor, semilla, iteraciones, presupuesto, grupos y parámetros ASAM. El menú SAP incluye **RESULTADOS ESTRUCTURALES — SAP2000** después de analizar el diseño actual con SAP. Un doble clic en una barra de la tabla permite cambiar su área.

Los cambios del modelo invalidan el historial anterior y recalculan FEM. Si el cambio produce un mecanismo, los resultados se retiran y se informa la inestabilidad; no se añade rigidez artificial. Los campos del panel de propiedades tienen desplazamiento vertical cuando la ventana es pequeña. Los divisores permiten redistribuir el espacio.

Los límites de desplazamiento se comprueban **por componente libre**. La tabla muestra además la norma del desplazamiento en los extremos de cada barra; esa norma puede superar 2 in aunque cada componente cumpla el límite.

Atajos: Ctrl+N nuevo, Ctrl+O abrir, Ctrl+S guardar, F5 FEM, F6 SAP2000 y Supr eliminar. En la escena, arrastrar orbita, la rueda cambia el zoom y Mayús+arrastrar desplaza la cámara mediante los controles de VTK.

## Condiciones del Caso I

- Plano XZ, Y = 0; Z vertical positivo.
- Nodos 1 a 6 y conectividades exactamente como en la especificación entregada.
- Dos cargas de 100 kips hacia abajo, en nodos 2 y 4.
- Apoyos traslacionales en nodos 5 y 6; desplazamientos Y restringidos en todos los nodos.
- E = 10,000 ksi, peso específico = 0.10 lb/in³, 0.1 ≤ A ≤ 35 in².
- Esfuerzo admisible **±25 ksi**, confirmado por el usuario. Desplazamientos libres ±2 in por componente.
- Peso propio desactivado en el patrón del benchmark.
- W = Σ ρ A L en **lb**. Fuerzas en kip, longitudes en in y esfuerzos en ksi.
- Barras axiales articuladas; los cruces no crean nodos adicionales.

El material se denomina benchmark: E = 10,000 ksi no se presenta como una propiedad de acero A36. No se copiaron las cargas ni los resultados decorativos de la imagen.

## SAP2000 existente

Se comprobó SAP2000 **26.3.0**, ejecutable `C:\SAAP2000\SAP2000.exe`, con `SAP2000v1.Helper` registrado. Se reutilizó esa vía COM existente y se inspeccionó su biblioteca de tipos junto con `CSI_OAPI_Documentation.chm` de la instalación.

Puedes configurar otra ruta existente mediante la variable `TRUSSLAB_SAP_EXE`. La aplicación puede consultar si hay una instancia activa, pero los análisis y transferencias crean una instancia propia y un archivo nuevo bajo `data/sap_FECHA_ID/`. No vacían ni sobrescriben modelos abiertos del usuario. Las sesiones visibles permanecen abiertas; solo el modo automático cierra su propia instancia.

Cada ejecución guarda el SDB, el registro `api_calls.json`, resultados y comparación. Se comprueban los códigos de retorno. Las operaciones de una instancia se ejecutan en serie sobre el hilo que creó sus objetos COM.

Se utiliza el solucionador estándar en el proceso de SAP, configurado con `SetSolverOption_3(0, 1, 1, 0, 1, '')`. Las rotaciones globales están inactivas y se liberan R2/R3 en ambos extremos, y R1 en uno, para evitar una doble liberación torsional inestable. El automallado de las barras está desactivado.

**Entorno de ejecución:** los primeros intentos desde el entorno restringido del agente pudieron crear y guardar el modelo, pero SAP devolvió código 1 al analizar. El análisis real se completó al permitir la ejecución normal del proceso instalado. Esto no requirió modificar SAP ni sus licencias. Los resultados FEM siguen disponibles sin SAP conectado.

## Comprobaciones realizadas

El Caso I inicial y un diseño optimizado fueron analizados con **SAP2000 real**, no con un simulador de API. El diseño verificado pesó **5,060.856586 lb** y cumplió ambos límites. La referencia bibliográfica de 5,060.877 lb se usa para comparar; nunca se usa como objetivo impuesto ni como resultado prefijado.

Para ese diseño:

| Comparación SAP2000 / FEM | Máximo error absoluto |
|---|---:|
| Desplazamientos | 6.67 × 10⁻¹⁶ in |
| Fuerzas axiales | 5.69 × 10⁻¹⁴ kip |
| Esfuerzos | 1.07 × 10⁻¹⁴ ksi |
| Reacciones | 1.14 × 10⁻¹³ kip |
| Peso | 0 lb |

Componentes no axiales de SAP: 0. Máximo esfuerzo relativo: 0.999998041. Máximo desplazamiento relativo por componente: 0.999999990.

La evidencia exacta está en `data/sap_case_i.trusslab.json` y la carpeta SAP referenciada en ese archivo. El ejemplo de inicio se regeneró después desde un arranque uniforme reproducible: pesa aproximadamente **5,060.855730 lb** y está comprobado por FEM; sus áreas difieren ligeramente del diseño SAP anterior. Esta regeneración fue analizada posteriormente también en el modo automático actualizado; véase la guía de validación de la integración visible.

Las **18 pruebas automáticas** pasaron; las pruebas físicas originales cubren: barra con solución cerrada, cercha espacial y rotación de coordenadas, equilibrio de fuerzas/momentos, linealidad, errores geométricos/mecanismos, persistencia, SLSQP, DE y comparación de resultados SAP guardados con el mismo modelo. Tolerancias de comparación: 10⁻⁵ in, 10⁻⁴ kip para fuerzas/reacciones y 10⁻⁵ ksi. La clasificación de factibilidad admite 10⁻⁶ relativo como tolerancia numérica; el resultado final del optimizador se escala mínimamente para eliminar violaciones de redondeo y se recalcula.

La ventana y el nuevo botón se inspeccionaron en Windows. El control de escritorio se detuvo después con Escape; las pruebas posteriores utilizaron OAPI y componentes Qt controlados, sin manejar las ventanas del usuario. La guía de validación distingue estas comprobaciones de la inspección visual de las capas de resultados de SAP.

## Ejecución por consola

Desde esta carpeta, usando PowerShell:

```powershell
& .\.venv\Scripts\python.exe -m trusslab.cli diagnose --output data
& .\.venv\Scripts\python.exe -m trusslab.cli fem --output data
& .\.venv\Scripts\python.exe -m trusslab.cli sap --output data
& .\.venv\Scripts\python.exe -m trusslab.cli optimize --method SLSQP --output data
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe scripts\reproduce_example.py
```

SLSQP es local: un arranque puede converger a aproximadamente 5,076.67 lb. El ejemplo aplica dos arranques documentados en `scripts/reproduce_example.py`, sin introducir áreas óptimas ni pesos finales prefijados. La segunda búsqueda modifica el área inicial A3 para abandonar la cuenca anterior. No se afirma que un resultado sea un óptimo global demostrado. DE está implementado y pasó una prueba breve; no se realizó un estudio estadístico de convergencia ni comparación de 100 corridas.

## Organización

`core.py` define entidades, benchmark y persistencia; `fem.py` contiene rigidez axial 3D; `validation.py` comprueba comparaciones, equilibrio y límites; `sap.py` aísla OAPI; `optimization.py` gestiona restricciones y algoritmos; `scene.py` dibuja la geometría; `ui.py`, `widgets.py` e `icons.py` construyen la interfaz. `tests/` contiene verificaciones físicas y `scripts/` permite reproducir el ejemplo.

## Fuentes y decisiones

- [Millán-Páramo, Matoski y Mazer (2017), DOI 10.18845/tm.v30i2.3209](https://doi.org/10.18845/tm.v30i2.3209). Se leyó el PDF aportado: objetivo y restricciones, modificaciones de ASAM y Cuadro 1. ASAM combina exploración preliminar, reducción del radio y aceptación logística 1/(1+exp(Δf/T)). Su reproducción y validación quedan pendientes; no se ofrece una implementación aproximada bajo ese nombre. El usuario confirmó 25 ksi como límite correcto.
- [SAP2000-python-for-structural-optimization](https://github.com/marco-rosso-m/SAP2000-python-for-structural-optimization): referencia de integración OAPI y uso de GA/pymoo; README incompleto y sin licencia explícita identificada en la vista inspeccionada. No se copió código.
- [PySap2000](https://github.com/HeisenbergJY1/PySap2000): wrapper COM con comtypes, Windows, SAP v20+ según README; declara MIT. Se optó por un adaptador reducido propio verificado contra la biblioteca instalada para controlar las firmas y retornos.
- [PyVista](https://github.com/pyvista/pyvista) y [PyVistaQt](https://github.com/pyvista/pyvistaqt): licencias MIT. Dependencias principales VTK/NumPy y QtPy/Qt. Se instalaron y utilizaron PyVista 0.49.1 y PyVistaQt 0.13.1 con PySide6 6.12.0. Su compatibilidad conjunta quedó comprobada al abrir el visor.
- [pymoo](https://github.com/anyoptimization/pymoo): Apache-2.0; biblioteca extensible para GA, DE, PSO y multiobjetivo. Revisada, sin instalar ni incorporar código. Se utiliza SciPy para los dos algoritmos actuales.
- [SciPy SLSQP](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html) y [evolución diferencial](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.differential_evolution.html). GA combina selección/cruce/mutación; PSO actualiza partículas mediante memoria individual y colectiva; DE usa diferencias entre candidatos y selección. Estos últimos se distinguen de una reproducción científica de ASAM.

La revisión de repositorios permitió evaluar arquitectura, dependencias y licencias. No se realizó una auditoría completa de mantenimiento, seguridad o compatibilidad de todas sus versiones; la compatibilidad afirmada se limita a las versiones efectivamente instaladas y probadas en este equipo. Las dependencias conservan sus licencias en el entorno; SAP2000 permanece como software externo del usuario.
