# Arquitectura

LaAutomate tiene tres capas que casi no se conocen entre sí:

- **`engine/`** — el motor. No sabe que existe una interfaz gráfica.
- **`core/`** — servicios transversales: configuración, logs, historial, credenciales.
- **`app/`** — la app de escritorio en PySide6. Solo presenta lo que el motor expone.

Las automatizaciones (`automations/`) son código del usuario que el motor descubre y
ejecuta. Nada en `engine/` conoce automatizaciones concretas.

## El recorrido de una ejecución

```
   registry.descubrir()        scheduler.iniciar()
importa automations/*    ──►  registra un job por        ──►  runner.ejecutar(spec)
y llena _REGISTRY             disparador cron/carpeta          │
                                                               ├─ Vault.credenciales_para(nombre)
                                                               ├─ ActionBundle.crear(logger)
                                                               ├─ instancia.ejecutar()
                                                               │    éxito → AutomationResult
                                                               │    excepción → screenshot + traceback
                                                               └─ guardar_ejecucion() → SQLite
```

### 1. Descubrimiento — `engine/registry.py`

`descubrir()` importa recursivamente todo lo que cuelgue de `automations/`. El único
efecto que importa de esos imports es que se ejecute el decorador:

```python
@registrar(nombre="conciliacion", disparador="cron:0 8 * * *", categoria="finanzas")
```

El decorador guarda un `AutomationSpec` (nombre, disparador, categoría, clase) en un
diccionario en memoria. No hay archivo de configuración ni registro en base de datos:
la fuente de verdad de "qué automatizaciones existen" es el propio código.

Esto es lo que permite que la vista **Automatizaciones** guarde un archivo y lo
recargue en caliente sin reiniciar la app.

### 2. Programación — `engine/scheduler.py`

Envuelve APScheduler. Al iniciar recorre el registry y traduce cada disparador:

| Disparador | Qué hace |
|---|---|
| `manual` | Nada: solo se ejecuta desde la UI o `manage.py ejecutar`. |
| `cron:M H D M DS` | `CronTrigger.from_crontab()` — cron estándar de 5 campos. |
| `carpeta:C:/ruta` | `engine/triggers/file_watcher.py` (watchdog), dispara al crear un archivo. |
| `webhook` | Se registra aparte en `engine/triggers/webhook_listener.py` (FastAPI local). |
| `correo` | Se registra aparte en `engine/triggers/email_watcher.py` (polling IMAP). |

`proximas_ejecuciones()` es lo que alimenta la vista **Programador** y el KPI de
"Próxima ejecución" del panel principal.

### 3. Ejecución — `engine/runner.py`

El runner es el único lugar donde una automatización se instancia, y hace siempre lo
mismo:

1. Crea un logger con el nombre de la automatización → `logs/<nombre>.log`.
2. Arma el `ActionBundle` (web, excel, http, correo, escritorio, copiloto).
3. Pide las credenciales de esa automatización a la bóveda.
4. Llama `ejecutar()`.
5. Pase lo que pase, cierra el navegador y guarda el resultado en SQLite.

**Una excepción es un fallo, y un fallo no tumba la app.** El runner la atrapa, guarda
el traceback, intenta dos capturas de pantalla (navegador y escritorio), llama al hook
`al_fallar(exc)` y devuelve un `AutomationResult(success=False)`. Por eso una
automatización mal escrita nunca deja la interfaz colgada.

`ejecutar_async()` lo corre en un hilo daemon: es lo que usa el botón "Ejecutar ahora"
y lo que dispara el scheduler.

### 4. Acciones — `engine/actions/`

`ActionBundle` es un dataclass que se inyecta en el constructor de `BaseAutomation`, y
la clase base lo reparte en atributos:

```python
self.web        WebActions          Selenium (Chrome, con reserva a Edge)
self.excel      ExcelActions        pandas + Excel.Application por COM
self.http       HttpActions         requests con sesión compartida
self.correo     EmailActions        Outlook por COM, o SMTP
self.escritorio DesktopActions      pywinauto + pyautogui como respaldo
self.copiloto   CopilotTeamsActions Microsoft 365 Copilot y Teams por UI Automation
```

Todas reciben el logger de la ejecución, así que lo que registran queda en el archivo
de esa automatización. Ver la [referencia de acciones](acciones.md).

## Dónde vive cada dato

| Dato | Dónde | Se versiona |
|---|---|---|
| Automatizaciones | `automations/<nombre>/automation.py` | Sí |
| Historial de ejecuciones | `core/rpa.db` (SQLite, tabla `ejecuciones`) | No |
| Logs | `logs/<nombre>.log`, uno por automatización | No |
| Capturas de error | `logs/screenshots/<nombre>_error.png` | No |
| Contraseñas y tokens | Almacén de credenciales de Windows, vía `keyring` | Nunca |
| Datos del equipo (correos, servidores, webhook) | `.env` | No (sí `.env.example`) |
| Nombre de la app, rutas base | `core/config.py` | Sí |

`core/config.py` es también quien resuelve `BASE_DIR`, y tiene un detalle importante:
cuando la app corre empaquetada con PyInstaller, `BASE_DIR` es **la carpeta del `.exe`**
y no la carpeta temporal de extracción. Así `automations/`, `logs/` y la base de datos
quedan junto al ejecutable instalado, donde el usuario puede verlos y editarlos. Ver
[empaquetado](empaquetado.md).

## La interfaz — `app/`

```
app/main.py              arranca registry + scheduler y abre la ventana
app/windows/             una vista por pestaña de la sidebar
app/widgets/             piezas reutilizables (KPI, tabla, badge, toast, header…)
app/resources/tokens.py  sistema de diseño: colores, espaciados, tipografía y el QSS
```

`tokens.py` es la fuente única de verdad visual: ningún componente inventa colores ni
tamaños, y `construir_qss()` genera la hoja de estilos completa a partir de esos
mismos tokens. Cambiar la paleta es cambiar un dataclass.

El nombre de la app también sale de un solo lugar — `NOMBRE_APP` en `core/config.py` —
del que dependen el título de la ventana y la marca de la barra lateral.

## Qué NO hace

- No aísla por proceso: cada automatización corre en un hilo del mismo proceso
  (`QThread` desde la interfaz — ver `app/workers.py` —, hilo daemon desde el
  programador). Por eso el botón "Cancelar" es mejor esfuerzo: inyecta una excepción
  en el hilo, que solo surte efecto en el siguiente bytecode que ese hilo ejecute.
- No hay reintentos automáticos ni colas: un fallo se registra, no se reintenta.
- No hay multiusuario ni servidor central: todo es local a la máquina.
