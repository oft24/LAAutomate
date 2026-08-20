"""Ejecuta una automatizacion en un hilo/proceso, captura logs y screenshots."""
from __future__ import annotations

import threading
import traceback
from datetime import datetime, timezone

from core.database import guardar_ejecucion
from core.logger import get_logger
from core.vault import Vault
from engine.actions import ActionBundle
from engine.automation_base import AutomationResult
from engine.registry import AutomationSpec

logger = get_logger(__name__)


class Runner:
    def __init__(self, vault: Vault | None = None) -> None:
        self.vault = vault or Vault()

    def ejecutar_async(self, spec: AutomationSpec) -> threading.Thread:
        hilo = threading.Thread(target=self.ejecutar, args=(spec,), daemon=True)
        hilo.start()
        return hilo

    def ejecutar(self, spec: AutomationSpec) -> AutomationResult:
        inicio = datetime.now(timezone.utc)
        run_logger = get_logger(spec.nombre)
        actions = ActionBundle.crear(run_logger)
        credenciales = self.vault.credenciales_para(spec.nombre)
        instancia = spec.cls(logger=run_logger, credenciales=credenciales, actions=actions)

        try:
            resultado = instancia.ejecutar() or AutomationResult(success=True)
            resultado.started_at, resultado.finished_at = inicio, datetime.now(timezone.utc)
            guardar_ejecucion(spec.nombre, resultado)
            return resultado
        except Exception as exc:  # noqa: BLE001 - una automatizacion puede fallar por cualquier razon
            run_logger.exception("Fallo en %s", spec.nombre)
            actions.web.screenshot_error(spec.nombre)
            try:
                actions.escritorio.capturar_pantalla(f"{spec.nombre}_error")
            except Exception:
                pass  # sin display disponible o pyautogui no pudo -- no tapar el error original
            instancia.al_fallar(exc)
            resultado = AutomationResult(
                success=False,
                message=f"{type(exc).__name__}: {exc}",
                data={"traceback": traceback.format_exc()},
                started_at=inicio,
                finished_at=datetime.now(timezone.utc),
            )
            guardar_ejecucion(spec.nombre, resultado)
            return resultado
        finally:
            actions.web.cerrar()
