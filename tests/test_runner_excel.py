"""Valida el pipeline completo (registry -> runner -> accion excel -> base
de datos) con una automatizacion de prueba definida aqui mismo (no depende
de ninguna carpeta en /automations), usando rutas temporales para no dejar
basura en el repo ni en la base de datos real."""
from __future__ import annotations

import core.database as database
from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import obtener, registrar
from engine.runner import Runner

PEDIDOS_DE_PRUEBA = [
    {"id": 1, "cliente": "Tienda Centro", "total": 1500.0},
    {"id": 2, "cliente": "Tienda Norte", "total": 890.5},
    {"id": 3, "cliente": "Tienda Sur", "total": 2310.0},
]


@registrar(nombre="_prueba_pipeline_excel", disparador="manual", categoria="_test")
class _AutomatizacionExcelDePrueba(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        self.excel.escribir("pedidos_entrada.xlsx", PEDIDOS_DE_PRUEBA)
        pedidos = self.excel.leer("pedidos_entrada.xlsx")
        for pedido in pedidos:
            pedido["total_con_iva"] = round(pedido["total"] * 1.16, 2)
        self.excel.escribir("pedidos_salida.xlsx", pedidos)
        return AutomationResult(success=True, data={"pedidos_procesados": len(pedidos)})


def test_ejecucion_excel_de_extremo_a_extremo(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "rpa_test.db")
    monkeypatch.chdir(tmp_path)  # los .xlsx de la automatizacion se crean relativos al cwd

    spec = obtener("_prueba_pipeline_excel")
    resultado = Runner().ejecutar(spec)

    assert resultado.success, resultado.message
    assert resultado.data["pedidos_procesados"] == 3
    assert (tmp_path / "pedidos_salida.xlsx").exists()

    filas = database.historial(nombre="_prueba_pipeline_excel", limite=1)
    assert len(filas) == 1
    assert filas[0]["exito"] == 1
