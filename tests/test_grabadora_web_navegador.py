"""Pruebas de la captura de texto de la Grabadora web CONTRA UN NAVEGADOR REAL.

Son las pruebas de regresión que `docs/logica-grabadora.md` exigía para dar
por corregido el defecto de la escritura perdida. Tienen que correr en un
navegador de verdad porque lo que se está validando es JavaScript: qué
evento emite el navegador y cuándo. Un doble de prueba solo confirmaría lo
que el doble ya finge.

La página se sirve por HTTP desde localhost en vez de abrirse como
`file://`: el listener guarda los eventos en `localStorage`, y un origen
`file://` es opaco -- los navegadores le niegan `localStorage` y la
grabadora no capturaría nada por una razón que no tiene que ver con lo que
se quiere medir.

No necesitan internet, solo un navegador instalado. Marcadas `navegador`;
para saltarlas: `pytest -m "not navegador"`.
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


PAGINA = """<!doctype html>
<html><head><meta charset="utf-8"><title>Formulario de prueba</title></head>
<body>
  <input id="nombre" type="text">
  <textarea id="notas"></textarea>
  <input id="clave" type="password">
  <input id="acepta" type="checkbox">
  <input id="opcion" type="radio" name="g">
  <input id="adjunto" type="file">
  <input id="enviar" type="submit" value="Enviar">
  <button id="otro">Otro</button>
</body></html>
"""


@pytest.fixture(scope="module")
def servidor(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("sitio")
    (raiz / "index.html").write_text(PAGINA, encoding="utf-8")

    servidor = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(raiz))
    )
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_port}/index.html"
    servidor.shutdown()


@pytest.fixture
def grabando(servidor):
    """Grabadora ya iniciada sobre la página de prueba; se cierra sola."""
    logger = logging.getLogger("prueba_grabadora_web")
    logger.addHandler(logging.NullHandler())
    web = WebActions(logger, headless=True)
    grabadora = GrabadoraWeb(web, logger)
    try:
        grabadora.iniciar(servidor)
        yield grabadora, web
    finally:
        try:
            web.cerrar()
        except Exception:
            pass


def _escribir_sin_perder_el_foco(web, id_campo, texto):
    """Teclea en el campo y NO toca nada más: reproduce exactamente el
    flujo del usuario que escribe y se va directo a presionar Detener."""
    web.driver.find_element("css selector", f"#{id_campo}").send_keys(texto)


def _valores_escritos(pasos, selector):
    return [p["valor"] for p in pasos if p["tipo"] == "escribir" and p["selector"] == selector]


# 1. escribir en un campo y detener sin blur genera `escribir`
def test_escribir_y_detener_sin_sacar_el_foco_si_genera_el_paso(grabando) -> None:
    """El defecto original: con el listener en 'change', el evento solo se
    emitía al perder el foco. Quien escribía y se iba a LaAutomate a
    presionar Detener nunca lo emitía y el paso no existía."""
    grabadora, web = grabando

    _escribir_sin_perder_el_foco(web, "nombre", "Luis")
    pasos = grabadora.detener()

    assert _valores_escritos(pasos, "#nombre") == ["Luis"]


def test_tambien_captura_un_textarea(grabando) -> None:
    grabadora, web = grabando

    _escribir_sin_perder_el_foco(web, "notas", "una nota larga")
    pasos = grabadora.detener()

    assert _valores_escritos(pasos, "#notas") == ["una nota larga"]


# 2. escribir, borrar y corregir conserva el valor final
def test_escribir_borrar_y_corregir_conserva_solo_el_valor_final(grabando) -> None:
    """'input' emite un evento por tecla; deben colapsarse en el valor que
    quedó en el campo, no en una lista de estados intermedios.

    Lo que se afirma es el valor FINAL y el código generado, no cuántos
    pasos crudos hay: el hilo de sondeo vacía `localStorage` cada 400 ms y,
    si ese vaciado cae entre dos teclas, el valor intermedio queda como un
    paso aparte. Eso es correcto y depende del reloj — afirmarlo haría una
    prueba que pasa sola y falla bajo carga.
    """
    grabadora, web = grabando

    campo = web.driver.find_element("css selector", "#nombre")
    campo.send_keys("Luiz")
    campo.send_keys("\b")  # backspace: corrige el typo
    campo.send_keys("s")
    pasos = grabadora.detener()

    assert _valores_escritos(pasos, "#nombre")[-1] == "Luis"

    # _depurar_pasos colapsa las escrituras consecutivas sobre el mismo
    # selector, así que el archivo generado escribe el valor final una vez.
    codigo = generar_codigo("correccion_de_typo", pasos)
    assert codigo.count("self.web.escribir('#nombre'") == 1
    assert "'Luis'" in codigo


# 3. un campo `password` nunca aparece en los pasos
def test_una_contrasena_nunca_llega_a_los_pasos_ni_al_codigo(grabando) -> None:
    grabadora, web = grabando

    _escribir_sin_perder_el_foco(web, "nombre", "Luis")
    _escribir_sin_perder_el_foco(web, "clave", "SuperSecreta123")
    pasos = grabadora.detener()

    assert "SuperSecreta123" not in str(pasos)
    assert _valores_escritos(pasos, "#clave") == []
    assert "SuperSecreta123" not in generar_codigo("prueba_password", pasos)


# 4. checkbox, radio, file y submit no generan `escribir`
def test_los_controles_que_no_son_texto_no_generan_escribir(grabando) -> None:
    """Su "valor" es un estado (marcado, un archivo elegido), no texto
    tecleado: convertirlo en self.web.escribir() genera código que no
    reproduce nada."""
    grabadora, web = grabando

    for id_control in ("acepta", "opcion", "enviar"):
        web.driver.find_element("css selector", f"#{id_control}").click()
    pasos = grabadora.detener()

    escrituras = [p for p in pasos if p["tipo"] == "escribir"]
    assert escrituras == [], f"no debería haber escrituras, hay: {escrituras}"
    # pero los clicks sí se graban: son acciones reales
    assert any(p["tipo"] == "click" for p in pasos)


def test_el_codigo_generado_de_una_escritura_sin_blur_es_valido_y_reproduce(grabando) -> None:
    """Cierra el círculo: no basta con capturar el paso, tiene que salir un
    automation.py que de verdad escriba ese valor."""
    grabadora, web = grabando

    _escribir_sin_perder_el_foco(web, "nombre", "Luis")
    pasos = grabadora.detener()
    codigo = generar_codigo("flujo_sin_blur", pasos)

    assert "self.web.escribir('#nombre', 'Luis')" in codigo
    compile(codigo, "<generado>", "exec")
