"""El prompt de generación debe documentar el contrato real del borrador."""
import re
from pathlib import Path

from app.windows.assistant_view import _IMPORTACIONES_PERMITIDAS, preparar_codigo
from core.gemini_client import _cargar_prompt_sistema


def test_prompt_documenta_lista_exacta_de_imports():
    texto = Path("docs/GEMINI_SYSTEM_PROMPT.md").read_text(encoding="utf-8")
    lista = texto.split("Raíces de importación permitidas:", 1)[1].split("- No generes", 1)[0]
    assert set(re.findall(r"`([^`]+)`", lista)) == _IMPORTACIONES_PERMITIDAS


def test_plantilla_prompt_pasa_validador_sin_ejecutarla():
    texto = Path("docs/GEMINI_SYSTEM_PROMPT.md").read_text(encoding="utf-8")
    codigo = re.search(r"```python\n(.*?)```", texto, re.S).group(1)
    assert "message=" in preparar_codigo(codigo, "ejemplo_estructura")


def test_prompt_efectivo_incluye_restricciones(monkeypatch):
    monkeypatch.setattr("core.gemini_client._cargar_practicas", lambda: "")
    texto = _cargar_prompt_sistema()
    assert "No generes `import os`" in texto
    assert "nunca `mensaje=`" in texto
    assert "iniciar_o_conectar" in texto
