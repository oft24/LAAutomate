"""Regresiones con datos simulados: no envían solicitudes ni graban el equipo."""
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtWidgets import QApplication

CODIGO = 'from __future__ import annotations\nfrom engine.registry import registrar\nfrom engine.automation_base import BaseAutomation\n@registrar(nombre="prueba", disparador="manual")\nclass Flujo(BaseAutomation):\n    def ejecutar(self):\n        pass\n'

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def grabadora(app, tmp_path, monkeypatch):
    import app.windows.recorder_view as modulo
    import core.config
    monkeypatch.setattr(core.config, "BASE_DIR", tmp_path)
    monkeypatch.setattr(modulo, "generar_codigo", lambda *args: CODIGO)
    vista = modulo.RecorderView()
    vista.campo_nombre_web.setText("prueba")
    vista._guardar_automatizacion = MagicMock()
    yield vista
    vista._detener_listener_f5()
    vista.deleteLater()

def test_detener_no_guarda_hasta_confirmar(grabadora):
    grabadora._al_detener_listo([{"tipo": "click"}])
    grabadora._guardar_automatizacion.assert_not_called()
    assert grabadora._pendiente_guardar == "prueba"
    assert not grabadora.vista_codigo.isReadOnly()
    grabadora.vista_codigo.setPlainText(CODIGO + "# revisado\n")
    grabadora._guardar_resultado()
    grabadora._guardar_automatizacion.assert_called_once_with("prueba", CODIGO + "# revisado\n")
    assert grabadora._pendiente_guardar is None
    assert not grabadora.boton_guardar.isEnabled()

def test_grabacion_vacia_no_crea_archivos(grabadora):
    grabadora._al_detener_listo([])
    grabadora._guardar_automatizacion.assert_not_called()
    assert "No se capturaron" in grabadora.estado.text()
    assert not grabadora.boton_guardar.isEnabled()

@pytest.mark.parametrize("url", ["ftp://ejemplo.com", "https://", "https://usuario:clave@ejemplo.com", "https://ejemplo .com", "https://ejemplo.com:roto"])
def test_url_invalida_no_abre_navegador(grabadora, url, monkeypatch):
    import app.windows.recorder_view as modulo
    worker = MagicMock()
    monkeypatch.setattr(modulo, "_AbrirNavegadorWorker", worker)
    grabadora.campo_url.setText(url)
    grabadora._iniciar_web()
    worker.assert_not_called()
    assert grabadora.boton_iniciar.isEnabled()

@pytest.fixture
def asistente(app, monkeypatch):
    import app.windows.assistant_view as modulo
    monkeypatch.setattr(modulo, "tiene_api_key", lambda: False)
    monkeypatch.setattr(modulo, "modelo_por_defecto", lambda: "gemini-prueba")
    monkeypatch.setattr(modulo, "listar", lambda: [])
    monkeypatch.setattr(modulo, "listar_en_disco", lambda: [])
    monkeypatch.setattr(modulo, "construir_contexto_proyecto", lambda *args: "contexto sintético")
    vista = modulo.AssistantView()
    monkeypatch.setattr(modulo, "tiene_api_key", lambda: True)
    monkeypatch.setattr(modulo, "_GeminiWorker", MagicMock())
    yield vista
    vista._timer_pensando.stop()
    vista._worker = None
    vista.deleteLater()

def test_error_gemini_conserva_mensaje_y_desbloquea(asistente):
    asistente.entrada.setPlainText("Crear mi reporte")
    asistente._enviar()
    assert asistente.entrada.isReadOnly()
    assert not asistente.boton_enviar.isEnabled()
    asistente._al_error("Error HTTP 429 simulado")
    asistente._liberar_worker()
    assert asistente.entrada.toPlainText() == "Crear mi reporte"
    assert not asistente.entrada.isReadOnly()
    assert asistente.boton_enviar.isEnabled()

def test_respuesta_muestra_codigo_separado(asistente):
    asistente.entrada.setPlainText("Crear reporte")
    asistente._enviar()
    respuesta = SimpleNamespace(texto="```python\n" + CODIGO + "```", modelo="gemini-prueba")
    asistente._al_responder("Crear reporte", respuesta)
    asistente._liberar_worker()
    assert asistente.codigo_resultado.toPlainText().strip() == CODIGO.strip()
    assert asistente.boton_crear.isEnabled()
    assert not asistente.entrada.toPlainText()


def test_cancelar_descarta_respuesta_y_conserva_texto(asistente):
    asistente.entrada.setPlainText("Mi solicitud")
    asistente._enviar()
    asistente._cancelar_chat()
    asistente._worker.cancelar.assert_called_once()
    asistente._al_responder("Mi solicitud", SimpleNamespace(texto="respuesta tardía", modelo="prueba"))
    asistente._liberar_worker()
    assert asistente.entrada.toPlainText() == "Mi solicitud"
    assert not asistente._historial
    assert asistente.boton_enviar.isEnabled()
    assert not asistente.boton_cancelar_chat.isEnabled()

def test_captura_inexistente_no_bloquea_formulario(asistente, tmp_path):
    asistente._capturas = [tmp_path / "no-existe.png"]
    asistente.entrada.setPlainText("Revisa esto")
    asistente._enviar()
    # La lectura ahora ocurre en el worker, nunca en el hilo de la ventana.
    assert asistente._worker is not None
    asistente._al_error("No encuentro la captura: no-existe.png")
    asistente._liberar_worker()
    assert asistente._worker is None
    assert asistente.boton_enviar.isEnabled()
    assert asistente.entrada.toPlainText() == "Revisa esto"

@pytest.mark.parametrize("extra", ["objeto().atributo = 1\n", "class Otro(fabrica()):\n    pass\n", "class Otro(BaseAutomation, metaclass=fabrica()):\n    pass\n"])
def test_crear_rechaza_ejecucion_al_importar(extra):
    from app.windows.assistant_view import preparar_codigo
    with pytest.raises(ValueError):
        preparar_codigo(CODIGO + extra, "prueba")

def test_kpis_no_se_limitan_a_cien_filas(tmp_path, monkeypatch):
    from core import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "historial.db")
    ahora = datetime(2026, 9, 4, 18, tzinfo=timezone.utc)
    inicio = ahora - timedelta(seconds=2)
    filas = [("prueba", 1, inicio.isoformat(), ahora.isoformat()) for _ in range(150)]
    filas += [("negativa", 0, ahora.isoformat(), inicio.isoformat()), ("futura", 0, (ahora + timedelta(days=1)).isoformat(), None), ("rota", 0, "fecha inválida", None)]
    with database._conexion() as conn:
        conn.executemany("INSERT INTO ejecuciones(automatizacion, exito, iniciado_en, finalizado_en) VALUES (?, ?, ?, ?)", filas)
    resumen = database.estadisticas_ejecuciones(ahora)
    assert resumen["hoy"] == 151
    assert resumen["total_7d"] == 151
    assert resumen["exitos_7d"] == 150
    assert resumen["duracion_7d"] == pytest.approx(2, abs=0.001)

def test_wiki_filtra_y_explica_ausencia_de_resultados(app):
    from app.windows.wiki_view import WikiView
    vista = WikiView()
    vista.campo_busqueda.setText("ninguna_accion_coincide_999")
    assert not vista._sin_resultados.isHidden()
    assert vista._introduccion.isHidden()
    vista.campo_busqueda.setText("excel")
    assert vista._sin_resultados.isHidden()
    assert any(not tarjeta.isHidden() for tarjeta, filas in vista._tarjetas)
    vista.campo_busqueda.clear()
    assert not vista._introduccion.isHidden()
    vista.deleteLater()
