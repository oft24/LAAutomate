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
    ocurre (log_line) y el AutomationResult final (finalizado).

    Por defecto una ejecucion termina donde falla: pulsar "Ejecutar" corre
    y ya. `autocorregir=True` activa el ciclo de `engine.autocorreccion`
    -- diagnostica con la captura del momento y la bitacora, aplica el
    arreglo, reanuda, anota la practica y versiona el prompt -- y emite la
    `Reparacion` por la senal `reparado`.

    Lo arranca el boton "Corregir código" de Automatizaciones, no un fallo.
    Que se metiera solo en cada fallo dejaba "Ejecutar" bloqueado varios
    minutos hablando con el modelo sin que nadie lo hubiera pedido.
    """

    log_line = Signal(str)
    finalizado = Signal(object)
    reparado = Signal(object)

    def __init__(
        self,
        runner: Runner,
        spec: AutomationSpec,
        autocorregir: bool = False,
        max_intentos: int | None = None,   # None = el maximo del modulo
    ) -> None:
        super().__init__()
        self.runner = runner
        self.spec = spec
        self.autocorregir = autocorregir
        self.max_intentos = max_intentos
        self._id_hilo: int | None = None
        self._cancelado = threading.Event()

    def run(self) -> None:
        # threading.get_ident() (no self.ident de QThread) es el que
        # necesita PyThreadState_SetAsyncExc para inyectar la excepcion de
        # cancelacion -- solo es valido leerlo desde DENTRO del hilo.
        self._id_hilo = threading.get_ident()

        logger = get_logger(self.spec.nombre)
        handler = _HandlerSenal(self.log_line)
        logger.addHandler(handler)
        try:
            resultado = self._correr()
        finally:
            logger.removeHandler(handler)
        self.finalizado.emit(resultado)

    def _correr(self):
        if not self.autocorregir:
            return self.runner.ejecutar(self.spec)

        # Import tardio: engine.autocorreccion arrastra el cliente de
        # Gemini, y una ejecucion sin autocorreccion no tiene por que
        # pagar ese import.
        from engine.autocorreccion import MAX_INTENTOS, Autocorrector

        corrector = Autocorrector(
            self.runner,
            max_intentos=self.max_intentos or MAX_INTENTOS,
            on_progreso=self.log_line.emit,
            cancelado=self._cancelado.is_set,
            mejorar_prompt=False,
        )
        reparacion = corrector.ejecutar(self.spec)
        self.reparado.emit(reparacion)
        return reparacion.resultado

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
        # Primero la bandera: el ciclo de reparacion la mira en cada
        # frontera y para aunque la excepcion asincrona todavia no pueda
        # entrar (el hilo puede estar dentro de la peticion al modelo).
        self._cancelado.set()
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
