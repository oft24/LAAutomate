---
tags: [laautomate, contexto, referencia-completa]
alias: ["Contexto completo", "Todo el proyecto", "Brief de LaAutomate"]
actualizado: 2026-09-05
---

# LaAutomate — contexto completo del proyecto

> [!abstract] Para qué sirve este archivo
> Es el punto único de extracción de contexto. Si alguien —persona o
> modelo— tiene que entender LaAutomate entera sin leer el resto, lee esto.
> Cubre qué se quería, qué hay hecho, qué hace cada botón, qué está roto y
> qué falta.
>
> El resto de `docs/` profundiza en cada parte; el índice está en
> [[README]]. Este archivo es el resumen ejecutable, no un sustituto del
> código: **si algo aquí no coincide con el código, el código manda.**

**Revisado el 5 de septiembre de 2026** · 419 pruebas pasaron en la corrida
final; 12 de red/navegador excluidas. Evidencias, alcance y límites en
[[REVISION-UX-2026-09-05]].

---

## 1. Qué es y qué problema resuelve

LaAutomate es una **plataforma de escritorio para Windows** que automatiza
tareas repetitivas de ordenador: rellenar formularios web, mover datos de
Excel a sistemas sin API, sacar reportes de portales, operar aplicaciones
de escritorio.

La diferencia con Power Automate o UiPath: **cada automatización es un
archivo de Python normal**, no un diagrama en un diseñador visual. Se lee,
se edita, se versiona con git y se depura como cualquier otro código. El
diseñador visual funciona hasta que necesitas algo que no previó; el código
no tiene ese techo.

### Qué NO es

- No es un diseñador visual. Si no quieres ver código nunca, no es esto.
- No es un servicio en la nube. Corre en tu equipo, contra tus apps.
- No sustituye a una API. Si el sistema destino tiene API, úsala.
- No burla protecciones. Ante un reCAPTCHA se detiene y lo dice.
- La autocorrección **no garantiza que el arreglo sea correcto**, solo que
  deje de fallar. Por eso el código queda siempre a la vista.

---

## 2. Lo que se pidió, y qué pasó con cada cosa

| Pedido | Estado | Dónde |
|---|---|---|
| Validar lógica, funcionalidad, UI/UX y API | **Revisado** | Evidencias y límites en [[REVISION-UX-2026-09-05]] |
| Agente conectado a la API de Gemini | **Hecho** | Vista *Asistente IA* |
| Probar modelos actuales y poder elegirlos | **Hecho** | Desplegable con los modelos reales de la cuenta |
| Automatizar algo a partir de capturas | **Hecho** | *Crear desde capturas* en el chat |
| Agente corrector de automatizaciones | **Hecho** | Botón *Corregir código* |
| Portar todo a la versión de UI oscura | **Hecho** | Es la versión viva del repo |
| Guardar capturas del fallo y corregir con ellas | **Hecho** | Captura por intento en `logs/reparaciones/` |
| Máximo N reintentos | **Hecho** | 3 (era 5; una línea en `engine/autocorreccion.py`) |
| `.md` de prácticas que mejore el prompt | **Hecho** | [[PRACTICAS]] + [[PROMPT_CHANGELOG]] |
| Mejora del prompt en cada corrección validada | **Hecho** | `engine/optimizador_prompt.py` |
| Los dos agentes especificados (reparación y optimización) | **Hecho** | [[PROMPT_REPARACION]], [[PROMPT_OPTIMIZADOR]] |
| Push a GitHub sin subir nada confidencial | **Hecho** | Rama `main`, identidad `oft24` |
| Automatización de prueba: vídeos de YouTube desde Excel | **Hecho** | `automations/buscar_videos_youtube/` |
| Prompts más robustos | **Hecho** | `repair_prompt_v2` |
| Documentación para Obsidian | **Hecho** | 18 notas con metadatos y enlaces |
| Quitar emojis y código no funcional | **Hecho** | 0 emojis; 3 módulos muertos borrados |
| Icono negro y ejecutable en el escritorio | **Hecho** | Acceso directo en el escritorio |
| Que un fallo no bloquee el play | **Hecho** | La ejecución termina donde falla |
| Corregir como botón, no automático | **Hecho** | *Corregir código* |

### Pendiente / no hecho

- El **búfer de las 10 últimas capturas** durante la ejecución. Hoy solo se
  guarda la del instante del fallo (una por intento). El prompt de
  reparación contempla una secuencia cronológica que todavía no recibe.
- La protección frente a cambios externos del editor quedó corregida en
  esta revisión: compara con la versión cargada y conserva el borrador ante
  conflictos. Sigue pendiente ofrecer una comparación visual y persistir
  los borradores entre sesiones.
- **El instalador restaura tus automatizaciones sobre las del paquete**:
  correcto para no perder tus cambios, pero significa que una corrección
  publicada en una automatización de ejemplo no llega a una instalación ya
  existente.
- `gob.mx/curp` usa **reCAPTCHA Enterprise invisible** (por puntuación).
  Eso limita la fiabilidad de `curp_desde_excel` en lote. No se intenta
  esquivar.

---

## 3. Arquitectura

Tres capas que casi no se conocen entre sí:

```
app/      interfaz PySide6. Solo presenta lo que el motor expone.
core/     servicios transversales: config, logs, historial, credenciales, Gemini.
engine/   el motor. No sabe que existe una interfaz gráfica.

automations/   código del usuario. Nada en engine/ conoce una automatización concreta.
```

### El recorrido de una ejecución

```
  automations/<nombre>/automation.py
        │  @registrar(nombre=..., disparador=..., categoria=...)
        ▼
  engine/registry.py      descubre e importa todo automations/
        │                 resiliente: una rota no tumba la app
        ▼
  engine/scheduler.py     cron: / carpeta: / manual
        │
        ▼
  engine/runner.py        instancia, inyecta acciones, ejecuta
        │                 captura traceback + screenshot al fallar
        ├──► core/logger.py     un archivo de log por automatización
        ├──► core/database.py   historial en SQLite
        └──► engine/bitacora.py qué acciones se hicieron, en orden
```

### Módulos de `engine/`

| Archivo | Qué hace |
|---|---|
| `registry.py` | `@registrar` + descubrimiento tolerante a fallos |
| `runner.py` | Ejecuta, captura errores y capturas, guarda historial |
| `scheduler.py` | APScheduler: `cron:`, `carpeta:`, `manual` |
| `automation_base.py` | `BaseAutomation` y `AutomationResult` |
| `almacen.py` | Escribe una automatización en disco y la deja registrada |
| `bitacora.py` | Anota cada acción en orden, para saber qué pasaba al fallar |
| `diagnostico.py` | Reúne log + captura + causa de un fallo |
| `autocorreccion.py` | El ciclo de reparación (hasta 3 intentos) |
| `practicas.py` | Lee y amplía la memoria de lo aprendido |
| `optimizador_prompt.py` | Versiona el prompt de reparación |
| `actions/` | Lo que se inyecta en `self` |
| `triggers/file_watcher.py` | Dispara al aparecer un archivo en una carpeta |

---

## 4. Cómo se escribe una automatización

```python
from __future__ import annotations

from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar


@registrar(nombre="reporte_diario", disparador="cron:0 8 * * *", categoria="reportes")
class ReporteDiario(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        self.web.ir_a("https://portal.interno/login")
        self.web.escribir("#usuario", self.credenciales.usuario)
        self.web.escribir("#clave", self.credenciales.password)
        self.web.click("#entrar")
        filas = self.excel.leer("C:/reportes/ventas.xlsx")
        return AutomationResult(success=True, data={"filas": len(filas)})
```

Esas dos rutas de import son **las únicas válidas**. `engine.base` o
`engine.actions.AutomationResult` no existen: inventarlas da `ImportError`.

`AutomationResult`: `success` (obligatorio), `message`, `data`,
`started_at`, `finished_at`.

> [!warning] El `nombre=` del decorador es la identidad
> Con él se busca la automatización, se guardan sus credenciales y se
> registra su historial. Cambiarlo la deja sin credenciales y sin
> historial aunque el código funcione.

### Disparadores

| Valor | Qué hace |
|---|---|
| `manual` | Solo desde la interfaz |
| `cron:M H D M DS` | Cron estándar de 5 campos |
| `carpeta:C:/ruta` | Al crear un archivo ahí |

**Son los únicos tres.** Cualquier otra cadena se registra en el log como
disparador desconocido; la automatización aparece en la lista y nunca se
dispara. (Hubo `webhook` y `correo` documentados pero nunca conectados; se
eliminaron.)

---

## 5. La API de acciones

Todo esto lo inyecta el runner en `self` dentro de `ejecutar()`.

| Atributo | Métodos |
|---|---|
| `self.web` | `ir_a`, `click`, `escribir`, `seleccionar`, `leer_texto`, `pestanas`, `cambiar_a_pestana`, `cambiar_a_pestana_nueva`, `nueva_pestana`, `cerrar_pestana`, `descargar_en`, `esperar_descarga`, `screenshot_error`, `cerrar`, `driver` |
| `self.escritorio` | `iniciar_o_conectar`, `conectar_por_titulo`, `conectar_por_clase`, `atajo`, `escribir`, `esperar`, `leer_items_lista`, `click_por_texto`, `click_por_tipo`, `click_en`, `click_por_imagen`, `capturar_pantalla` |
| `self.excel` | `leer`, `escribir`, `com` |
| `self.http` | `get`, `post`, `con_token` |
| `self.correo` | `enviar_outlook`, `buscar_outlook_por_remitente`, `enviar_smtp` |
| `self.copiloto` | `abrir_copilot`, `buscar_agente`, `enviar_prompt`, `leer_tabla_de_respuesta`, `esperar_y_copiar_tabla`, `abrir_teams`, `abrir_chat_propio`, `pegar_y_enviar`, … |
| `self.credenciales` | `.usuario`, `.password`, `.token` — de la Bóveda |
| `self.logger` | Log de esta ejecución |

La referencia completa, con firmas, está en [[acciones]] y dentro de la app
en la pestaña **Wiki**.

---

## 6. Las ocho vistas y qué hace cada botón

### Panel principal

Cuatro KPIs (ejecuciones hoy, tasa de éxito a 7 días, duración media,
próxima ejecución), una tira de las últimas corridas y la tabla de
historial.

Revisión UX del 2026-09-04: los KPIs consultan todo el historial, no solo
las 100 filas visibles. «Hoy» usa la fecha local; éxito y duración usan
los últimos 7 días, excluyendo fechas futuras y duraciones negativas.
La tasa baja se muestra en rojo/ámbar, no siempre en verde.

| Botón | Qué hace |
|---|---|
| **Ejecutar todo** | Lanza todas las automatizaciones registradas, en serie |
| **01…08** | Chips de la tira: abren el detalle de esa corrida |
| **⋯** (por fila) | Menú de acciones de esa ejecución |
| **Ver captura de pantalla** | Abre la captura del error |
| **Abrir log completo** | Abre el `.log` de esa automatización |
| **Reintentar** | Vuelve a ejecutarla |
| **Ir a Automatizaciones** | Atajo cuando no hay ninguna todavía |

### Automatizaciones

Lista a la izquierda, editor de `automation.py` en el centro, riel de
acciones a la derecha, salida en vivo abajo.

| Botón | Qué hace |
|---|---|
| **▶ Ejecutar** | Guarda el editor, recarga el módulo y ejecuta. **La ejecución termina donde falla**: sin ciclo de reparación automático |
| **■ Cancelar** | Inyecta una cancelación en el hilo. Durante una reparación puede tardar hasta 2 min: el hilo espera la respuesta del modelo |
| **Corregir código** | Apagado hasta que una ejecución falla. Arranca el ciclo de reparación (3 intentos). Sin API key, carga el fallo en el chat para corregirlo a mano |
| **Guardar / Ctrl+S** | Valida sintaxis, identidad y disparador; escribe el editor, recarga el módulo y actualiza el programador activo. Si falla la importación, indica que el archivo se guardó pero no se activó |
| **Recargar archivo** | Lee la versión del disco; pide confirmación antes de descartar un borrador |
| **Bóveda** | Salta a la vista de credenciales |
| **Eliminar** | Borra la automatización (abajo del todo, lejos de los de uso frecuente) |

Los borradores se conservan al cambiar de selección durante la sesión.
Si el archivo fue editado externamente y también hay cambios locales,
Guardar/Ejecutar no sobrescribe: conserva el borrador y explica el conflicto.
Sin cambios locales, se recarga el archivo externo y se pide revisarlo antes
de ejecutar. Durante una ejecución se bloquean edición, selección y guardado.
Cerrar la ventana avisa de borradores pendientes y bloquea el cierre durante
operaciones activas de la interfaz. Esto no es una copia de seguridad persistente.

### Grabadora

| Botón | Qué hace |
|---|---|
| **Web / Escritorio** | Elige el modo |
| **Iniciar grabación** | Web: abre Chrome instrumentado. Escritorio: escucha clics y teclas |
| **Detener y generar código** | Convierte los pasos en un borrador editable; todavía no crea archivos |
| **Guardar automatización** | Valida y registra el código revisado; no sobrescribe nombres existentes |
| **Cancelar** | Descarta la grabación |
| **Ver registro** | Log de la grabadora |

Flujo: configurar → grabar → detener → revisar/editar → guardar explícitamente.
Una captura vacía no genera una automatización. La URL debe ser HTTP/HTTPS,
sin usuario/contraseña embebidos. Nombre y destino quedan bloqueados durante
la grabación. Iniciar otra sesión pide permiso para descartar un borrador pendiente.

**Nunca graba contraseñas**: detecta los campos de tipo `password` y deja
un `# TODO` apuntando a la Bóveda.

En escritorio, el **primer clic fija la ventana objetivo por HWND**; todo
clic en otra ventana se ignora mientras esa siga abierta. Existe por un
incidente real: una versión anterior escuchaba clics globales y un clic mal
calculado (varios monitores, escalado DPI) capturó texto de una ventana de
Edge distinta.

### Programador

Muestra las próximas ejecuciones de los disparadores `cron:`. Es una vista
de solo lectura: el disparador se declara en el decorador.
«Editar disparador» lleva al código de la automatización seleccionada. Los
cambios guardados se aplican sin reiniciar. Un cron inválido se informa sin
derribar el arranque; al cambiar/eliminar un disparador de carpeta se detiene
su observador. La aplicación debe permanecer abierta para disparar los trabajos.

### Asistente IA

| Botón | Qué hace |
|---|---|
| **Generar con Gemini** | Envía el mensaje, las capturas y el contexto |
| **Configurar clave** | Guarda la API key en el Almacén de credenciales de Windows |
| **Olvidar** | Borra la clave guardada |
| **Adjuntar / Limpiar capturas** | Imágenes de este turno |
| **Quitar seleccionada** | Retira una captura concreta; la lista muestra miniaturas y cantidad |
| **Actualizar modelos** | Vuelve a consultar los modelos de la cuenta; navegar a la vista no repite una consulta ya completada |
| **Crear desde capturas** | Plantilla de mensaje para generar desde imágenes |
| **Mejorar un flujo** | Plantilla para modificar una existente |
| **Explicar un error** | Carga el log y la captura del último fallo |
| **Copiar código** | Copia el bloque generado |
| **Crear automatización** | Escribe el código a disco y lo registra |

Un desplegable lista **los modelos reales de tu cuenta** (los usables
primero, separador, y el resto), y otro elige qué `automation.py` viaja
como contexto.

No incorpora `.env` ni la Bóveda automáticamente. **El diagnóstico sí carga
un fragmento del log en el mensaje**, y ese texto viaja al generar. Revisa
mensaje, código y capturas, que pueden contener datos sensibles; no existe
una garantía de anonimización automática. Las imágenes salen del equipo al
pulsar *Generar con Gemini*.

El contexto lateral tiene desplazamiento propio. La respuesta de código se
previsualiza en un panel separado con Copiar/Crear; nunca se ejecuta al recibirla.
Si la petición falla se conserva el mensaje para reintentar. Durante el envío
se bloquean los campos del turno. Se validan imágenes reales, formato, tamaño
total (12 MiB) y resolución (25 MP) antes del envío; una respuesta truncada
por MAX_TOKENS se trata como incompleta, no como código listo para guardar.
La validación AST al crear rechaza llamadas en herencia/metaclases y destinos
de asignación ejecutables: es una comprobación preventiva, **no un sandbox**.
El código generado necesita revisión humana antes de importarse o ejecutarse.

### Registros

| Botón | Qué hace |
|---|---|
| **Abrir carpeta** | Abre `logs/` en el Explorador |
| **Actualizar** | Relee el archivo |

Incluye búsqueda por nombre de archivo y búsqueda de texto con Enter.
La lectura del contenido y del indicador de errores está acotada a la cola
del archivo; un error más antiguo fuera de esa cola puede no marcarse.

### Bóveda de credenciales

| Botón | Qué hace |
|---|---|
| **Guardar en la bóveda** | Usuario / contraseña / token para una automatización |
| **Cancelar edición** | Descarta |

Todo va al **Administrador de credenciales de Windows** vía `keyring`.
Nunca a SQLite, ni al log, ni al código. `keyring` no permite enumerar, así
que la app pregunta por cada automatización conocida.
El formulario permite guardar usuario y contraseña para una automatización
registrada; muestra también la existencia de tokens, pero no añade un editor
de tokens. Los errores del almacén se informan sin mostrar los valores secretos;
las contraseñas guardadas no se precargan al editar.

### Wiki

La referencia de acciones, buscable, dentro de la app. La búsqueda permanece
arriba y todo el contenido explicativo se desplaza, sin comprimir ni recortar
sus párrafos. Al buscar se oculta la introducción; si no hay coincidencias,
se indica explícitamente.

---

## 7. El ciclo de autocorrección

```
   Ejecutar  ──falla──►  error en rojo, el play vuelve
                              │
                    la persona pulsa «Corregir código»
                              │
                              ▼
        ┌──── por cada intento (máximo 3) ─────────────┐
        │  ejecutar con bitácora activa                │
        │  si falla: captura + traceback + acciones    │
        │  → PROMPT_REPARACION + código + PRACTICAS    │
        │  → JSON de diagnóstico + código corregido    │
        │  → tres puertas de seguridad                 │
        │  → guardar, recargar módulo, reintentar      │
        └──────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
         reparada                        no reparada
              │                                │
   práctica nueva en PRACTICAS        informe al chat
   repair_prompt_vN+1                 (capturas + por qué + acciones)
   entrada en PROMPT_CHANGELOG
```

### Las tres puertas

| Puerta | Si no pasa |
|---|---|
| `status == "ESCALATE"` | Para y avisa: el agente se rindió |
| `safe_to_execute` falso o ausente | No se aplica. **Falla cerrada** |
| `risk == "HIGH"` | No se aplica: requiere revisión humana |

Y dos guardias más: si el código propuesto es **idéntico** al actual, se
corta (insistir gasta cuota); si no compila o pierde `@registrar`, se
restaura el original.

### Qué se aprende, y cuándo

Solo cuando la reparación **funcionó de verdad**. Una lección sacada de un
arreglo que no arregló nada contaminaría todas las reparaciones
siguientes.

- **Práctica** → [[PRACTICAS]], que se inyecta en el prompt de cada
  reparación **y de cada generación**.
- **Versión nueva del prompt** → `repair_prompt_vN+1`, archivada en
  `docs/prompts/`, con entrada en [[PROMPT_CHANGELOG]].

### La memoria vive en dos archivos

| Archivo | Qué es |
|---|---|
| `_internal/docs/PRACTICAS.md` | Lo que trae la versión. Solo lectura |
| `practicas_aprendidas.md` (junto al `.exe`) | Lo que aprendió **esta** instalación |

Están separados porque `_internal/` lo borra el instalador en cada
actualización: con un solo archivo había que elegir entre perder lo
aprendido o perder lo que trae la versión nueva. Lo que quedara en el
formato viejo se muda solo la primera vez.

---

## 8. Los tres prompts

| Archivo | Quién lo carga | Cuándo |
|---|---|---|
| [[GEMINI_SYSTEM_PROMPT]] | `core/gemini_client.py` | Cada mensaje del chat |
| [[PROMPT_REPARACION]] | `engine/autocorreccion.py` | Cada intento de reparación |
| [[PROMPT_OPTIMIZADOR]] | `engine/optimizador_prompt.py` | Tras una reparación validada |

Están en archivos `.md` y no dentro del `.py` para que se puedan revisar en
un *diff* y cambiar sin tocar el motor. **No llevan metadatos de Obsidian**:
su contenido se envía literal al modelo y el optimizador lee la versión de
la primera línea.

`PROMPT_REPARACION.md` va por `repair_prompt_v2`. Filtros que el código
aplica antes de aceptar una versión nueva: mínimo 2 000 caracteres,
crecimiento máximo ×1,6, y debe conservar las secciones *Reglas de
seguridad* y *Salida obligatoria*, la cadena `"status"` y los tres
`{{PLACEHOLDERS}}`.

> [!danger] El optimizador no se reescribe a sí mismo
> Solo crea versiones del prompt de reparación. Un sistema que reescribe
> las reglas con las que se juzga no tiene punto de apoyo.

---

## 9. Seguridad y privacidad

- **Credenciales**: Almacén de credenciales de Windows. Nunca en código,
  SQLite, logs ni historial de conversación.
- **La bitácora redacta**: `escribir`, `escribir_credencial` y
  `pegar_y_enviar` se anotan como *«texto de N caracteres, no registrado»*.
- **Los prompts indican tratar capturas, webs y logs como datos, no como
  instrucciones.** Es una mitigación de inyección de instrucciones, no una
  garantía de seguridad ni un aislamiento de ejecución. Revisa el código.
- **Exclusiones de Git**: `.env`, `datos/`, `logs/` y `core/rpa.db`
  están excluidos por defecto. Esto no reemplaza revisar lo que se va a
  publicar, ni elimina secretos pegados accidentalmente en otros archivos.
- La grabadora **no graba contraseñas**.
- Ante un captcha, la automatización se detiene y lo dice.

---

## 10. Instalación y empaquetado

```bash
empaquetar.bat
```

PyInstaller en modo **onedir**: `LaAutomate.exe` necesita su carpeta
`_internal` al lado (~345 MB, casi todo PySide6). Por eso el ejecutable
vive en `%LOCALAPPDATA%\LaAutomate` y en el escritorio va un acceso
directo.

Luego `dist\LaAutomate\INSTALL.bat`.

> [!warning] No instalar desde un proceso hijo de una app empaquetada MSIX
> Windows redirige las escrituras a `%LOCALAPPDATA%` hacia
> `...\Packages\<app>\LocalCache\Local\`. La instalación acaba en una copia
> fantasma y el acceso directo apunta a una ruta vacía. Pasó de verdad. La
> salida: lanzar el instalador desde el Programador de tareas, que corre
> fuera del contenedor.

El instalador borra el destino y **respalda antes** —a
`%LOCALAPPDATA%\LaAutomate_respaldos\<fecha>_<hora>\`, que no se consume—
estas seis cosas: `automations/`, `.env`, `core/rpa.db` (historial),
`logs/`, `datos/` (tus Excel) y `practicas_aprendidas.md`.

---

## 11. Desarrollo

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Windows y Python 3.11+. 14 dependencias (se eliminaron 8 que ningún
`import` usaba).

```bash
pytest -q                    # suite completa; el número aumenta con las regresiones
python tools/smoke_ui.py     # recorre la interfaz sin abrir ventana
python tools/review_ui.py    # 8 vistas × 2 tamaños; datos sintéticos, sin red ni ejecución
python tools/evaluar_prompts.py   # banco de casos de los prompts
```

`tests/test_runner_web.py` y `tests/test_pestanas_navegador.py` abren
Chrome de verdad; el resto no toca la red.

Para verificar los cambios de esta revisión de manera aislada:
`pytest -q tests/test_revision_ux.py tests/test_revision_flujos.py`.
`tools/review_ui.py` deja las capturas en `build/revision-ux/` y comprueba
que la ventana conserve 1360×860 y 1100×700. No sustituye una prueba interactiva
de accesibilidad ni ejecuta las automatizaciones personales.

> [!tip] Un doble de prueba más cómodo que el original no prueba nada
> Está en [[PRACTICAS]] porque costó: un doble que devolvía `str` donde el
> real devuelve un dataclass hacía pasar unas pruebas que en producción
> reventaban.

---

## 12. Lecciones que costaron caro

Estas no se deducen leyendo el código. Están medidas.

| Hallazgo | Consecuencia |
|---|---|
| `conectar_por_titulo` recorre el escritorio entero: **0,0 s por HWND vs. más de 2 min por título** con 389 ventanas abiertas | Se conecta por HWND cuando hay una sola coincidencia |
| `click_por_texto` busca el nombre de **accesibilidad**, no el texto dibujado. En la Calculadora en español `1`, `×` y `=` se llaman `Uno`, `Multiplicar por` y `Es igual a` | Si se puede por teclado, `escribir()`/`atajo()` no dependen del idioma |
| Un botón de navegación **marcable** de Qt se expone como `CheckBox`, no `Button`, y con espacios delante | `control_type="CheckBox"` y comparar con `.strip()` |
| Una celda vacía de Excel es `float("nan")`, y `str(nan)` es `"nan"` | Sin normalizar se envió «nan» como apellido a un servicio oficial |
| `elemento.text` de Selenium devuelve `""` si el elemento no está renderizado | Usar `get_attribute("textContent")` |
| Las apps WinUI descartan un `click_input()` de pywinauto por mandar los dos eventos demasiado rápido | Pausa real entre mouse-down y mouse-up |
| `change` solo se emite al perder el foco | La grabadora web escucha `input` |
| Un `<select>` no se rellena con `escribir()` | `self.web.seleccionar()`, o el formulario se envía vacío sin error |
| `MAX_INTENTOS` no se puede interrumpir dentro de una llamada HTTP | Bandera cooperativa además de la excepción asíncrona |

---

## 13. Las dos automatizaciones que hay

### `curp_desde_excel`

Lee `datos/personas.xlsx`, consulta gob.mx/curp fila por fila y guarda los
resultados. Selectores verificados contra la página real. **Limitación
conocida**: reCAPTCHA Enterprise invisible.

### `buscar_videos_youtube`

Lee `datos/videos_buscar.xlsx` (una fila por búsqueda: `tema` + `canal`
opcional), busca en YouTube y escribe `datos/videos_encontrados.xlsx`.

Es **incremental**: las búsquedas que ya tienen resultados se saltan, así
que añadir filas y volver a ejecutar solo consulta las nuevas. Si el Excel
no existe, lo crea con su cabecera y ejemplos.

Medido: 3 búsquedas / 15 filas / 50 s; luego +2 filas → solo buscó las 2
nuevas.

---

## 14. Mapa de archivos

```
LaAutomate/
├── app/                27 archivos · interfaz PySide6
│   ├── main.py
│   ├── workers.py          hilo de ejecución + ciclo de reparación
│   ├── windows/            las 8 vistas
│   ├── widgets/            tabla, badges, toast, sidebar…
│   └── resources/          tokens de color, iconos SVG, app_icon.ico
├── core/               6 archivos · servicios transversales
│   ├── config.py           rutas base, .env, nombre de la app
│   ├── logger.py           un log por automatización
│   ├── database.py         historial en SQLite
│   ├── vault.py            credenciales vía keyring
│   └── gemini_client.py    cliente multimodal, modelos, contexto
├── engine/             22 archivos · el motor
├── automations/        el código del usuario
├── docs/               18 notas · bóveda de Obsidian
├── tests/              suite de regresión + pruebas UX y de flujos
├── tools/              smoke_ui, evaluar_prompts, plantillas
├── instalador/         INSTALL.bat / UNINSTALL.bat
├── LaAutomate.spec     PyInstaller
└── empaquetar.bat
```

---

## 15. Por dónde seguir

| Quiero… | Nota |
|---|---|
| Entenderlo en 5 minutos | [[vision-general]] |
| Escribir una automatización | [[escribir-automatizaciones]] → [[acciones]] |
| Grabar en vez de escribir | [[logica-grabadora]] |
| Que la IA lo escriba | [[asistente-ia]] |
| Entender la reparación | [[autocorreccion]] → [[prompts]] |
| Ver los errores ya aprendidos | [[PRACTICAS]] |
| Tocar el código | [[arquitectura]] → [[desarrollo]] |
| Entregar la app | [[empaquetado]] |
| El índice completo | [[README]] |
| Cambios y comprobaciones de esta revisión | [[REVISION-UX-2026-09-05]] |
