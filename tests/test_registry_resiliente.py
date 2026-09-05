"""Una automatización rota no puede impedir que la app arranque.

`descubrir()` corre en app/main.py ANTES de crear la QApplication. Cuando
dejaba subir la excepción, un solo automation.py con un error de sintaxis
hacía que el .exe no abriera: sin ventana, sin mensaje, solo un traceback
en una consola que el usuario del ejecutable ni siquiera ve. Y llegar a
ese estado es fácil -- el editor de la vista Automatizaciones guarda lo
que sea, y el Agente IA también escribe ahí.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from engine.registry import descubrir, errores_de_descubrimiento, listar, olvidar_error

CARPETA_ROTA = Path("automations") / "_prueba_automatizacion_rota"


@pytest.fixture
def automatizacion_rota():
    """Deja en automations/ una automatización que no compila.

    Tiene que estar en la carpeta REAL: lo que se prueba es justamente el
    recorrido de `pkgutil.walk_packages` sobre el paquete `automations`,
    que no se puede redirigir a un tmp_path sin dejar de probar el camino
    que corre de verdad al arrancar.
    """
    CARPETA_ROTA.mkdir(parents=True, exist_ok=True)
    (CARPETA_ROTA / "__init__.py").write_text(
        "from automations._prueba_automatizacion_rota.automation import Rota\n", encoding="utf-8"
    )
    (CARPETA_ROTA / "automation.py").write_text("esto no es python valido (((\n", encoding="utf-8")
    try:
        yield "_prueba_automatizacion_rota"
    finally:
        shutil.rmtree(CARPETA_ROTA, ignore_errors=True)
        descubrir()  # deja el registry como estaba para el resto de las pruebas


def test_una_automatizacion_rota_no_tumba_el_descubrimiento(automatizacion_rota) -> None:
    from engine.almacen import listar_en_disco

    registro = descubrir()
    sanas = [n for n in listar_en_disco() if n != automatizacion_rota]

    assert sanas, "hace falta al menos una automatizacion sana para que la prueba diga algo"
    for nombre in sanas:
        assert nombre in registro, f"{nombre} dejo de cargar por culpa de la rota"
    assert automatizacion_rota not in registro


def test_la_causa_del_fallo_queda_disponible_para_la_interfaz(automatizacion_rota) -> None:
    descubrir()
    errores = errores_de_descubrimiento()

    assert automatizacion_rota in errores
    assert "SyntaxError" in errores[automatizacion_rota]


def test_olvidar_error_limpia_la_marca_al_corregirla(automatizacion_rota) -> None:
    """Tras arreglarla no debe seguir saliendo con la marca de "no compila"
    hasta reiniciar -- ni mandarle al modelo un error que ya no existe."""
    descubrir()
    assert automatizacion_rota in errores_de_descubrimiento()

    olvidar_error(automatizacion_rota)

    assert automatizacion_rota not in errores_de_descubrimiento()


def test_descubrir_limpia_errores_de_la_vuelta_anterior(automatizacion_rota) -> None:
    descubrir()
    assert errores_de_descubrimiento()

    shutil.rmtree(CARPETA_ROTA)
    descubrir()

    assert automatizacion_rota not in errores_de_descubrimiento()


def test_sin_automatizaciones_rotas_no_hay_errores() -> None:
    descubrir()
    assert errores_de_descubrimiento() == {}
    assert listar(), "el repo trae automatizaciones de ejemplo"
