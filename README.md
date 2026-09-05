# LaAutomate

LaAutomate es una aplicación de escritorio para Windows que convierte tareas
repetitivas en automatizaciones locales escritas en Python. Combina una
interfaz gráfica, una grabadora de acciones, un asistente multimodal con
Gemini y un motor de ejecución con historial, logs y autocorrección supervisada.

La aplicación está pensada para una persona que quiere automatizar su propio
equipo sin depender de una plataforma cloud ni de un diseñador visual. El
código generado siempre se puede leer, editar y revisar antes de ejecutarlo.
La ejecución, el historial y los reportes son locales; únicamente el Asistente
IA y la autocorrección envían el contenido que confirmes al API de Gemini.

> Estado actual: proyecto personal en evolución. Las funciones descritas aquí
> reflejan el código y las pruebas del repositorio; si una nota antigua difiere,
> el código y las pruebas son la fuente de verdad.

## Descargar e instalar LaAutomate en Windows

### Opción 1 — Instalador listo para usar (recomendada)

**[Descargar LaAutomate para Windows x64](https://github.com/oft24/LAAutomate/releases/latest/download/LaAutomate-Windows-x64.zip)** · [Ver versiones publicadas](https://github.com/oft24/LAAutomate/releases)

Requiere Windows 10/11 de 64 bits. No necesitas Python ni una cuenta de GitHub
para descargar el instalador. La clave de Gemini es opcional.

1. Abre la página de [Releases de LaAutomate](https://github.com/oft24/LAAutomate/releases).
2. En la versión más reciente, descarga **`LaAutomate-Windows-x64.zip`**.
3. Haz clic derecho sobre el ZIP → **Extraer todo**. Abre la carpeta `LaAutomate` resultante. No separes `LaAutomate.exe` de la carpeta `_internal`.
4. Cierra LaAutomate si estaba abierta y ejecuta **`INSTALL.bat`** desde la carpeta extraída, no desde el ZIP.
5. Abre **LaAutomate** desde el acceso directo creado en el escritorio.

Esta opción no requiere instalar Python. La aplicación se copia a
`%LOCALAPPDATA%\LaAutomate`; las actualizaciones conservan las automatizaciones,
la configuración, el historial, los logs y la carpeta `datos/`. Si Windows
SmartScreen muestra una advertencia porque el ejecutable todavía no está firmado,
revisa que el archivo proceda de este repositorio antes de elegir **Más información
→ Ejecutar de todas formas**.

> Descarga el archivo **LaAutomate-Windows-x64.zip**, no **Source code (zip)**:
> este último contiene código fuente y requiere la opción 2.
> El repositorio no contiene `dist/` ni el ejecutable; ambos se distribuyen en Releases.

### Si algo falla al instalar

- **No aparece INSTALL.bat:** comprueba que descargaste el ZIP de Windows de la Release y extraíste su carpeta completa.
- **Falta _internal o una DLL:** vuelve a extraer el paquete completo; el ejecutable no funciona separado de sus dependencias.
- **No aparece el acceso directo:** conserva el mensaje del instalador. Puedes abrir `LaAutomate.exe` en `%LOCALAPPDATA%\LaAutomate` si la copia terminó correctamente.
- **El navegador no inicia:** instala Chrome o Edge y permite conexión a internet para que Selenium obtenga su controlador en la primera ejecución.
- **Gemini no responde:** la clave y disponibilidad del proveedor solo afectan las funciones de IA. Puedes abrir y usar las automatizaciones locales sin configurar Gemini.
- **GitHub muestra una cruz roja junto al commit:** consulta el detalle en **Actions**. Indica el resultado de la construcción automática, no el estado de la descarga de una Release ya publicada. La Release v0.1.0 se construyó y publicó manualmente; su ZIP está disponible independientemente de ese trabajo.

### Opción 2 — Instalar desde el repositorio

Requiere Windows 10/11, Python 3.11 o posterior y conexión a internet durante la
primera instalación:

1. Descarga **Code → Download ZIP** o clona el repositorio.
2. Extrae el ZIP y abre la carpeta `LAAutomate`.
3. Haz doble clic en **`INSTALAR_LAAUTOMATE.bat`**.
4. Espera mientras crea un entorno privado e instala las dependencias.
5. Abre **LaAutomate** desde el acceso directo del escritorio.

El instalador desde código no modifica otra instalación de Python y no necesita
una API key para abrir la aplicación, usar automatizaciones locales o probar la
grabadora. Gemini es opcional y se configura posteriormente desde **Asistente IA
→ Configurar clave**. No muevas ni elimines la carpeta descargada después de crear
el acceso directo, porque esta modalidad ejecuta la aplicación desde ahí.

### Primera prueba segura

Al abrir la aplicación puedes revisar `comparativo_compras` en
**Automatizaciones** y seguir la [demo local](docs/DEMO-COMPARATIVO-COMPRAS.md).
La demo usa un catálogo ficticio y no necesita credenciales ni realiza compras.

## Qué resuelve

- Navegar por sitios web con Selenium y controlar aplicaciones de Windows con
  UI Automation.
- Leer y escribir Excel, procesar datos y generar reportes.
- Ejecutar flujos manualmente, por horario o cuando aparece un archivo en una
  carpeta.
- Grabar clicks y escritura para obtener un primer `automation.py`.
- Describir un flujo en el chat, adjuntar una o varias capturas (también con
  `Ctrl+V`) y recibir un borrador de código Python para revisar.
- Guardar credenciales en el Administrador de credenciales de Windows, fuera
  del código y de la base de datos.
- Registrar cada ejecución, su duración, el resultado, el traceback y una
  captura cuando ocurre un fallo.
- Solicitar una autocorrección después de un fallo. Gemini recibe el código,
  el error, la bitácora y las capturas del intento; el arreglo solo se aplica
  después de validar el contrato y vuelve a ejecutarse como máximo tres veces.

## Qué no es

- No es un servicio multiusuario ni una API pública: se ejecuta con los
  permisos de la cuenta de Windows que lo abrió.
- No es un sandbox. El código de una automatización puede usar las acciones
  inyectadas para operar el equipo; revisa siempre el código antes de guardar
  y ejecutar.
- No evade CAPTCHA, límites de frecuencia, autenticación ni condiciones de
  uso de un sitio externo. Si un sitio bloquea el flujo, la automatización debe
  detenerse y dejar evidencia en el log.
- La autocorrección no garantiza que el objetivo de negocio sea correcto: solo
  aplica cambios que pasan sus validaciones técnicas y deja la decisión final
  en la persona usuaria.

## Funcionalidades actuales

| Área | Comportamiento disponible |
|---|---|
| Automatizaciones | Una carpeta por flujo dentro de `automations/`, descubierta por `@registrar`. |
| Navegador | Chrome o Edge mediante Selenium; navegación, espera, clicks, escritura, lectura de texto, descargas y pestañas. |
| Escritorio | pywinauto/UI Automation, atajos, escritura, clicks por texto/tipo/coordenada/imagen y captura de pantalla. |
| Excel | Lectura y escritura de hojas con `pandas`/`openpyxl`, incluyendo formato del reporte comparativo. |
| HTTP | Peticiones `GET` y `POST`, con opción de cliente autenticado por token. |
| Correo | Outlook mediante COM o SMTP; lectura de Outlook por remitente cuando está disponible. |
| Copilot/Teams | Acciones específicas para abrir Copilot, copiar tablas y pegar/enviar contenido en Teams. Requiere que esas aplicaciones estén instaladas y disponibles. |
| Disparadores | `manual`, `cron:` con cron de cinco campos y `carpeta:` mediante `watchdog`. |
| Grabadora | Modo Web y Escritorio. No registra contraseñas; puede seguir pestañas web nuevas y cambiar entre ventanas si se activa el modo correspondiente. |
| Asistente IA | Gemini opcional. Admite varias capturas, copiado de mensajes, sondeo de hasta 10 modelos por capacidad y conserva el mensaje/capturas si se cancela o falla la generación. |
| Historial | SQLite local, un log por automatización y capturas de error en `logs/`. |
| Interfaz | Panel principal, Automatizaciones, Grabadora, Programador, Asistente IA, Registros, Bóveda de credenciales y Wiki, con selector persistente Español/English en la barra superior. |

## Requisitos

- Windows 10/11.
- Python 3.11 o superior para ejecutar desde el código fuente.
- Chrome o Edge para flujos web y para la grabadora Web.
- Microsoft Excel/Outlook/Teams/Copilot únicamente si una automatización los
  utiliza.
- Una API key de Gemini solo para el Asistente IA y la autocorrección. La app
  funciona sin ella para automatizaciones escritas o grabadas manualmente.

Las dependencias principales son PySide6, Selenium, APScheduler, watchdog,
pandas, openpyxl, pywinauto, pyautogui, pynput, requests, python-dotenv,
keyring, Pillow y PyInstaller. La lista exacta y sus versiones mínimas están en
[`requirements.txt`](requirements.txt).

## Inicio rápido: probar sin Gemini

La primera prueba no necesita API key, cuenta cloud ni una tienda externa. Solo
requiere Windows, Python y las dependencias del proyecto:

```powershell
git clone https://github.com/oft24/LAAutomate.git
cd LAAutomate
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
python manage.py listar
python -m app.main
```

Si `python manage.py listar` muestra `comparativo_compras`, el motor descubrió
correctamente las automatizaciones. La ventana se abre sin configurar Gemini.
Desde **Automatizaciones** puedes revisar el código de ejemplo; desde
**Grabadora** puedes crear un flujo manual; y desde **Panel principal** puedes
ver el historial local. Cierra la app con normalidad para que el programador y
los observadores se detengan correctamente.

Para ejecutar la demo dinámica también necesitas Chrome o Edge. La demo usa un
catálogo HTML local, por lo que no requiere internet ni credenciales. La
instrucción detallada está en la [guía de la demo](docs/DEMO-COMPARATIVO-COMPRAS.md).

## Instalación desde el código fuente

En PowerShell o CMD, desde la carpeta del repositorio:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

El archivo `.env` es local y no debe publicarse. Contiene configuración de la
máquina, no contraseñas. Para Gemini se admite `GEMINI_API_KEY`, aunque se
recomienda configurar la clave desde **Asistente IA → Configurar clave** para
guardarla en la Bóveda de Windows. `GEMINI_MODEL` permite fijar un modelo; si se
deja vacío se usa `gemini-3.7-flash` y la vista puede actualizar la lista real
de modelos disponibles para esa cuenta.

## Primera ejecución

```powershell
python -m app.main
```

Al iniciar, LaAutomate:

1. Descubre los módulos de `automations/` mediante el decorador `@registrar`.
2. Anota en la interfaz los módulos que no puedan importarse, sin impedir que
   la aplicación abra el resto de automatizaciones.
3. Registra los disparadores válidos en APScheduler o en el observador de
   carpetas.
4. Abre la ventana y conserva los datos de historial en la base SQLite local.

Para usar la aplicación sin abrir la interfaz:

```powershell
python manage.py listar
python manage.py nueva mi_automatizacion
python manage.py ejecutar mi_automatizacion
python manage.py historial mi_automatizacion
```

El programador solo funciona mientras la aplicación está abierta. El disparador
`manual` nunca se ejecuta por sí solo.

## Crear una automatización

La forma mínima es una carpeta con `__init__.py` y `automation.py`:

```python
from __future__ import annotations

from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar


@registrar(
    nombre="reporte_diario",
    disparador="cron:0 8 * * *",
    categoria="reportes",
)
class ReporteDiario(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        self.logger.info("Iniciando reporte")
        self.web.ir_a("https://portal.ejemplo.local/login")
        self.web.escribir("#usuario", self.credenciales.usuario or "")
        self.web.escribir("#password", self.credenciales.password or "")
        self.web.click("#entrar")

        filas = self.excel.leer("C:/reportes/ventas.xlsx")
        self.http.post("https://api.ejemplo.local/ventas", json={"filas": len(filas)})
        return AutomationResult(success=True, data={"filas": len(filas)})
```

Reglas importantes:

1. Hereda de `BaseAutomation` e implementa `ejecutar()`.
2. El `nombre` del decorador debe coincidir con la carpeta y es la identidad
   usada para logs, historial y credenciales.
3. Un error debe lanzarse como excepción. El runner captura el traceback,
   registra el fallo y guarda la evidencia; no devuelvas `success=False` como
   sustituto de una excepción.
4. Nunca escribas contraseñas, tokens ni API keys en `automation.py`.

### Disparadores

```python
@registrar(nombre="manual", disparador="manual")
@registrar(nombre="diario", disparador="cron:0 8 * * *")
@registrar(nombre="cada_15_min", disparador="cron:*/15 * * * *")
@registrar(nombre="laboral", disparador="cron:0 9 * * 1-5")
@registrar(nombre="entrada", disparador="carpeta:C:/entradas")
```

El cron usa cinco campos: minuto, hora, día del mes, mes y día de la semana.
Una carpeta debe existir al iniciar la aplicación. No se aceptan disparadores
webhook, IMAP ni otros no implementados.

### Acciones inyectadas

Cada clase recibe `self.web`, `self.escritorio`, `self.excel`, `self.http`,
`self.correo` y `self.copiloto`. La referencia completa de métodos, parámetros
y ejemplos está en [`docs/acciones.md`](docs/acciones.md).

## Grabadora

En **Grabadora** se puede elegir:

- **Web**: abre un navegador instrumentado, registra clicks y escritura como
  selectores y genera llamadas a `self.web`. Si aparece una pestaña nueva, la
  sigue y genera el cambio correspondiente.
- **Escritorio**: registra clicks y teclas de aplicaciones Windows usando UI
  Automation y genera llamadas a `self.escritorio`. El modo “cualquier ventana”
  permite saltar entre aplicaciones.

La grabadora ignora los clicks sobre la propia LaAutomate y nunca copia el texto
de un campo marcado como contraseña. El resultado es un punto de partida: los
selectores, textos visibles, coordenadas y tiempos deben revisarse porque pueden
cambiar con la versión o el idioma de la aplicación objetivo. `F5` inicia o
detiene la grabación; **Cancelar** descarta los pasos.

La secuencia de estados, el diagnóstico de escritura y sus limitaciones están
en [`docs/logica-grabadora.md`](docs/logica-grabadora.md).

## Asistente IA con Gemini

El asistente está diseñado como un flujo supervisado:

1. Describe el objetivo y las condiciones de éxito.
2. Pega una imagen con `Ctrl+V` o adjunta varias capturas PNG/JPG/WEBP.
3. La app valida que las imágenes sean legibles, que no excedan 10 archivos ni
   12 MB en total y que no superen 25 megapíxeles por imagen.
4. La app añade únicamente documentación versionada y, si se solicita, el
   código de la automatización elegida. No envía `.env`, la Bóveda ni logs por
   defecto.
5. Gemini devuelve un borrador. La persona lo revisa y confirma antes de crear
   la carpeta de automatización.

Los mensajes permiten seleccionar texto con el mouse o teclado y también
incluyen **Copiar mensaje**. El mismo botón junto al campo de escritura copia
la selección actual o el borrador completo. Cambiar **Español / English** en la
barra superior traduce navegación y controles, pero conserva literalmente el
borrador, el código, las capturas y las respuestas del chat.

La solicitud usa un timeout de red y reintentos para respuestas temporales 429,
500 y 503. **Cancelar generación** conserva el mensaje y las capturas; la
cancelación es inmediata entre reintentos y puede tardar hasta que termine la
petición HTTP que ya esté en curso.

### Autocorrección

Desde **Automatizaciones → Corregir código** se puede ejecutar el flujo fallido
con bitácora, captura y traceback. La corrección:

- comprueba disponibilidad del modelo antes de enviar el diagnóstico;
- prueba modelos de texto disponibles en orden de capacidad cuando el elegido
  está saturado;
- exige un informe JSON con diagnóstico, riesgo, evidencia, validación y código;
- rechaza arreglos inseguros, incompletos, de riesgo alto o que no conserven la
  estructura de la automatización;
- guarda cada intento en `logs/reparaciones/` y vuelve a ejecutar solo después
  de recargar el módulo;
- se detiene tras tres intentos, si el modelo repite el mismo código o si la
  persona pulsa **Cancelar**.

Un arreglo aplicado no equivale a una aprobación funcional. Revisa el diff y
prueba el flujo con datos de prueba antes de usar credenciales reales.
Consulta [`docs/autocorreccion.md`](docs/autocorreccion.md) y
[`docs/PROMPT_REPARACION.md`](docs/PROMPT_REPARACION.md) para el contrato.

## Demo dinámica: Excel → navegador → comparativo

El repositorio incluye una demo reproducible para mostrar el funcionamiento sin
depender de una tienda real:

- Automatización: [`automations/comparativo_compras/automation.py`](automations/comparativo_compras/automation.py)
- Catálogo local ficticio: [`demos/comparativo/catalogo.html`](demos/comparativo/catalogo.html)
- Plantilla de entrada: [`outputs/demo-compras/productos.xlsx`](outputs/demo-compras/productos.xlsx)
- Guía completa: [`docs/DEMO-COMPARATIVO-COMPRAS.md`](docs/DEMO-COMPARATIVO-COMPRAS.md)

La automatización relee el Excel en **cada ejecución**, consulta el catálogo
local con Selenium, filtra stock, calcula precio × cantidad + envío, marca la
opción más económica y guarda un reporte nuevo. Si agregas un producto válido
al Excel, la siguiente ejecución lo incluye sin editar Python. Los códigos que
no están en el catálogo producen “Sin resultados”.

Esta demo no consulta Google, Cyberpuerta ni una tienda externa, no compra y no
envía información. Para integrar un sitio real hay que adaptar selectores,
respetar sus términos de uso, registrar URL/fecha/precio y aceptar que puede
haber CAPTCHA, cambios de diseño o límites de frecuencia.

### Ejecutar la demo

1. Reabre LaAutomate para descubrir la automatización.
2. Abre `outputs/demo-compras/productos.xlsx`, modifica o agrega filas en la
   hoja **Productos** y guarda/cierra Excel.
3. En **Automatizaciones**, selecciona `comparativo_compras` y pulsa
   **Ejecutar**.
4. Revisa el archivo nuevo en `datos/comparativo_compras/`; la ruta también
   aparece en la salida de la aplicación.

Necesitas Chrome o Edge y un controlador compatible. El catálogo de la demo no
necesita internet.

## Seguridad, privacidad y archivos locales

La guía de seguridad completa está en [`SECURITY.md`](SECURITY.md). En resumen:

- La Bóveda usa Windows Credential Manager mediante `keyring`.
- `.env`, logs, capturas, SQLite, `datos/`, `build/` y `dist/` están excluidos
  del repositorio por `.gitignore`.
- Las respuestas del chat se muestran como texto; no cargan enlaces ni recursos
  generados por el modelo.
- El borrador IA pasa por validación AST antes de cargarse.
- La API key de Gemini viaja solo en el header de la petición HTTPS; nunca se
  registra en la URL ni en los logs.
- El equipo local y la persona que ejecuta el código son el perímetro de
  confianza. Usa cuentas y datos de prueba para validar un flujo nuevo.

Antes de publicar cambios, revisa `git status`, el diff y la lista de archivos
preparados. No publiques `.env`, tokens, contraseñas, certificados, capturas,
logs, reportes ni bases de datos locales.

## Crear un instalable y acceso directo

El script [`empaquetar.bat`](empaquetar.bat) genera `dist/LaAutomate/` con
PyInstaller, copia el README, `.env.example`, automatizaciones de ejemplo, la
demo local (HTML + plantilla Excel) y los scripts del instalador. Después
ejecuta:

```bat
dist\LaAutomate\INSTALL.bat
```

El instalador copia la aplicación a `%LOCALAPPDATA%\LaAutomate` y crea un acceso
directo en el escritorio. Conserva el `.env` y las automatizaciones existentes
al actualizar. Para quitar esa instalación usa `UNINSTALL.bat` desde la carpeta
instalada. Detalles y migraciones están en
[`docs/empaquetado.md`](docs/empaquetado.md).

Si recibes una carpeta `dist/LaAutomate` ya construida, no necesitas crear un
entorno virtual: extrae la carpeta, ejecuta su `INSTALL.bat` y abre el acceso
directo **LaAutomate** del escritorio. La carpeta instalada conserva la plantilla
en `outputs/demo-compras/productos.xlsx` y la demo en `demos/comparativo/`.

### Publicar una versión para el público

El flujo [`.github/workflows/windows-release.yml`](.github/workflows/windows-release.yml)
ejecuta las pruebas deterministas, construye el paquete en Windows y genera
`LaAutomate-Windows-x64.zip`. También puede ejecutarse manualmente desde la pestaña
**Actions** para revisar el artefacto. Para crear una Release descargable y permanente:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

Usa el número de versión que corresponda. La etiqueta activa el flujo y adjunta el
ZIP a GitHub Releases. El empaquetado copia únicamente archivos versionados de las
carpetas públicas; automatizaciones creadas localmente, reportes, logs, capturas y
datos sin versionar quedan fuera del instalador.

## Solución rápida de problemas

- **`No module named ...`**: activa `.venv` y vuelve a ejecutar
  `python -m pip install -r requirements.txt`.
- **No abre el navegador / `NoSuchDriverException`**: instala Chrome o Edge y
  permite que Selenium Manager obtenga un controlador compatible. En equipos
  sin internet, instala previamente el driver que corresponda a la versión del
  navegador y vuelve a ejecutar la prueba.
- **La demo no encuentra el Excel**: ejecuta desde la carpeta raíz del proyecto,
  confirma que exista `outputs/demo-compras/productos.xlsx` y que la hoja se
  llame `Productos`.
- **Gemini responde 429 o 503**: es un límite temporal o saturación del modelo.
  Actualiza los modelos desde el Asistente IA, elige otro modelo Flash o vuelve
  a intentarlo más tarde. No repitas una acción externa si el resultado es
  incierto.
- **La Bóveda informa un error de Windows**: inicia la app desde una sesión
  interactiva de Windows con acceso al Administrador de credenciales; la
  automatización puede seguir funcionando sin guardar credenciales nuevas.
- **El flujo falla después de un cambio en la web o escritorio**: revisa el
  log y la captura, prueba primero con datos de prueba y usa
  **Corregir código** solo después de confirmar que el diagnóstico corresponde
  al fallo.

## Validación reproducible

La siguiente validación se realizó el 5 de septiembre de 2026 sobre el estado
actual del repositorio:

- 72 pruebas deterministas de UI, controles, idioma, copiado, distribución, flujos, adjuntos,
  sondeo de modelos y regresión visual aprobadas.
- 12 casos cubiertos por la demo dinámica y el runner de Excel. En la revisión
  anterior se aprobaron los 12, incluyendo dos ejecuciones reales con
  Selenium contra el catálogo local; la repetición actual dejó 11 aprobados y
  1 bloqueado porque Chrome cerró la sesión WebDriver y no había EdgeDriver
  disponible en modo offline.
- La revisión visual sintética renderizó 18 vistas sin errores de layout.
- La suite completa terminó con 487 aprobadas y 1 omitida; también dejó 17 casos
  dependientes del entorno sin completar: Selenium Manager intentó obtener
  drivers por red y Windows Credential Manager no estaba disponible en la
  sesión de prueba.
  Esos casos requieren un navegador/driver instalado o una sesión interactiva
  de Windows y no deben interpretarse como una garantía de que cada integración
  externa funciona en cualquier equipo.

Para repetir las pruebas deterministas:

```powershell
.venv\Scripts\python.exe -m pytest -q `
  tests/test_design_components.py `
  tests/test_controles_ui.py `
  tests/test_revision_ux.py `
  tests/test_revision_flujos.py `
  tests/test_adjuntar_capturas.py `
  tests/test_idioma_copia.py `
  tests/test_disponibilidad.py

$env:LAAUTOMATE_DEMO_BROWSER = "1"
$env:SE_OFFLINE = "true"
.venv\Scripts\python.exe -m pytest -q tests/test_demo_compras.py tests/test_runner_excel.py
```

Para una auditoría más amplia consulta [`docs/desarrollo.md`](docs/desarrollo.md)
y separa las pruebas marcadas `network` o `navegador`.

## Estructura del repositorio

```text
app/          interfaz PySide6, vistas, workers y sistema de diseño
engine/       registry, runner, scheduler, triggers, acciones y grabadoras
automations/  automatizaciones editables, una carpeta por flujo
core/         configuración, logs, historial, bóveda y cliente Gemini
demos/        recursos de demostración locales
outputs/      plantillas públicas de entrada para demos
instalador/   scripts INSTALL.bat y UNINSTALL.bat
tests/        pruebas unitarias, de UI e integración controlada
docs/         guía técnica y contexto para mantener la lógica
```

## Documentación recomendada

| Necesidad | Documento |
|---|---|
| Vista completa del proyecto | [`docs/CONTEXTO-COMPLETO.md`](docs/CONTEXTO-COMPLETO.md) |
| Empezar a escribir flujos | [`docs/escribir-automatizaciones.md`](docs/escribir-automatizaciones.md) |
| Referencia de acciones | [`docs/acciones.md`](docs/acciones.md) |
| Grabadora | [`docs/logica-grabadora.md`](docs/logica-grabadora.md) |
| Asistente IA | [`docs/asistente-ia.md`](docs/asistente-ia.md) |
| Autocorrección y contrato | [`docs/autocorreccion.md`](docs/autocorreccion.md) |
| Arquitectura | [`docs/arquitectura.md`](docs/arquitectura.md) |
| Desarrollo y pruebas | [`docs/desarrollo.md`](docs/desarrollo.md) |
| Empaquetado | [`docs/empaquetado.md`](docs/empaquetado.md) |
| Demo dinámica | [`docs/DEMO-COMPARATIVO-COMPRAS.md`](docs/DEMO-COMPARATIVO-COMPRAS.md) |
| Seguridad y checklist de publicación | [`SECURITY.md`](SECURITY.md) |

La carpeta `docs/` también funciona como base para Obsidian. Sus enlaces
internos están pensados para conservar la lógica y el contexto del proyecto;
este README es la guía pública de entrada.

## Licencia

Proyecto personal sin licencia de distribución declarada. Antes de reutilizarlo
o redistribuirlo, solicita autorización al propietario del repositorio.
