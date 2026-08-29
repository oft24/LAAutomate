"""Pruebas de la logica PURA de los widgets nuevos -- describir_paso y los
ayudantes de la vista Registros. Igual que test_workers.py, aqui no se
arranca QApplication ni se construye ningun widget: lo visual se valida
con smoke offscreen, no con pytest.

describir_paso merece pruebas propias aunque "solo" sea presentacion: es
lo que un humano lee EN VIVO para decidir si la grabacion va bien o hay
que abortarla. Si etiquetara mal un paso de credencial, alguien podria
creer que su contraseña quedo escrita en el .py (o al reves, que se grabo
cuando no).
"""
from __future__ import annotations

from app.widgets.grabacion import describir_paso
from app.windows.logs_view import LogsView


# --------------------------------------------------------- describir_paso


def test_conectar_por_clase_se_distingue_de_conectar_por_titulo() -> None:
    llamada, detalle, _ = describir_paso({"tipo": "conectar", "modo": "clase", "valor": "Shell_TrayWnd"})
    assert llamada == "conectar_por_clase"
    assert detalle == "Shell_TrayWnd"

    llamada, detalle, _ = describir_paso({"tipo": "conectar", "modo": "titulo", "valor": "Bloc de notas"})
    assert llamada == "conectar_por_titulo"
    assert detalle == "Bloc de notas"


def test_conectar_tras_revinculacion_lo_dice() -> None:
    """La revinculacion es la decision mas consecuente que toma la
    grabadora sola (empezo a confiar en OTRA ventana). Tiene que verse en
    el paso, no solo en un contador aparte."""
    _llamada, detalle, _ = describir_paso(
        {"tipo": "conectar", "modo": "titulo", "valor": "Sesion", "tras_rebind": True}
    )
    assert "revinculación" in detalle


def test_click_muestra_texto_tipo_y_desambiguacion() -> None:
    llamada, detalle, _ = describir_paso(
        {"tipo": "click", "texto": "Aceptar", "control_tipo": "Button", "found_index": 2}
    )
    assert llamada == "click_por_texto"
    assert "Aceptar" in detalle
    assert "Button" in detalle
    assert "#2" in detalle


def test_found_index_cero_no_se_pierde() -> None:
    """found_index=0 es un indice valido (el PRIMER control que coincide),
    no 'sin indice' -- un `if paso.get('found_index')` lo tiraria."""
    _llamada, detalle, _ = describir_paso(
        {"tipo": "click", "texto": "OK", "control_tipo": "Button", "found_index": 0}
    )
    assert "#0" in detalle


def test_click_password_se_marca_sensible_y_no_lleva_valor() -> None:
    llamada, detalle, sensible = describir_paso(
        {"tipo": "click_password", "x": 354, "y": 88, "control_tipo": "Edit"}
    )
    assert llamada == "click_en"
    assert sensible is True
    assert "354, 88" in detalle
    assert "contraseña" in detalle


def test_escribir_credencial_dice_que_el_valor_nunca_se_capturo() -> None:
    llamada, detalle, sensible = describir_paso({"tipo": "escribir_credencial"})
    assert llamada == "escribir"
    assert sensible is True
    assert "nunca se capturó" in detalle


def test_escribir_normal_no_es_sensible_y_muestra_el_valor() -> None:
    llamada, detalle, sensible = describir_paso({"tipo": "escribir", "valor": "hola mundo"})
    assert (llamada, detalle, sensible) == ("escribir", "hola mundo", False)


def test_navegacion_repetida_muestra_el_contador() -> None:
    _llamada, detalle, _ = describir_paso({"tipo": "tecla_navegacion", "tecla": "DOWN", "veces": 5})
    assert detalle == "{DOWN 5}"

    _llamada, detalle, _ = describir_paso({"tipo": "tecla_navegacion", "tecla": "UP"})
    assert detalle == "{UP}"


def test_tab_y_enter_muestran_el_atajo_que_van_a_generar() -> None:
    assert describir_paso({"tipo": "tecla_tab"})[0] == 'atajo("{TAB}")'
    assert describir_paso({"tipo": "tecla_enter"})[0] == 'atajo("{ENTER}")'


def test_pasos_de_la_grabadora_web_tambien_se_describen() -> None:
    assert describir_paso({"tipo": "ir_a", "url": "https://portal.interno"})[:2] == (
        "ir_a",
        "https://portal.interno",
    )


def test_tipo_desconocido_no_revienta() -> None:
    """La lista se dibuja en vivo, cada 500 ms, sobre pasos que otro hilo
    esta agregando. Un tipo nuevo (o un paso a medio construir) no puede
    tumbar la vista entera."""
    llamada, detalle, sensible = describir_paso({"tipo": "algo_que_no_existe"})
    assert (llamada, detalle, sensible) == ("algo_que_no_existe", "", False)

    llamada, _detalle, _ = describir_paso({})
    assert llamada == "?"


def test_cada_tipo_que_emite_la_grabadora_muestra_la_llamada_que_va_a_generar() -> None:
    """Guardia contra un tipo de paso nuevo que se agregue a la grabadora
    y se olvide aqui: saldria en la lista en vivo con su nombre interno
    crudo. La llamada mostrada tiene que ser LA MISMA que
    generar_codigo_escritorio va a escribir en el .py -- si divergen, lo
    que el usuario revisa mientras graba no es lo que va a correr."""
    esperado = {
        "conectar": "conectar_por_titulo",  # modo 'clase' se cubre en su propia prueba
        "click": "click_por_texto",
        "click_coordenada": "click_en",
        "click_password": "click_en",
        "escribir": "escribir",
        "escribir_credencial": "escribir",
        "tecla_enter": 'atajo("{ENTER}")',
        "tecla_tab": 'atajo("{TAB}")',
        "tecla_navegacion": "atajo",
    }
    for tipo, llamada_esperada in esperado.items():
        llamada, _detalle, _sensible = describir_paso({"tipo": tipo, "valor": "", "x": 0, "y": 0})
        assert llamada == llamada_esperada, f"el paso {tipo!r} se describe como {llamada!r}"


# --------------------------------------------------- ayudantes de Registros


def test_tamano_legible_cambia_de_unidad() -> None:
    assert LogsView._tamano_legible(512) == "512 B"
    assert LogsView._tamano_legible(2048) == "2 KB"
    assert LogsView._tamano_legible(5 * 1024 * 1024) == "5.0 MB"


def test_tiene_errores_detecta_error_y_critical(tmp_path) -> None:
    con_error = tmp_path / "con_error.log"
    con_error.write_text("INFO | arranco\nERROR | ElementNotFoundError\n", encoding="utf-8")
    assert LogsView._tiene_errores(con_error) is True

    critico = tmp_path / "critico.log"
    critico.write_text("CRITICAL | se cayo todo\n", encoding="utf-8")
    assert LogsView._tiene_errores(critico) is True

    limpio = tmp_path / "limpio.log"
    limpio.write_text("INFO | todo bien\nWARNING | ojo\n", encoding="utf-8")
    assert LogsView._tiene_errores(limpio) is False


def test_tiene_errores_no_revienta_con_un_archivo_que_no_existe(tmp_path) -> None:
    """La lista se relee mientras las automatizaciones escriben: un log
    puede desaparecer entre el glob y la lectura."""
    assert LogsView._tiene_errores(tmp_path / "no_existe.log") is False
