"""Hilo Qt para ejecutar una automatizacion desde la GUI sin bloquear la
ventana, transmitiendo su log en vivo a la interfaz via senales."""
from __future__ import annotations

import ctypes
import logging
import threading

from PySide6.QtCore import QThread, Signal

from core.logger import get_logger
from engine.registry import AutomationSpec
from engine.runner import Runner


class EjecucionCancelada(Exception):
    """Se inyecta en el hilo de la automatizacion cuando el usuario
    presiona "Cancelar" -- una Exception normal (no BaseException) para
    que el manejo de errores existente en Runner.ejecutar la capture
    igual que cualquier otro fallo y guarde un AutomationResult(success=
    False) en el Historial, sin necesitar un camino especial."""

    def __init__(self, mensaje: str = "Cancelada por el usuario desde la interfaz.") -> None:
        super().__init__(mensaje)


class _HandlerSenal(logging.Handler):
    def __init__(self, senal: Signal) -> None:
        super().__init__()
        self._senal = senal
        self.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        self._senal.emit(self.format(record))


class AutomationWorker(QThread):
    """Corre `spec` en un hilo aparte. Emite cada linea de log conforme
    ocurre (log_line) y el AutomationResult final (finalizado)."""

    log_line = Signal(str)
    finalizado = Signal(object)

    def __init__(self, runner: Runner, spec: AutomationSpec) -> None:
        super().__init__()
        self.runner = runner
        self.spec = spec
        self._id_hilo: int | None = None

    def run(self) -> None:
        # threading.get_ident() (no self.ident de QThread) es el que
        # necesita PyThreadState_SetAsyncExc para inyectar la excepcion de
        # cancelacion -- solo es valido leerlo desde DENTRO del hilo.
        self._id_hilo = threading.get_ident()

        logger = get_logger(self.spec.nombre)
        handler = _HandlerSenal(self.log_line)
        logger.addHandler(handler)
        try:
            resultado = self.runner.ejecutar(self.spec)
        finally:
            logger.removeHandler(handler)
        self.finalizado.emit(resultado)

    def cancelar(self) -> None:
        """Mejor esfuerzo, no instantaneo: Python solo revisa excepciones
        asincronas pendientes en el siguiente bytecode que corre en el
        interprete, asi que si el hilo esta bloqueado dentro de una
        llamada C larga (ej. un pywinauto wait_until con sondeo interno)
        la cancelacion toma efecto en su siguiente vuelta, no de
        inmediato. Es el mismo mecanismo que usan herramientas como
        `stopit` para cancelar hilos en Python -- no hay una forma
        totalmente limpia de "matar" un hilo nativo, y correr cada
        automatizacion en un proceso aparte (la alternativa robusta) es
        un cambio de arquitectura mucho mayor que agregar un boton
        Cancelar."""
        if self._id_hilo is None:
            return
        # se pasa la CLASE, no una instancia: ctypes marshalla un objeto
        # normal via py_object de forma que _PyErr_SetObject ya no lo
        # reconoce como excepcion valida ("is not a BaseException
        # subclass") -- pasando la clase, Python la instancia el mismo al
        # lanzarla (como "raise EjecucionCancelada" sin argumentos), por
        # eso el mensaje por defecto vive en __init__, no aqui.
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(self._id_hilo), ctypes.py_object(EjecucionCancelada)
        )
