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
    def crear(cls, logger) -> "ActionBundle":
        return cls(
            web=WebActions(logger),
            excel=ExcelActions(logger),
            http=HttpActions(logger),
            correo=EmailActions(logger),
            escritorio=DesktopActions(logger),
            copiloto=CopilotTeamsActions(logger),
        )
