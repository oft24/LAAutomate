"""Ejecuta una automatizacion en un hilo/proceso, captura logs y screenshots."""
from __future__ import annotations

import threading
import traceback
from contextlib import nullcontext
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

    def ejecutar(
        self,
        spec: AutomationSpec,
        bitacora=None,
        etiqueta_captura: str = "",
    ) -> AutomationResult:
        """Corre la automatizacion y devuelve su resultado.

        `bitacora` (engine.bitacora.Bitacora) anota cada accion para poder
        contar despues que estaba haciendo cuando fallo. `etiqueta_captura`
        se anade al nombre de las capturas de error: sin ella cada intento
        de reparacion pisaria la captura del anterior, y comparar el antes
        y el despues es justo lo que hace falta para saber si el arreglo
        avanzo.
        """
        inicio = datetime.now(timezone.utc)
        run_logger = get_logger(spec.nombre)
        actions = ActionBundle.crear(run_logger, bitacora=bitacora)
        credenciales = self.vault.credenciales_para(spec.nombre)
        instancia = spec.cls(logger=run_logger, credenciales=credenciales, actions=actions)

        try:
            resultado = instancia.ejecutar() or AutomationResult(success=True)
            resultado.started_at, resultado.finished_at = inicio, datetime.now(timezone.utc)
            guardar_ejecucion(spec.nombre, resultado)
            return resultado
        except Exception as exc:  # noqa: BLE001 - una automatizacion puede fallar por cualquier razon
            run_logger.exception("Fallo en %s", spec.nombre)
            base = f"{spec.nombre}{etiqueta_captura}"
            # Con la bitacora en pausa: estas capturas son limpieza del
            # motor, no acciones de la automatizacion, y anotarlas las
            # dejaria como las ultimas -- tapando lo que de verdad fallo.
            contexto = bitacora.en_pausa() if bitacora is not None else nullcontext()
            with contexto:
                ruta_web = actions.web.screenshot_error(base)
                ruta_escritorio = None
                try:
                    # Las dos capturas escribian en logs/screenshots/<nombre>_error.png,
                    # asi que en una automatizacion web con navegador vivo la foto del
                    # escritorio pisaba la del navegador -- justo la util, la que
                    # encuadra la pagina donde fallo. Si la del navegador existe, la
                    # del escritorio va a un archivo aparte y quedan las dos.
                    sufijo = "_error_escritorio" if ruta_web else "_error"
                    ruta_escritorio = actions.escritorio.capturar_pantalla(f"{base}{sufijo}")
                except Exception:
                    pass  # sin display disponible o pyautogui no pudo -- no tapar el error original
            instancia.al_fallar(exc)
            datos = {"traceback": traceback.format_exc()}
            if ruta_web:
                datos["captura_web"] = str(ruta_web)
            if ruta_escritorio:
                datos["captura_escritorio"] = str(ruta_escritorio)
            if bitacora is not None:
                datos["acciones"] = bitacora.como_texto()
            resultado = AutomationResult(
                success=False,
                message=f"{type(exc).__name__}: {exc}",
                data=datos,
                started_at=inicio,
                finished_at=datetime.now(timezone.utc),
            )
            guardar_ejecucion(spec.nombre, resultado)
            return resultado
        finally:
            actions.web.cerrar()
