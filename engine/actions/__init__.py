"""Bundle de acciones inyectado en cada BaseAutomation (self.web, self.excel, ...)."""
from __future__ import annotations

from dataclasses import dataclass

from engine.actions.copilot_teams import CopilotTeamsActions
from engine.actions.desktop import DesktopActions
from engine.actions.email_actions import EmailActions
from engine.actions.excel import ExcelActions
from engine.actions.http_client import HttpActions
from engine.actions.web import WebActions


@dataclass
class ActionBundle:
    web: WebActions
    excel: ExcelActions
    http: HttpActions
    correo: EmailActions
    escritorio: DesktopActions
    copiloto: CopilotTeamsActions

    @classmethod
    def crear(cls, logger, bitacora=None) -> "ActionBundle":
        """Construye las acciones. Con `bitacora`, cada llamada queda anotada.

        Sin bitacora no se envuelve nada y el coste es exactamente el de
        antes: la instrumentacion no debe pagarse cuando no se usa. Con
        ella, `engine.bitacora.Espia` intercepta cualquier metodo publico
        -- incluidos los que se anadan en el futuro, sin tocar este
        archivo -- para poder contar despues que estaba haciendo la
        automatizacion cuando fallo.
        """
        acciones = {
            "web": WebActions(logger),
            "excel": ExcelActions(logger),
            "http": HttpActions(logger),
            "correo": EmailActions(logger),
            "escritorio": DesktopActions(logger),
            "copiloto": CopilotTeamsActions(logger),
        }
        if bitacora is not None:
            from engine.bitacora import Espia

            acciones = {n: Espia(o, n, bitacora) for n, o in acciones.items()}
        return cls(**acciones)
