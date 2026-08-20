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
pytest -q                     # todo
pytest -m "not network"       # sin las que navegan a un sitio real
pytest tests/test_runner_failure.py -v
```

~100 pruebas, todas con el escritorio y el navegador **mockeados**: la suite no abre
ventanas, no mueve el mouse y no toca Outlook. Las que necesitan internet están
marcadas con `@pytest.mark.network` (declarado en `pytest.ini`).

Dónde está cubierto qué:

| Archivo | Cubre |
|---|---|
| `test_registry.py` | Descubrimiento y decorador `@registrar`. |
| `test_runner_*.py` | Ejecución, manejo de fallos, captura de error, integración con Excel y web. |
| `test_scheduler.py` | Traducción de disparadores a jobs de APScheduler. |
| `test_desktop_actions.py` | Clicks por texto, por coordenada y por imagen. |
| `test_desktop_recorder.py` | La grabadora de escritorio — el módulo con más casos borde. |
| `test_recorder.py` | La grabadora web. |
| `test_copilot_teams.py` | Lectura y copiado de tablas de Copilot, envío en Teams. |
| `test_vault.py` | Bóveda de credenciales sobre `keyring`. |
| `test_workers.py` | El hilo Qt y la cancelación. |

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
├── scheduler.py        APScheduler + disparadores
├── automation_base.py  BaseAutomation y AutomationResult
├── actions/            web, excel, http, correo, escritorio, copilot, grabadoras
└── triggers/           carpeta (watchdog), correo (IMAP), webhook (FastAPI)
core/
├── config.py           rutas base, .env, nombre de la app
├── logger.py           un archivo de log por automatización
├── database.py         historial en SQLite
├── vault.py            credenciales vía keyring
└── notifier.py         alerta a Teams/Slack por webhook cuando algo falla
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
- **Nada de secretos en el código.** Contraseñas → bóveda. Datos del equipo → `.env`,
  leídos con `core.config.var()` y declarados en `.env.example`.
- **Una automatización que falla lanza una excepción.** No se devuelve `success=False`
  a mano por un error.

## Deuda conocida

- `automations/ingresointento5`, `intento10` e `ingresovnc2` son grabaciones de prueba
  contra UltraVNC; sirven de ejemplo del código que genera la grabadora, no son
  automatizaciones de producción.
- Los disparadores `webhook` y `correo` se declaran en el decorador pero hay que
  conectarlos a mano en `engine/triggers/`.
- No hay reintentos automáticos: un fallo se registra y ahí queda.
