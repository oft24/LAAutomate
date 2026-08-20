"""Valida el pipeline con Selenium de verdad, contra un sandbox publico hecho
para practicar automatizacion web, usando una automatizacion de prueba
definida aqui mismo (no depende de ninguna carpeta en /automations).
Requiere internet y un navegador (Chrome o Edge) instalado -- por eso lleva
el marcador "network" y se puede excluir con `pytest -m "not network"` en
un entorno sin navegador/red.
"""
from __future__ import annotations

import pytest

from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import obtener, registrar
from engine.runner import Runner


@registrar(nombre="_prueba_pipeline_web", disparador="manual", categoria="_test")
class _AutomatizacionWebDePrueba(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        usuario = self.credenciales.usuario or "tomsmith"
        password = self.credenciales.password or "SuperSecretPassword!"

        self.web.ir_a("https://the-internet.herokuapp.com/login")
        self.web.escribir("#username", usuario)
        self.web.escribir("#password", password)
        self.web.click("button.radius")

        mensaje = self.web.leer_texto("#flash")
        if "You logged into a secure area" not in mensaje:
            raise RuntimeError(f"Login no confirmado, mensaje recibido: {mensaje!r}")

        return AutomationResult(success=True, data={"mensaje": mensaje.strip()})


@pytest.mark.network
def test_pipeline_web_contra_sandbox_real(tmp_path, monkeypatch) -> None:
    import core.database as database

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "rpa_test.db")

    spec = obtener("_prueba_pipeline_web")
    resultado = Runner().ejecutar(spec)

    assert resultado.success, resultado.message
    assert "secure area" in resultado.data["mensaje"]
