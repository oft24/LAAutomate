"""Reunir el rastro de un fallo para que el Asistente pueda corregirlo.

El Asistente ya sabe generar automatizaciones desde capturas. Lo que le
faltaba para CORREGIR era el contexto del fallo, que hoy hay que buscar a
mano en tres sitios distintos: el log de la automatización, la captura que
el runner tomó en el momento del error, y —si ni siquiera importa— la
causa que registró el descubrimiento.

Aquí se junta todo. No habla con Gemini ni con la interfaz: devuelve
texto y rutas, así que se puede probar sin red y sin ventana.
"""
from __future__ import annotations

from pathlib import Path

# Cuánto log se manda. El traceback y las últimas acciones están al FINAL
# del archivo, así que se recorta por la cola: 12k caracteres son ~3k
# tokens, suficiente para ver el fallo sin gastar la ventana de contexto
# en ejecuciones de la semana pasada.
MAX_CARACTERES_LOG = 12_000


def contexto_de_fallo(nombre: str, logs_dir: Path) -> tuple[str, Path | None]:
    """La cola del log y la captura del error de esta automatización.

    El runner guarda el traceback en `AutomationResult.data`, pero
    `core.database.guardar_ejecucion` solo persiste el mensaje -- así que
    el traceback completo únicamente sobrevive en el archivo de log, y de
    ahí lo saca esta función.
    """
    ruta_log = logs_dir / f"{nombre.replace('.', '_')}.log"
    log = ""
    if ruta_log.exists():
        try:
            log = ruta_log.read_text(encoding="utf-8", errors="ignore")[-MAX_CARACTERES_LOG:]
        except OSError:
            log = ""

    captura = logs_dir / "screenshots" / f"{nombre}_error.png"
    return log, captura if captura.exists() else None


def prompt_de_correccion(nombre: str, log: str, causa_import: str = "") -> str:
    """El mensaje que se pone en la caja de entrada del Asistente.

    Se redacta aquí y no en la vista para que el texto -- que es lo que
    determina la calidad del arreglo -- se pueda leer, revisar y probar
    sin abrir la interfaz.

    Las tres reglas del final salen de fallos reales medidos contra la
    Calculadora de Windows en español; ver docs/asistente-ia.md.
    """
    partes = [
        f"Corrige la automatización «{nombre}». Diagnostica primero la CAUSA REAL del fallo "
        "(no el síntoma) y después devuelve el archivo automation.py completo y corregido "
        "en un único bloque ```python.",
        "",
    ]

    if causa_import:
        partes += [
            "## No llega ni a importarse",
            "```",
            causa_import,
            "```",
            "",
        ]

    if log.strip():
        partes += [
            f"## Final de logs/{nombre}.log",
            "```",
            log.strip()[-MAX_CARACTERES_LOG:],
            "```",
            "",
        ]
    else:
        partes += [
            "No hay log de esta automatización todavía: dedúcelo del código y di claramente "
            "qué estás suponiendo.",
            "",
        ]

    partes += [
        "## Cosas que fallan de verdad en este proyecto",
        "- `click_por_texto` busca el nombre de ACCESIBILIDAD del control, que a menudo NO es "
        "el texto que se ve. Comprobado en la Calculadora de Windows en español: los botones "
        "`1`, `×` y `=` se llaman `Uno`, `Multiplicar por` y `Es igual a`. Si la tarea se puede "
        "hacer por teclado, `escribir(...)`/`atajo(...)` no dependen del idioma y son más robustos.",
        "- `ElementNotFoundError` sobre un campo de texto suele significar que se usó su "
        "CONTENIDO como localizador; la solución es `click_por_tipo('Edit')`.",
        "- `ElementAmbiguousError`: añade `control_type=` y, si no basta, `found_index=`.",
        "- «Llama iniciar_o_conectar() antes de interactuar con la ventana»: falta un "
        "`conectar_por_titulo`/`conectar_por_clase` antes de ese click.",
        "- `escribir(None)` NO se arregla escribiendo la contraseña en el código: significa que "
        "falta guardarla en la Bóveda de credenciales.",
        "",
        "Si con esto no puedes determinar la causa, dilo y no inventes un arreglo que solo mueva "
        "el problema de sitio.",
    ]
    return "\n".join(partes)
