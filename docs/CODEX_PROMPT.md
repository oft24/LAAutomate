# Prompt para Codex

> **Documento histórico.** Es el prompt con el que se especificó el proyecto y
> guio su construcción. Se conserva como registro de las decisiones de diseño
> originales: partes ya no reflejan el estado actual (hoy la app tiene 8 vistas,
> grabadora de escritorio y wiki). Para el estado real, ver el resto de `docs/`.

Estás trabajando en `rpa-code-platform/`, una plataforma de escritorio en Python para
crear y operar automatizaciones (RPA) **100% en código**, sin diseñador visual — el
equivalente de Power Automate pero para gente que prefiere escribir Python en vez de
arrastrar cajas, y sin el límite de conectores fijos.

## Ya existe (no lo regeneres, extiéndelo)

- `engine/automation_base.py` — clase `BaseAutomation` que toda automatización hereda.
- `engine/registry.py` — decorador `@registrar(nombre, disparador, categoria)` +
  descubrimiento automático de módulos bajo `automations/`.
- `engine/runner.py` — ejecuta una automatización, captura excepciones, guarda
  screenshot de error y persiste el resultado en SQLite.
- `engine/scheduler.py` — envuelve APScheduler para disparadores `cron:` y `carpeta:`.
- `engine/actions/` — librería de acciones reutilizables inyectadas en cada
  automatización (`self.web`, `self.excel`, `self.http`, `self.correo`, `self.escritorio`):
  - `web.py` (Selenium: esperas explícitas, click, escribir, leer texto, screenshot).
  - `excel.py` (pandas + acceso COM opcional a Excel).
  - `http_client.py` (requests con sesión y soporte de bearer token).
  - `email_actions.py` (Outlook COM o SMTP).
  - `desktop.py` (pywinauto para apps de escritorio no-web, con respaldo por imagen
    vía pyautogui para apps sin árbol de accesibilidad usable).
- `engine/triggers/` — disparadores: `file_watcher.py` (watchdog), `email_watcher.py`
  (polling IMAP), `webhook_listener.py` (FastAPI local, equivalente al trigger de
  "HTTP request" de Power Automate).
- `core/` — `config.py`, `logger.py` (logging a archivo por automatización),
  `database.py` (historial de ejecuciones en SQLite), `vault.py` (credenciales
  cifradas en el almacén de Windows vía `keyring`, nunca en texto plano),
  `notifier.py` (alerta a Teams por webhook cuando algo falla).
- `app/` — shell de escritorio en **PySide6**: `main.py` arranca el registry y el
  scheduler y abre `MainWindow`; `windows/` tiene un sidebar de navegación con 5
  vistas: Panel principal, Automatizaciones, Programador, Registros, Bóveda de
  credenciales. Las vistas actuales son funcionales pero mínimas (tablas/listas
  simples, sin estilos).
- `automations/ejemplo_login/` — automatización de ejemplo que sirve de plantilla.
- Mockup de diseño de referencia para el look & feel deseado: panel oscuro tipo IDE,
  sidebar con iconos, tarjetas de estadísticas, tabla de automatizaciones con pills
  de estado (éxito/reintentando/error/en espera), feed de actividad, vista de
  programador con línea de tiempo de próximas ejecuciones, vista de bóveda con
  secretos enmascarados.

## Lo que necesito que hagas

1. **Aplicar el diseño visual a la app PySide6.** Traduce el mockup (paleta,
   tipografía del sistema, pills de estado con color semántico, tarjetas con sombra
   sutil, layout de sidebar + topbar + contenido) a QSS + widgets reales. Soporta
   tema claro/oscuro. No hace falta que sea pixel-perfect, pero debe sentirse como
   una herramienta de desarrollador seria, no un formulario genérico de Qt.

2. **Completar las vistas** con lo que falta del mockup:
   - Panel principal: tarjetas de estadísticas (activas, ejecuciones hoy, tasa de
     éxito, próxima ejecución) calculadas desde `core/database.py`, tabla de
     automatizaciones con pill de estado, panel de actividad reciente.
   - Automatizaciones: acciones de "ejecutar ahora", "ver código fuente" (abrir el
     archivo `automation.py` en el editor del sistema), "ver últimas corridas".
   - Programador: línea de tiempo de próximas ejecuciones (usa
     `scheduler._sched.get_jobs()` de APScheduler para las próximas fechas reales).
   - Registros: filtro por automatización y por nivel (INFO/WARN/ERROR), botón para
     abrir el screenshot de error asociado si existe.
   - Bóveda: listar los nombres de credenciales guardadas (sin exponer el valor),
     eliminar, rotar.

3. **Reforzar el motor** para que cubra lo que hace Power Automate y más:
   - Reintentos configurables por automatización (decorador o parámetro en
     `@registrar`, ej. `reintentos=3, backoff_seg=10`) implementados en `runner.py`.
   - Variables/inputs por ejecución (para poder parametrizar una corrida manual
     desde la UI, como los "inputs" de un flujo de Power Automate).
   - Notificación automática (Teams/correo) cuando una automatización falla,
     conectando `core/notifier.py` al `runner.py`.
   - Registro de trigger tipo webhook y correo desde `app/main.py` (ya existen los
     módulos en `engine/triggers/`, falta conectarlos al arranque de la app).
   - Empaquetado final con PyInstaller a un `.exe` de Windows (spec file +
     instrucciones en el README).

4. **Mantener las convenciones existentes**: nombres de variables y docstrings en
   español (así está el resto del proyecto), type hints, sin abstracciones que no
   se usen todavía, sin agregar dependencias nuevas salvo que sean claramente
   necesarias (si agregas una, súmala a `requirements.txt`).

5. **No toques** `flask_app/` en la carpeta padre — es un proyecto distinto
   (catálogo web de automatizaciones) que no forma parte de esta app de escritorio.

## Criterio de aceptación

- `python -m app.main` abre la ventana, muestra el registry con `ejemplo_login`, y
  puedo ejecutarla manualmente desde la UI y ver el resultado en Panel principal y
  en Registros.
- Crear una automatización nueva sigue siendo: copiar una carpeta en `automations/`,
  cambiar el decorador `@registrar`, escribir `ejecutar()`. Cero configuración
  visual, cero XML/JSON de flujo — solo código Python.
- Un fallo real (excepción en `ejecutar()`) queda registrado con traceback, genera
  un screenshot si había un `self.web` activo, y aparece como pill roja en la UI.
