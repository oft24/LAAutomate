"""Descubre automatizaciones en /automations via el decorador @registrar."""
from __future__ import annotations

import importlib
import pkgutil
import sys
from dataclasses import dataclass
from typing import Callable

from core.logger import get_logger
from engine.automation_base import BaseAutomation

logger = get_logger(__name__)

_REGISTRY: dict[str, "AutomationSpec"] = {}

# Automatizaciones que estan en disco pero no se pudieron importar, con la
# causa. Se guardan en vez de dejar que la excepcion suba, porque
# `descubrir()` corre en app/main.py ANTES de crear la QApplication: un
# solo automation.py con un error de sintaxis mataba el arranque entero y
# la app simplemente no abria -- sin ventana, sin mensaje, solo un
# traceback en una consola que el usuario del .exe ni siquiera ve. Y es un
# estado facil de alcanzar: el editor de la vista Automatizaciones guarda
# lo que sea que haya escrito, y ahora el Agente IA tambien escribe aqui.
_ERRORES: dict[str, str] = {}


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
    los decoradores @registrar se ejecuten y llenen el registry.

    Una automatizacion que no importa NO tumba al resto: se anota en
    `errores_de_descubrimiento()` y se sigue. La app arranca con las que
    si funcionan y ensena cual esta rota y por que, que es exactamente lo
    que hace falta para arreglarla (a mano o con el Agente IA).
    """
    _ERRORES.clear()

    def _anotar(nombre_modulo: str) -> None:
        """walk_packages llama aqui cuando falla al importar un PAQUETE
        (automations/x/__init__.py). Sin este callback, walk_packages
        relanza la excepcion y volvemos al arranque muerto."""
        exc = sys.exc_info()[1]
        _ERRORES[nombre_modulo] = f"{type(exc).__name__}: {exc}" if exc else "error de importación"

    modulo_paquete = importlib.import_module(paquete)
    for _, nombre_modulo, _es_paquete in pkgutil.walk_packages(
        modulo_paquete.__path__, prefix=f"{paquete}.", onerror=_anotar
    ):
        try:
            importlib.import_module(nombre_modulo)
        except Exception as exc:  # noqa: BLE001 - cualquier error de import es culpa de ESA automatizacion, no de la app
            _ERRORES[nombre_modulo] = f"{type(exc).__name__}: {exc}"
            logger.error("No se pudo cargar %s: %s", nombre_modulo, exc)

    return dict(_REGISTRY)


def errores_de_descubrimiento() -> dict[str, str]:
    """{nombre de la automatizacion: causa} de las que no se pudieron
    importar en el ultimo `descubrir()`. La clave es el nombre de la
    CARPETA (no el del modulo), que es como la ve el usuario en disco."""
    salida: dict[str, str] = {}
    for modulo, causa in _ERRORES.items():
        partes = modulo.split(".")
        salida[partes[1] if len(partes) > 1 else modulo] = causa
    return salida


def olvidar_error(nombre: str) -> None:
    """Marca una automatizacion como ya no rota.

    La llama `engine.almacen` cuando un automation.py vuelve a importarse
    bien tras corregirlo. Sin esto, una automatizacion arreglada seguiria
    marcada como "no compila" hasta reiniciar la app -- y el
    Agente IA le seguiria mandando al modelo un error de import que ya no
    existe."""
    for modulo in [m for m in _ERRORES if m.split(".")[1:2] == [nombre]]:
        _ERRORES.pop(modulo, None)


def obtener(nombre: str) -> AutomationSpec:
    return _REGISTRY[nombre]


def listar() -> list[AutomationSpec]:
    return list(_REGISTRY.values())


def eliminar(nombre: str) -> None:
    """Quita una automatizacion del registry en memoria -- no toca sus
    archivos en disco (eso lo hace quien llama, ej. AutomationsView, antes
    de llamar aqui). No falla si el nombre no estaba registrado."""
    _REGISTRY.pop(nombre, None)
