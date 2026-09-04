"""Elección de modelo, reintentos y diagnóstico — sin tocar la red.

Se falsifica `requests.Session`, no el cliente: así lo que se prueba es el
contrato real que la app espera de la API (qué header lleva la clave, qué
parte de la respuesta es la respuesta) y no una imitación del propio
cliente, que pasaría igual aunque el cliente estuviera roto.
"""
from __future__ import annotations

import json

import pytest
import requests

from core.gemini_client import (
    CODIGOS_REINTENTABLES,
    ErrorGemini,
    GeminiClient,
    ModeloGemini,
    es_modelo_de_texto,
    listar_modelos,
    modelo_por_defecto,
    ordenar_para_elegir,
)


class _RespuestaFalsa:
    def __init__(self, datos, codigo: int = 200) -> None:
        self._datos = datos
        self.status_code = codigo
        self.ok = codigo < 400
        self.text = json.dumps(datos)

    def json(self):
        if self._datos is None:
            raise ValueError("no es json")
        return self._datos


class _SesionFalsa:
    def __init__(self, *respuestas) -> None:
        self._respuestas = list(respuestas)
        self.peticiones: list[dict] = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.peticiones.append({"metodo": "GET", "url": url, "headers": headers, "params": params})
        return self._respuestas.pop(0)

    def post(self, url, headers=None, json=None, timeout=None):
        self.peticiones.append({"metodo": "POST", "url": url, "headers": headers, "json": json})
        return self._respuestas.pop(0)


def _texto(t: str) -> _RespuestaFalsa:
    return _RespuestaFalsa({"candidates": [{"content": {"parts": [{"text": t}]}}]})


# ------------------------------------------------------ elección de modelo


def test_modelo_por_defecto_elige_la_version_mas_alta() -> None:
    """Se elige por VERSIÓN y no por una lista de nombres: cualquier lista
    escrita hoy nombra modelos que en unos meses contestan 404."""
    disponibles = [
        ModeloGemini("gemini-2.5-flash"),
        ModeloGemini("gemini-3.8-flash"),
        ModeloGemini("gemini-3.5-flash"),
    ]
    assert modelo_por_defecto(disponibles) == "gemini-3.8-flash"


def test_un_modelo_estable_le_gana_a_un_preview_mas_nuevo() -> None:
    """Un -preview cambia de comportamiento o desaparece sin aviso, y este
    es el modelo que se elige SOLO, sin que nadie lo haya pedido."""
    disponibles = [ModeloGemini("gemini-3.5-flash"), ModeloGemini("gemini-9.9-pro-preview")]
    assert modelo_por_defecto(disponibles) == "gemini-3.5-flash"


def test_a_igual_version_se_prefiere_pro_sobre_flash_sobre_lite() -> None:
    disponibles = [
        ModeloGemini("gemini-3.5-flash-lite"),
        ModeloGemini("gemini-3.5-flash"),
        ModeloGemini("gemini-3.5-pro"),
    ]
    assert modelo_por_defecto(disponibles) == "gemini-3.5-pro"


@pytest.mark.parametrize(
    "nombre",
    [
        "gemini-3-pro-image",
        "gemini-2.5-flash-preview-tts",
        "gemma-4-31b-it",
        "lyria-3.5",
        "gemini-2.5-computer-use-preview-10-2025",
        "gemini-3.5-transcribe",
        "gemini-1.5-flash",
    ],
)
def test_se_descartan_los_modelos_que_no_escriben_codigo(nombre: str) -> None:
    """Todos estos aparecen de verdad en /models con generateContent --
    salen del listado real de una cuenta. Elegir uno da una respuesta
    inútil o un 400 que el usuario no puede explicarse."""
    assert not es_modelo_de_texto(nombre)


def test_los_utiles_van_primero_pero_no_se_pierde_ninguno() -> None:
    revueltos = [
        ModeloGemini("antigravity-preview-05-2026"),
        ModeloGemini("gemini-3.5-flash"),
        ModeloGemini("lyria-3.5"),
        ModeloGemini("gemini-3.8-flash"),
    ]
    ordenados = [m.nombre for m in ordenar_para_elegir(revueltos)]

    assert ordenados[:2] == ["gemini-3.8-flash", "gemini-3.5-flash"]
    assert len(ordenados) == len(revueltos), "solo cambia el orden, no se filtra nada"


def test_sin_modelos_se_explica_en_vez_de_reventar_con_indexerror() -> None:
    with pytest.raises(ErrorGemini, match="generateContent"):
        modelo_por_defecto([])


# ----------------------------------------------------------- listar_modelos


def test_listar_modelos_descarta_los_que_no_generan_contenido() -> None:
    sesion = _SesionFalsa(
        _RespuestaFalsa(
            {
                "models": [
                    {
                        "name": "models/gemini-3.5-flash",
                        "displayName": "Gemini 3.5 Flash",
                        "supportedGenerationMethods": ["generateContent"],
                        "inputTokenLimit": 1048576,
                    },
                    {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
                ]
            }
        )
    )
    modelos = listar_modelos(api_key="clave-de-prueba", session=sesion)

    assert [m.nombre for m in modelos] == ["gemini-3.5-flash"]
    assert "1048k" in modelos[0].resumen()


def test_la_clave_viaja_en_el_header_y_nunca_en_la_url() -> None:
    """Una clave en la query string acaba en logs de proxy y en cualquier
    traza que alguien pegue para pedir ayuda."""
    sesion = _SesionFalsa(_RespuestaFalsa({"models": []}))
    listar_modelos(api_key="clave-de-prueba", session=sesion)

    peticion = sesion.peticiones[0]
    assert peticion["headers"]["x-goog-api-key"] == "clave-de-prueba"
    assert "clave-de-prueba" not in peticion["url"]
    assert "clave-de-prueba" not in json.dumps(peticion["params"] or {})


# ---------------------------------------------------------------- reintentos


def _cliente(*respuestas, reintentos: int = 0):
    sesion = _SesionFalsa(*respuestas)
    return GeminiClient(api_key="k", modelo="gemini-3.5-flash", session=sesion, reintentos=reintentos), sesion


def test_un_503_se_reintenta_y_la_segunda_vez_funciona(monkeypatch) -> None:
    """La API contesta 503 "high demand" con frecuencia; se comprobó que el
    mismo modelo responde bien unos segundos después."""
    monkeypatch.setattr("core.gemini_client.time.sleep", lambda _s: None)
    cliente, sesion = _cliente(
        _RespuestaFalsa({"error": {"message": "high demand"}}, 503), _texto("por fin"), reintentos=2
    )
    assert cliente.generar("hola").texto == "por fin"
    assert len(sesion.peticiones) == 2


def test_se_respeta_el_retrydelay_que_pide_la_api(monkeypatch) -> None:
    dormidas: list[float] = []
    monkeypatch.setattr("core.gemini_client.time.sleep", dormidas.append)
    cliente, _ = _cliente(
        _RespuestaFalsa({"error": {"message": "quota", "details": [{"retryDelay": "17s"}]}}, 429),
        _texto("ok"),
        reintentos=1,
    )
    cliente.generar("hola")
    assert dormidas == [17.0]


def test_la_espera_se_limita_para_no_colgar_la_interfaz(monkeypatch) -> None:
    dormidas: list[float] = []
    monkeypatch.setattr("core.gemini_client.time.sleep", dormidas.append)
    cliente, _ = _cliente(
        _RespuestaFalsa({"error": {"message": "quota", "details": [{"retryDelay": "3600s"}]}}, 429),
        _texto("ok"),
        reintentos=1,
    )
    cliente.generar("hola")
    assert dormidas == [30.0]


def test_un_404_no_se_reintenta_nunca() -> None:
    """Un modelo retirado no va a aparecer por esperar."""
    cliente, sesion = _cliente(_RespuestaFalsa({"error": {"message": "retirado"}}, 404), reintentos=2)
    with pytest.raises(ErrorGemini, match="retirado|no está disponible"):
        cliente.generar("hola")
    assert len(sesion.peticiones) == 1


def test_el_429_dice_que_hacer_y_no_solo_el_codigo() -> None:
    cliente, _ = _cliente(_RespuestaFalsa({"error": {"message": "quota"}}, 429))
    with pytest.raises(ErrorGemini, match="cuota"):
        cliente.generar("hola")


def test_todos_los_codigos_reintentables_son_temporales() -> None:
    assert CODIGOS_REINTENTABLES == {429, 500, 503}


# -------------------------------------------- partes de razonamiento


def test_se_ignoran_las_partes_de_razonamiento() -> None:
    """Los modelos 2.5+ devuelven su borrador interno marcado thought=True.
    Colarlo en la burbuja del chat rompe extraer_codigo_python cuando el
    borrador también trae un bloque ```python."""
    cliente, _ = _cliente(
        _RespuestaFalsa(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "pensando: quizá use click_por_texto...", "thought": True},
                                {"text": "La respuesta buena."},
                            ]
                        }
                    }
                ]
            }
        )
    )
    assert cliente.generar("hola").texto == "La respuesta buena."


def test_respuesta_vacia_por_max_tokens_se_explica() -> None:
    cliente, _ = _cliente(
        _RespuestaFalsa({"candidates": [{"content": {"parts": []}, "finishReason": "MAX_TOKENS"}]})
    )
    with pytest.raises(ErrorGemini, match="presupuesto de salida"):
        cliente.generar("hola")


def test_prompt_bloqueado_se_explica() -> None:
    cliente, _ = _cliente(_RespuestaFalsa({"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(ErrorGemini, match="SAFETY"):
        cliente.generar("hola")


def test_sin_red_el_mensaje_sigue_siendo_legible() -> None:
    class _SinRed:
        def post(self, *a, **k):
            raise requests.ConnectionError("boom")

    cliente = GeminiClient(api_key="k", modelo="gemini-3.5-flash", session=_SinRed())
    with pytest.raises(ErrorGemini, match="No se pudo conectar"):
        cliente.generar("hola")


def test_los_2_5_quedan_por_debajo_de_cualquier_3_x() -> None:
    """No se pueden filtrar: la API NO marca los modelos retirados
    (gemini-2.5-pro se describe como "Stable release" igual que uno vivo).
    Lo que sí se puede es no proponerlos nunca por defecto."""
    disponibles = [ModeloGemini("gemini-2.5-pro"), ModeloGemini("gemini-3.5-flash-lite")]
    assert modelo_por_defecto(disponibles) == "gemini-3.5-flash-lite"

    orden = [m.nombre for m in ordenar_para_elegir(disponibles)]
    assert orden.index("gemini-3.5-flash-lite") < orden.index("gemini-2.5-pro")
