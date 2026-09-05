"""Regresiones de la revisión UX: datos aislados, sin red ni automatizaciones reales."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def codigo(nombre, comentario=""):
    return f'@registrar(nombre="{nombre}", disparador="manual")\nclass Flujo(BaseAutomation):\n    def ejecutar(self):\n        return None\n# {comentario}\n'


@pytest.fixture
def editor(app, tmp_path, monkeypatch):
    import app.windows.automations_view as modulo

    specs = [SimpleNamespace(nombre=n, categoria="prueba", disparador="manual") for n in ("uno", "dos")]
    for spec in specs:
        carpeta = tmp_path / "automations" / spec.nombre
        carpeta.mkdir(parents=True)
        (carpeta / "automation.py").write_text(codigo(spec.nombre), encoding="utf-8")
    monkeypatch.setattr(modulo, "BASE_DIR", tmp_path)
    monkeypatch.setattr(modulo, "listar", lambda: specs)
    monkeypatch.setattr(modulo, "obtener", lambda n: next(s for s in specs if s.nombre == n))
    monkeypatch.setattr(modulo.AutomationsView, "_actualizar_info_boveda", lambda *args: None)
    vista = modulo.AutomationsView(MagicMock())
    vista._recargar_modulo = MagicMock()
    yield vista, tmp_path
    vista.deleteLater()


def test_editor_conserva_borrador_al_cambiar_de_seleccion(editor):
    vista, _ = editor
    vista.editor.setPlainText(codigo("uno", "borrador"))
    vista.lista.setCurrentRow(1)
    vista.lista.setCurrentRow(0)
    assert vista.editor.toPlainText() == codigo("uno", "borrador")


def test_editor_detecta_conflicto_incluso_despues_de_cambiar_seleccion(editor):
    vista, raiz = editor
    vista.editor.setPlainText(codigo("uno", "borrador"))
    vista.lista.setCurrentRow(1)
    ruta = raiz / "automations/uno/automation.py"
    ruta.write_text(codigo("uno", "externo"), encoding="utf-8")
    vista.lista.setCurrentRow(0)
    assert vista._guardar_codigo() is False
    assert vista.editor.toPlainText() == codigo("uno", "borrador")
    assert ruta.read_text(encoding="utf-8") == codigo("uno", "externo")
    vista._recargar_modulo.assert_not_called()


def test_editor_recarga_cambio_externo_sin_ejecutar(editor):
    vista, raiz = editor
    (raiz / "automations/uno/automation.py").write_text(codigo("uno", "externo"), encoding="utf-8")
    assert vista._guardar_codigo() is False
    assert vista.editor.toPlainText() == codigo("uno", "externo")


@pytest.mark.parametrize("invalido", ["def roto(:", codigo("otro"), ""])
def test_editor_no_escribe_codigo_invalido(editor, invalido):
    vista, raiz = editor
    vista.editor.setPlainText(invalido)
    assert vista._guardar_codigo() is False
    assert (raiz / "automations/uno/automation.py").read_text(encoding="utf-8") == codigo("uno")


def test_guardar_actualiza_codigo_y_programador(editor):
    vista, raiz = editor
    vista.editor.setPlainText(codigo("uno", "nuevo"))
    assert vista._guardar_codigo() is True
    vista._recargar_modulo.assert_called_once_with("uno")
    vista.scheduler.actualizar.assert_called_once()
    assert not vista._borradores
    assert "nuevo" in (raiz / "automations/uno/automation.py").read_text(encoding="utf-8")


def test_error_de_recarga_se_informa_sin_ejecutar(editor):
    vista, _ = editor
    vista._recargar_modulo.side_effect = ImportError("dependencia ausente")
    assert vista._guardar_codigo() is False
    assert "Archivo guardado" in vista.estado.text()
    vista.scheduler.actualizar.assert_not_called()


def test_ejecucion_bloquea_edicion_y_seleccion(editor):
    vista, _ = editor
    vista._worker = object()
    vista._actualizar_controles()
    assert vista.editor.isReadOnly()
    assert not vista.lista.isEnabled()
    assert not vista.boton_guardar.isEnabled()
    vista._worker = None


@pytest.mark.parametrize("valor", ["cron:no es cron", "carpeta:", "desconocido"])
def test_disparador_invalido_no_reemplaza_el_activo(valor):
    from engine.scheduler import Scheduler

    sched = Scheduler(MagicMock())
    sched._sched = MagicMock()
    with pytest.raises(ValueError):
        sched.actualizar(SimpleNamespace(nombre="uno", disparador=valor))
    sched._sched.remove_job.assert_not_called()


def test_quitar_disparador_carpeta_detiene_observador():
    from engine.scheduler import Scheduler

    sched = Scheduler(MagicMock())
    observador = MagicMock()
    sched._observadores["uno"] = observador
    sched.desregistrar("uno")
    observador.stop.assert_called_once()
    observador.join.assert_called_once_with(timeout=2)
    assert not sched._observadores


def test_scheduler_pendiente_no_accede_a_fecha_inexistente():
    from engine.scheduler import Scheduler

    sched = Scheduler(MagicMock())
    sched._sched = MagicMock()
    sched._sched.get_jobs.return_value = [SimpleNamespace(id="pendiente")]
    assert sched.proximas_ejecuciones() == []


def test_imagen_corrupta_no_sale_a_la_red(tmp_path):
    from core.gemini_client import ErrorGemini, GeminiClient

    imagen = tmp_path / "falsa.png"
    imagen.write_bytes(b"no es una imagen")
    sesion = MagicMock()
    with pytest.raises(ErrorGemini):
        GeminiClient(api_key="solo-prueba", modelo="gemini-prueba", session=sesion).generar("hola", capturas=[imagen])
    sesion.post.assert_not_called()


def test_respuesta_truncada_no_se_presenta_como_codigo_completo():
    from core.gemini_client import ErrorGemini, GeminiClient

    sesion = MagicMock()
    sesion.post.return_value.ok = True
    sesion.post.return_value.json.return_value = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "```python\nclass Flujo:"}]}}]}
    with pytest.raises(ErrorGemini, match="incompleta"):
        GeminiClient(api_key="solo-prueba", modelo="gemini-prueba", session=sesion).generar("hola")


def test_log_grande_lee_solo_el_final(tmp_path):
    from app.windows.logs_view import LogsView

    ruta = tmp_path / "grande.log"
    ruta.write_text("antiguo\n" * 100000 + "ULTIMA LINEA\n", encoding="utf-8")
    texto, truncado = LogsView._leer_final(ruta)
    assert texto.rstrip().endswith("ULTIMA LINEA")
    assert truncado
    assert len(texto) < 401000
