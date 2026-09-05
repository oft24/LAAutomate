"""El agente que mejora el prompt de reparación.

Un sistema que reescribe sus propias instrucciones puede degradarse sin que
nadie lo note: el prompt crece, se contradice, o pierde una regla de
seguridad, y el efecto no se ve hasta la siguiente reparación importante.
Estas pruebas cubren las barandillas, no la calidad de la escritura —eso no
se puede probar automáticamente.
"""
from __future__ import annotations

import json

import pytest

from engine import optimizador_prompt as opt


class _Respuesta:
    def __init__(self, texto: str) -> None:
        self.texto = texto


class _ClienteFalso:
    def __init__(self, carga) -> None:
        self._carga = carga
        self.peticiones: list[str] = []

    def generar(self, mensaje, **_kwargs):
        self.peticiones.append(mensaje)
        texto = self._carga if isinstance(self._carga, str) else json.dumps(self._carga)
        return _Respuesta(texto)


# Los huecos que `autocorreccion` rellena en cada intento. Un prompt de
# prueba que no los lleve es mas comodo que el de verdad, y entonces deja
# sin probar justo la parte que importa.
HUECOS = (
    "\n\nMAX_REPAIR_ATTEMPTS = {{MAX_REPAIR_ATTEMPTS}}\n"
    "Intento actual: {{CURRENT_ATTEMPT}}\n\n"
    "## Intentos anteriores\n\n{{PREVIOUS_ATTEMPTS}}\n"
)

PROMPT_BASE = (
    "# repair_prompt_v1\n\n"
    + "Eres un agente de reparación. " * 60
    + HUECOS
    + "\n\n## Reglas de seguridad\nNunca expongas credenciales.\n"
    + "\n## Salida obligatoria\nDevuelve JSON con \"status\".\n"
)


def _prompt_valido(version: str = "repair_prompt_v2") -> str:
    return (
        f"# {version}\n\n"
        + "Eres un agente de reparación mejorado. " * 55
        + HUECOS
        + "\n\n## Reglas de seguridad\nNunca expongas credenciales.\n"
        + "\n## Salida obligatoria\nDevuelve JSON con \"status\".\n"
    )


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Aísla los archivos de prompt en un directorio temporal."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PROMPT_REPARACION.md").write_text(PROMPT_BASE, encoding="utf-8")
    (docs / "PROMPT_OPTIMIZADOR.md").write_text(
        "Mejora {{CURRENT_PROMPT}} con {{INCIDENT}} y {{SUCCESSFUL_CORRECTION}}. "
        "Versión {{PROMPT_VERSION}}. Fallidos: {{FAILED_ATTEMPTS}}. "
        "Validación: {{SUCCESS_VALIDATION}}. Capturas: {{SCREENSHOT_ANALYSIS}}. "
        "Error: {{ORIGINAL_ERROR}}.",
        encoding="utf-8",
    )
    monkeypatch.setattr(opt, "BASE_DIR", tmp_path)
    monkeypatch.setattr(opt, "CARPETA_VERSIONES", docs / "prompts")
    monkeypatch.setattr(opt, "CHANGELOG", docs / "PROMPT_CHANGELOG.md")
    monkeypatch.setattr(opt, "_ruta_recurso", lambda rel: tmp_path / rel)
    return {"docs": docs, "tmp": tmp_path}


def _llamar(cliente, **cambios):
    argumentos = {
        "incidente": "mi_proceso: click_por_texto('1')",
        "error_original": "ElementNotFoundError",
        "analisis_capturas": "la ventana estaba al frente, sin diálogos",
        "intentos_fallidos": "(ninguno)",
        "correccion_exitosa": "usar el teclado en vez de clics por glifo",
        "validacion": "la automatización devolvió success=True",
        "cliente": cliente,
    }
    argumentos.update(cambios)
    return opt.optimizar(**argumentos)


# ------------------------------------------------------------ versionado


def test_una_mejora_valida_crea_la_version_siguiente(entorno) -> None:
    cliente = _ClienteFalso(
        {
            "update_prompt": True,
            "new_prompt": _prompt_valido(),
            "learning": {"generalized_rule": "comprueba si un diálogo bloquea el elemento"},
            "changelog": "añadida comprobación de diálogos antes de culpar al selector",
            "regression_risk": "LOW",
        }
    )
    resultado = _llamar(cliente)

    assert resultado.actualizado
    assert resultado.version_anterior == "repair_prompt_v1"
    assert resultado.version_nueva == "repair_prompt_v2"
    assert opt.version_actual() == "repair_prompt_v2", "el prompt activo se actualizó"


def test_la_version_anterior_queda_archivada(entorno) -> None:
    """Sin esto, la primera mejora deja la v1 sin copia a la que volver."""
    cliente = _ClienteFalso(
        {"update_prompt": True, "new_prompt": _prompt_valido(), "learning": {}, "changelog": "x"}
    )
    _llamar(cliente)

    versiones = entorno["docs"] / "prompts"
    assert (versiones / "repair_prompt_v1.md").exists(), "volver atrás es copiar un archivo"
    assert (versiones / "repair_prompt_v2.md").exists()
    assert (versiones / "repair_prompt_v1.md").read_text(encoding="utf-8") == PROMPT_BASE


def test_cada_version_deja_entrada_en_el_changelog(entorno) -> None:
    cliente = _ClienteFalso(
        {
            "update_prompt": True,
            "new_prompt": _prompt_valido(),
            "learning": {"generalized_rule": "mira si hay un modal"},
            "changelog": "regla nueva sobre modales",
            "regression_risk": "MEDIUM",
        }
    )
    _llamar(cliente)

    texto = (entorno["docs"] / "PROMPT_CHANGELOG.md").read_text(encoding="utf-8")
    assert "repair_prompt_v2" in texto
    assert "mira si hay un modal" in texto
    assert "MEDIUM" in texto


# --------------------------------------------------------- barandillas


def test_update_prompt_false_no_cambia_nada(entorno) -> None:
    """Es la respuesta más común y la más sana: no todo incidente enseña
    algo generalizable."""
    cliente = _ClienteFalso({"update_prompt": False, "reason": "no hay mejora generalizable"})
    resultado = _llamar(cliente)

    assert not resultado.actualizado
    assert "generalizable" in resultado.motivo
    assert opt.version_actual() == "repair_prompt_v1"


def test_un_prompt_que_crece_demasiado_se_rechaza(entorno) -> None:
    """Generalizar debería resumir. Si el prompt engorda, el modelo se puso
    a narrar el incidente en vez de extraer la regla."""
    cliente = _ClienteFalso(
        {"update_prompt": True, "new_prompt": _prompt_valido() + "relleno " * 3000, "learning": {}}
    )
    resultado = _llamar(cliente)

    assert not resultado.actualizado
    assert "crece" in resultado.motivo
    assert opt.version_actual() == "repair_prompt_v1"


def test_un_prompt_demasiado_corto_se_rechaza(entorno) -> None:
    cliente = _ClienteFalso({"update_prompt": True, "new_prompt": "sé mejor", "learning": {}})
    resultado = _llamar(cliente)

    assert not resultado.actualizado
    assert "corto" in resultado.motivo


@pytest.mark.parametrize("seccion", ["## Reglas de seguridad", "## Salida obligatoria"])
def test_no_se_acepta_un_prompt_que_pierde_una_seccion_critica(entorno, seccion) -> None:
    """«Mejorar» no puede significar quedarse sin las reglas de seguridad ni
    sin el contrato de salida."""
    mutilado = _prompt_valido().replace(seccion, "## Otra cosa")
    cliente = _ClienteFalso({"update_prompt": True, "new_prompt": mutilado, "learning": {}})

    resultado = _llamar(cliente)

    assert not resultado.actualizado
    assert "perdió" in resultado.motivo
    assert opt.version_actual() == "repair_prompt_v1"


@pytest.mark.parametrize(
    "hueco", ["{{MAX_REPAIR_ATTEMPTS}}", "{{CURRENT_ATTEMPT}}", "{{PREVIOUS_ATTEMPTS}}"]
)
def test_no_se_acepta_un_prompt_que_pierde_un_hueco(entorno, hueco) -> None:
    """Sin estos huecos el agente deja de saber en qué intento va y qué ya
    probó. Nada falla de forma visible: repite la misma corrección para
    siempre, que es la degradación más cara de detectar."""
    mutilado = _prompt_valido().replace(hueco, "")
    cliente = _ClienteFalso({"update_prompt": True, "new_prompt": mutilado, "learning": {}})

    resultado = _llamar(cliente)

    assert not resultado.actualizado
    assert hueco in resultado.motivo
    assert opt.version_actual() == "repair_prompt_v1"


def test_una_respuesta_que_no_es_json_no_rompe_nada(entorno) -> None:
    resultado = _llamar(_ClienteFalso("lo siento, no puedo ayudarte con eso"))

    assert not resultado.actualizado
    assert opt.version_actual() == "repair_prompt_v1"


def test_si_el_modelo_falla_la_reparacion_sigue_siendo_valida(entorno) -> None:
    """No poder mejorar el prompt nunca debe romper una reparación que sí
    funcionó."""

    class _ClienteQueRevienta:
        def generar(self, *a, **k):
            raise RuntimeError("sin red")

    resultado = _llamar(_ClienteQueRevienta())

    assert not resultado.actualizado
    assert "RuntimeError" in resultado.motivo


# ------------------------------------------------------------- el prompt


def test_el_optimizador_recibe_todo_el_contexto(entorno) -> None:
    cliente = _ClienteFalso({"update_prompt": False})
    _llamar(cliente)

    peticion = cliente.peticiones[0]
    assert PROMPT_BASE[:40] in peticion, "debe ver el prompt actual entero"
    assert "click_por_texto" in peticion
    assert "ElementNotFoundError" in peticion
    assert "success=True" in peticion
    assert "repair_prompt_v1" in peticion
    for marcador in (
        "{{CURRENT_PROMPT}}", "{{INCIDENT}}", "{{ORIGINAL_ERROR}}",
        "{{SCREENSHOT_ANALYSIS}}", "{{FAILED_ATTEMPTS}}",
        "{{SUCCESSFUL_CORRECTION}}", "{{SUCCESS_VALIDATION}}", "{{PROMPT_VERSION}}",
    ):
        assert marcador not in peticion, f"{marcador} llegó sin sustituir"
    # Los huecos del prompt DE REPARACION si tienen que seguir ahi: van
    # dentro de {{CURRENT_PROMPT}} y el optimizador debe conservarlos en la
    # version que devuelva.
    assert "{{PREVIOUS_ATTEMPTS}}" in peticion


def test_la_version_se_lee_de_la_primera_linea() -> None:
    assert opt.version_actual("# repair_prompt_v7\n\nlo que sea") == "repair_prompt_v7"
    assert opt.version_actual("sin version declarada") == "repair_prompt_v1"


def test_json_con_cerca_de_markdown_se_lee_igual(entorno) -> None:
    cuerpo = json.dumps({"update_prompt": True, "new_prompt": _prompt_valido(), "learning": {}})
    resultado = _llamar(_ClienteFalso(f"```json\n{cuerpo}\n```"))

    assert resultado.actualizado
