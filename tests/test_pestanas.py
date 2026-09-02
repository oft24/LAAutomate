"""Pruebas del control de pestañas del navegador (WebActions) y de que la
Grabadora web siga al usuario cuando un click abre una pestaña nueva.

Todo contra un driver falso: el objetivo es fijar el CONTRATO (a qué
pestaña queda apuntando el driver después de cada operación), que es
justo donde Selenium tiene sus trampas silenciosas -- no abrir un
navegador de verdad.
"""
from __future__ import annotations

import pytest
from selenium.common.exceptions import WebDriverException

from engine.actions.recorder import GrabadoraWeb, _depurar_pasos, generar_codigo
from engine.actions.web import WebActions


class _DriverFalso:
    """Imita lo justo de Selenium: un conjunto de handles, cuál está
    activo, y el título/URL de cada uno."""

    def __init__(self, paginas: dict[str, tuple[str, str]], activo: str | None = None) -> None:
        self._paginas = dict(paginas)
        self._activo = activo if activo is not None else next(iter(paginas))
        self.cerrado = False
        self.switch_to = self._SwitchTo(self)

    class _SwitchTo:
        def __init__(self, driver) -> None:
            self._driver = driver

        def window(self, handle):
            if handle not in self._driver._paginas:
                raise WebDriverException(f"no such window: {handle}")
            self._driver._activo = handle

        def new_window(self, _tipo):
            handle = f"h{len(self._driver._paginas) + 1}"
            self._driver._paginas[handle] = ("", "about:blank")
            self._driver._activo = handle

    @property
    def window_handles(self):
        return list(self._paginas)

    @property
    def current_window_handle(self):
        if self._activo not in self._paginas:
            raise WebDriverException("no such window: target window already closed")
        return self._activo

    @property
    def title(self):
        return self._paginas[self._activo][0]

    @property
    def current_url(self):
        return self._paginas[self._activo][1]

    def get(self, url):
        self._paginas[self._activo] = (self._paginas[self._activo][0], url)

    def close(self):
        del self._paginas[self._activo]

    def quit(self):
        self.cerrado = True

    # --- helpers de la prueba, no parte de la API de Selenium ---
    def abrir_pestana(self, handle, titulo, url):
        self._paginas[handle] = (titulo, url)

    def execute_script(self, _s):
        return []

    def execute_cdp_cmd(self, *_a, **_k):
        return None


class _LoggerFalso:
    def info(self, *a, **k):
        pass

    def debug(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass


def _web(driver) -> WebActions:
    web = WebActions(_LoggerFalso(), timeout=1)
    web._driver = driver
    # Mismo estado con el que nace en producción: la propiedad `driver`
    # apunta la foto de pestañas conocidas al abrir el navegador. Inyectar
    # el driver a mano se la salta, y sin ella TODA pestaña parecería nueva.
    web._recordar_pestanas()
    return web


TRES_PESTANAS = {
    "h1": ("Portal de ventas", "https://portal.interno/ventas"),
    "h2": ("Facturación", "https://erp.interno/facturas"),
    "h3": ("Correo", "https://correo.interno/inbox"),
}


# --------------------------- cambiar de pestaña ---------------------------


def test_cambiar_a_pestana_por_indice() -> None:
    driver = _DriverFalso(TRES_PESTANAS, activo="h1")
    assert _web(driver).cambiar_a_pestana(1) == "Facturación"
    assert driver.current_window_handle == "h2"


def test_cambiar_a_pestana_por_fragmento_de_titulo_sin_importar_mayusculas() -> None:
    driver = _DriverFalso(TRES_PESTANAS, activo="h1")
    assert _web(driver).cambiar_a_pestana("factur") == "Facturación"
    assert driver.current_window_handle == "h2"


def test_cambiar_a_pestana_tambien_busca_en_la_url() -> None:
    """El título de una SPA cambia solo (notificaciones, "(3) Bandeja");
    la URL es lo estable, así que también debe servir de referencia."""
    driver = _DriverFalso(TRES_PESTANAS, activo="h1")
    assert _web(driver).cambiar_a_pestana("correo.interno") == "Correo"
    assert driver.current_window_handle == "h3"


def test_cambiar_a_pestana_inexistente_deja_el_foco_donde_estaba() -> None:
    """Si la búsqueda falla, la automatización debe poder capturar el error
    y seguir trabajando en la pestaña en la que estaba -- no quedarse
    apuntando a la última que el barrido visitó."""
    driver = _DriverFalso(TRES_PESTANAS, activo="h2")
    with pytest.raises(LookupError, match="Ninguna pestaña"):
        _web(driver).cambiar_a_pestana("no existe")
    assert driver.current_window_handle == "h2"


def test_cambiar_a_pestana_indice_fuera_de_rango_menciona_cuantas_hay() -> None:
    driver = _DriverFalso(TRES_PESTANAS, activo="h1")
    with pytest.raises(LookupError, match="hay 3 abierta"):
        _web(driver).cambiar_a_pestana(9)


def test_pestanas_devuelve_los_titulos_y_restaura_el_foco() -> None:
    driver = _DriverFalso(TRES_PESTANAS, activo="h2")
    assert _web(driver).pestanas() == ["Portal de ventas", "Facturación", "Correo"]
    assert driver.current_window_handle == "h2"


def test_pestanas_no_deja_el_driver_sin_ventana_si_la_activa_ya_se_cerro() -> None:
    """Tras cerrar una pestaña por fuera, current_window_handle revienta.
    pestanas() debe dejar el foco en una válida en vez de propagar el
    fallo: cualquier comando siguiente moriría con NoSuchWindowException."""
    driver = _DriverFalso(TRES_PESTANAS, activo="h1")
    del driver._paginas["h1"]  # se cerró por fuera; el driver aún la apunta

    titulos = _web(driver).pestanas()

    assert titulos == ["Facturación", "Correo"]
    assert driver.current_window_handle == "h3"


# ------------------------- seguir una pestaña nueva -------------------------


def test_cambiar_a_pestana_nueva_espera_y_cambia() -> None:
    driver = _DriverFalso({"h1": ("Portal", "https://portal.interno")}, activo="h1")
    web = _web(driver)
    driver.abrir_pestana("h2", "Comprobante", "https://portal.interno/pdf")

    assert web.cambiar_a_pestana_nueva() == "Comprobante"
    assert driver.current_window_handle == "h2"


def test_cambiar_a_pestana_nueva_sin_pestana_nueva_avisa_y_no_mueve_el_foco() -> None:
    driver = _DriverFalso({"h1": ("Portal", "https://portal.interno")}, activo="h1")
    with pytest.raises(TimeoutError, match="No se abrió ninguna pestaña nueva"):
        _web(driver).cambiar_a_pestana_nueva(timeout=0.3)
    assert driver.current_window_handle == "h1"


def test_nueva_pestana_abre_cambia_y_navega() -> None:
    driver = _DriverFalso({"h1": ("Portal", "https://portal.interno")}, activo="h1")
    _web(driver).nueva_pestana("https://erp.interno")

    assert driver.current_window_handle != "h1"
    assert driver.current_url == "https://erp.interno"


# ----------------------------- cerrar pestaña -----------------------------


def test_cerrar_pestana_reposiciona_el_foco() -> None:
    """El fallo que esto evita: tras close() el driver se queda SIN ventana
    válida y el siguiente comando revienta, aunque el navegador siga
    abierto con otras pestañas a la vista."""
    driver = _DriverFalso(TRES_PESTANAS, activo="h2")
    _web(driver).cerrar_pestana()

    assert driver.window_handles == ["h1", "h3"]
    assert driver.current_window_handle == "h3"


def test_cerrar_la_ultima_pestana_deja_el_navegador_cerrado() -> None:
    """close() sobre la última ventana termina el navegador pero no el
    proceso del driver: sin quit() queda un chromedriver huérfano, y el
    cerrar() final del runner ya no lo recoge porque ve _driver en None."""
    driver = _DriverFalso({"h1": ("Portal", "https://portal.interno")}, activo="h1")
    web = _web(driver)

    web.cerrar_pestana()

    assert web._driver is None
    assert driver.cerrado is True, "faltó quit(): el proceso del driver quedaría vivo"


# --------------------- la grabadora sigue la pestaña nueva ---------------------


class _WebFalso:
    def __init__(self, driver) -> None:
        self._driver = driver

    @property
    def driver(self):
        return self._driver


def test_la_grabadora_detecta_y_sigue_una_pestana_nueva() -> None:
    driver = _DriverFalso({"h1": ("Portal", "https://portal.interno")}, activo="h1")
    grabadora = GrabadoraWeb(_WebFalso(driver), _LoggerFalso())

    conocidas = set(driver.window_handles)
    driver.abrir_pestana("h2", "Comprobante", "https://portal.interno/pdf")

    assert grabadora._seguir_pestana_nueva(driver, conocidas) == "h2"
    assert driver.current_window_handle == "h2"


def test_la_grabadora_no_cambia_de_pestana_si_no_hay_ninguna_nueva() -> None:
    driver = _DriverFalso(TRES_PESTANAS, activo="h2")
    grabadora = GrabadoraWeb(_WebFalso(driver), _LoggerFalso())

    assert grabadora._seguir_pestana_nueva(driver, set(driver.window_handles)) is None
    assert driver.current_window_handle == "h2"


def test_generar_codigo_emite_el_cambio_de_pestana_en_orden() -> None:
    pasos = [
        {"tipo": "ir_a", "url": "https://portal.interno"},
        {"tipo": "click", "selector": "#ver-comprobante", "texto": "Ver comprobante"},
        {"tipo": "cambiar_pestana", "titulo": "Comprobante", "url": "https://portal.interno/pdf"},
        {"tipo": "escribir", "selector": "#nota", "valor": "revisado"},
    ]
    codigo = generar_codigo("flujo_dos_pestanas", pasos)

    assert "self.web.cambiar_a_pestana_nueva()" in codigo
    # el cambio va DESPUÉS del click que abrió la pestaña y ANTES de lo
    # que se escribe ya dentro de ella
    assert codigo.index("#ver-comprobante") < codigo.index("cambiar_a_pestana_nueva")
    assert codigo.index("cambiar_a_pestana_nueva") < codigo.index("#nota")


def test_generar_codigo_neutraliza_un_titulo_de_pestana_con_salto_de_linea() -> None:
    """Misma defensa que ya tenían los clicks: el título viene de una página
    en la que no se puede confiar y termina dentro de un COMENTARIO de
    Python -- un salto de línea ahí convertiría el resto en código real."""
    pasos = [
        {"tipo": "ir_a", "url": "https://ejemplo.com"},
        {
            "tipo": "cambiar_pestana",
            "titulo": "inocente\nimport os",
            "url": "https://ejemplo.com/x",
        },
    ]
    codigo = generar_codigo("titulo_malicioso", pasos)

    for linea in codigo.splitlines():
        assert not linea.strip().startswith("import os")


def test_depurar_pasos_colapsa_cambios_de_pestana_repetidos() -> None:
    pasos = [
        {"tipo": "cambiar_pestana", "titulo": "PDF", "url": "https://x/pdf"},
        {"tipo": "cambiar_pestana", "titulo": "PDF", "url": "https://x/pdf"},
        {"tipo": "cambiar_pestana", "titulo": "Otra", "url": "https://x/otra"},
    ]
    limpios = _depurar_pasos(pasos)
    assert [p["url"] for p in limpios] == ["https://x/pdf", "https://x/otra"]
