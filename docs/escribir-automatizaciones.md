---
tags: [laautomate, guia, automatizaciones]
alias: ["Escribir automatizaciones", "Guia de la clase base"]
---

# Escribir automatizaciones

Una automatización es una carpeta dentro de `automations/` con dos archivos:

```
automations/mi_automatizacion/
├── __init__.py      importa la clase (lo genera manage.py)
└── automation.py    tu código
```

Créala con la plantilla en vez de a mano:

```bash
python manage.py nueva mi_automatizacion
```

## La forma mínima

```python
from __future__ import annotations

from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar


@registrar(nombre="mi_automatizacion", disparador="manual", categoria="general")
class MiAutomatizacion(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        self.logger.info("Empezando")
        ...
        return AutomationResult(success=True, data={"filas": 42})
```

Tres reglas y ya:

1. **Hereda de `BaseAutomation`** e implementa `ejecutar()`.
2. **Decórala con `@registrar`** — el `nombre` es la identidad de la automatización:
   con él se guardan sus logs, su historial y sus credenciales. Que coincida con el
   nombre de la carpeta.
3. **Fallar es lanzar una excepción.** No devuelvas `success=False` a mano por un
   error: deja que reviente. El runner atrapa, registra el traceback, guarda captura
   de pantalla y marca el fallo en el historial.

`ejecutar()` puede devolver `None`; el runner lo interpreta como éxito. El `data` que
devuelvas se guarda con la ejecución y es útil para el historial ("cuántas filas
procesó hoy").

### Hook opcional

```python
    def al_fallar(self, exc: Exception) -> None:
        """Se llama antes de la captura de pantalla, para limpiar lo tuyo."""
        self.mi_conexion.cerrar()
```

## Disparadores

Se declaran en el decorador y los traduce `engine/scheduler.py`:

```python
@registrar(nombre="x", disparador="manual")                  # solo a mano
@registrar(nombre="x", disparador="cron:0 8 * * *")          # diario 8:00 am
@registrar(nombre="x", disparador="cron:*/15 * * * *")       # cada 15 minutos
@registrar(nombre="x", disparador="cron:0 9 * * 1-5")        # 9:00 am, lunes a viernes
@registrar(nombre="x", disparador="carpeta:C:/entradas")     # al crear un archivo ahí
```

El cron es el estándar de 5 campos: `minuto hora día-del-mes mes día-de-semana`.

Esos tres son los únicos que existen. Escribir otra cosa no da error al guardar: la
automatización se registra, aparece en la lista y simplemente no se dispara nunca. El
scheduler lo anota en el log como disparador desconocido.

## Credenciales

Nunca escribas una contraseña en el código. La bóveda (`core/vault.py`) las guarda en
el Almacén de credenciales de Windows vía `keyring`, indexadas por el nombre de la
automatización, y el runner te las inyecta ya resueltas:

```python
self.credenciales.usuario    # str | None
self.credenciales.password   # str | None
self.credenciales.token      # str | None
```

Se cargan desde la vista **Bóveda de credenciales** de la app, o desde el diálogo que
aparece al terminar de grabar una automatización que escribió en un campo de
contraseña.

Detalle a tener presente: `keyring` no ofrece una API para *listar* todo lo guardado,
por eso la bóveda solo puede responder "¿hay algo guardado para este nombre?" y no
mostrar un inventario completo.

## Datos del equipo: el `.env`

Nombres de servidores, correos, rutas, URLs internas — todo lo que cambia entre
máquinas o que no quieres publicar — va al `.env`, no al código:

```python
from core.config import var

SERVIDOR = var("VNC_SERVIDOR", "servidor.demo")
```

`var()` lee del `.env` (ya cargado) con un valor por defecto de ejemplo. Registra la
variable nueva en `.env.example` para que quien clone el repo sepa que existe.

## La grabadora

La vista **Grabadora** graba lo que haces y genera el `automation.py` correspondiente.
Dos modos:

**Web** — abre un Chrome instrumentado, graba tus clicks y escrituras como selectores
CSS, y genera llamadas a `self.web`. Si un click abre una **pestaña nueva**, la
grabadora te sigue a ella y agrega el `cambiar_a_pestana_nueva()` correspondiente.

**Escritorio** — graba clicks y teclas sobre cualquier app de Windows usando UI
Automation, y genera llamadas a `self.escritorio`. Identifica los controles por su
texto visible cuando lo tienen, y cae a coordenadas cuando no. Como casi siempre estás
grabando *otra* aplicación, **F5 inicia y detiene la grabación desde cualquier
ventana**.

### Grabar un proceso que toca varias aplicaciones

Por defecto la grabadora se queda con **una sola ventana**: la del primer click.
Todo lo que hagas en otra se ignora. Es a propósito — evita que un click mal
calculado capture contenido de una aplicación que no tiene nada que ver.

Para grabar un flujo que salta entre apps, marca **"Cualquier ventana (sin
candado)"** antes de iniciar. Entonces cada cambio de ventana genera una conexión
nueva en el código. Dos cosas que conviene saber:

- **Haz un click dentro de cada ventana nueva antes de teclear.** La ventana
  objetivo se mueve con los clicks; cambiar de app con Alt+Tab y ponerte a
  escribir deja ese texto fuera de la grabación. La vista te avisa en vivo si
  está descartando teclas por esto.
- Los diálogos de la propia app ("Guardar como", "Buscar") **sí** cuentan como la
  misma ventana: no necesitas el modo sin candado para ellos.

Dos cosas que la grabadora hace a propósito:

- **Nunca graba contraseñas.** Si detecta que el control es un campo de contraseña
  (propiedad `IsPassword` de UI Automation), guarda el tipo de control y las
  coordenadas, pero jamás el texto: el código generado escribe
  `self.credenciales.password` y te ofrece guardar esa contraseña en la bóveda.
- **Ignora los clicks sobre la propia app.** Compara por PID, no por título, para que
  el click en "Detener" no termine grabado como un paso de tu automatización.

Mientras grabas, la vista muestra la ventana o URL que está capturando, los pasos
que lleva y tres contadores: clicks ignorados, teclas ignoradas y veces que la
ventana objetivo cambió. Si alguno sube cuando no lo esperabas, **Cancelar**
aborta y descarta todo sin crear la automatización, y **Ver registro** abre el
log de la grabadora sin salir de la vista.

El código generado es un punto de partida, no un producto terminado: los controles se
identifican por texto visible, así que un cambio de versión o de idioma de la app
objetivo puede romperlo. Revísalo siempre.

La secuencia completa de eventos, los estados de la UI y las limitaciones conocidas
están documentados en [Lógica de la Grabadora](logica-grabadora.md).

## Probar

```bash
python manage.py ejecutar mi_automatizacion     # sin abrir la app
python manage.py historial mi_automatizacion    # últimas corridas
```

Desde la app, la pestaña **Automatizaciones** permite editar el código y "Guardar y
ejecutar", que recarga el módulo en caliente — sin reiniciar.

Los logs quedan en `logs/mi_automatizacion.log`, y las capturas de los fallos en
`logs/screenshots/`.

---

## Notas relacionadas

- [[acciones]] - todo lo que puedes llamar desde `ejecutar()`
- [[logica-grabadora]] - grabar en vez de escribir
- [[asistente-ia]] - que lo escriba la IA
- [[PRACTICAS]] - errores reales que conviene no repetir
