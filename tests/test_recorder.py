"""Pruebas de la Grabadora de clicks: sobre todo, que generar_codigo()
nunca deje que contenido capturado de una pagina se convierta en codigo
Python ejecutable (encontrado por una revision adversarial de codigo)."""
from __future__ import annotations

import ast
import threading
import time

import py_compile
import tempfile
from pathlib import Path

import pytest

from engine.actions.recorder import GrabadoraWeb, _depurar_pasos, generar_codigo


def _compila_sin_error(codigo: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(codigo)
        ruta = tmp.name
    try:
        py_compile.compile(ruta, doraise=True)
    finally:
        Path(ruta).unlink(missing_ok=True)


def test_generar_codigo_escapa_comillas_y_backslashes_en_valores() -> None:
    pasos = [
        {"tipo": "ir_a", "url": "https://ejemplo.com"},
        {"tipo": "escribir", "selector": "#campo", "valor": 'valor con "comillas" y \\backslash\\'},
    ]
    codigo = generar_codigo("mi_prueba", pasos)
    _compila_sin_error(codigo)
    assert codigo.count("def ejecutar(self)") == 1


def test_generar_codigo_click_con_salto_de_linea_en_texto_no_inyecta_codigo() -> None:
    """Reproduce el hallazgo critico de la revision adversarial: una pagina
    puede controlar `innerText` (con <br>, elementos de bloque, o CSS
    white-space:pre) para meter un salto de linea real seguido de texto que
    parece codigo Python. Antes del fix, esto rompia el comentario y el
    texto se ejecutaba como una sentencia de modulo aparte."""
    payload_malicioso = "Enviar\nimport os\nos.mkdir('deberia_no_crearse_jamas')\ndef _cierre():"

    pasos = [
        {"tipo": "ir_a", "url": "https://ejemplo.com"},
        {"tipo": "click", "selector": "#boton", "texto": payload_malicioso},
    ]
    codigo = generar_codigo("mi_prueba", pasos)

    _compila_sin_error(codigo)

    arbol = ast.parse(codigo)
    definiciones_de_clase = [n for n in arbol.body if isinstance(n, ast.ClassDef)]
    assert len(definiciones_de_clase) == 1, "debe haber exactamente una clase, nada inyectado a nivel de modulo"

    metodo = next(n for n in definiciones_de_clase[0].body if isinstance(n, ast.FunctionDef))
    # el body de ejecutar() debe ser exactamente: ir_a(...), click(...), return -- nada mas
    # (ni un Import, If, Assign, o cualquier otra sentencia que el payload pudiera haber colado)
    tipos = [type(n) for n in metodo.body]
    assert tipos == [ast.Expr, ast.Expr, ast.Return], f"sentencias inesperadas en el body: {tipos}"

    # ninguna linea fuera de la del click puede contener el payload sin ser un comentario
    for linea in codigo.split("\n"):
        if "self.web.click" in linea:
            continue
        assert "import os" not in linea, f"el payload se escapo del comentario en: {linea!r}"

    # el payload completo debe sobrevivir, pero solo como cola de un comentario en la misma linea del click
    linea_click = next(l for l in codigo.split("\n") if "self.web.click" in l)
    assert "# " in linea_click
    cola_comentario = linea_click.split("# ", 1)[1]
    assert "import os" in cola_comentario and "os.mkdir" in cola_comentario


def test_generar_codigo_valida_nombre_antes_de_generar() -> None:
    with pytest.raises(ValueError):
        generar_codigo("../../escape", [])
    with pytest.raises(ValueError):
        generar_codigo("123_empieza_con_numero", [])


def test_depurar_pasos_conserva_borrado_intencional_de_campo() -> None:
    """Regresion: antes, un 'escribir' con valor vacio (el usuario borro el
    campo a proposito) se descartaba en silencio y el valor viejo, ya
    borrado por el usuario, terminaba reproduciendose igual."""
    pasos = [
        {"tipo": "escribir", "selector": "#codigo_descuento", "valor": "PROMO10"},
        {"tipo": "escribir", "selector": "#codigo_descuento", "valor": ""},
    ]
    limpios = _depurar_pasos(pasos)
    assert len(limpios) == 1
    assert limpios[0]["valor"] == ""


def test_depurar_pasos_dedup_por_selector_conserva_el_ultimo_valor() -> None:
    pasos = [
        {"tipo": "escribir", "selector": "#usuario", "valor": "tom"},
        {"tipo": "escribir", "selector": "#usuario", "valor": "tomsmith"},
    ]
    limpios = _depurar_pasos(pasos)
    assert len(limpios) == 1
    assert limpios[0]["valor"] == "tomsmith"


class _WebActionsFalso:
    """Sustituto minimo de WebActions para probar GrabadoraWeb.detener()
    sin necesitar un navegador real."""

    def __init__(self, bloquear_segundos: float = 0.0) -> None:
        self._bloquear_segundos = bloquear_segundos
        self.current_url = "https://ejemplo.com"
        self.cerrado = False

    @property
    def driver(self):
        return self

    def execute_script(self, _script):
        time.sleep(self._bloquear_segundos)
        return []

    def execute_cdp_cmd(self, *_args, **_kwargs):
        return None

    def cerrar(self) -> None:
        self.cerrado = True


class _LoggerFalso:
    def info(self, *a, **k):
        pass

    def debug(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass


def test_detener_marca_detencion_no_limpia_si_el_hilo_no_responde() -> None:
    """Regresion: si el hilo de sondeo queda bloqueado (ej. un dialogo nativo
    de la pagina), detener() no debe fingir que ya es seguro tocar el driver
    de nuevo -- debe reportarlo via detencion_limpia=False."""
    web = _WebActionsFalso(bloquear_segundos=1.0)
    grabadora = GrabadoraWeb(web, _LoggerFalso())

    # Simulamos el hilo de sondeo bloqueado dentro de execute_script,
    # como pasaria de verdad con un dialogo nativo abierto en la pagina.
    grabadora._grabando = True
    grabadora._hilo = threading.Thread(target=lambda: web.execute_script(""), daemon=True)
    grabadora._hilo.start()

    # timeout de espera bien corto (0.05s) contra un hilo que tarda 1s en
    # terminar -- reproduce "el hilo sigue vivo cuando se acaba la espera"
    # sin tener que esperar los 5s del timeout real de produccion.
    pasos = grabadora.detener(tiempo_espera_hilo=0.05)

    assert grabadora.detencion_limpia is False
    assert isinstance(pasos, list)
    grabadora._hilo.join(timeout=3)  # limpieza: dejar que el hilo de la prueba termine


def test_detener_hace_flush_final_cuando_el_hilo_si_termina() -> None:
    web = _WebActionsFalso(bloquear_segundos=0)
    grabadora = GrabadoraWeb(web, _LoggerFalso())
    grabadora.pasos = [{"tipo": "ir_a", "url": "https://ejemplo.com"}]
    grabadora._grabando = True
    grabadora._hilo = threading.Thread(target=lambda: None, daemon=True)
    grabadora._hilo.start()

    pasos = grabadora.detener()

    assert grabadora.detencion_limpia is True
    assert pasos == grabadora.pasos
