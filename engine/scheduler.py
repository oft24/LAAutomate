"""Envuelve APScheduler. Disparadores admitidos: `cron:<expresion>`,
`carpeta:<ruta>` y `manual`. Cualquier otro se registra en el log como
desconocido en vez de aceptarse en silencio."""
from __future__ import annotations

import ast

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from core.logger import get_logger
from engine.registry import AutomationSpec, listar
from engine.runner import Runner

logger = get_logger(__name__)


class Scheduler:
    def __init__(self, runner: Runner) -> None:
        self.runner = runner
        self._sched = BackgroundScheduler()
        self._observadores = {}

    def iniciar(self) -> None:
        for spec in listar():
            try:
                self._registrar_disparador(spec)
            except (ValueError, OSError) as exc:
                logger.error("No se pudo programar %s: %s", spec.nombre, exc)
        self._sched.start()
        logger.info("Scheduler iniciado con %d automatizaciones", len(listar()))

    def detener(self) -> None:
        for nombre in list(self._observadores):
            self.desregistrar(nombre)
        if self._sched.running:
            self._sched.shutdown(wait=False)

    def ejecutar_ahora(self, spec: AutomationSpec) -> None:
        self.runner.ejecutar_async(spec)

    def desregistrar(self, nombre: str) -> None:
        """Quita el job de APScheduler para esta automatizacion (si tenia
        uno, ej. un disparador cron) -- para usar al eliminar una
        automatizacion, sin dejar un job huerfano que intente correr un
        modulo que ya no existe. No falla si no tenia job (ej. las
        automatizaciones "manual" nunca llegan a add_job)."""
        observador = self._observadores.pop(nombre, None)
        if observador is not None:
            observador.stop()
            observador.join(timeout=2)
        try:
            self._sched.remove_job(nombre)
        except Exception:
            pass

    def proximas_ejecuciones(self) -> list[tuple[str, object]]:
        """(nombre, next_run_time) de los jobs con cron, ordenados por
        fecha mas proxima primero. Metodo aditivo de solo lectura -- no
        cambia nada de como se registran o corren los disparadores."""
        jobs = [j for j in self._sched.get_jobs() if getattr(j, "next_run_time", None) is not None]
        jobs.sort(key=lambda j: j.next_run_time)
        return [(j.id, j.next_run_time) for j in jobs]

    @staticmethod
    def validar_disparador(disparador: str) -> None:
        if disparador.startswith("cron:"):
            CronTrigger.from_crontab(disparador.removeprefix("cron:"))
        elif disparador.startswith("carpeta:"):
            from pathlib import Path
            if not disparador[8:].strip() or not Path(disparador[8:]).is_dir():
                raise ValueError("La carpeta del disparador no existe.")
        elif disparador != "manual":
            raise ValueError("Usa manual, cron: o carpeta: como disparador.")

    @staticmethod
    def validar_disparador_codigo(codigo: str) -> None:
        for nodo in ast.walk(ast.parse(codigo)):
            if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", "") == "registrar":
                for kw in nodo.keywords:
                    if kw.arg == "disparador" and isinstance(kw.value, ast.Constant):
                        Scheduler.validar_disparador(str(kw.value.value))

    def actualizar(self, spec: AutomationSpec) -> None:
        """Actualiza el disparador sin conservar una clase vieja en el job."""
        self.validar_disparador(spec.disparador)
        self.desregistrar(spec.nombre)
        self._registrar_disparador(spec)

    def _registrar_disparador(self, spec: AutomationSpec) -> None:
        disparador = spec.disparador
        if disparador.startswith("cron:"):
            expresion = disparador.removeprefix("cron:")
            self._sched.add_job(
                self.runner.ejecutar_async,
                CronTrigger.from_crontab(expresion),
                args=[spec],
                id=spec.nombre,
                replace_existing=True,
            )
        elif disparador.startswith("carpeta:"):
            from engine.triggers.file_watcher import observar_carpeta

            self._observadores[spec.nombre] = observar_carpeta(
                disparador.removeprefix("carpeta:"), lambda: self.ejecutar_ahora(spec)
            )
        elif disparador == "manual":
            pass
        else:
            logger.warning("Disparador desconocido '%s' para %s", disparador, spec.nombre)
