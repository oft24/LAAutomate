"""Lee y amplía `docs/PRACTICAS.md`, la memoria del autocorrector.

El archivo se inyecta en el prompt de cada reparación y el autocorrector le
añade una línea cada vez que un arreglo funciona. Así el sistema deja de
tropezar dos veces con la misma piedra.

Escribir en un archivo que luego alimenta un prompt merece cuidado, y por
eso todo lo que entra aquí pasa por tres filtros: se recorta a una línea,
se limita en longitud, y se descarta si ya hay una práctica parecida. Sin
eso el archivo crece hasta que la parte útil se diluye — y una práctica
repetida veinte veces no enseña veinte veces más.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

from core.config import BASE_DIR

MARCA_INICIO = "<!-- INICIO AUTOCORRECTOR -->"
MARCA_FIN = "<!-- FIN AUTOCORRECTOR -->"

MAX_LARGO_PRACTICA = 300
# Cuántas prácticas aprendidas se conservan. Las viejas se van por el
# principio: si una regla sigue siendo cierta, volverá a aprenderse.
MAX_PRACTICAS = 40
# Cuánto del archivo se manda al modelo. Es contexto en cada reparación,
# así que no puede crecer sin límite.
MAX_CARACTERES_PROMPT = 12_000


def ruta() -> Path:
    """Localiza el archivo en desarrollo y dentro del .exe empaquetado."""
    directa = BASE_DIR / "docs" / "PRACTICAS.md"
    if directa.exists():
        return directa
    empaquetada = Path(getattr(sys, "_MEIPASS", BASE_DIR)) / "docs" / "PRACTICAS.md"
    return empaquetada if empaquetada.exists() else directa


def leer() -> str:
    """El texto completo, recortado a lo que cabe en un prompt."""
    archivo = ruta()
    if not archivo.exists():
        return ""
    try:
        return archivo.read_text(encoding="utf-8")[:MAX_CARACTERES_PROMPT]
    except OSError:
        return ""


def _normalizar(texto: str) -> str:
    """Para comparar prácticas: sin acentos, sin puntuación, en minúsculas.

    Dos redacciones distintas de la misma regla no deben acumularse -- y
    el modelo casi nunca repite la frase palabra por palabra.
    """
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return " ".join(re.sub(r"[^\w\s]", " ", sin_acentos.lower()).split())


def _parecidas(a: str, b: str) -> bool:
    """True si dos prácticas dicen esencialmente lo mismo.

    Se comparan como conjuntos de palabras y no con difflib porque lo que
    importa es de qué HABLAN: «usa click_por_tipo Edit en campos de texto»
    y «en un campo de texto usa click_por_tipo('Edit')» comparten casi
    todas las palabras significativas aunque el orden cambie del todo.
    """
    palabras_a = {p for p in _normalizar(a).split() if len(p) > 3}
    palabras_b = {p for p in _normalizar(b).split() if len(p) > 3}
    if not palabras_a or not palabras_b:
        return False
    comunes = palabras_a & palabras_b
    return len(comunes) / min(len(palabras_a), len(palabras_b)) >= 0.7


def _aprendidas(texto: str) -> list[str]:
    inicio = texto.find(MARCA_INICIO)
    fin = texto.find(MARCA_FIN)
    if inicio == -1 or fin <= inicio:
        return []
    bloque = texto[inicio + len(MARCA_INICIO) : fin]
    return [l.strip() for l in bloque.splitlines() if l.strip().startswith("- ")]


def anotar(practica: str, automatizacion: str, error: str = "") -> bool:
    """Añade una práctica aprendida. Devuelve True si se guardó.

    Se descarta —sin ruido— cuando viene vacía, cuando es demasiado larga
    para ser una regla (probablemente el modelo se puso a narrar) o cuando
    ya hay una que dice lo mismo.
    """
    practica = " ".join(str(practica).split())
    if len(practica) < 15 or len(practica) > MAX_LARGO_PRACTICA:
        return False

    archivo = ruta()
    if not archivo.exists():
        return False
    try:
        texto = archivo.read_text(encoding="utf-8")
    except OSError:
        return False

    existentes = _aprendidas(texto)
    if any(_parecidas(practica, e) for e in existentes):
        return False

    causa = f" (tras: {error.strip()[:90]})" if error.strip() else ""
    nueva = f"- **{date.today().isoformat()} · {automatizacion}** — {practica}{causa}"

    lineas = existentes + [nueva]
    if len(lineas) > MAX_PRACTICAS:
        lineas = lineas[-MAX_PRACTICAS:]

    inicio = texto.find(MARCA_INICIO)
    fin = texto.find(MARCA_FIN)
    if inicio == -1 or fin <= inicio:
        return False

    nuevo_texto = (
        texto[: inicio + len(MARCA_INICIO)] + "\n\n" + "\n".join(lineas) + "\n\n" + texto[fin:]
    )
    try:
        archivo.write_text(nuevo_texto, encoding="utf-8")
    except OSError:
        return False
    return True
