"""El ciclo fallo → diagnóstico → arreglo → reanudar.

Todo con dobles: ni se abre navegador ni se llama a Gemini. Lo que importa
aquí no es que el modelo acierte —eso no se puede probar— sino que el bucle
se comporte cuando el modelo se equivoca: que no insista con un arreglo
idéntico, que no deje la automatización peor que antes, que respete el
tope de intentos y que no aprenda «lecciones» de reparaciones que
fracasaron.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from engine.automation_base import AutomationResult
from engine.autocorreccion import MAX_INTENTOS, Autocorrector, Reparacion


class _SpecFalso:
    nombre = "mi_proceso"
    disparador = "manual"
    categoria = "prueba"
    cls = None


class _RunnerFalso:
    """Devuelve resultados preparados y recuerda cómo se le llamó."""

    def __init__(self, *resultados) -> None:
        self._resultados = list(resultados)
        self.llamadas: list[dict] = []

    def ejecutar(self, spec, bitacora=None, etiqueta_captura=""):
        self.llamadas.append({"etiqueta": etiqueta_captura, "bitacora": bitacora})
        return self._resultados.pop(0) if self._resultados else _fallo("sin más resultados")


def _fallo(mensaje: str, acciones: str = "escritorio.click_por_texto('1')") -> AutomationResult:
    return AutomationResult(success=False, message=mensaje, data={"acciones": acciones})


def _exito() -> AutomationResult:
    return AutomationResult(success=True)


RESPUESTA = """DIAGNOSTICO: el botón se buscaba por su glifo y no por su nombre de accesibilidad.
CAMBIOS: cambiado click_por_texto('1') por escribir('1')
PRACTICA: en la Calculadora usa el teclado, no clics por glifo.

```python
CODIGO_NUEVO = 1
```
"""


@pytest.fixture
def sin_efectos(monkeypatch, tmp_path):
    """Aísla disco, API key y el archivo de prácticas."""
    guardado: dict = {}
    monkeypatch.setattr("engine.autocorreccion.tiene_api_key", lambda: True)
    monkeypatch.setattr("engine.autocorreccion.leer_codigo", lambda n: guardado.get(n, "CODIGO_VIEJO = 1"))
    monkeypatch.setattr(
        "engine.autocorreccion.guardar_automatizacion",
        lambda n, c, *a, **k: guardado.__setitem__(n, c),
    )
    monkeypatch.setattr("engine.autocorreccion.obtener", lambda n: _SpecFalso())
    monkeypatch.setattr("engine.autocorreccion.CARPETA_REPARACIONES", tmp_path / "reparaciones")
    anotadas: list[tuple] = []
    monkeypatch.setattr(
        "engine.practicas.anotar", lambda p, a, e="": (anotadas.append((p, a, e)), True)[1]
    )
    return {"guardado": guardado, "anotadas": anotadas}


def _con_respuesta(monkeypatch, *respuestas):
    """Sustituye GeminiClient por uno que devuelve respuestas preparadas.

    Devuelve un `RespuestaGemini` de verdad, no una cadena: el doble tiene
    que respetar el contrato del cliente real. Cuando devolvia un str, las
    pruebas pasaban y la ejecucion real moria con
    `TypeError: expected string or bytes-like object, got 'RespuestaGemini'`
    -- un doble mas comodo que el original no prueba nada.
    """
    from core.gemini_client import RespuestaGemini

    pendientes = list(respuestas)

    class _ClienteFalso:
        def __init__(self, *a, **k):
            pass

        def generar(self, mensaje, capturas=(), **k):
            _ClienteFalso.ultimo_prompt = mensaje
            _ClienteFalso.ultimas_capturas = list(capturas)
            return RespuestaGemini(texto=pendientes.pop(0), modelo="doble")

    monkeypatch.setattr("engine.autocorreccion.GeminiClient", _ClienteFalso)
    return _ClienteFalso


# ------------------------------------------------------------ camino feliz


def test_si_funciona_a_la_primera_no_se_llama_a_gemini(sin_efectos, monkeypatch) -> None:
    cliente = _con_respuesta(monkeypatch)  # sin respuestas: llamarlo reventaría
    runner = _RunnerFalso(_exito())

    reparacion = Autocorrector(runner).ejecutar(_SpecFalso())

    assert reparacion.exito
    assert reparacion.intentos == []
    assert not reparacion.reparada
    assert "no hubo nada que reparar" in reparacion.resumen()
    assert not hasattr(cliente, "ultimo_prompt")


def test_falla_una_vez_se_repara_y_reanuda(sin_efectos, monkeypatch) -> None:
    _con_respuesta(monkeypatch, RESPUESTA)
    runner = _RunnerFalso(_fallo("ElementNotFoundError: '1'"), _exito())

    reparacion = Autocorrector(runner).ejecutar(_SpecFalso())

    assert reparacion.exito and reparacion.reparada
    assert len(runner.llamadas) == 2, "tiene que volver a ejecutar tras el arreglo"
    assert sin_efectos["guardado"]["mi_proceso"].strip() == "CODIGO_NUEVO = 1"
    intento = reparacion.intentos[0]
    assert intento.aplicado
    assert "accesibilidad" in intento.diagnostico
    assert intento.cambios


def test_cada_intento_deja_su_propia_captura(sin_efectos, monkeypatch) -> None:
    """Sin etiquetas distintas, el intento 2 pisaría la captura del 1 --
    y comparar el antes y el después es justo lo que hace falta."""
    _con_respuesta(monkeypatch, RESPUESTA, RESPUESTA.replace("CODIGO_NUEVO = 1", "CODIGO_NUEVO = 2"))
    runner = _RunnerFalso(_fallo("a"), _fallo("b"), _exito())

    Autocorrector(runner).ejecutar(_SpecFalso())

    etiquetas = [ll["etiqueta"] for ll in runner.llamadas]
    assert etiquetas == ["", "_intento2", "_intento3"]
    assert len(set(etiquetas)) == len(etiquetas), "ninguna captura debe pisar a otra"


def test_siempre_se_pasa_una_bitacora_al_runner(sin_efectos, monkeypatch) -> None:
    _con_respuesta(monkeypatch)
    runner = _RunnerFalso(_exito())

    Autocorrector(runner).ejecutar(_SpecFalso())

    assert runner.llamadas[0]["bitacora"] is not None


# --------------------------------------------------------- cuando no sale


def test_el_tope_de_intentos_se_respeta(sin_efectos, monkeypatch) -> None:
    respuestas = [RESPUESTA.replace("CODIGO_NUEVO = 1", f"CODIGO_NUEVO = {i}") for i in range(9)]
    _con_respuesta(monkeypatch, *respuestas)
    runner = _RunnerFalso(*[_fallo(f"fallo {i}") for i in range(9)])

    reparacion = Autocorrector(runner, max_intentos=5).ejecutar(_SpecFalso())

    assert not reparacion.exito
    assert len(runner.llamadas) == 5, "cinco ejecuciones, ni una más"
    assert "No se pudo reparar" in reparacion.resumen()


def test_no_se_pueden_pedir_mas_de_cinco_intentos(sin_efectos, monkeypatch) -> None:
    """El tope es del sistema, no una sugerencia: cada intento cuesta una
    ejecución real sobre las apps del usuario y una llamada de pago."""
    # Respuestas DISTINTAS: con arreglos idénticos saltaría antes el
    # guardia de "no reintentes con el mismo código", y esta prueba mide
    # el tope, no ese guardia.
    _con_respuesta(monkeypatch, *[RESPUESTA.replace("= 1", f"= {i}") for i in range(20)])
    runner = _RunnerFalso(*[_fallo("x")] * 20)

    Autocorrector(runner, max_intentos=99).ejecutar(_SpecFalso())

    assert len(runner.llamadas) == MAX_INTENTOS


def test_un_arreglo_identico_corta_el_ciclo(sin_efectos, monkeypatch) -> None:
    """Insistir con un arreglo que no cambia nada solo gasta cuota."""
    identico = RESPUESTA.replace("CODIGO_NUEVO = 1", "CODIGO_VIEJO = 1")
    _con_respuesta(monkeypatch, identico)
    runner = _RunnerFalso(*[_fallo("x")] * 5)

    reparacion = Autocorrector(runner).ejecutar(_SpecFalso())

    assert len(runner.llamadas) == 1, "no debe reintentar con el mismo código"
    assert "idéntico" in reparacion.intentos[0].motivo_descarte


def test_una_respuesta_sin_codigo_corta_el_ciclo(sin_efectos, monkeypatch) -> None:
    _con_respuesta(monkeypatch, "DIAGNOSTICO: ni idea, lo siento.")
    runner = _RunnerFalso(*[_fallo("x")] * 5)

    reparacion = Autocorrector(runner).ejecutar(_SpecFalso())

    assert len(runner.llamadas) == 1
    assert "bloque de código" in reparacion.intentos[0].motivo_descarte


def test_un_arreglo_que_no_carga_restaura_el_codigo_anterior(sin_efectos, monkeypatch) -> None:
    """Un intento fallido no puede dejar la automatización PEOR que antes,
    con código que ni siquiera importa."""
    _con_respuesta(monkeypatch, RESPUESTA)
    intentos_guardado = []

    def _guardar_que_falla(nombre, codigo, *a, **k):
        intentos_guardado.append(codigo)
        if len(intentos_guardado) == 1:
            raise SyntaxError("no compila")
        sin_efectos["guardado"][nombre] = codigo

    monkeypatch.setattr("engine.autocorreccion.guardar_automatizacion", _guardar_que_falla)
    runner = _RunnerFalso(*[_fallo("x")] * 5)

    reparacion = Autocorrector(runner).ejecutar(_SpecFalso())

    assert "no se pudo cargar" in reparacion.intentos[0].motivo_descarte
    assert intentos_guardado[-1].strip() == "CODIGO_VIEJO = 1", "debe restaurar el original"


def test_sin_api_key_se_ejecuta_pero_no_se_repara(sin_efectos, monkeypatch) -> None:
    monkeypatch.setattr("engine.autocorreccion.tiene_api_key", lambda: False)
    _con_respuesta(monkeypatch)
    runner = _RunnerFalso(*[_fallo("x")] * 3)

    reparacion = Autocorrector(runner).ejecutar(_SpecFalso())

    assert len(runner.llamadas) == 1
    assert "API key" in reparacion.intentos[0].motivo_descarte


# ------------------------------------------------------------- prácticas


def test_solo_se_aprende_de_las_reparaciones_que_funcionaron(sin_efectos, monkeypatch) -> None:
    """Una «lección» sacada de un arreglo que no arregló nada contamina el
    prompt de todas las reparaciones siguientes."""
    _con_respuesta(monkeypatch, *[RESPUESTA.replace("= 1", f"= {i}") for i in range(6)])
    runner = _RunnerFalso(*[_fallo("x")] * 6)

    Autocorrector(runner).ejecutar(_SpecFalso())

    assert sin_efectos["anotadas"] == [], "no se aprende de un fracaso"


def test_una_reparacion_exitosa_deja_su_practica(sin_efectos, monkeypatch) -> None:
    _con_respuesta(monkeypatch, RESPUESTA)
    runner = _RunnerFalso(_fallo("x"), _exito())

    Autocorrector(runner).ejecutar(_SpecFalso())

    assert len(sin_efectos["anotadas"]) == 1
    practica, automatizacion, _error = sin_efectos["anotadas"][0]
    assert "teclado" in practica
    assert automatizacion == "mi_proceso"


def test_una_practica_vacia_no_se_anota(sin_efectos, monkeypatch) -> None:
    _con_respuesta(monkeypatch, RESPUESTA.replace(
        "PRACTICA: en la Calculadora usa el teclado, no clics por glifo.", "PRACTICA: ninguna"
    ))
    runner = _RunnerFalso(_fallo("x"), _exito())

    Autocorrector(runner).ejecutar(_SpecFalso())

    assert sin_efectos["anotadas"] == []


# ----------------------------------------------------------- el prompt


def test_el_prompt_lleva_error_acciones_codigo_y_practicas(sin_efectos, monkeypatch) -> None:
    cliente = _con_respuesta(monkeypatch, RESPUESTA)
    monkeypatch.setattr("engine.practicas.leer", lambda: "- usa el teclado cuando puedas")
    runner = _RunnerFalso(_fallo("ElementNotFoundError: '1'", "escritorio.click_por_texto('1')"), _exito())

    Autocorrector(runner).ejecutar(_SpecFalso())

    prompt = cliente.ultimo_prompt
    assert "ElementNotFoundError" in prompt
    assert "click_por_texto('1')" in prompt, "las últimas acciones son el contexto que falta"
    assert "CODIGO_VIEJO" in prompt
    assert "usa el teclado cuando puedas" in prompt, "las prácticas aprendidas se inyectan"
    assert "DIAGNOSTICO" in prompt and "PRACTICA" in prompt


def test_se_avisa_del_progreso_mientras_repara(sin_efectos, monkeypatch) -> None:
    """Una reparación tarda minutos; el silencio es indistinguible de un
    cuelgue."""
    _con_respuesta(monkeypatch, RESPUESTA)
    mensajes: list[str] = []
    runner = _RunnerFalso(_fallo("x"), _exito())

    Autocorrector(runner, on_progreso=mensajes.append).ejecutar(_SpecFalso())

    assert any("intento 1" in m for m in mensajes)
    assert any("Arreglo aplicado" in m for m in mensajes)


def test_un_fallo_pintando_el_progreso_no_rompe_la_reparacion(sin_efectos, monkeypatch) -> None:
    _con_respuesta(monkeypatch, RESPUESTA)

    def _revienta(_mensaje):
        raise RuntimeError("la interfaz se cerró")

    runner = _RunnerFalso(_fallo("x"), _exito())
    reparacion = Autocorrector(runner, on_progreso=_revienta).ejecutar(_SpecFalso())

    assert reparacion.exito


# ------------------------------------------- modelo de reserva y bitácora


def test_si_el_modelo_se_satura_se_prueba_con_otro(sin_efectos, monkeypatch) -> None:
    """Medido de verdad: gemini-3.7-flash devolvió 503 «high demand» en el
    segundo intento y la reparación se quedó a medias. El cliente ya
    reintenta sobre el MISMO modelo; esto cubre que ese modelo esté
    saturado de forma sostenida."""
    from core.gemini_client import ErrorGemini, ModeloGemini, RespuestaGemini

    monkeypatch.setattr(
        "engine.autocorreccion.listar_modelos",
        lambda: [ModeloGemini("gemini-3.8-flash"), ModeloGemini("gemini-3.5-flash")],
    )
    usados: list[str] = []

    class _ClienteQueSeSatura:
        def __init__(self, modelo=None, *a, **k):
            self.modelo = modelo

        def generar(self, mensaje, capturas=(), **k):
            usados.append(self.modelo)
            if len(usados) == 1:
                raise ErrorGemini("El modelo está saturado ahora mismo.")
            return RespuestaGemini(texto=RESPUESTA, modelo=self.modelo)

    monkeypatch.setattr("engine.autocorreccion.GeminiClient", _ClienteQueSeSatura)
    runner = _RunnerFalso(_fallo("x"), _exito())

    reparacion = Autocorrector(runner).ejecutar(_SpecFalso())

    assert reparacion.reparada, "debe repararse con el modelo de reserva"
    assert len(usados) == 2 and usados[0] != usados[1]


def test_un_error_que_no_es_saturacion_no_prueba_otros_modelos(sin_efectos, monkeypatch) -> None:
    """Una clave inválida fallaría igual en todos: recorrer la lista solo
    gastaría tiempo y cuota."""
    from core.gemini_client import ErrorGemini, ModeloGemini

    monkeypatch.setattr(
        "engine.autocorreccion.listar_modelos",
        lambda: [ModeloGemini("gemini-3.8-flash"), ModeloGemini("gemini-3.5-flash")],
    )
    llamadas: list[str] = []

    class _ClienteConClaveMala:
        def __init__(self, modelo=None, *a, **k):
            self.modelo = modelo

        def generar(self, *a, **k):
            llamadas.append(self.modelo)
            raise ErrorGemini("API key no válida o vacía.")

    monkeypatch.setattr("engine.autocorreccion.GeminiClient", _ClienteConClaveMala)
    runner = _RunnerFalso(*[_fallo("x")] * 3)

    reparacion = Autocorrector(runner).ejecutar(_SpecFalso())

    assert len(llamadas) == 1, "no debe recorrer modelos por un error que no es de saturación"
    assert "no válida" in reparacion.intentos[0].motivo_descarte


def test_la_limpieza_del_runner_no_ensucia_la_bitacora() -> None:
    """Las capturas de diagnóstico pasan por los mismos objetos espiados y
    quedaban como las ÚLTIMAS acciones, tapando lo que de verdad falló."""
    from engine.bitacora import Bitacora

    bitacora = Bitacora()
    bitacora.registrar("escritorio.click_por_texto", "'1'", ok=False, error="ElementNotFoundError")
    with bitacora.en_pausa():
        bitacora.registrar("web.screenshot_error", "'x'")
        bitacora.registrar("escritorio.capturar_pantalla", "'x_error'")
    bitacora.registrar("escritorio.esperar", "1")

    acciones = [p.accion for p in bitacora.pasos]
    assert acciones == ["escritorio.click_por_texto", "escritorio.esperar"]


def test_la_pausa_se_deshace_aunque_algo_reviente() -> None:
    from engine.bitacora import Bitacora

    bitacora = Bitacora()
    with pytest.raises(RuntimeError):
        with bitacora.en_pausa():
            raise RuntimeError("la captura falló")
    bitacora.registrar("escritorio.esperar", "1")

    assert len(bitacora.pasos) == 1, "tras el bloque hay que volver a anotar"
