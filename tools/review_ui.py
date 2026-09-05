"""Render reproducible de las ocho vistas con datos sintéticos, sin red ni ejecución.

Uso: .venv/Scripts/python tools/review_ui.py
Salidas: build/revision-ux/*.png. No abre ni graba el escritorio.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from contextlib import ExitStack

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


def main():
    app = QApplication.instance() or QApplication([])
    for fuente in ("segoeui.ttf", "segoeuib.ttf", "consola.ttf", "consolab.ttf", "seguisym.ttf"):
        QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{fuente}")
    app.setFont(QFont("Segoe UI", 10))
    from app.windows.main_window import MainWindow
    from app.widgets.sidebar import CLAVES
    from core import database
    from engine.scheduler import Scheduler
    from engine.automation_base import AutomationResult

    salida = ROOT / "build/revision-ux"
    salida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="laautomate-ui-") as temporal, ExitStack() as pila:
        raiz = Path(temporal)
        logs = raiz / "logs"
        logs.mkdir()
        (logs / "reporte_diario.log").write_text("INFO | Inicio de prueba visual\nERROR | Elemento no encontrado: selector de demostración\nINFO | Revisa el código antes de reintentar\n", encoding="utf-8")
        pila.enter_context(patch("app.windows.logs_view.LOGS_DIR", logs))
        specs = [SimpleNamespace(nombre=n, categoria="pruebas", disparador="manual") for n in ("reporte_diario", "validar_archivos")]
        for spec in specs:
            carpeta = raiz / "automations" / spec.nombre
            carpeta.mkdir(parents=True)
            (carpeta / "automation.py").write_text(f'from engine.registry import registrar\nfrom engine.automation_base import BaseAutomation, AutomationResult\n\n@registrar(nombre="{spec.nombre}", disparador="manual")\nclass Flujo(BaseAutomation):\n    def ejecutar(self):\n        # Datos sintéticos de revisión visual; no se ejecuta.\n        return AutomationResult(success=True)\n', encoding="utf-8")
        pila.enter_context(patch.object(database, "DB_PATH", raiz / "historial.db"))
        for modulo in ("automations_view", "assistant_view", "scheduler_view", "vault_view", "dashboard_view"):
            pila.enter_context(patch(f"app.windows.{modulo}.listar", return_value=specs))
        pila.enter_context(patch("app.windows.automations_view.BASE_DIR", raiz))
        pila.enter_context(patch("app.windows.assistant_view.listar_en_disco", return_value=[]))
        pila.enter_context(patch("app.windows.assistant_view.tiene_api_key", return_value=False))
        pila.enter_context(patch("app.windows.assistant_view.modelo_por_defecto", return_value="gemini-prueba"))
        pila.enter_context(patch("app.windows.assistant_view.AssistantView._cargar_modelos_disponibles", return_value=None))
        pila.enter_context(patch("core.vault.Vault.credenciales_para", return_value=SimpleNamespace(usuario=None, password=None, token=None)))
        ahora = datetime.now(timezone.utc)
        for i in range(6):
            database.guardar_ejecucion(specs[i % 2].nombre, AutomationResult(success=i % 3 == 0, message="Validación completada" if i % 3 == 0 else "Elemento no encontrado: revisa el selector", started_at=ahora-timedelta(minutes=i*15, seconds=12), finished_at=ahora-timedelta(minutes=i*15)))
        runner = MagicMock()
        ventana = MainWindow(Scheduler(runner), runner)
        fallos = []
        for ancho, alto in ((1360, 860), (1100, 700)):
            ventana.resize(ancho, alto)
            ventana.show()
            app.processEvents()
            for indice, clave in enumerate(CLAVES):
                ventana.sidebar.establecer_vista(clave)
                if app.focusWidget() is not None:
                    app.focusWidget().clearFocus()
                from PySide6.QtTest import QTest
                QTest.qWait(180)
                if ventana._animacion_pagina is not None:
                    ventana._animacion_pagina.stop()
                if ventana._pagina_animada is not None:
                    ventana._pagina_animada.setGraphicsEffect(None)
                app.processEvents()
                destino = salida / f"{ancho}-{clave}.png"
                if not ventana.grab().save(str(destino)):
                    raise RuntimeError(f"No se pudo guardar {destino}")
                if ventana.width() != ancho or ventana.height() != alto:
                    fallos.append(f"{clave}: solicitado {ancho}x{alto}, real {ventana.width()}x{ventana.height()}")
        ventana.resize(1360, 860)
        ventana.sidebar.establecer_vista("grabadora")
        QTest.qWait(180)
        if ventana._animacion_pagina is not None:
            ventana._animacion_pagina.stop()
        if ventana._pagina_animada is not None:
            ventana._pagina_animada.setGraphicsEffect(None)
        ventana.sidebar._alternar_colapso()
        QTest.qWait(300)
        app.processEvents()
        ventana.grab().save(str(salida / "1360-grabadora-menu-compacto.png"))
        ventana.sidebar._alternar_colapso()
        QTest.qWait(300)
        ventana.sidebar.establecer_vista("asistente")
        ventana.assistant_view._agregar_burbuja(
            "model", "## Revisión del flujo\n\n**Borrador listo para revisar.**\n\n"
            "1. Abrir la aplicación.\n2. Comprobar el destino.\n3. Validar el resultado.\n\n"
            "```python\nresultado = AutomationResult(success=True)\n```\n\n"
            "Este ejemplo es sintético; no se ha ejecutado ninguna automatización."
        )
        QTest.qWait(300)
        app.processEvents()
        ventana.grab().save(str(salida / "1360-asistente-respuesta.png"))
        print("RENDERED", 18, "synthetic views", flush=True)
        print("LAYOUT", "OK" if not fallos else "; ".join(fallos), flush=True)
        print("OUTPUT", salida, flush=True)
        ventana.close()
    return bool(fallos)


if __name__ == "__main__":
    raise SystemExit(main())
