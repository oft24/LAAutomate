from unittest.mock import MagicMock

from engine.registry import AutomationSpec
from engine.scheduler import Scheduler


def test_desregistrar_quita_el_job_si_existia() -> None:
    scheduler = Scheduler(MagicMock())
    spec = AutomationSpec(nombre="prueba_cron", disparador="cron:0 8 * * *", categoria="general", cls=object)
    scheduler._registrar_disparador(spec)

    assert scheduler._sched.get_job("prueba_cron") is not None

    scheduler.desregistrar("prueba_cron")

    assert scheduler._sched.get_job("prueba_cron") is None


def test_desregistrar_nombre_sin_job_no_falla() -> None:
    scheduler = Scheduler(MagicMock())
    scheduler.desregistrar("esto_nunca_tuvo_job")  # no debe lanzar excepcion
