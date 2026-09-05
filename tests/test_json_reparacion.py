import pytest
from core.gemini_client import extraer_json, extraer_codigo_python


@pytest.mark.parametrize("cercado", [False, True])
def test_informe_separado_de_llaves_python(cercado):
    informe = '{"status": "CORRECTION_PROPOSED", "evidence": ["texto con } y { literal"]}'
    prefijo = "```json\n" + informe + "\n```" if cercado else informe
    codigo = 'datos = {"canal": "general"}\nmensaje = f"Enviado: {datos}"\n'
    respuesta = prefijo + "\n\n```python\n" + codigo + "```"
    assert extraer_json(respuesta)["status"] == "CORRECTION_PROPOSED"
    assert extraer_codigo_python(respuesta) == codigo


def test_rechaza_dos_informes():
    with pytest.raises(ValueError):
        extraer_json('{"safe": true}\n{"safe": false}')


def test_json_roto_no_se_recupera_del_codigo():
    with pytest.raises(ValueError):
        extraer_json('{"status": roto}\n```python\ndatos = {"status": "OK"}\n```')
