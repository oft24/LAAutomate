"""El contexto que el Asistente necesita para CORREGIR, no solo para crear.

El chip "Explicar un error" pegaba una plantilla vacía y dejaba al usuario
buscando el traceback a mano en `logs/`. Estas pruebas cubren lo que ahora
carga por él: la cola del log, la captura del momento del fallo y —si la
automatización ni siquiera importa— la causa de ese ImportError.
"""
from __future__ import annotations

from engine.diagnostico import MAX_CARACTERES_LOG, contexto_de_fallo, prompt_de_correccion


def test_lee_el_log_y_encuentra_la_captura(tmp_path) -> None:
    (tmp_path / "mi_proceso.log").write_text("linea 1\nERROR boom\n", encoding="utf-8")
    (tmp_path / "screenshots").mkdir()
    (tmp_path / "screenshots" / "mi_proceso_error.png").write_bytes(b"png")

    log, captura = contexto_de_fallo("mi_proceso", tmp_path)

    assert "boom" in log
    assert captura is not None and captura.name == "mi_proceso_error.png"


def test_sin_nada_en_disco_no_revienta(tmp_path) -> None:
    log, captura = contexto_de_fallo("nunca_corrio", tmp_path)
    assert log == ""
    assert captura is None


def test_un_log_gigante_se_recorta_por_la_cola(tmp_path) -> None:
    """El traceback está al final; mandar 40 MB de log gastaría la ventana
    de contexto en ejecuciones de la semana pasada."""
    (tmp_path / "grande.log").write_text("x" * 50_000 + "\nEL FINAL\n", encoding="utf-8")

    log, _ = contexto_de_fallo("grande", tmp_path)

    assert len(log) <= MAX_CARACTERES_LOG
    assert "EL FINAL" in log


def test_el_punto_en_el_nombre_se_traduce_igual_que_en_el_logger(tmp_path) -> None:
    """core.logger escribe `engine_runner.log`, no `engine.runner.log`."""
    (tmp_path / "a_b.log").write_text("hola", encoding="utf-8")
    log, _ = contexto_de_fallo("a.b", tmp_path)
    assert log == "hola"


# ------------------------------------------------------------ el prompt


def test_el_prompt_pide_la_causa_real_y_el_archivo_completo() -> None:
    texto = prompt_de_correccion("mi_proceso", "ERROR boom")

    assert "CAUSA REAL" in texto
    assert "completo" in texto
    assert "boom" in texto
    assert "```python" in texto


def test_el_error_de_import_va_antes_que_el_log() -> None:
    """Si ni siquiera importa, ESA es la causa: el log es de la última vez
    que sí corrió, un fallo distinto que ya no es el problema."""
    texto = prompt_de_correccion("mi_proceso", "fallo viejo", "SyntaxError: '(' was never closed")

    assert texto.index("SyntaxError") < texto.index("fallo viejo")


def test_sin_log_se_pide_que_diga_lo_que_supone() -> None:
    texto = prompt_de_correccion("mi_proceso", "")
    assert "suponiendo" in texto


def test_el_prompt_lleva_los_fallos_medidos_de_este_proyecto() -> None:
    """No son consejos genéricos: salen de fallos reales reproducidos
    contra la Calculadora de Windows en español."""
    texto = prompt_de_correccion("mi_proceso", "ERROR")

    assert "Multiplicar por" in texto, "el nombre de accesibilidad real"
    assert "click_por_tipo('Edit')" in texto
    assert "Bóveda" in texto
