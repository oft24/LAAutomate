"""Lógica pura de la búsqueda de vídeos: sin navegador y sin red.

Lo que se cubre aquí es lo que decide QUÉ se busca y qué se salta. Un fallo
en esta parte no da error: da datos silenciosamente equivocados —una
consulta con una palabra de más, o una búsqueda repetida cada vez que se
ejecuta— y eso es peor que una excepción.
"""
from __future__ import annotations

import pytest

from automations.buscar_videos_youtube.automation import (
    clave_de_busqueda,
    construir_consulta,
    normalizar,
    url_de_busqueda,
)


# ------------------------------------------------- celdas vacías de Excel


def test_una_celda_vacia_de_excel_no_se_convierte_en_la_palabra_nan() -> None:
    """El defecto real: pandas devuelve `float("nan")` para una celda vacía
    y `str(nan)` es «nan». La búsqueda acabó consultando literalmente
    «automatización con python nan».
    """
    assert normalizar(float("nan")) == ""
    assert normalizar(None) == ""
    assert normalizar("  ") == ""


def test_la_cadena_nan_tambien_se_trata_como_vacio() -> None:
    """Según por dónde pase el dato, el NaN llega ya convertido a texto."""
    assert normalizar("nan") == ""
    assert normalizar("NaN") == ""


def test_un_valor_normal_no_se_toca() -> None:
    assert normalizar("  Python  ") == "Python"
    assert normalizar(2026) == "2026"


def test_la_consulta_de_una_fila_sin_canal_no_arrastra_basura() -> None:
    fila = {"tema": "automatización con python", "canal": float("nan")}
    assert construir_consulta(fila) == "automatización con python"


# ------------------------------------------------------------- consulta


def test_el_canal_se_suma_al_tema() -> None:
    fila = {"tema": "selenium tutorial", "canal": "Código Espinoza"}
    assert construir_consulta(fila) == "selenium tutorial Código Espinoza"


def test_una_fila_con_solo_canal_tambien_vale() -> None:
    assert construir_consulta({"tema": "", "canal": "IBM Technology"}) == "IBM Technology"


def test_una_fila_del_todo_vacia_se_rechaza() -> None:
    with pytest.raises(ValueError, match="ni tema ni canal"):
        construir_consulta({"tema": "", "canal": ""})


def test_la_url_escapa_los_espacios_y_los_acentos() -> None:
    url = url_de_busqueda("automatización con python")
    assert url.startswith("https://www.youtube.com/results?search_query=")
    assert " " not in url
    assert "automatizaci" in url


# --------------------------------------------- saltar lo ya buscado


def test_la_misma_busqueda_escrita_distinto_es_la_misma() -> None:
    """Es lo que evita repetir una consulta —y gastar tiempo— porque
    alguien dejó un espacio de más o cambió una mayúscula."""
    a = clave_de_busqueda({"tema": "  Python  Automatización ", "canal": ""})
    b = clave_de_busqueda({"tema": "python automatización", "canal": ""})
    assert a == b


def test_dos_busquedas_distintas_no_se_confunden() -> None:
    a = clave_de_busqueda({"tema": "selenium", "canal": "Canal A"})
    b = clave_de_busqueda({"tema": "selenium", "canal": "Canal B"})
    assert a != b


def test_el_canal_vacio_no_cambia_la_clave() -> None:
    """Añadir un canal vacío a una fila no puede convertirla en una
    búsqueda «nueva»: se repetiría en cada ejecución."""
    con_nan = clave_de_busqueda({"tema": "rpa", "canal": float("nan")})
    sin_columna = clave_de_busqueda({"tema": "rpa"})
    vacio = clave_de_busqueda({"tema": "rpa", "canal": ""})
    assert con_nan == sin_columna == vacio == "rpa"
