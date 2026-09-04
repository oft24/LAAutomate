"""Versiona el prompt de reparación y lo mejora tras un éxito validado.

El agente de reparación usa `docs/PROMPT_REPARACION.md`. Cuando una
corrección se valida objetivamente, este módulo le pide al optimizador que
extraiga la lección **generalizable** y produzca una versión nueva del
prompt, con changelog.

Tres barandillas, porque un sistema que reescribe sus propias
instrucciones puede degradarse sin que nadie lo note:

1. **Solo se aprende de éxitos validados.** Un `update_prompt: false` es
   una respuesta perfectamente válida y la más común.
2. **Nunca se sobrescribe una versión.** Cada una se guarda aparte en
   `docs/prompts/repair_prompt_vN.md` y el archivo activo es una copia.
   Volver atrás es copiar un archivo.
3. **El prompt del optimizador no se toca a sí mismo.** Un sistema que
   reescribe las reglas con las que se juzga no tiene punto de apoyo.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.config import BASE_DIR
from core.logger import get_logger

logger = get_logger(__name__)

CARPETA_VERSIONES = BASE_DIR / "docs" / "prompts"
CHANGELOG = BASE_DIR / "docs" / "PROMPT_CHANGELOG.md"

# Un prompt que crece sin freno acaba diluyendo sus propias reglas. Si el
# optimizador devuelve algo mucho mayor que el original, es que se puso a
# narrar en vez de a generalizar.
MAX_CRECIMIENTO = 1.6
MIN_LARGO_PROMPT = 2_000

_PATRON_VERSION = re.compile(r"repair_prompt_v(\d+)")


@dataclass
class ResultadoOptimizacion:
    actualizado: bool
    motivo: str = ""
    version_anterior: str = ""
    version_nueva: str = ""
    regla: str = ""
    changelog: str = ""
    riesgo_regresion: str = ""


def _ruta_recurso(relativa: str) -> Path:
    """Localiza el archivo en desarrollo y dentro del .exe empaquetado."""
    directa = BASE_DIR / relativa
    if directa.exists():
        return directa
    return Path(getattr(sys, "_MEIPASS", BASE_DIR)) / relativa


def ruta_prompt_reparacion() -> Path:
    return _ruta_recurso("docs/PROMPT_REPARACION.md")


def leer_prompt_reparacion() -> str:
    ruta = ruta_prompt_reparacion()
    try:
        return ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    except OSError:
        return ""


def version_actual(texto: str | None = None) -> str:
    """La versión declarada en la primera línea del prompt."""
    contenido = texto if texto is not None else leer_prompt_reparacion()
    encontrado = _PATRON_VERSION.search(contenido or "")
    return f"repair_prompt_v{encontrado.group(1)}" if encontrado else "repair_prompt_v1"


def _siguiente_version(actual: str) -> str:
    encontrado = _PATRON_VERSION.search(actual)
    numero = int(encontrado.group(1)) + 1 if encontrado else 2
    return f"repair_prompt_v{numero}"


def _extraer_json(texto: str) -> dict:
    """Lee el JSON de la respuesta, aunque venga con cerca de markdown."""
    limpio = (texto or "").strip()
    if limpio.startswith("```"):
        limpio = limpio.split("\n", 1)[-1].removesuffix("```").strip()
        if limpio.startswith("json"):
            limpio = limpio[4:].strip()
    try:
        datos = json.loads(limpio)
    except json.JSONDecodeError:
        inicio, fin = limpio.find("{"), limpio.rfind("}")
        if inicio == -1 or fin <= inicio:
            raise ValueError("la respuesta del optimizador no es JSON") from None
        datos = json.loads(limpio[inicio : fin + 1])
    if not isinstance(datos, dict):
        raise ValueError("el optimizador devolvió JSON, pero no un objeto")
    return datos


def _es_aceptable(nuevo: str, anterior: str) -> tuple[bool, str]:
    """Filtros que el prompt nuevo debe pasar antes de sustituir al viejo."""
    if len(nuevo) < MIN_LARGO_PROMPT:
        return False, f"el prompt nuevo es demasiado corto ({len(nuevo)} caracteres): faltan secciones"
    if anterior and len(nuevo) > len(anterior) * MAX_CRECIMIENTO:
        return False, (
            f"el prompt nuevo crece un {100 * len(nuevo) / len(anterior) - 100:.0f}%: "
            "generalizar debería resumir, no acumular"
        )
    # Las secciones que no pueden perderse por mucho que se "mejore".
    for imprescindible in ("Reglas de seguridad", "Salida obligatoria", '"status"'):
        if imprescindible not in nuevo:
            return False, f"el prompt nuevo perdió la sección «{imprescindible}»"
    return True, ""


def _guardar_version(texto: str, version: str) -> Path:
    CARPETA_VERSIONES.mkdir(parents=True, exist_ok=True)
    destino = CARPETA_VERSIONES / f"{version}.md"
    destino.write_text(texto, encoding="utf-8")
    return destino


def _anotar_changelog(resultado: ResultadoOptimizacion, incidente: str) -> None:
    CHANGELOG.parent.mkdir(parents=True, exist_ok=True)
    if not CHANGELOG.exists():
        CHANGELOG.write_text(
            "# Historial del prompt de reparación\n\n"
            "Una entrada por cada versión que el optimizador creó tras una\n"
            "corrección validada. Las versiones completas viven en\n"
            "`docs/prompts/`; volver atrás es copiar una de ahí sobre\n"
            "`docs/PROMPT_REPARACION.md`.\n",
            encoding="utf-8",
        )
    entrada = (
        f"\n## {resultado.version_nueva} — {datetime.now():%Y-%m-%d %H:%M}\n\n"
        f"- **Desde**: {resultado.version_anterior}\n"
        f"- **Incidente**: {incidente}\n"
        f"- **Regla aprendida**: {resultado.regla}\n"
        f"- **Riesgo de regresión**: {resultado.riesgo_regresion or 'no declarado'}\n"
        f"- **Cambio**: {resultado.changelog}\n"
    )
    with CHANGELOG.open("a", encoding="utf-8") as archivo:
        archivo.write(entrada)


def optimizar(
    incidente: str,
    error_original: str,
    analisis_capturas: str,
    intentos_fallidos: str,
    correccion_exitosa: str,
    validacion: str,
    cliente=None,
    modelo: str | None = None,
) -> ResultadoOptimizacion:
    """Pide una versión mejorada del prompt de reparación.

    `cliente` se inyecta en las pruebas; en producción se construye un
    GeminiClient. Cualquier fallo devuelve `actualizado=False`: no poder
    mejorar el prompt nunca debe romper una reparación que sí funcionó.
    """
    prompt_actual = leer_prompt_reparacion()
    if not prompt_actual:
        return ResultadoOptimizacion(False, "no encuentro docs/PROMPT_REPARACION.md")

    plantilla_ruta = _ruta_recurso("docs/PROMPT_OPTIMIZADOR.md")
    if not plantilla_ruta.exists():
        return ResultadoOptimizacion(False, "no encuentro docs/PROMPT_OPTIMIZADOR.md")

    version = version_actual(prompt_actual)
    plantilla = plantilla_ruta.read_text(encoding="utf-8")
    peticion = (
        plantilla.replace("{{CURRENT_PROMPT}}", prompt_actual)
        .replace("{{INCIDENT}}", incidente)
        .replace("{{ORIGINAL_ERROR}}", error_original)
        .replace("{{SCREENSHOT_ANALYSIS}}", analisis_capturas or "(sin análisis de capturas)")
        .replace("{{FAILED_ATTEMPTS}}", intentos_fallidos or "(ninguno)")
        .replace("{{SUCCESSFUL_CORRECTION}}", correccion_exitosa)
        .replace("{{SUCCESS_VALIDATION}}", validacion)
        .replace("{{PROMPT_VERSION}}", version)
    )

    try:
        if cliente is None:
            from core.gemini_client import GeminiClient

            cliente = GeminiClient(modelo=modelo)
        respuesta = cliente.generar(peticion)
        datos = _extraer_json(respuesta.texto if hasattr(respuesta, "texto") else str(respuesta))
    except Exception as exc:  # noqa: BLE001 - no poder optimizar no rompe nada
        logger.info("El optimizador no pudo proponer una mejora: %s", exc)
        return ResultadoOptimizacion(False, f"{type(exc).__name__}: {exc}")

    if not datos.get("update_prompt"):
        motivo = datos.get("reason", "el incidente no aporta una mejora generalizable")
        return ResultadoOptimizacion(False, motivo, version_anterior=version)

    nuevo = str(datos.get("new_prompt", ""))
    aceptable, problema = _es_aceptable(nuevo, prompt_actual)
    if not aceptable:
        logger.info("Se descarta la versión propuesta del prompt: %s", problema)
        return ResultadoOptimizacion(False, problema, version_anterior=version)

    siguiente = _siguiente_version(version)
    # La versión va en la primera línea: es de donde la lee `version_actual`.
    nuevo = _PATRON_VERSION.sub(siguiente, nuevo, count=1)
    if siguiente not in nuevo.splitlines()[0]:
        nuevo = f"# {siguiente}\n\n" + nuevo

    resultado = ResultadoOptimizacion(
        actualizado=True,
        version_anterior=version,
        version_nueva=siguiente,
        regla=str(datos.get("learning", {}).get("generalized_rule", "")),
        changelog=str(datos.get("changelog", "")),
        riesgo_regresion=str(datos.get("regression_risk", "")),
    )

    try:
        # La versión ANTERIOR también se archiva si aún no lo estaba: sin
        # eso, la primera mejora deja la v1 sin copia a la que volver.
        anterior = CARPETA_VERSIONES / f"{version}.md"
        if not anterior.exists():
            _guardar_version(prompt_actual, version)
        _guardar_version(nuevo, siguiente)
        ruta_prompt_reparacion().write_text(nuevo, encoding="utf-8")
        _anotar_changelog(resultado, incidente)
    except OSError as exc:
        return ResultadoOptimizacion(False, f"no se pudo escribir el prompt nuevo: {exc}")

    logger.info("Prompt de reparación: %s -> %s", version, siguiente)
    return resultado
