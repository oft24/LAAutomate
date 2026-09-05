"""La memoria del autocorrector: lo que ya se aprendió reparando.

Son dos archivos que se leen juntos:

- `docs/PRACTICAS.md` — lo que viene con la versión. Dentro del `.exe` vive
  en `_internal/`, que el instalador borra y recrea en cada actualización,
  así que aquí es de **solo lectura**.
- `practicas_aprendidas.md`, junto al ejecutable — lo que ha aprendido
  ESTA instalación. Es lo único que se escribe, y por vivir fuera de
  `_internal/` sobrevive a las actualizaciones.

Tenerlo todo en un archivo obligaba a elegir, al reinstalar, entre perder
lo aprendido o perder lo que traía la versión nueva. Se comprobó en vivo:
tras una reinstalación el bloque de aprendidas quedaba vacío.

Todo lo que entra pasa por tres filtros —una sola línea, longitud acotada
y descarte si ya existe una práctica parecida— porque esto va en el prompt
de cada reparación y lo repetido diluye lo útil.
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


def ruta_base() -> Path:
    """Las prácticas que trae la versión. Solo lectura."""
    directa = BASE_DIR / "docs" / "PRACTICAS.md"
    if directa.exists():
        return directa
    empaquetada = Path(getattr(sys, "_MEIPASS", BASE_DIR)) / "docs" / "PRACTICAS.md"
    return empaquetada if empaquetada.exists() else directa


def ruta() -> Path:
    """Donde escribe esta instalación. Fuera de `_internal/` a propósito.

    En desarrollo es el mismo `docs/PRACTICAS.md` de siempre: no tiene
    sentido partir en dos un repositorio que ya se versiona con git.
    """
    if not getattr(sys, "frozen", False):
        return ruta_base()
    return BASE_DIR / "practicas_aprendidas.md"


PLANTILLA_APRENDIDAS = (
    "# Prácticas aprendidas en este equipo\n\n"
    "Las escribe el autocorrector cuando una reparación funciona. Se leen\n"
    "junto a las que trae la versión y sobreviven a las actualizaciones.\n\n"
    f"{MARCA_INICIO}\n\n{MARCA_FIN}\n"
)


def _leer(archivo: Path) -> str:
    if not archivo.exists():
        return ""
    try:
        return archivo.read_text(encoding="utf-8")
    except OSError:
        return ""


def ruta_por_migrar() -> Path:
    """El archivo que deja el instalador con la memoria del formato viejo.

    Es un nombre aparte a propósito. Restaurarlo sobre el `PRACTICAS.md`
    del paquete perdía las prácticas nuevas que trajera la versión —pasó—,
    así que el del paquete no se toca nunca.
    """
    return BASE_DIR / "practicas_por_migrar.md"


def migrar_si_hace_falta() -> int:
    """Muda lo aprendido en el formato viejo al archivo propio.

    Se hace sola la primera vez y luego borra el archivo de origen.
    Devuelve cuántas se mudaron; 0 si no había nada o ya se hizo.
    """
    propias = ruta()
    origen = ruta_por_migrar()
    if propias == ruta_base() or propias.exists() or not origen.exists():
        return 0

    heredadas = _aprendidas(_leer(origen))
    if not heredadas:
        origen.unlink(missing_ok=True)
        return 0
    try:
        propias.parent.mkdir(parents=True, exist_ok=True)
        propias.write_text(
            PLANTILLA_APRENDIDAS.replace(
                f"{MARCA_INICIO}\n\n{MARCA_FIN}",
                f"{MARCA_INICIO}\n\n" + "\n".join(heredadas) + f"\n\n{MARCA_FIN}",
            ),
            encoding="utf-8",
        )
    except OSError:
        return 0
    origen.unlink(missing_ok=True)   # mudanza hecha: no se repite
    return len(heredadas)


def leer() -> str:
    """Las dos memorias juntas, limpias y recortadas para un prompt."""
    migrar_si_hace_falta()
    partes = [_leer(ruta_base())]
    propias = ruta()
    if propias != ruta_base():
        aprendidas = _aprendidas(_leer(propias))
        if aprendidas:
            partes.append(
                "\n## Aprendidas en este equipo\n\n" + "\n".join(aprendidas) + "\n"
            )
    texto = "\n".join(p for p in partes if p.strip())
    try:
        from core.gemini_client import limpiar_nota

        texto = limpiar_nota(texto)
    except Exception:  # noqa: BLE001 - sin limpiar se manda igual, solo con ruido
        pass
    return texto[:MAX_CARACTERES_PROMPT]


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

    migrar_si_hace_falta()
    archivo = ruta()
    if not archivo.exists():
        # La primera práctica de una instalación nueva crea el archivo.
        try:
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_text(PLANTILLA_APRENDIDAS, encoding="utf-8")
        except OSError:
            return False
    texto = _leer(archivo)
    if not texto:
        return False

    existentes = _aprendidas(texto)
    # Se compara tambien contra las que trae la version: si la regla ya
    # esta escrita ahi, repetirla aqui solo ocupa sitio en el prompt.
    ya_conocidas = existentes + _aprendidas(_leer(ruta_base()))
    if any(_parecidas(practica, e) for e in ya_conocidas):
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
