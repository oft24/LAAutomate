"""Escribir una automatización en disco: `engine.almacen`.

Lo importante aquí es el `__init__.py`. Antes se escribía siempre
`nombre_de_clase(carpeta)`, dando por hecho que la clase se llama igual que
la carpeta en CamelCase. Cuando no coincide —porque alguien renombró la
clase en el editor, o porque el Asistente IA la llamó de otra forma— el
`__init__.py` importaba un nombre inexistente y la automatización moría con
un ImportError al RECARGAR, no al guardar: el peor tipo de fallo, porque
todo parece haber ido bien.
"""
from __future__ import annotations

import pytest

from engine.almacen import (
    clase_exportada,
    escribir_paquete,
    leer_codigo,
    listar_en_disco,
    nombre_de_clase,
    validar_nombre,
)

CODIGO = '''"""Prueba."""
from __future__ import annotations

from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar


@registrar(nombre="mi_proceso", disparador="manual", categoria="ia")
class MiProceso(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        return AutomationResult(success=True)
'''


def test_escribir_paquete_deja_automation_e_init(tmp_path) -> None:
    escribir_paquete("mi_proceso", CODIGO, base=tmp_path)

    assert (tmp_path / "mi_proceso" / "automation.py").read_text(encoding="utf-8") == CODIGO
    init = (tmp_path / "mi_proceso" / "__init__.py").read_text(encoding="utf-8")
    assert "from automations.mi_proceso.automation import MiProceso" in init
    assert leer_codigo("mi_proceso", base=tmp_path) == CODIGO


def test_el_init_importa_la_clase_que_el_codigo_define_de_verdad(tmp_path) -> None:
    """El bug real: Gemini llamó `CalcDemo` a la clase de la carpeta
    `mi_proceso`, y el __init__.py importaba `MiProceso`, que no existe."""
    escribir_paquete("mi_proceso", CODIGO.replace("class MiProceso(", "class CalcDemo("), base=tmp_path)

    init = (tmp_path / "mi_proceso" / "__init__.py").read_text(encoding="utf-8")
    assert "import CalcDemo" in init
    assert "MiProceso" not in init


def test_se_prefiere_la_clase_decorada_con_registrar(tmp_path) -> None:
    """Es la que el motor va a instanciar; una clase auxiliar definida
    antes en el archivo no debe ganarle."""
    codigo = "class Ayudante:\n    pass\n\n\n" + CODIGO.replace("class MiProceso(", "class CalcDemo(")
    escribir_paquete("mi_proceso", codigo, base=tmp_path)

    assert "import CalcDemo" in (tmp_path / "mi_proceso" / "__init__.py").read_text(encoding="utf-8")


def test_sin_ninguna_clase_el_init_no_importa_nada(tmp_path) -> None:
    """Un __init__.py que importa de un archivo sin clases es un
    ImportError garantizado. Vacío es correcto: el registry importa
    automation.py, no el paquete."""
    escribir_paquete("mi_proceso", "x = 1\n", base=tmp_path)

    assert "import" not in (tmp_path / "mi_proceso" / "__init__.py").read_text(encoding="utf-8")


def test_codigo_que_no_compila_no_inventa_una_clase(tmp_path) -> None:
    escribir_paquete("mi_proceso", "class Rota(:\n", base=tmp_path)

    assert "import" not in (tmp_path / "mi_proceso" / "__init__.py").read_text(encoding="utf-8")


def test_clase_exportada_cae_al_nombre_de_la_carpeta_si_no_hay_pistas() -> None:
    codigo = "class MiProceso:\n    pass\n\n\nclass Otra:\n    pass\n"
    assert clase_exportada(codigo, "mi_proceso") == "MiProceso"


def test_escribir_paquete_rechaza_un_nombre_invalido(tmp_path) -> None:
    """El nombre acaba siendo una carpeta y un módulo importable: 'Mi
    Proceso' produciría un import imposible de escribir."""
    with pytest.raises(ValueError, match="minúscula"):
        escribir_paquete("Mi Proceso", CODIGO, base=tmp_path)
    assert not (tmp_path / "Mi Proceso").exists()


def test_leer_codigo_de_algo_que_no_existe_devuelve_cadena_vacia(tmp_path) -> None:
    assert leer_codigo("no_existe", base=tmp_path) == ""


def test_listar_en_disco_ve_las_que_el_registry_no_conoce(tmp_path) -> None:
    """A propósito distinto de `registry.listar()`: el registry solo tiene
    las que se importaron BIEN, y la que hay que arreglar —la que no
    compila— justo no está ahí."""
    escribir_paquete("buena", CODIGO, base=tmp_path)
    escribir_paquete("rota", "def x(:\n", base=tmp_path)
    (tmp_path / "_privada").mkdir()
    (tmp_path / "_privada" / "automation.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "sin_codigo").mkdir()

    assert listar_en_disco(base=tmp_path) == ["buena", "rota"]


def test_nombres_validos_e_invalidos() -> None:
    validar_nombre("mi_proceso_web_2")
    assert nombre_de_clase("mi_proceso_web") == "MiProcesoWeb"
    with pytest.raises(ValueError):
        validar_nombre("2_empieza_con_numero")
