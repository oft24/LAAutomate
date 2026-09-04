from __future__ import annotations

import base64

import pytest

from app.windows.assistant_view import normalizar_nombre, preparar_codigo
from core.gemini_client import ErrorGemini, GeminiClient, extraer_codigo_python


class _RespuestaFalsa:
    ok = True
    status_code = 200

    @staticmethod
    def json() -> dict:
        return {
            "candidates": [{"content": {"parts": [{"text": "respuesta lista"}]}}],
            "usageMetadata": {"promptTokenCount": 42, "candidatesTokenCount": 7},
            "modelVersion": "gemini-prueba",
        }


class _SesionFalsa:
    def __init__(self) -> None:
        self.llamada = None

    def post(self, url, **kwargs):
        self.llamada = (url, kwargs)
        return _RespuestaFalsa()


def test_gemini_envia_clave_en_header_y_captura_inline(tmp_path) -> None:
    captura = tmp_path / "pantalla.png"
    captura.write_bytes(b"imagen-de-prueba")
    sesion = _SesionFalsa()

    respuesta = GeminiClient(
        api_key="clave-prueba",
        modelo="gemini-prueba",
        session=sesion,
    ).generar("crea un flujo", capturas=[captura], contexto="acciones permitidas")

    url, opciones = sesion.llamada
    assert "clave-prueba" not in url
    assert opciones["headers"]["x-goog-api-key"] == "clave-prueba"
    partes = opciones["json"]["contents"][-1]["parts"]
    assert partes[0]["inline_data"]["mime_type"] == "image/png"
    assert base64.b64decode(partes[0]["inline_data"]["data"]) == b"imagen-de-prueba"
    assert "acciones permitidas" in partes[-1]["text"]
    assert respuesta.texto == "respuesta lista"
    assert respuesta.tokens_entrada == 42


def test_gemini_rechaza_modelo_que_podria_manipular_url() -> None:
    with pytest.raises(ErrorGemini, match="modelo"):
        GeminiClient(api_key="x", modelo="modelo/../../otro")


def test_extrae_unico_bloque_python() -> None:
    texto = "Explicación.\n```python\nprint('hola')\n```\nFin."
    assert extraer_codigo_python(texto) == "print('hola')\n"
    assert extraer_codigo_python("sin código") is None


def test_preparar_codigo_normaliza_nombre_y_valida_clase() -> None:
    codigo = '''from __future__ import annotations

from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar

@registrar(nombre="borrador", disparador="manual", categoria="general")
class Flujo(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        return AutomationResult(success=True)
'''
    preparado = preparar_codigo(codigo, "Reporte Diario 01")
    assert 'nombre="reporte_diario_01"' in preparado
    assert normalizar_nombre("99 pruebas") == "automatizacion_99_pruebas"


def test_preparar_codigo_rechaza_respuesta_sin_contrato() -> None:
    with pytest.raises(ValueError, match="BaseAutomation"):
        preparar_codigo(
            'from __future__ import annotations\n@registrar(nombre="x")\nclass Flujo:\n    pass\n',
            "x",
        )


def test_preparar_codigo_no_ejecuta_llamadas_al_importar() -> None:
    codigo = '''from __future__ import annotations
from engine.automation_base import BaseAutomation
from engine.registry import registrar

os.remove("archivo")

@registrar(nombre="x")
class Flujo(BaseAutomation):
    def ejecutar(self):
        return None
'''
    with pytest.raises(ValueError, match="nivel de módulo"):
        preparar_codigo(codigo, "x")
