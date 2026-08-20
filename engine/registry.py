"""Descubre automatizaciones en /automations via el decorador @registrar."""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable

from engine.automation_base import BaseAutomation

_REGISTRY: dict[str, "AutomationSpec"] = {}


@dataclass
class AutomationSpec:
    nombre: str
    disparador: str
    categoria: str
    cls: type[BaseAutomation]


def registrar(nombre: str, disparador: str = "manual", categoria: str = "general") -> Callable:
    """Decorador que marca una clase BaseAutomation como automatizacion activa.

    Uso:
        @registrar(nombre="conciliacion_pagos", disparador="cron:0 30 14 * * *")
        class ConciliacionPagos(BaseAutomation):
            ...
    """

    def _wrap(cls: type[BaseAutomation]) -> type[BaseAutomation]:
        cls.nombre = nombre
        cls.disparador = disparador
        cls.categoria = categoria
        _REGISTRY[nombre] = AutomationSpec(nombre, disparador, categoria, cls)
        return cls

    return _wrap


def descubrir(paquete: str = "automations") -> dict[str, AutomationSpec]:
    """Importa recursivamente todos los modulos bajo /automations para que
    los decoradores @registrar se ejecuten y llenen el registry."""
    modulo_paquete = importlib.import_module(paquete)
    for _, nombre_modulo, es_paquete in pkgutil.walk_packages(
        modulo_paquete.__path__, prefix=f"{paquete}."
    ):
        importlib.import_module(nombre_modulo)
    return dict(_REGISTRY)


def obtener(nombre: str) -> AutomationSpec:
    return _REGISTRY[nombre]


def listar() -> list[AutomationSpec]:
    return list(_REGISTRY.values())


def eliminar(nombre: str) -> None:
    """Quita una automatizacion del registry en memoria -- no toca sus
    archivos en disco (eso lo hace quien llama, ej. AutomationsView, antes
    de llamar aqui). No falla si el nombre no estaba registrado."""
    _REGISTRY.pop(nombre, None)
