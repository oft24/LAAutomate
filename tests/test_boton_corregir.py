"""El fallo no secuestra la ejecución, y corregir es una decisión explícita.

Antes, al fallar una automatización, el worker entraba solo en el ciclo de
reparación: hasta cinco vueltas hablando con el modelo, con sus esperas y
sus cambios de modelo. Mientras tanto «Ejecutar» seguía deshabilitado y no
se podía ni reintentar ni leer el error con calma.

Estas pruebas fijan el comportamiento nuevo: la ejecución termina donde
falla, el error se marca, y «Corregir código» lleva el rastro al chat.
"""
from __future__ import annotations

import os

import pytest

# Qt sin ventana: esto corre en una terminal. Antes de importar PySide6.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from engine.automation_base import AutomationResult  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def vista(app, monkeypatch):
    from unittest.mock import MagicMock

    from app.windows.automations_view import AutomationsView

    return AutomationsView(scheduler=MagicMock())


# ------------------------------------------------- el botón y su estado


def test_el_boton_corregir_empieza_apagado(vista) -> None:
    assert vista.boton_corregir.text() == "Corregir código"
    assert not vista.boton_corregir.isEnabled()


def test_un_fallo_devuelve_el_play_y_enciende_corregir(vista) -> None:
    """Lo que se rompía: el play quedaba bloqueado mientras el ciclo
    automático hablaba con el modelo."""
    vista.boton_ejecutar.setEnabled(False)
    vista.boton_cancelar.setEnabled(True)

    vista._al_finalizar("buscar_videos_youtube", AutomationResult(success=False, message="FileNotFoundError"))

    assert vista.boton_ejecutar.isEnabled(), "el play sigue bloqueado tras fallar"
    assert not vista.boton_cancelar.isEnabled()
    assert vista.boton_corregir.isEnabled()
    assert vista._automatizacion_fallida == "buscar_videos_youtube"


def test_el_fallo_se_marca_en_el_estado(vista) -> None:
    vista._al_finalizar("x", AutomationResult(success=False, message="algo se rompió"))

    assert "falló" in vista.estado.text()
    assert "algo se rompió" in vista.estado.text()


def test_un_exito_apaga_corregir(vista) -> None:
    vista._al_finalizar("x", AutomationResult(success=False, message="fallo"))
    assert vista.boton_corregir.isEnabled()

    vista._al_finalizar("x", AutomationResult(success=True, message="ok"))

    assert not vista.boton_corregir.isEnabled()
    assert vista._automatizacion_fallida == ""


def test_corregir_sin_fallo_previo_no_hace_nada(vista) -> None:
    """Pulsarlo por teclado o por script no debe reventar."""
    vista._automatizacion_fallida = ""
    vista._corregir_el_ultimo_fallo()  # no lanza


# ------------------------------------------ la ejecución no repara sola


def test_la_ejecucion_manual_no_arrastra_el_ciclo_de_reparacion() -> None:
    """Pulsar «Ejecutar» corre y ya. Reparar lo arranca el otro botón."""
    from unittest.mock import MagicMock

    from app.workers import AutomationWorker

    worker = AutomationWorker(runner=MagicMock(), spec=MagicMock())

    assert worker.autocorregir is False


def test_el_worker_de_reparacion_usa_el_ciclo_de_siempre() -> None:
    from unittest.mock import MagicMock

    from app.workers import AutomationWorker

    worker = AutomationWorker(
        runner=MagicMock(), spec=MagicMock(), autocorregir=True, max_intentos=3
    )

    assert worker.autocorregir is True
    assert worker.max_intentos == 3


def test_importar_el_worker_no_arrastra_el_cliente_de_gemini() -> None:
    """El import de `engine.autocorreccion` es tardío a propósito: una
    ejecución normal no tiene por qué pagar el cliente de Gemini."""
    import subprocess
    import sys

    salida = subprocess.run(
        [sys.executable, "-c",
         "import sys, app.workers; "
         "print('engine.autocorreccion' in sys.modules)"],
        capture_output=True, text=True,
    )
    assert salida.stdout.strip() == "False", salida.stdout + salida.stderr


def test_son_tres_intentos() -> None:
    """Lo pidió el usuario: tres, no cinco. Cambiarlo es una línea."""
    from engine.autocorreccion import MAX_INTENTOS

    assert MAX_INTENTOS == 3


def test_el_autocorrector_no_acepta_mas_del_maximo() -> None:
    from unittest.mock import MagicMock

    from engine.autocorreccion import MAX_INTENTOS, Autocorrector

    assert Autocorrector(MagicMock(), max_intentos=99).max_intentos == MAX_INTENTOS
    assert Autocorrector(MagicMock(), max_intentos=0).max_intentos == 1


def test_al_correr_sin_autocorreccion_se_llama_al_runner_a_secas() -> None:
    from unittest.mock import MagicMock

    from app.workers import AutomationWorker

    runner = MagicMock()
    esperado = AutomationResult(success=True)
    runner.ejecutar.return_value = esperado
    spec = MagicMock()

    worker = AutomationWorker(runner=runner, spec=spec)
    assert worker._correr() is esperado
    runner.ejecutar.assert_called_once_with(spec)


# ------------------------------------------------ lo que viaja al chat


def test_el_asistente_expone_preparar_correccion() -> None:
    """Es lo que llama el botón; si deja de ser pública, el botón no hace
    nada y nadie se entera hasta pulsarlo."""
    from app.windows.assistant_view import AssistantView

    assert callable(getattr(AssistantView, "preparar_correccion", None))


def test_sin_rastro_del_fallo_lo_dice_en_vez_de_mandar_un_prompt_vacio(tmp_path) -> None:
    from engine.diagnostico import contexto_de_fallo

    log, captura = contexto_de_fallo("no_existe", tmp_path)

    assert log == ""
    assert captura is None


def test_el_prompt_lleva_el_log_del_fallo() -> None:
    from engine.diagnostico import prompt_de_correccion

    prompt = prompt_de_correccion("mi_auto", "FileNotFoundError: no encuentro datos/x.xlsx")

    assert "mi_auto" in prompt
    assert "FileNotFoundError" in prompt
    assert "CAUSA REAL" in prompt


def test_el_mensaje_de_un_exito_se_muestra(vista) -> None:
    """Una automatización que acaba bien puede tener algo que decir."""
    vista._al_finalizar(
        "buscar_videos_youtube",
        AutomationResult(success=True, message="Creé la plantilla en datos/videos_buscar.xlsx"),
    )

    assert "exitoso" in vista.estado.text()
    assert "Creé la plantilla" in vista.estado.text()


def test_un_exito_sin_mensaje_no_deja_un_guion_suelto(vista) -> None:
    vista._al_finalizar("x", AutomationResult(success=True))

    assert vista.estado.text() == "x: exitoso"


def test_sin_api_key_el_boton_cae_al_camino_manual(vista, monkeypatch) -> None:
    """No hay ciclo posible sin clave: en vez de no hacer nada, deja el
    fallo cargado en el chat para corregirlo a mano."""
    llamadas = []
    monkeypatch.setattr(
        "app.windows.automations_view.tiene_api_key", lambda: False
    )
    monkeypatch.setattr(
        type(vista), "_corregir_a_mano",
        lambda self, nombre, motivo: llamadas.append((nombre, motivo)),
    )

    vista._automatizacion_fallida = "mi_auto"
    vista._corregir_el_ultimo_fallo()

    assert llamadas == [("mi_auto", "no hay API key de Gemini configurada")]


def test_no_se_arranca_una_reparacion_con_otra_corriendo(vista, monkeypatch) -> None:
    """Doble click no debe lanzar dos ciclos sobre el mismo archivo."""
    from unittest.mock import MagicMock

    monkeypatch.setattr("app.windows.automations_view.tiene_api_key", lambda: True)
    vista._automatizacion_fallida = "mi_auto"
    vista._worker = MagicMock()   # ya hay uno corriendo

    vista._corregir_el_ultimo_fallo()   # no lanza ni reemplaza nada

    assert isinstance(vista._worker, MagicMock)


def test_el_boton_arranca_el_ciclo_con_tres_intentos(vista, monkeypatch) -> None:
    """El crux: pulsarlo crea el worker de reparación, no uno normal.

    Es lo único que no se puede comprobar mirando el código de al lado:
    que el botón y el ciclo estén de verdad conectados.
    """
    from unittest.mock import MagicMock

    from engine.autocorreccion import MAX_INTENTOS

    creados = []

    class _WorkerFalso:
        def __init__(self, runner, spec, autocorregir=False, max_intentos=None):
            creados.append({"autocorregir": autocorregir, "max_intentos": max_intentos})
            self.log_line = MagicMock()
            self.reparado = MagicMock()
            self.finalizado = MagicMock()

        def start(self):
            pass

    monkeypatch.setattr("app.windows.automations_view.tiene_api_key", lambda: True)
    monkeypatch.setattr("app.windows.automations_view.AutomationWorker", _WorkerFalso)
    monkeypatch.setattr("app.windows.automations_view.obtener", lambda n: MagicMock(nombre=n))

    vista._automatizacion_fallida = "mi_auto"
    vista._corregir_el_ultimo_fallo()

    assert creados == [{"autocorregir": True, "max_intentos": MAX_INTENTOS}]
    assert MAX_INTENTOS == 3
    assert not vista.boton_ejecutar.isEnabled(), "durante la reparación no se reejecuta"
    assert vista.boton_cancelar.isEnabled(), "una reparación se tiene que poder parar"
    assert not vista.boton_corregir.isEnabled(), "ni lanzar dos a la vez"
    assert "Reparando" in vista.estado.text()


def test_una_reparacion_aplicada_recarga_el_editor(vista, monkeypatch) -> None:
    """Si el ciclo cambió el archivo, el editor tiene que releerlo: si no,
    el siguiente «Guardar» pisa el arreglo con la versión vieja."""
    from unittest.mock import MagicMock

    recargas = []
    monkeypatch.setattr(type(vista), "_cargar_codigo", lambda self, i: recargas.append(i))

    reparacion = MagicMock()
    reparacion.intentos = [MagicMock(aplicado=False), MagicMock(aplicado=True)]
    vista._al_reparar(reparacion)

    assert recargas, "el editor se quedó con el código viejo"


def test_una_reparacion_sin_cambios_no_toca_el_editor(vista, monkeypatch) -> None:
    from unittest.mock import MagicMock

    recargas = []
    monkeypatch.setattr(type(vista), "_cargar_codigo", lambda self, i: recargas.append(i))

    reparacion = MagicMock()
    reparacion.intentos = [MagicMock(aplicado=False)]
    vista._al_reparar(reparacion)

    assert not recargas
