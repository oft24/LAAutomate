from unittest.mock import MagicMock
import pytest
from core.gemini_client import GeminiClient, ErrorGemini
from engine.autocorreccion import Autocorrector


def test_sondeo_no_envia_contexto():
    sesion = MagicMock()
    sesion.post.return_value.ok = True
    sesion.post.return_value.json.return_value = {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}
    GeminiClient(api_key="prueba", modelo="prueba", session=sesion).comprobar_disponibilidad()
    opciones = sesion.post.call_args.kwargs
    assert opciones["timeout"] == (5, 15)
    assert opciones["json"] == {"contents": [{"role": "user", "parts": [{"text": "Responde solamente OK."}]}]}


def test_saturado_no_recibe_codigo_y_se_prueba_reserva(monkeypatch):
    clientes = {m: MagicMock() for m in ("uno", "dos")}
    clientes["uno"].comprobar_disponibilidad.side_effect = ErrorGemini("modelo saturado")
    clientes["dos"].generar.return_value.texto = "correccion"
    monkeypatch.setattr("engine.autocorreccion.GeminiClient", lambda modelo: clientes[modelo])
    corrector = Autocorrector(MagicMock())
    corrector._reservas = ["uno", "dos"]
    assert corrector._preguntar("codigo privado", []) == "correccion"
    clientes["uno"].generar.assert_not_called()
    clientes["dos"].comprobar_disponibilidad.assert_called_once()


def test_error_de_credenciales_no_prueba_reservas(monkeypatch):
    cliente = MagicMock()
    cliente.comprobar_disponibilidad.side_effect = ErrorGemini("API key no valida")
    fabrica = MagicMock(return_value=cliente)
    monkeypatch.setattr("engine.autocorreccion.GeminiClient", fabrica)
    corrector = Autocorrector(MagicMock())
    corrector._reservas = ["uno", "dos"]
    with pytest.raises(ErrorGemini):
        corrector._preguntar("codigo", [])
    fabrica.assert_called_once()
    cliente.generar.assert_not_called()


def test_orden_capacidad_y_tope_diez(monkeypatch):
    from core.gemini_client import ModeloGemini
    modelos = [ModeloGemini(f"gemini-3.{n}-flash") for n in range(1, 10)]
    modelos += [ModeloGemini("gemini-3.9-pro"), ModeloGemini("gemini-3.9-flash-lite"), ModeloGemini("gemini-3.9-live")]
    monkeypatch.setattr("engine.autocorreccion.listar_modelos", lambda: modelos)
    corrector = Autocorrector(MagicMock(), modelo="gemini-3.1-flash")
    orden = corrector._modelos_a_probar()
    assert len(orden) == 10
    assert orden[:3] == ["gemini-3.9-pro", "gemini-3.9-flash", "gemini-3.9-flash-lite"]
    assert not any("live" in m for m in orden)


def test_no_inventa_diez_modelos(monkeypatch):
    from core.gemini_client import ModeloGemini
    monkeypatch.setattr("engine.autocorreccion.listar_modelos", lambda: [ModeloGemini("gemini-3.8-flash")])
    assert Autocorrector(MagicMock())._modelos_a_probar() == ["gemini-3.8-flash"]
