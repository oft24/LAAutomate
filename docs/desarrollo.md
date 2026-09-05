---
tags: [laautomate, desarrollo, interno]
alias: ["Desarrollo", "Contribuir"]
---

# Desarrollo

## Entorno

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Windows y Python 3.11 o superior. Varias dependencias son específicas de Windows
(`pywin32`, `pywinauto`) y están marcadas así en `requirements.txt`; el resto del
proyecto asume Windows de todas formas: COM para Outlook y Excel, UI Automation para
la grabadora de escritorio, `keyring` sobre el Almacén de credenciales de Windows.

> El `.venv` no se versiona. Si clonas el repo en otra máquina, créalo de nuevo: un
> `.venv` copiado apunta al Python de la máquina original y no arranca.

## Correr

```bash
python -m app.main                              # la app
python manage.py listar                         # sin interfaz
python manage.py ejecutar mi_automatizacion
```

## Pruebas

```bash
pytest -q                            # todo
pytest -m "not network"              # sin las que navegan a un sitio real
pytest -m "not network and not navegador"   # sin navegador de ningún tipo
pytest tests/test_runner_failure.py -v
```

La suite actual reúne 494 pruebas recopiladas. Casi todas corren con el escritorio y el navegador **mockeados**: no
abren ventanas, no mueven el mouse y no tocan Outlook. Dos marcadores acotan las
que sí necesitan algo del entorno (ambos declarados en `pytest.ini`):

| Marcador | Necesita | Por qué no se puede mockear |
|---|---|---|
| `network` | Internet y un navegador | Valida el pipeline completo contra un sitio real. |
| `navegador` | Un navegador, **no** internet | Valida el JavaScript de la Grabadora web: qué evento emite el navegador y cuándo. Sirve su propia página desde `localhost`. Un doble solo confirmaría lo que el doble finge. |

> **Si `tmp_path` falla con `PermissionError`** sobre
> `%LOCALAPPDATA%\Temp\pytest-of-<usuario>`: es una carpeta que quedó de una
> corrida anterior con permisos rotos, no un fallo del proyecto. Bórrala, o corre
> con `pytest --basetemp=<carpeta vacía>`.

Dónde está cubierto qué:

| Archivo | Cubre |
|---|---|
| `test_registry.py` | Descubrimiento y decorador `@registrar`. |
| `test_runner_*.py` | Ejecución, manejo de fallos, captura de error, integración con Excel y web. |
| `test_scheduler.py` | Traducción de disparadores a jobs de APScheduler. |
| `test_desktop_actions.py` | Clicks por texto, por coordenada y por imagen. |
| `test_desktop_recorder.py` | La grabadora de escritorio — el módulo con más casos borde. |
| `test_recorder.py` | La grabadora web (lógica pura, sin navegador). |
| `test_grabadora_web_navegador.py` | La captura de texto de la grabadora web contra un navegador real. Marcado `navegador`. |
| `test_pestanas.py` | Control de pestañas del navegador y que la grabadora siga las que se abren. |
| `test_pestanas_navegador.py` | El mismo flujo de pestañas contra un navegador real. Marcado `navegador`. |
| `test_grabadora_validacion.py` | El camino entero de la grabadora de escritorio contra un escritorio falso: `_al_click`/`_al_tecla` -> `_depurar_pasos` -> código generado. |
| `test_vista_grabadora.py` | La descripción de pasos en vivo y el selector de logs. |
| `test_copilot_teams.py` | Lectura y copiado de tablas de Copilot, envío en Teams. |
| `test_vault.py` | Bóveda de credenciales sobre `keyring`. |
| `test_workers.py` | El hilo Qt y la cancelación. |
| `test_gemini_client.py` | Payload multimodal, clave fuera de la URL y validación del código sugerido. |

Cuando arregles un caso borde de la grabadora, la prueba correspondiente documenta
*por qué* está ese código: casi todas nombran el comportamiento roto que las originó.

## Estructura

```
app/
├── main.py             arranca registry + scheduler y abre la ventana
├── workers.py          QThread que corre una automatización y transmite su log
├── resources/tokens.py sistema de diseño (colores, espaciados, tipografía, QSS)
├── widgets/            KPI, tabla, badge, toast, encabezado, sidebar, pista de pasos
└── windows/            una vista por pestaña
engine/
├── registry.py         @registrar + descubrimiento
├── runner.py           ejecuta, captura errores, guarda historial
├── scheduler.py        APScheduler: cron y carpeta vigilada
├── automation_base.py  BaseAutomation y AutomationResult
├── almacen.py          escribir una automatizacion en disco y registrarla
├── bitacora.py         anota cada accion, para saber que pasaba al fallar
├── diagnostico.py      reune log + captura + causa de un fallo
├── autocorreccion.py   el ciclo de reparacion (hasta 3 intentos)
├── practicas.py        lee y amplia docs/PRACTICAS.md
├── optimizador_prompt.py  versiona docs/PROMPT_REPARACION.md
├── actions/            web, excel, http, correo, escritorio, copilot, grabadoras
└── triggers/           file_watcher.py: dispara al crear un archivo (watchdog)
core/
├── config.py           rutas base, .env, nombre de la app
├── logger.py           un archivo de log por automatización
├── database.py         historial en SQLite
├── vault.py            credenciales vía keyring
└── gemini_client.py    chat multimodal; contexto y capturas sin depender de la UI
automations/            código del usuario
instalador/             INSTALL.bat / UNINSTALL.bat
docs/                   esta documentación
```

## Convenciones

- **Español en el código.** Nombres de métodos, variables y mensajes de log en
  español; el inglés queda para lo que viene de las librerías.
- **Comentarios que explican el porqué, no el qué.** Los comentarios largos del
  repositorio existen donde una decisión no es obvia (por qué el escritorio se lee del
  registro, por qué la cancelación es mejor esfuerzo, por qué se compara por PID y no
  por título). Si escribes uno nuevo, que responda una pregunta que el código no
  responde solo.
- **Nada de valores mágicos en la interfaz.** Colores, tamaños y espacios salen de
  `app/resources/tokens.py`.
- **Nada de secretos en el código.** Contraseñas -> bóveda. Datos del equipo -> `.env`,
  leídos con `core.config.var()` y declarados en `.env.example`.
- **Una automatización que falla lanza una excepción.** No se devuelve `success=False`
  a mano por un error.

## Deuda conocida

- Los únicos disparadores que existen son `manual`, `cron:` y `carpeta:`. Cualquier
  otro se anota en el log y la automatización no se dispara nunca.
- `_control_en()` de la grabadora de escritorio corre dentro del hook de bajo nivel
  de pynput y puede superar el `LowLevelHooksTimeout` (300 ms), lo que retira el
  hook y mata la grabación en silencio.
- La grabadora web sigue las pestañas **nuevas**, pero no detecta que el usuario
  vuelva a una que ya estaba abierta. Ver
  [Lógica de la Grabadora § Limitaciones conocidas](logica-grabadora.md#limitaciones-conocidas).

---

## Notas relacionadas

- [[arquitectura]] - como encajan las piezas
- [[empaquetado]] - generar el ejecutable
- [[escribir-automatizaciones]] - el codigo que escribe quien usa la app
