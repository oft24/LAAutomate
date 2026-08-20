"""Envuelve APScheduler para disparadores tipo cron/intervalo, mas
disparadores propios (carpeta, correo, webhook) via engine.triggers.*"""
from __future__ import annotations

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

    def iniciar(self) -> None:
        for spec in listar():
            self._registrar_disparador(spec)
        self._sched.start()
        logger.info("Scheduler iniciado con %d automatizaciones", len(listar()))

    def detener(self) -> None:
        self._sched.shutdown(wait=False)

    def ejecutar_ahora(self, spec: AutomationSpec) -> None:
        self.runner.ejecutar_async(spec)

    def desregistrar(self, nombre: str) -> None:
        """Quita el job de APScheduler para esta automatizacion (si tenia
        uno, ej. un disparador cron) -- para usar al eliminar una
        automatizacion, sin dejar un job huerfano que intente correr un
        modulo que ya no existe. No falla si no tenia job (ej. las
        automatizaciones "manual" nunca llegan a add_job)."""
        try:
            self._sched.remove_job(nombre)
        except Exception:
            pass

    def proximas_ejecuciones(self) -> list[tuple[str, object]]:
        """(nombre, next_run_time) de los jobs con cron, ordenados por
        fecha mas proxima primero. Metodo aditivo de solo lectura -- no
        cambia nada de como se registran o corren los disparadores."""
        jobs = [j for j in self._sched.get_jobs() if j.next_run_time is not None]
        jobs.sort(key=lambda j: j.next_run_time)
        return [(j.id, j.next_run_time) for j in jobs]

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

            observar_carpeta(disparador.removeprefix("carpeta:"), lambda: self.ejecutar_ahora(spec))
        elif disparador == "manual" or disparador.startswith("webhook") or disparador.startswith("correo"):
            # webhook y correo se registran por separado (engine/triggers/*) en app/main.py
            pass
        else:
            logger.warning("Disparador desconocido '%s' para %s", disparador, spec.nombre)
