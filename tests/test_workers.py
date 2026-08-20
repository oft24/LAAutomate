"""Pruebas del mecanismo de cancelacion de AutomationWorker. Se prueba la
inyeccion de excepcion (ctypes.PyThreadState_SetAsyncExc) contra un hilo
real de threading -- exactamente el mecanismo que AutomationWorker.run()
usa internamente (threading.get_ident()), sin necesitar arrancar QThread
ni QApplication (el resto de la app tampoco prueba GUI/Qt directamente;
eso se valida con smoke scripts manuales, no con pytest)."""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from app.workers import AutomationWorker, EjecucionCancelada


def test_cancelar_sin_hilo_iniciado_no_falla() -> None:
    worker = AutomationWorker(runner=MagicMock(), spec=MagicMock())
    worker.cancelar()  # _id_hilo sigue en None -- no debe lanzar


def test_cancelar_inyecta_ejecucioncancelada_en_el_hilo_real() -> None:
    worker = AutomationWorker(runner=MagicMock(), spec=MagicMock())
    excepcion_capturada = []

    def _tarea_larga() -> None:
        worker._id_hilo = threading.get_ident()
        try:
            for _ in range(100):  # margen amplio -- se cancela mucho antes
                time.sleep(0.1)
        except EjecucionCancelada as exc:
            excepcion_capturada.append(exc)

    hilo = threading.Thread(target=_tarea_larga)
    hilo.start()
    time.sleep(0.3)  # deja que _id_hilo se asigne y el loop empiece
    worker.cancelar()
    hilo.join(timeout=5)

    assert not hilo.is_alive()
    assert len(excepcion_capturada) == 1
    assert "Cancelada por el usuario" in str(excepcion_capturada[0])
