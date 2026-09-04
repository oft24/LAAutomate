"""Valida que un fallo real en una automatizacion queda registrado como
fallo (el runner no se crashea) y que se genera un screenshot de
diagnostico -- solo se confirma que el archivo existe, nunca se abre."""
from __future__ import annotations

import core.database as database
from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import obtener, registrar
from engine.runner import Runner


@registrar(nombre="_prueba_fallo_interno", disparador="manual", categoria="_test")
class _AutomatizacionQueFalla(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        raise ValueError("fallo simulado para la prueba")


def test_fallo_se_registra_sin_crashear_el_runner(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "rpa_test.db")
    monkeypatch.chdir(tmp_path)  # el fallo tambien toma screenshot; que no caiga en el repo real

    spec = obtener("_prueba_fallo_interno")
    resultado = Runner().ejecutar(spec)

    assert resultado.success is False
    assert "fallo simulado" in resultado.message
    assert "Traceback" in resultado.data["traceback"]

    filas = database.historial(nombre="_prueba_fallo_interno", limite=1)
    assert len(filas) == 1
    assert filas[0]["exito"] == 0


def test_fallo_genera_screenshot_de_escritorio(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "rpa_test.db")
    monkeypatch.chdir(tmp_path)  # logs/screenshots se crea relativo al cwd, aislado en tmp_path

    spec = obtener("_prueba_fallo_interno")
    Runner().ejecutar(spec)

    captura = tmp_path / "logs" / "screenshots" / "_prueba_fallo_interno_error.png"
    assert captura.exists() and captura.stat().st_size > 0


def test_la_captura_del_navegador_no_la_pisa_la_del_escritorio(tmp_path, monkeypatch) -> None:
    """Las dos capturas de error escribian en <nombre>_error.png, asi que
    en una automatizacion web con navegador vivo la foto del escritorio
    borraba la del navegador -- la unica que encuadra la pagina donde
    fallo. Ahora conviven en archivos distintos."""
    from engine.actions.web import WebActions

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "rpa_test.db")
    monkeypatch.chdir(tmp_path)

    capturas = tmp_path / "logs" / "screenshots"
    capturas.mkdir(parents=True)

    def _screenshot_web_falso(self, nombre):
        ruta = capturas / f"{nombre}_error.png"
        ruta.write_bytes(b"captura-del-navegador")
        return ruta

    monkeypatch.setattr(WebActions, "screenshot_error", _screenshot_web_falso)

    Runner().ejecutar(obtener("_prueba_fallo_interno"))

    del_navegador = capturas / "_prueba_fallo_interno_error.png"
    del_escritorio = capturas / "_prueba_fallo_interno_error_escritorio.png"
    assert del_navegador.read_bytes() == b"captura-del-navegador"
    assert del_escritorio.exists() and del_escritorio.stat().st_size > 0
