"""Validación de las filas del Excel antes de consultar el CURP.

Todo esto corre SIN navegador y sin red: es exactamente el punto. Cada
consulta a gob.mx cuesta una petición contra un servicio con reCAPTCHA que
puntúa el comportamiento, así que descubrir en la fila 300 que el estado
estaba mal escrito —con 299 consultas ya gastadas— es el peor resultado
posible. Estas pruebas cubren que una fila mala se rechace antes de salir a
la red.
"""
from __future__ import annotations

import pytest

from automations.curp_desde_excel.automation import (
    DatosInvalidos,
    anio_valido,
    clave_entidad,
    clave_sexo,
    dos_digitos,
    nombre_archivo,
)


# --------------------------------------------------------------- sexo


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("Hombre", "H"), ("hombre", "H"), ("MASCULINO", "H"), ("h", "H"),
        ("Mujer", "M"), ("femenino", "M"), ("F", "M"),
        ("No binario", "X"), ("x", "X"),
    ],
)
def test_sexo_acepta_lo_que_la_gente_escribe_de_verdad(entrada, esperado) -> None:
    assert clave_sexo(entrada) == esperado


def test_una_m_suelta_se_rechaza_por_ambigua() -> None:
    """«M» es Masculino para unos y Mujer para otros. Adivinar significa
    consultar a la persona equivocada y devolver un CURP que no es suyo;
    preguntar cuesta una corrección en el Excel."""
    with pytest.raises(DatosInvalidos, match="ambigu"):
        clave_sexo("M")


def test_sexo_desconocido_dice_que_poner() -> None:
    with pytest.raises(DatosInvalidos, match="Hombre/Mujer"):
        clave_sexo("varón")


# -------------------------------------------------------------- estado


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("Jalisco", "JC"), ("jalisco", "JC"),
        ("Michoacán", "MN"), ("Michoacan", "MN"),  # con y sin acento
        ("Ciudad de México", "DF"), ("CDMX", "DF"), ("Distrito Federal", "DF"),
        ("Estado de México", "MC"), ("EdoMex", "MC"),
        ("Nuevo León", "NL"), ("San Luis Potosí", "SP"),
        ("JC", "JC"), ("df", "DF"),  # la clave directa, en cualquier caja
        ("Nacido en el extranjero", "NE"), ("extranjero", "NE"),
    ],
)
def test_estado_acepta_nombre_o_clave_con_o_sin_acentos(entrada, esperado) -> None:
    assert clave_entidad(entrada) == esperado


def test_estado_inventado_dice_que_poner() -> None:
    with pytest.raises(DatosInvalidos, match="2 letras"):
        clave_entidad("Barcelona")


# ---------------------------------------------------------- fecha


def test_el_dia_se_rellena_a_dos_digitos() -> None:
    """El <select> del formulario tiene «01», no «1»: un 1 suelto no hace
    match con ninguna opción y Selenium falla sin decir por qué."""
    assert dos_digitos(5, "dia", 1, 31) == "05"
    assert dos_digitos("5", "dia", 1, 31) == "05"
    assert dos_digitos(22, "dia", 1, 31) == "22"


def test_un_5_leido_como_5_0_por_pandas_sigue_siendo_05() -> None:
    """pandas lee una columna numérica de Excel como float: 5 llega como
    5.0 y `str(5.0)` es «5.0», que no existe en el desplegable."""
    assert dos_digitos(5.0, "dia", 1, 31) == "05"
    assert anio_valido(1990.0) == "1990"


@pytest.mark.parametrize("valor", [0, 32, -1])
def test_dia_fuera_de_rango_se_rechaza(valor) -> None:
    with pytest.raises(DatosInvalidos, match="fuera de rango"):
        dos_digitos(valor, "dia", 1, 31)


def test_mes_trece_se_rechaza() -> None:
    with pytest.raises(DatosInvalidos, match="fuera de rango"):
        dos_digitos(13, "mes", 1, 12)


def test_texto_en_una_fecha_se_rechaza() -> None:
    with pytest.raises(DatosInvalidos, match="no es un número"):
        dos_digitos("marzo", "mes", 1, 12)


@pytest.mark.parametrize("valor", [1800, 2200])
def test_anio_imposible_se_rechaza(valor) -> None:
    with pytest.raises(DatosInvalidos, match="fuera de rango"):
        anio_valido(valor)


# ------------------------------------------------- nombre de archivo


def test_el_nombre_de_archivo_es_estable_y_valido_en_windows() -> None:
    """Estable importa: es lo que permite reanudar el lote. Si el PDF ya
    existe, esa fila ya se consultó y se salta."""
    fila = {"nombres": "María Fernanda", "primer_apellido": "Pérez", "segundo_apellido": "Ñáñez"}
    nombre = nombre_archivo(fila)

    assert nombre == "perez_nanez_maria_fernanda"
    assert not set(nombre) & set('<>:"/\\|?*'), "sin caracteres prohibidos en Windows"
    assert nombre_archivo(dict(fila)) == nombre, "el mismo dato da el mismo archivo"


def test_sin_segundo_apellido_no_deja_un_hueco() -> None:
    fila = {"nombres": "Ana", "primer_apellido": "Ruiz", "segundo_apellido": ""}
    assert nombre_archivo(fila) == "ruiz_ana"


def test_una_fila_vacia_no_produce_un_archivo_sin_nombre() -> None:
    assert nombre_archivo({}) == "sin_nombre"
