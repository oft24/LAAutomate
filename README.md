# LaAutomate

Plataforma de escritorio para escribir automatizaciones (RPA) **100 % en código** y
operarlas como si fueran Power Automate: programador, disparadores, historial de
ejecuciones, logs por automatización, captura de pantalla cuando algo falla y bóveda
de credenciales — sin diseñador visual y sin límite de conectores.

Python + PySide6 + Selenium + pywinauto. Windows.

```
┌─────────────┐   @registrar    ┌──────────┐   dispara   ┌───────────┐
│ automations/│ ──────────────► │ registry │ ──────────► │ scheduler │
│  tu código  │                 └──────────┘             └─────┬─────┘
└─────────────┘                                                │
                                                               ▼
┌──────────────────────────────┐   inyecta acciones      ┌──────────┐
│ self.web .excel .http        │ ◄────────────────────── │  runner  │
│ .correo .escritorio .copiloto│                         └─────┬────┘
└──────────────────────────────┘                               │
                                                    logs + screenshot + SQLite
```

## Qué trae

| | |
|---|---|
| **Automatizaciones en Python** | Una carpeta por automatización, una clase que hereda `BaseAutomation` e implementa `ejecutar()`. |
| **Acciones listas** | Navegador (Selenium, con control de pestañas), Excel (pandas + COM), HTTP, correo (Outlook COM o SMTP), escritorio (pywinauto), Microsoft 365 Copilot + Teams. |
| **Varias pestañas y varias apps** | Una automatización puede saltar entre pestañas del navegador y entre ventanas de aplicaciones distintas dentro del mismo proceso. |
| **Disparadores** | Manual, cron, carpeta vigilada, webhook HTTP local, buzón IMAP. |
| **Grabadora** | Graba clicks y teclas —en el navegador o en apps de escritorio— y genera el código Python de la automatización. Sigue las pestañas que se abren y, si se le pide, varias ventanas. Nunca graba contraseñas. |
| **Historial** | Cada corrida queda en SQLite: éxito/fallo, mensaje, duración. Visible en el panel principal. |
| **Bóveda de credenciales** | Usuarios y contraseñas en el Almacén de credenciales de Windows vía `keyring`, nunca en el código ni en la base de datos. |
| **Asistente IA** | Chat multimodal con Gemini: combina instrucciones, capturas y la documentación real para proponer `automation.py`; la persona revisa y confirma antes de guardar. |
| **App de escritorio** | PySide6, 8 vistas: Panel principal, Automatizaciones, Grabadora, Programador, Asistente IA, Registros, Bóveda y Wiki. |

## Instalar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

El `.env` guarda datos del equipo (correos, nombres de servidores, webhook de Teams),
**nunca contraseñas**: esas van a la Bóveda. Ver [`.env.example`](.env.example).

## Usar

```bash
python -m app.main
```

O desde la línea de comandos, sin abrir la app:

```bash
python manage.py listar
python manage.py nueva mi_automatizacion
python manage.py ejecutar mi_automatizacion
python manage.py historial mi_automatizacion
```

## Una automatización en 20 líneas

```python
from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar


@registrar(nombre="reporte_diario", disparador="cron:0 8 * * *", categoria="reportes")
class ReporteDiario(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        self.web.ir_a("https://portal.interno/login")
        self.web.escribir("#usuario", self.credenciales.usuario)
        self.web.escribir("#password", self.credenciales.password)
        self.web.click("#entrar")

        filas = self.excel.leer("C:/reportes/ventas.xlsx")
        self.http.post("https://api.interno/ventas", json={"filas": len(filas)})

        return AutomationResult(success=True, data={"filas": len(filas)})
```

El registry la descubre sola al reiniciar la app. Si falla, el runner guarda el
traceback en `logs/reporte_diario.log`, deja una captura en `logs/screenshots/` y
registra el fallo en el historial.

## Documentación

Empieza por el **[índice de `docs/`](docs/README.md)**, que dice qué leer según lo
que quieras hacer. Los documentos, uno por uno:

| Documento | Para qué |
|---|---|
| [Arquitectura](docs/arquitectura.md) | Cómo encajan registry, runner, scheduler, acciones y core. Dónde vive cada dato. |
| [Lógica de la Grabadora](docs/logica-grabadora.md) | Flujo Web/Escritorio, estados, diagnóstico de escritura y criterios de corrección. |
| [Asistente IA](docs/asistente-ia.md) | Gemini, capturas, contexto, almacenamiento seguro de la clave y creación supervisada de código. |
| [Escribir automatizaciones](docs/escribir-automatizaciones.md) | La clase base, los disparadores, credenciales, la grabadora, errores comunes. |
| [Referencia de acciones](docs/acciones.md) | Todos los métodos de `self.web`, `.excel`, `.http`, `.correo`, `.escritorio`, `.copiloto`. |
| [Empaquetado e instalación](docs/empaquetado.md) | Generar el `.exe`, el instalador y cómo cambian las rutas al empaquetar. |
| [Desarrollo](docs/desarrollo.md) | Estructura del repo, pruebas, convenciones. |
| [Prompt original](docs/CODEX_PROMPT.md) | Histórico: la especificación con la que nació el proyecto. |

## Estructura

```
app/          interfaz de escritorio (PySide6): ventanas, widgets, tokens de diseño
engine/       motor: registry, runner, scheduler, triggers, actions, grabadoras
automations/  tus automatizaciones — una carpeta por cada una
core/         config, logging, historial (SQLite), bóveda de credenciales, alertas
instalador/   INSTALL.bat / UNINSTALL.bat que se copian al paquete distribuible
tests/        pruebas con pytest (sin tocar el escritorio real: todo mockeado)
docs/         esta documentación (empieza por docs/README.md)
```

## Licencia

Proyecto personal, sin licencia declarada.
