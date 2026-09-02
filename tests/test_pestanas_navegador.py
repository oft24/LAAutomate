"""Comprobación de extremo a extremo del control de pestañas CONTRA UN
NAVEGADOR REAL: un click abre una pestaña, la automatización la sigue,
trabaja dentro, la cierra y vuelve.

`test_pestanas.py` fija el contrato contra un driver falso; esto comprueba
que el contrato coincide con lo que hace Selenium de verdad. Las dos cosas
hacen falta: el doble no sabe que Selenium NO sigue una pestaña nueva por
su cuenta, que es justo el fallo silencioso que todo esto existe para
evitar.

Necesitan un navegador instalado, no internet: la página se sirve desde
localhost. Marcadas `navegador`; para saltarlas: `pytest -m "not navegador"`.
"""
from __future__ import annotations

import logging
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from engine.actions.recorder import GrabadoraWeb, generar_codigo
from engine.actions.web import WebActions

pytestmark = pytest.mark.navegador


PORTAL = """<!doctype html>
<html><head><meta charset="utf-8"><title>Portal de facturas</title></head>
<body>
  <h1 id="titulo">Portal de facturas</h1>
  <a id="ver-comprobante" href="comprobante.html" target="_blank">Ver comprobante</a>
</body></html>
"""

COMPROBANTE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Comprobante A-1234</title></head>
<body><span id="folio">A-1234</span></body></html>
"""


@pytest.fixture(scope="module")
def portal(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("portal")
    (raiz / "index.html").write_text(PORTAL, encoding="utf-8")
    (raiz / "comprobante.html").write_text(COMPROBANTE, encoding="utf-8")

    servidor = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(raiz))
    )
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{servidor.server_port}/index.html"
    servidor.shutdown()


@pytest.fixture
def web(portal):
    logger = logging.getLogger("prueba_pestanas")
    logger.addHandler(logging.NullHandler())
    navegador = WebActions(logger, headless=True)
    try:
        yield navegador
    finally:
        try:
            navegador.cerrar()
        except Exception:
            pass


def test_una_automatizacion_puede_trabajar_en_la_pestana_que_abrio_un_click(web, portal) -> None:
    """El flujo completo tal como lo escribiría una automatización real."""
    web.ir_a(portal)
    web.click("#ver-comprobante")

    web.cambiar_a_pestana_nueva()
    assert web.leer_texto("#folio") == "A-1234"

    web.cerrar_pestana()
    assert web.leer_texto("#titulo") == "Portal de facturas"


def test_sin_cambiar_de_pestana_se_sigue_leyendo_la_pagina_vieja(web, portal) -> None:
    """La razón de existir de todo esto: Selenium NO sigue la pestaña nueva.
    Sin el cambio explícito, los pasos siguientes se ejecutan contra la
    página anterior -- y aquí ni siquiera dan error, simplemente devuelven
    lo que no es."""
    web.ir_a(portal)
    web.click("#ver-comprobante")

    assert web.leer_texto("#titulo") == "Portal de facturas"  # seguimos en la vieja


def test_cambiar_a_pestana_por_titulo_encuentra_la_correcta(web, portal) -> None:
    web.ir_a(portal)
    web.click("#ver-comprobante")
    web.cambiar_a_pestana_nueva()

    assert web.cambiar_a_pestana("Portal") == "Portal de facturas"
    assert web.cambiar_a_pestana("Comprobante") == "Comprobante A-1234"


def test_pestanas_lista_las_dos_abiertas(web, portal) -> None:
    web.ir_a(portal)
    web.click("#ver-comprobante")
    web.cambiar_a_pestana_nueva()

    assert sorted(web.pestanas()) == ["Comprobante A-1234", "Portal de facturas"]


def test_la_grabadora_genera_el_cambio_de_pestana_de_un_flujo_real(web, portal) -> None:
    """Cierra el círculo: grabar un click que abre una pestaña tiene que
    producir un automation.py que también la siga al reproducirse."""
    logger = logging.getLogger("prueba_pestanas")
    logger.addHandler(logging.NullHandler())
    grabadora = GrabadoraWeb(web, logger)
    grabadora.iniciar(portal)

    web.driver.find_element("css selector", "#ver-comprobante").click()
    # el sondeo corre cada 400 ms: se le da margen para ver la pestaña nueva
    espera = threading.Event()
    espera.wait(2.0)

    pasos = grabadora.detener()
    codigo = generar_codigo("flujo_comprobante", pasos)

    assert any(p["tipo"] == "cambiar_pestana" for p in pasos), pasos
    assert "self.web.cambiar_a_pestana_nueva()" in codigo
    compile(codigo, "<generado>", "exec")
