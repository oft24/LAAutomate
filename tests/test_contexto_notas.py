"""Las notas de `docs/` se limpian antes de entrar en el prompt.

Son notas de Obsidian: metadatos YAML, enlaces `[[nota]]` y avisos
`> [!warning]`. Nada de eso significa algo para el modelo, y los enlaces
apuntan a notas que no va a recibir. Lo que se prueba aquí es que la
decoración desaparece sin llevarse el contenido por delante.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.gemini_client import construir_contexto_proyecto, limpiar_nota


# ------------------------------------------------------------ frontmatter


def test_los_metadatos_de_obsidian_no_llegan_al_modelo() -> None:
    nota = "---\ntags: [x, y]\nalias: [\"Otro nombre\"]\n---\n\n# Título\n\ncuerpo\n"

    assert limpiar_nota(nota) == "# Título\n\ncuerpo\n"


def test_una_nota_sin_metadatos_no_se_toca() -> None:
    nota = "# Título\n\ncuerpo con --- guiones en medio\n"

    assert limpiar_nota(nota) == nota


def test_unos_guiones_sin_cierre_no_se_comen_la_nota() -> None:
    """Un `---` inicial sin su pareja es una línea horizontal, no metadatos.
    Cortar hasta el final dejaría la nota vacía."""
    nota = "---\n\n# Título\n\ncuerpo\n"

    assert "# Título" in limpiar_nota(nota)
    assert "cuerpo" in limpiar_nota(nota)


# ---------------------------------------------------------------- enlaces


@pytest.mark.parametrize(
    ("enlace", "esperado"),
    [
        ("[[acciones]]", "acciones"),
        ("[[acciones|la referencia]]", "la referencia"),
        ("[[acciones#Web]]", "acciones"),
        ("[[acciones#Web|el navegador]]", "el navegador"),
    ],
)
def test_un_enlace_se_queda_en_su_texto(enlace: str, esperado: str) -> None:
    assert limpiar_nota(f"Ver {enlace} para más.") == f"Ver {esperado} para más."


def test_dos_enlaces_en_la_misma_linea_no_se_pisan() -> None:
    limpio = limpiar_nota("Ver [[acciones]] y también [[arquitectura|el motor]].")

    assert limpio == "Ver acciones y también el motor."


# ----------------------------------------------------------------- avisos


def test_un_aviso_conserva_su_titulo() -> None:
    nota = "> [!warning] Cuidado con esto\n> el detalle\n"

    assert limpiar_nota(nota) == "> **Cuidado con esto**\n> el detalle\n"


def test_un_aviso_plegable_tambien() -> None:
    assert limpiar_nota("> [!tip]- Truco\n") == "> **Truco**\n"


def test_una_cita_normal_no_se_toca() -> None:
    assert limpiar_nota("> una cita cualquiera\n") == "> una cita cualquiera\n"


# --------------------------------------------- sobre las notas de verdad


@pytest.mark.parametrize(
    "nota", ["arquitectura.md", "acciones.md", "logica-grabadora.md"]
)
def test_las_notas_que_se_inyectan_quedan_limpias(nota: str) -> None:
    """Estas tres se mandan enteras en cada petición del asistente."""
    ruta = Path("docs") / nota
    if not ruta.exists():  # pragma: no cover - solo si se renombra una nota
        pytest.skip(f"{nota} ya no existe")

    limpia = limpiar_nota(ruta.read_text(encoding="utf-8"))

    assert not limpia.startswith("---"), "los metadatos siguen ahí"
    assert "[[" not in limpia, "quedaron enlaces de Obsidian"
    assert "[!" not in limpia, "quedaron avisos sin convertir"
    assert len(limpia) > 1_000, "la limpieza se llevó el contenido"


def test_el_contexto_del_proyecto_no_arrastra_decoracion() -> None:
    contexto = construir_contexto_proyecto()

    assert "[[" not in contexto
    assert "\n---\ntags:" not in contexto


def test_las_practicas_tampoco_llegan_decoradas() -> None:
    """PRACTICAS.md se lee entera en cada reparación y en cada generación."""
    from engine import practicas

    texto = practicas.leer()

    assert texto, "sin prácticas no hay nada que comprobar"
    assert not texto.startswith("---"), "los metadatos llegan al prompt"
    assert "[[" not in texto, "los enlaces de Obsidian llegan al prompt"
