"""Clase base que toda automatizacion debe heredar."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AutomationResult:
    success: bool
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class BaseAutomation(ABC):
    """Toda automatizacion (modulo en /automations) implementa `ejecutar`.

    El registry la descubre via el decorador `@registrar` y el runner
    le inyecta logger, credenciales y helpers de accion (web, excel, etc).
    """

    nombre: str = ""
    disparador: str = ""
    categoria: str = "general"

    def __init__(self, logger, credenciales, actions) -> None:
        self.logger = logger
        self.credenciales = credenciales
        self.web = actions.web
        self.excel = actions.excel
        self.http = actions.http
        self.correo = actions.correo
        self.escritorio = actions.escritorio
        self.copiloto = actions.copiloto

    @abstractmethod
    def ejecutar(self) -> AutomationResult | None:
        """Logica de negocio de la automatizacion. Lanzar excepcion = fallo."""
        raise NotImplementedError

    def al_fallar(self, exc: Exception) -> None:
        """Hook opcional: se llama antes de que el runner tome screenshot y relance."""
        return None
