"""Pruebas de la logica pura de la Grabadora de escritorio -- no requieren
mouse/teclado real ni ninguna app abierta, solo cubren generar_codigo_escritorio
y _depurar_pasos."""
from __future__ import annotations

import ast
from unittest.mock import MagicMock, patch

import py_compile
import tempfile
from pathlib import Path

import pytest

from pywinauto.findwindows import ElementNotFoundError as _NoEncontrado

from engine.actions.desktop_recorder import GrabadoraEscritorio, _depurar_pasos, generar_codigo_escritorio


class _LoggerFalso:
    def info(self, *a, **k):
        pass

    def debug(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass


def _compila_sin_error(codigo: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(codigo)
        ruta = tmp.name
    try:
        py_compile.compile(ruta, doraise=True)
    finally:
        Path(ruta).unlink(missing_ok=True)


def test_generar_codigo_escapa_comillas_y_backslashes() -> None:
    pasos = [
        {"tipo": "conectar", "modo": "titulo", "valor": 'Bloc de notas "raro"'},
        {"tipo": "escribir", "valor": 'texto con "comillas" y \\backslash\\'},
    ]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)
    assert codigo.count("def ejecutar(self)") == 1


def test_generar_codigo_click_con_salto_de_linea_en_texto_no_inyecta_codigo() -> None:
    """Mismo hallazgo critico que en la grabadora web: el texto de un
    control (window_text) puede traer saltos de linea reales si la app
    los pone ahi -- no debe poder inyectar una sentencia de modulo."""
    payload_malicioso = "Enviar\nimport os\nos.mkdir('nunca_deberia_crearse')\ndef _cierre():"

    pasos = [
        {"tipo": "conectar", "modo": "titulo", "valor": "Alguna App"},
        {"tipo": "click", "texto": payload_malicioso, "control_tipo": "Button"},
    ]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)

    _compila_sin_error(codigo)

    arbol = ast.parse(codigo)
    definiciones_de_clase = [n for n in arbol.body if isinstance(n, ast.ClassDef)]
    assert len(definiciones_de_clase) == 1, "nada debe quedar inyectado a nivel de modulo"

    metodo = next(n for n in definiciones_de_clase[0].body if isinstance(n, ast.FunctionDef))
    tipos = [type(n) for n in metodo.body]
    assert tipos == [ast.Expr, ast.Expr, ast.Return], f"sentencias inesperadas en el body: {tipos}"

    linea_click = next(l for l in codigo.split("\n") if "self.escritorio.click_por_texto" in l)
    assert "import os" not in linea_click.split("(", 1)[0]


def test_generar_codigo_control_tipo_con_salto_de_linea_no_rompe_el_comentario() -> None:
    """control_tipo viene de element_info.control_type (un enum de UIA),
    pero por si acaso trajera algo raro, tambien se sanea antes de usarlo
    en el comentario."""
    pasos = [
        {"tipo": "conectar", "modo": "titulo", "valor": "App"},
        {"tipo": "click", "texto": "Aceptar", "control_tipo": "Button\nimport os"},
    ]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)
    for linea in codigo.split("\n"):
        if "self.escritorio.click_por_texto" in linea:
            continue
        assert "import os" not in linea


def test_generar_codigo_valida_nombre() -> None:
    with pytest.raises(ValueError):
        generar_codigo_escritorio("123_invalido", [])


def test_depurar_pasos_conecta_una_sola_vez_a_la_misma_ventana() -> None:
    pasos = [
        {"tipo": "conectar", "modo": "titulo", "valor": "Notepad"},
        {"tipo": "conectar", "modo": "titulo", "valor": "Notepad"},
        {"tipo": "click", "texto": "Archivo", "control_tipo": "MenuItem"},
    ]
    limpios = _depurar_pasos(pasos)
    assert sum(1 for p in limpios if p["tipo"] == "conectar") == 1


def test_depurar_pasos_escribir_se_queda_con_el_ultimo_valor() -> None:
    pasos = [
        {"tipo": "escribir", "valor": "ho"},
        {"tipo": "escribir", "valor": "hola"},
    ]
    limpios = _depurar_pasos(pasos)
    assert len(limpios) == 1
    assert limpios[0]["valor"] == "hola"


def test_generar_codigo_escapa_titulo_con_caracteres_de_regex() -> None:
    """Un titulo de ventana con parentesis (comun: 'Documento (recuperado)')
    no debe tratarse como patron de regex sin escapar -- si no, buscar esos
    parentesis literales fallaria en tiempo de reproduccion."""
    pasos = [{"tipo": "conectar", "modo": "titulo", "valor": "Documento (recuperado) - Bloc de notas"}]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)

    import re as re_mod

    linea = next(l for l in codigo.split("\n") if "conectar_por_titulo" in l)
    # el literal de Python en esa linea debe ser el titulo ESCAPADO para regex
    valor = linea.split("conectar_por_titulo(", 1)[1].rsplit(")", 1)[0]
    patron_generado = eval(valor)  # noqa: S307 - es un literal de cadena controlado por la prueba
    assert patron_generado == re_mod.escape("Documento (recuperado) - Bloc de notas")
    assert re_mod.match(patron_generado, "Documento (recuperado) - Bloc de notas")


def test_grabadora_ignora_clicks_fuera_de_la_ventana_objetivo() -> None:
    """Prueba de regresion DIRECTA del incidente real: un click fuera de
    la ventana fijada por el primer click no debe leerse ni grabarse --
    ni siquiera su texto, para que jamas pueda filtrarse contenido de
    otra ventana no relacionada."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as win32gui_falso, patch.object(
        GrabadoraEscritorio, "_control_en", side_effect=[("BotonA", "Button", False), ("BotonB", "Button", False)]
    ):
        win32gui_falso.WindowFromPoint.side_effect = [111, 222]
        win32gui_falso.GetAncestor.side_effect = [111, 222]
        win32gui_falso.GetWindowText.side_effect = ["Ventana A", "Ventana B (no relacionada)"]
        win32gui_falso.ScreenToClient.return_value = (10, 10)
        win32gui_falso.IsWindow.return_value = True  # la ventana A SIGUE abierta -- no debe revincular

        grabadora._al_click(10, 10, None, True)  # primer click -> fija la ventana 111 como objetivo
        grabadora._al_click(50, 50, None, True)  # click en OTRA ventana (222) -> debe ignorarse por completo

    assert grabadora._hwnd_objetivo == 111
    assert grabadora._clicks_ignorados_fuera_de_ventana == 1
    assert grabadora._ventanas_revinculadas == 0

    clicks = [p for p in grabadora.pasos if p["tipo"] == "click"]
    assert len(clicks) == 1
    assert clicks[0]["texto"] == "BotonA"
    # el texto/control de la ventana no relacionada JAMAS debe aparecer en los pasos
    assert not any("BotonB" in str(p) or "no relacionada" in str(p) for p in grabadora.pasos)


def test_grabadora_ignora_tecleo_cuando_el_foco_sale_de_la_ventana_objetivo() -> None:
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True
    grabadora._hwnd_objetivo = 111
    grabadora._ultimo_click_editable = True

    with patch("engine.actions.desktop_recorder.win32gui") as win32gui_falso:
        win32gui_falso.GetForegroundWindow.return_value = 222  # otra ventana tiene el foco

        class _TeclaFalsa:
            char = "x"

        grabadora._al_tecla(_TeclaFalsa())

    assert grabadora._buffer_texto == ""  # no se debio bufferear nada


def test_generar_codigo_sin_pasos_no_falla() -> None:
    codigo = generar_codigo_escritorio("vacia_de_prueba", [])
    _compila_sin_error(codigo)
    assert "no se capturó ningún paso" in codigo


def test_generar_codigo_conecta_por_clase_cuando_no_hay_titulo() -> None:
    """Ventanas sin titulo (ej. la barra de tareas, clase Shell_TrayWnd)
    deben conectarse por su nombre de clase de Win32 en vez de titulo."""
    pasos = [
        {"tipo": "conectar", "modo": "clase", "valor": "Shell_TrayWnd"},
        {"tipo": "click", "texto": "Buscar", "control_tipo": "Button"},
    ]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)
    assert "self.escritorio.conectar_por_clase('Shell_TrayWnd')" in codigo
    assert "conectar_por_titulo" not in codigo


def test_grabadora_usa_clase_cuando_la_ventana_no_tiene_titulo() -> None:
    """Prueba de regresion DIRECTA de un caso real: un click en una
    ventana SIN titulo (ej. la barra de tareas) nunca debia dejar de
    grabar el paso 'conectar' -- sin el, el codigo generado fallaba en
    reproduccion con 'llama iniciar_o_conectar() antes de interactuar'."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as win32gui_falso, patch.object(
        GrabadoraEscritorio, "_control_en", return_value=("Buscar", "Button", False)
    ):
        win32gui_falso.WindowFromPoint.return_value = 111
        win32gui_falso.GetAncestor.return_value = 111
        win32gui_falso.GetWindowText.return_value = ""  # sin titulo, ej. Shell_TrayWnd
        win32gui_falso.GetClassName.return_value = "Shell_TrayWnd"
        win32gui_falso.ScreenToClient.return_value = (10, 10)

        grabadora._al_click(10, 10, None, True)

    conectar = [p for p in grabadora.pasos if p["tipo"] == "conectar"]
    assert conectar == [{"tipo": "conectar", "modo": "clase", "valor": "Shell_TrayWnd"}]

    codigo = generar_codigo_escritorio("mi_prueba", grabadora.pasos)
    _compila_sin_error(codigo)
    assert "self.escritorio.conectar_por_clase('Shell_TrayWnd')" in codigo


def test_generar_codigo_click_sin_texto_usa_coordenada() -> None:
    """Un control sin texto identificable (ej. el lienzo de un escritorio
    remoto en un cliente VNC) no debe generar click_por_texto('') -- eso
    matchearia CUALQUIER control sin titulo. Debe usar coordenadas."""
    pasos = [
        {"tipo": "conectar", "modo": "titulo", "valor": "Visor VNC"},
        {"tipo": "click_coordenada", "x": 120, "y": 340, "control_tipo": "Pane"},
    ]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)
    assert "self.escritorio.click_en(120, 340)" in codigo
    assert "click_por_texto('')" not in codigo


def test_grabadora_click_sin_texto_graba_coordenada_no_texto_vacio() -> None:
    """Prueba de regresion de un caso real: un click en un control 'Pane'
    sin texto (ej. dentro de la barra de tareas) se grababa como
    click_por_texto('') -- ahora debe grabarse por coordenada."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as win32gui_falso, patch.object(
        GrabadoraEscritorio, "_control_en", return_value=("", "Pane", False)
    ):
        win32gui_falso.WindowFromPoint.return_value = 111
        win32gui_falso.GetAncestor.return_value = 111
        win32gui_falso.GetWindowText.return_value = "Alguna Ventana"
        win32gui_falso.ScreenToClient.return_value = (42, 84)

        grabadora._al_click(500, 700, None, True)

    clicks = [p for p in grabadora.pasos if p["tipo"] in ("click", "click_coordenada")]
    assert clicks == [{"tipo": "click_coordenada", "x": 42, "y": 84, "control_tipo": "Pane"}]


def _procesar_desambiguacion_pendiente(grabadora) -> None:
    """La desambiguacion corre en un hilo aparte que solo arranca en
    iniciar(); estas pruebas no llaman a iniciar(), asi que se drena la
    cola a mano -- equivale exactamente a lo que hace _bucle_desambiguacion."""
    while not grabadora._cola_desambiguacion.empty():
        tarea = grabadora._cola_desambiguacion.get_nowait()
        if tarea is not None:
            grabadora._resolver_ambiguedad(grabadora.pasos, *tarea)


def _grabar_un_click_con_coincidencias(indice, total, texto="UltraVNC Viewer", tipo="Button"):
    """Graba UN click cuyo (texto, tipo) hace `total` matches, siendo
    `indice` el clickeado -- _indice_entre_coincidencias se mockea porque
    consultar UI Automation de verdad requeriria una app real abierta."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch.object(
        GrabadoraEscritorio, "_control_en", return_value=(texto, tipo, False)
    ), patch.object(
        GrabadoraEscritorio, "_indice_entre_coincidencias", return_value=(indice, total)
    ):
        w.WindowFromPoint.return_value = 111
        w.GetAncestor.return_value = 111
        w.GetWindowText.return_value = ""  # barra de tareas: sin titulo -> conecta por clase
        w.GetClassName.return_value = "Shell_SecondaryTrayWnd"
        w.ScreenToClient.return_value = (30, 40)

        grabadora._al_click(1500, 1050, None, True)
        _procesar_desambiguacion_pendiente(grabadora)

    return grabadora


def test_click_con_texto_unico_no_graba_found_index() -> None:
    """Si el texto+tipo ya identifican un solo control, el paso NO debe
    llevar found_index -- el codigo generado se mantiene legible."""
    grabadora = _grabar_un_click_con_coincidencias(indice=None, total=1)

    clicks = [p for p in grabadora.pasos if p["tipo"].startswith("click")]
    assert clicks == [{"tipo": "click", "texto": "UltraVNC Viewer", "control_tipo": "Button"}]
    assert "found_index" not in clicks[0]


def test_click_con_texto_ambiguo_graba_cual_se_clickeo() -> None:
    """Regresion del bug real: el icono de una app anclada aparece
    DUPLICADO en la barra de tareas de un segundo monitor
    (Shell_SecondaryTrayWnd) con texto y control_type identicos -- el
    codigo grabado reventaba al reproducir con ElementAmbiguousError.
    Ahora se graba CUAL de los que hacen match se clickeo."""
    grabadora = _grabar_un_click_con_coincidencias(indice=1, total=2)

    clicks = [p for p in grabadora.pasos if p["tipo"].startswith("click")]
    assert clicks == [
        {"tipo": "click", "texto": "UltraVNC Viewer", "control_tipo": "Button", "found_index": 1}
    ]

    codigo = generar_codigo_escritorio("mi_prueba", grabadora.pasos)
    _compila_sin_error(codigo)
    assert (
        "self.escritorio.click_por_texto('UltraVNC Viewer', control_type='Button', found_index=1)"
        in codigo
    )


def test_click_ambiguo_sin_indice_identificable_cae_a_coordenada() -> None:
    """Si hay varias coincidencias y NO se pudo determinar cual se clickeo,
    grabar el texto produciria codigo irreproducible
    (ElementAmbiguousError) -- se cae a coordenadas, que siempre
    identifican un solo punto."""
    grabadora = _grabar_un_click_con_coincidencias(indice=None, total=3)

    clicks = [p for p in grabadora.pasos if p["tipo"].startswith("click")]
    assert clicks == [{"tipo": "click_coordenada", "x": 30, "y": 40, "control_tipo": "Button"}]

    codigo = generar_codigo_escritorio("mi_prueba", grabadora.pasos)
    _compila_sin_error(codigo)
    assert "click_por_texto" not in codigo
    assert "self.escritorio.click_en(30, 40)" in codigo


def test_el_callback_no_desambigua_lo_delega_a_otro_hilo() -> None:
    """Regresion de un riesgo real medido: desambiguar cuesta ~250-400 ms
    de consultas UIA, y en Windows pynput despacha el callback en el MISMO
    hilo que sirve al hook de bajo nivel; bloquearlo hace que Windows deje
    de entregar eventos (LowLevelHooksTimeout, 300 ms) y la grabación se
    muere en silencio. El callback debe volver de inmediato: el paso queda
    grabado y la desambiguación encolada, no ejecutada."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch.object(
        GrabadoraEscritorio, "_control_en", return_value=("Campo", "Edit", False)
    ), patch.object(GrabadoraEscritorio, "_indice_entre_coincidencias") as desambiguar_falso:
        w.WindowFromPoint.return_value = 111
        w.GetAncestor.return_value = 111
        w.GetWindowText.return_value = "Ventana"
        w.ScreenToClient.return_value = (5, 5)

        grabadora._al_click(10, 10, None, True)

        # el callback NO hizo la consulta cara...
        desambiguar_falso.assert_not_called()

    # ...pero sí dejó el paso grabado y la bandera de tecleo lista (si se
    # retrasara, el texto tecleado justo despues del click se perdería)
    assert any(p["tipo"] == "click" for p in grabadora.pasos)
    assert grabadora._ultimo_click_editable is True
    assert grabadora._cola_desambiguacion.qsize() == 1


def test_paso_ambiguo_se_convierte_en_coordenada_sin_perder_su_posicion() -> None:
    """Al no poder desambiguar, el paso ya grabado se REEMPLAZA en su
    misma posicion -- no se agrega uno nuevo al final, porque eso
    alteraria el orden de la secuencia grabada."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch.object(
        GrabadoraEscritorio, "_control_en", side_effect=[("Primero", "Button", False), ("Ambiguo", "Button", False)]
    ), patch.object(
        GrabadoraEscritorio, "_indice_entre_coincidencias", side_effect=[(None, 1), (None, 3)]
    ):
        w.WindowFromPoint.return_value = 111
        w.GetAncestor.return_value = 111
        w.GetWindowText.return_value = "Ventana"
        w.ScreenToClient.return_value = (7, 8)

        grabadora._al_click(10, 10, None, True)   # click normal
        grabadora._al_click(20, 20, None, True)   # click ambiguo -> coordenada
        _procesar_desambiguacion_pendiente(grabadora)

    clicks = [p for p in grabadora.pasos if p["tipo"].startswith("click")]
    assert clicks == [
        {"tipo": "click", "texto": "Primero", "control_tipo": "Button"},
        {"tipo": "click_coordenada", "x": 7, "y": 8, "control_tipo": "Button"},
    ]


def test_resolver_ambiguedad_no_muta_el_dict_que_detener_ya_entrego() -> None:
    """detener() entrega copias de los pasos; la desambiguación que llegue
    tarde debe REEMPLAZAR el elemento de la lista, nunca mutar el dict que
    alguien ya tiene en la mano -- si lo mutara a medias (clear()+update())
    quien lo esté traduciendo a código vería un paso sin 'tipo' y
    reventaría con KeyError."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    paso = {"tipo": "click", "texto": "Ambiguo", "control_tipo": "Button"}
    grabadora.pasos = [paso]
    referencia_externa = paso  # como si detener() ya lo hubiera entregado

    with patch.object(GrabadoraEscritorio, "_indice_entre_coincidencias", return_value=(None, 2)):
        grabadora._resolver_ambiguedad(grabadora.pasos, paso, 111, "Ambiguo", "Button", 1, 2, 7, 8)

    assert referencia_externa == {"tipo": "click", "texto": "Ambiguo", "control_tipo": "Button"}
    assert grabadora.pasos == [{"tipo": "click_coordenada", "x": 7, "y": 8, "control_tipo": "Button"}]


def test_total_cero_conserva_el_click_por_texto_no_lo_degrada() -> None:
    """total=0 NO debe degradar el paso a coordenadas. La consulta corre
    cientos de ms DESPUES del click, cuando la app ya reacciono: un boton
    que alterna su texto ("Conectar" -> "Desconectar") da total=0 aunque el
    control SI existia al clickear -- y volvera a existir al reproducir,
    que llega con la app en el estado PRE-click. Degradar aqui convertia un
    click_por_texto correcto en coordenadas de forma no determinista."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    paso = {"tipo": "click", "texto": "Conectar", "control_tipo": "Button"}
    grabadora.pasos = [paso]

    with patch.object(GrabadoraEscritorio, "_indice_entre_coincidencias", return_value=(None, 0)):
        grabadora._resolver_ambiguedad(grabadora.pasos, paso, 111, "Conectar", "Button", 1, 2, 9, 4)

    assert grabadora.pasos == [{"tipo": "click", "texto": "Conectar", "control_tipo": "Button"}]


def test_fallo_transitorio_deja_el_paso_intacto() -> None:
    """Un tropiezo pasajero (la ventana se cerro a media consulta, COM
    ocupado) no debe alterar el paso ya grabado."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    paso = {"tipo": "click", "texto": "Boton", "control_tipo": "Button"}
    grabadora.pasos = [paso]

    with patch.object(
        GrabadoraEscritorio, "_indice_entre_coincidencias", side_effect=RuntimeError("COM ocupado")
    ):
        grabadora._resolver_ambiguedad(grabadora.pasos, paso, 111, "Boton", "Button", 1, 2, 9, 4)

    assert grabadora.pasos == [{"tipo": "click", "texto": "Boton", "control_tipo": "Button"}]


def _elemento_falso(left, right, top=0, bottom=100):
    """UIAElementInfo falso: rectangle es una PROPIEDAD, no un metodo."""
    return MagicMock(rectangle=MagicMock(left=left, right=right, top=top, bottom=bottom))


def _parchar_busqueda(elementos):
    """Sustituye la busqueda de pywinauto por una lista fija, y deja
    Application().connect().window().wrapper_object() encadenado."""
    app = MagicMock()
    app.connect.return_value = app
    modulo = MagicMock(
        Application=MagicMock(return_value=app),
        findwindows=MagicMock(find_elements=MagicMock(return_value=elementos)),
    )
    return patch.dict("sys.modules", {"pywinauto": modulo}), modulo


def test_indice_entre_coincidencias_devuelve_none_cuando_solo_hay_una() -> None:
    """Con una sola coincidencia no hace falta found_index -- debe
    devolver (None, 1) para que el codigo generado quede limpio."""
    parche, _ = _parchar_busqueda([_elemento_falso(0, 100)])
    with parche:
        indice, total = GrabadoraEscritorio._indice_entre_coincidencias(111, "Boton", "Button", 50, 50)

    assert (indice, total) == (None, 1)


def test_indice_entre_coincidencias_encuentra_el_que_contiene_el_click() -> None:
    """Con varias coincidencias, se elige la que CONTIENE el punto
    clickeado."""
    parche, _ = _parchar_busqueda([_elemento_falso(0, 100), _elemento_falso(200, 300)])
    with parche:
        indice, total = GrabadoraEscritorio._indice_entre_coincidencias(111, "Boton", "Button", 250, 50)

    assert (indice, total) == (1, 2)


def test_indice_entre_coincidencias_usa_los_mismos_criterios_que_reproduccion() -> None:
    """Regresion de un defecto confirmado ejecutando pywinauto real: la
    grabadora debe enumerar con los MISMOS criterios que usa la
    reproduccion (visible_only en su default True). Antes se usaba
    exists(), que escribe visible_only=False sobre sus propios criterios y
    hacia enumerar tambien controles fuera de pantalla -- el found_index
    grabado terminaba apuntando a otro control. Tampoco debe tocarse el
    Timings global, que comparten las automatizaciones en ejecucion."""
    from pywinauto.timings import Timings

    parche, modulo = _parchar_busqueda([_elemento_falso(0, 100), _elemento_falso(0, 100)])
    timeout_previo = Timings.window_find_timeout
    with parche:
        GrabadoraEscritorio._indice_entre_coincidencias(111, "Boton", "Button", 50, 50)

    kwargs = modulo.findwindows.find_elements.call_args.kwargs
    assert kwargs["title"] == "Boton"
    assert kwargs["control_type"] == "Button"
    assert kwargs["top_level_only"] is False
    assert "visible_only" not in kwargs  # se deja el default (True), igual que reproduccion
    assert Timings.window_find_timeout == timeout_previo  # no se toca el global


def test_indice_entre_coincidencias_respeta_el_tope_de_coincidencias() -> None:
    """Una ventana con cientos de controles del mismo texto no debe hacer
    que se recorra la lista entera."""
    muchos = [_elemento_falso(0, 10) for _ in range(50)]
    parche, _ = _parchar_busqueda(muchos)
    with parche:
        _, total = GrabadoraEscritorio._indice_entre_coincidencias(111, "Celda", "Text", 5, 5)

    assert total == 12  # _MAX_COINCIDENCIAS_A_REVISAR



def test_generar_codigo_credencial_no_escribe_password_en_texto_plano() -> None:
    """El paso 'escribir_credencial' nunca debe llevar la contraseña real
    -- el codigo generado debe usar self.credenciales.password (Boveda),
    nunca un literal."""
    pasos = [
        {"tipo": "conectar", "modo": "titulo", "valor": "Cliente VNC"},
        {"tipo": "escribir_credencial"},
    ]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)
    assert "self.escritorio.escribir(self.credenciales.password)" in codigo


def test_grabadora_detecta_campo_password_via_uia() -> None:
    """Prueba de regresion de seguridad: si el click aterriza en un campo
    marcado como password por UI Automation (CurrentIsPassword), el
    tecleo posterior NUNCA debe terminar en self._buffer_texto ni en los
    pasos como texto plano -- solo debe marcarse escribir_credencial."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as win32gui_falso, patch.object(
        GrabadoraEscritorio, "_control_en", return_value=("", "Edit", True)  # es_password=True
    ):
        win32gui_falso.WindowFromPoint.return_value = 111
        win32gui_falso.GetAncestor.return_value = 111
        win32gui_falso.GetWindowText.return_value = "Cliente VNC"
        win32gui_falso.ScreenToClient.return_value = (5, 5)

        grabadora._al_click(1, 1, None, True)

    assert grabadora._ultimo_click_es_password is True

    with patch("engine.actions.desktop_recorder.win32gui") as win32gui_falso:
        win32gui_falso.GetForegroundWindow.return_value = 111

        class _TeclaFalsa:
            def __init__(self, c):
                self.char = c

        for c in "s3cr3t0-real":
            grabadora._al_tecla(_TeclaFalsa(c))

    assert grabadora._buffer_texto == ""  # jamas se bufferea la contraseña real
    assert grabadora._se_tecleo_password is True
    assert not any("s3cr3t0" in str(p) for p in grabadora.pasos)  # jamas en los pasos ya grabados

    grabadora._flush_texto()
    assert grabadora.pasos[-1] == {"tipo": "escribir_credencial"}
    assert not any("s3cr3t0" in str(p) for p in grabadora.pasos)  # tampoco tras el flush


def test_grabadora_click_en_campo_password_ya_lleno_no_graba_su_valor() -> None:
    """Prueba de regresion CRITICA de un hallazgo real de auditoria:
    CurrentIsPassword solo le dice a lectores de pantalla que no lo
    anuncien -- NO garantiza que window_text() venga enmascarado (muchos
    Edit nativos Win32/MFC devuelven el valor real). Si el click aterriza
    en un campo de password que YA TENIA texto (typo a corregir, password
    recordado/autocompletado), ese valor jamas debe grabarse -- ni con
    repr(), el problema es capturarlo, no solo escaparlo."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as win32gui_falso, patch.object(
        GrabadoraEscritorio,
        "_control_en",
        return_value=("micontraseñareal123", "Edit", True),  # texto NO vacio + es_password=True
    ):
        win32gui_falso.WindowFromPoint.return_value = 111
        win32gui_falso.GetAncestor.return_value = 111
        win32gui_falso.GetWindowText.return_value = "Cliente VNC"
        win32gui_falso.ScreenToClient.return_value = (7, 7)

        grabadora._al_click(1, 1, None, True)

    assert not any("micontraseñareal123" in str(p) for p in grabadora.pasos)
    clicks = [p for p in grabadora.pasos if p["tipo"].startswith("click")]
    assert clicks == [{"tipo": "click_password", "control_tipo": "Edit", "x": 7, "y": 7}]

    codigo = generar_codigo_escritorio("mi_prueba", grabadora.pasos)
    _compila_sin_error(codigo)
    assert "micontraseñareal123" not in codigo


def test_generar_codigo_click_password_no_incluye_ningun_valor() -> None:
    pasos = [
        {"tipo": "conectar", "modo": "titulo", "valor": "Cliente VNC"},
        {"tipo": "click_password", "control_tipo": "Edit", "x": 335, "y": 47},
    ]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)
    assert "click_por_texto" not in codigo


def test_generar_codigo_click_password_incluye_click_en_real() -> None:
    """Antes el click sobre un campo de password SOLO generaba un
    comentario TODO (sin ejecutar ningun click real) -- el tecleo de la
    credencial que sigue caia entonces sobre el ultimo control con foco
    real (ej. el campo de usuario justo antes), no sobre el campo de
    password. Las coordenadas no son secretas (solo el valor tecleado lo
    es), asi que ahora se emite un click_en(x, y) real."""
    pasos = [
        {"tipo": "conectar", "modo": "titulo", "valor": "Cliente VNC"},
        {"tipo": "click_password", "control_tipo": "Edit", "x": 335, "y": 47},
        {"tipo": "escribir_credencial"},
    ]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)
    assert "self.escritorio.click_en(335, 47)" in codigo
    indice_click = codigo.index("click_en(335, 47)")
    indice_credencial = codigo.index("self.credenciales.password")
    assert indice_click < indice_credencial


def test_clicks_ignorados_property_expone_el_contador() -> None:
    """Antes solo se sabia el conteo de clicks ignorados al TERMINAR la
    grabacion (via log) -- expuesto como property para que la UI pueda
    avisar en vivo (util en flujos tipo login->sesion VNC, donde el
    candado de una sola ventana ignora todos los clicks posteriores)."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    assert grabadora.clicks_ignorados == 0
    grabadora._clicks_ignorados_fuera_de_ventana = 3
    assert grabadora.clicks_ignorados == 3


# ---------- revinculacion de ventana (buscar -> abrir app -> interactuar) ----------


def test_grabadora_revincula_cuando_la_ventana_objetivo_ya_no_existe() -> None:
    """Camino feliz del rebind: la ventana objetivo (111) se cierra --
    IsWindow(111) devuelve False -- y el siguiente click cae en una
    ventana NUEVA (222). Debe revincularse (no ignorarse), emitir un
    'conectar' nuevo marcado tras_rebind, y NO incrementar
    clicks_ignorados (esto no es el incidente original: la ventana vieja
    ya no existe, no es un click mal calculado con ella todavia abierta)."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch.object(
        GrabadoraEscritorio, "_control_en", side_effect=[("A", "Button", False), ("B", "Button", False)]
    ):
        w.WindowFromPoint.side_effect = [111, 222]
        w.GetAncestor.side_effect = [111, 222]
        w.IsWindow.return_value = False  # la ventana 111 ya no existe
        w.GetWindowText.side_effect = ["Ventana A", "Ventana B"]
        w.ScreenToClient.return_value = (10, 10)

        grabadora._al_click(10, 10, None, True)
        grabadora._al_click(50, 50, None, True)

    assert grabadora._hwnd_objetivo == 222
    assert grabadora._clicks_ignorados_fuera_de_ventana == 0
    assert grabadora.ventanas_revinculadas == 1

    conectar = [p for p in grabadora.pasos if p["tipo"] == "conectar"]
    assert [p["valor"] for p in conectar] == ["Ventana A", "Ventana B"]
    assert "tras_rebind" not in conectar[0]
    assert conectar[1]["tras_rebind"] is True


def test_grabadora_no_revincula_a_ventana_de_fondo_mientras_objetivo_original_existe() -> None:
    """Regresion DIRECTA del hallazgo de seguridad mas severo de la
    auditoria: aunque la propuesta de revinculacion exista, un click en
    una ventana de fondo NO relacionada mientras la ventana objetivo
    SIGUE viva debe seguir ignorandose exactamente como antes -- esto es
    el incidente original, y IsWindow(objetivo)==True debe bloquear
    cualquier revinculacion sin importar que otra ventana reciba el click."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch.object(
        GrabadoraEscritorio, "_control_en", return_value=("X", "Button", False)
    ):
        w.WindowFromPoint.side_effect = [111, 999]
        w.GetAncestor.side_effect = [111, 999]
        w.IsWindow.return_value = True  # 111 SIGUE viva
        w.GetWindowText.return_value = "Ventana A"
        w.ScreenToClient.return_value = (10, 10)

        grabadora._al_click(10, 10, None, True)
        grabadora._al_click(50, 50, None, True)  # click en ventana de fondo no relacionada (999)

    assert grabadora._hwnd_objetivo == 111
    assert grabadora._clicks_ignorados_fuera_de_ventana == 1
    assert grabadora.ventanas_revinculadas == 0
    assert not any("999" in str(p) for p in grabadora.pasos)


def test_grabadora_reaplica_el_candado_tras_un_rebind() -> None:
    """Prueba de tres ventanas: 111 (objetivo original) -> se cierra ->
    click en 222 = rebind legitimo -> click en 333 CON 222 todavia viva =
    debe seguir ignorandose. El candado de una sola ventana debe volver a
    aplicarse completo contra la ventana NUEVA, no quedar 'abierto' tras
    la primera revinculacion."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch.object(
        GrabadoraEscritorio, "_control_en", side_effect=[("A", "Button", False), ("B", "Button", False)]
    ):
        w.WindowFromPoint.side_effect = [111, 222]
        w.GetAncestor.side_effect = [111, 222]
        w.IsWindow.return_value = False  # 111 ya no existe -> rebind a 222
        w.GetWindowText.side_effect = ["Ventana A", "Ventana B"]
        w.ScreenToClient.return_value = (10, 10)

        grabadora._al_click(10, 10, None, True)  # fija 111
        grabadora._al_click(50, 50, None, True)  # 111 murio -> revincula a 222

    with patch("engine.actions.desktop_recorder.win32gui") as w:
        w.WindowFromPoint.return_value = 333
        w.GetAncestor.return_value = 333
        w.IsWindow.return_value = True  # 222 SIGUE viva -- no debe revincular a 333

        grabadora._al_click(90, 90, None, True)  # click en una TERCERA ventana no relacionada

    assert grabadora._hwnd_objetivo == 222  # sigue en 222, NO se revinculo a 333
    assert grabadora._clicks_ignorados_fuera_de_ventana == 1
    assert grabadora.ventanas_revinculadas == 1
    assert not any("333" in str(p) for p in grabadora.pasos)


def test_click_en_ventana_propia_nunca_fija_la_ventana_objetivo() -> None:
    """Un click sobre la propia app LAAutomate (mismo PID) nunca debe
    convertirse en la ventana objetivo, ni siquiera si es el PRIMER click
    de la grabación."""
    import os

    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch(
        "engine.actions.desktop_recorder.win32process"
    ) as wp:
        w.WindowFromPoint.return_value = 111
        w.GetAncestor.return_value = 111
        wp.GetWindowThreadProcessId.return_value = (0, os.getpid())  # ventana propia

        grabadora._al_click(10, 10, None, True)

    assert grabadora._hwnd_objetivo is None
    assert grabadora.pasos == []
    assert grabadora.clicks_ignorados == 0  # ni siquiera cuenta como "ignorado"


def test_click_en_ventana_propia_no_causa_rebind_ni_se_registra() -> None:
    """Regresion del bug real: la ventana objetivo (111, ej. una sesión
    VNC) se cierra, y el click del usuario para DETENER la grabación cae
    sobre la propia LAAutomate (222) -- antes esto se trataba como un
    rebind legítimo y quedaba grabado como el último paso (irreproducible,
    porque ese botón está deshabilitado fuera de una grabación). Debe
    ignorarse por completo, sin tocar _hwnd_objetivo ni el contador de
    revinculaciones -- y una ventana de verdad (333) despues SI debe poder
    revincular con normalidad."""
    import os

    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True
    grabadora._hwnd_objetivo = 111  # ventana objetivo original, ya cerrada

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch(
        "engine.actions.desktop_recorder.win32process"
    ) as wp:
        w.WindowFromPoint.return_value = 222
        w.GetAncestor.return_value = 222
        w.IsWindow.return_value = False  # 111 ya no existe
        wp.GetWindowThreadProcessId.return_value = (0, os.getpid())  # 222 = LAAutomate

        grabadora._al_click(20, 20, None, True)  # click en "Detener y generar código"

    assert grabadora._hwnd_objetivo == 111  # sin cambios -- nunca se reenlazo a LAAutomate
    assert grabadora.ventanas_revinculadas == 0
    assert grabadora.pasos == []

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch(
        "engine.actions.desktop_recorder.win32process"
    ) as wp, patch.object(GrabadoraEscritorio, "_control_en", return_value=("C", "Button", False)):
        w.WindowFromPoint.return_value = 333
        w.GetAncestor.return_value = 333
        w.IsWindow.return_value = False
        w.GetWindowText.return_value = "Ventana real C"
        w.ScreenToClient.return_value = (5, 5)
        wp.GetWindowThreadProcessId.return_value = (0, 999999)  # una app real, no LAAutomate

        grabadora._al_click(30, 30, None, True)

    assert grabadora._hwnd_objetivo == 333  # esta SI reenlaza -- es una ventana real
    assert grabadora.ventanas_revinculadas == 1


def test_marca_tras_rebind_sobrevive_un_click_intermedio_fallido() -> None:
    """La bandera de 'el proximo conectar es tras un rebind' vive como
    atributo de instancia (no una variable local) precisamente porque un
    click intermedio puede fallar (excepcion al identificar el control) y
    retornar ANTES de llegar a emitir el 'conectar' real -- la marca debe
    sobrevivir hasta la primera llamada exitosa subsecuente."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w:
        w.WindowFromPoint.side_effect = [111, 222, 222]
        w.GetAncestor.side_effect = [111, 222, 222]
        w.IsWindow.return_value = False
        # 1er click: GetWindowText exitoso ("Ventana A"). 2do click (tras el
        # rebind): GetWindowText FALLA. Se corrige en el 3er click.
        w.GetWindowText.side_effect = ["Ventana A", RuntimeError("fallo simulado en la 2a llamada")]
        w.ScreenToClient.return_value = (10, 10)

        with patch.object(GrabadoraEscritorio, "_control_en", return_value=("A", "Button", False)):
            grabadora._al_click(10, 10, None, True)  # fija 111, conectar #1 emitido

        # 2do click: rebind se dispara (111 ya no existe), pero identificar
        # el control de la ventana nueva FALLA (GetWindowText lanza) -- la
        # funcion debe retornar sin emitir "conectar", con la marca ya puesta.
        grabadora._al_click(50, 50, None, True)

        assert grabadora._hwnd_objetivo == 222  # el rebind SI se aplico
        assert grabadora._marca_conectar_tras_rebind is True  # la marca sobrevivio
        assert len([p for p in grabadora.pasos if p["tipo"] == "conectar"]) == 1

        # 3er click: identificar el control ahora SI funciona -- el
        # "conectar" real se emite aqui, y debe llevar tras_rebind=True.
        w.GetWindowText.side_effect = None
        w.GetWindowText.return_value = "Ventana B"
        with patch.object(GrabadoraEscritorio, "_control_en", return_value=("B", "Button", False)):
            grabadora._al_click(50, 50, None, True)

    assert grabadora._marca_conectar_tras_rebind is False
    conectar = [p for p in grabadora.pasos if p["tipo"] == "conectar"]
    assert len(conectar) == 2
    assert "tras_rebind" not in conectar[0]
    assert conectar[1]["tras_rebind"] is True


def test_isWindow_con_excepcion_no_revincula_por_precaucion() -> None:
    """Si IsWindow() lanza una excepcion inesperada, se asume 'la ventana
    objetivo sigue viva' (el comportamiento MAS conservador) -- nunca se
    escala a revincular ante una duda, siguiendo la misma convencion
    defensiva que el resto de _al_click."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True
    grabadora._hwnd_objetivo = 111

    with patch("engine.actions.desktop_recorder.win32gui") as w:
        w.WindowFromPoint.return_value = 222
        w.GetAncestor.return_value = 222
        w.IsWindow.side_effect = RuntimeError("handle invalido")

        grabadora._al_click(10, 10, None, True)

    assert grabadora._hwnd_objetivo == 111  # no se revinculo
    assert grabadora._clicks_ignorados_fuera_de_ventana == 1
    assert grabadora.ventanas_revinculadas == 0


def test_generar_codigo_conectar_tras_rebind_usa_mas_tiempo_de_espera() -> None:
    pasos = [
        {"tipo": "conectar", "modo": "titulo", "valor": "Búsqueda de Windows"},
        {"tipo": "click", "texto": "vnc", "control_tipo": "Edit"},
        {"tipo": "conectar", "modo": "titulo", "valor": "UltraVNC Viewer", "tras_rebind": True},
    ]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)
    lineas = codigo.split("\n")
    # re.escape escapa tambien los espacios (Python 3.7+) -- se busca por
    # una subcadena sin espacios para no depender de esa transformacion.
    linea_busqueda = next(l for l in lineas if "squeda" in l)
    linea_vnc = next(l for l in lineas if "UltraVNC" in l)
    assert "tiempo_espera" not in linea_busqueda
    assert "tiempo_espera=30" in linea_vnc


def test_depurar_pasos_no_colapsa_dos_conexiones_distintas_en_la_misma_grabacion() -> None:
    pasos = [
        {"tipo": "conectar", "modo": "titulo", "valor": "Búsqueda de Windows"},
        {"tipo": "click", "texto": "vnc", "control_tipo": "Edit"},
        {"tipo": "conectar", "modo": "titulo", "valor": "UltraVNC Viewer", "tras_rebind": True},
        {"tipo": "click", "texto": "Conectar", "control_tipo": "Button"},
    ]
    limpios = _depurar_pasos(pasos)
    conectar = [p for p in limpios if p["tipo"] == "conectar"]
    assert [p["valor"] for p in conectar] == ["Búsqueda de Windows", "UltraVNC Viewer"]
    assert conectar[1]["tras_rebind"] is True


# ---------- tecla Enter como paso propio ----------


def test_grabadora_enter_sobre_campo_editable_genera_paso_propio() -> None:
    """Enter suele ser la accion que CONFIRMA/DISPARA el paso (enviar un
    login, lanzar el resultado seleccionado en un buscador) -- antes se
    grababa el texto tecleado pero nunca el Enter que lo confirma."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True
    grabadora._hwnd_objetivo = 111
    grabadora._ultimo_click_editable = True
    grabadora._buffer_texto = "vnc"

    with patch("engine.actions.desktop_recorder.win32gui") as w:
        w.GetForegroundWindow.return_value = 111

        from pynput.keyboard import Key

        grabadora._al_tecla(Key.enter)

    assert grabadora.pasos[-2] == {"tipo": "escribir", "valor": "vnc"}
    assert grabadora.pasos[-1] == {"tipo": "tecla_enter"}


def test_grabadora_enter_fuera_de_campo_editable_no_genera_paso() -> None:
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True
    grabadora._hwnd_objetivo = 111
    grabadora._ultimo_click_editable = False

    with patch("engine.actions.desktop_recorder.win32gui") as w:
        w.GetForegroundWindow.return_value = 111

        from pynput.keyboard import Key

        grabadora._al_tecla(Key.enter)

    assert grabadora.pasos == []


def test_generar_codigo_tecla_enter() -> None:
    pasos = [
        {"tipo": "conectar", "modo": "titulo", "valor": "App"},
        {"tipo": "escribir", "valor": "vnc"},
        {"tipo": "tecla_enter"},
    ]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)
    assert 'self.escritorio.atajo("{ENTER}")' in codigo


def test_ventanas_revinculadas_property_expone_el_contador() -> None:
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    assert grabadora.ventanas_revinculadas == 0
    grabadora._ventanas_revinculadas = 2
    assert grabadora.ventanas_revinculadas == 2


# ---------- ventana que cambia de titulo sin cerrarse (ej. Outlook segun carpeta) ----------


def test_grabadora_mismo_hwnd_cambia_titulo_no_duplica_conectar() -> None:
    """Regresion directa de un caso real: Outlook pone el nombre de la
    carpeta actual en el titulo de su ventana (ej. 'Inbox - ... - Outlook'
    -> 'Sent Items - ... - Outlook') SIN cerrar la ventana. El HWND nunca
    cambia (no es un rebind) -- no debe emitirse un segundo paso
    'conectar': el mismo paso ya grabado se amplia con los titulos
    alternativos vistos."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch.object(
        GrabadoraEscritorio, "_control_en", side_effect=[("Sent Items", "TreeItem", False), ("Archive", "TreeItem", False)]
    ):
        w.WindowFromPoint.return_value = 111
        w.GetAncestor.return_value = 111
        w.GetWindowText.side_effect = ["Inbox - Luis - Outlook", "Sent Items - Luis - Outlook"]
        w.ScreenToClient.return_value = (10, 10)

        grabadora._al_click(10, 10, None, True)  # fija 111, titulo "Inbox - ..."
        grabadora._al_click(20, 20, None, True)  # MISMO hwnd 111, titulo cambio a "Sent Items - ..."

    conectar = [p for p in grabadora.pasos if p["tipo"] == "conectar"]
    assert len(conectar) == 1  # nunca dos -- se amplio el mismo paso
    assert conectar[0]["valor"] == "Inbox - Luis - Outlook"
    assert conectar[0]["titulos_alternativos"] == ["Inbox - Luis - Outlook", "Sent Items - Luis - Outlook"]
    assert grabadora._ventanas_revinculadas == 0  # esto NO es un rebind
    assert grabadora._clicks_ignorados_fuera_de_ventana == 0

    clicks = [p for p in grabadora.pasos if p["tipo"] == "click"]
    assert [c["texto"] for c in clicks] == ["Sent Items", "Archive"]


def test_generar_codigo_usa_titulos_alternativos_cuando_ventana_cambia_de_titulo() -> None:
    pasos = [
        {
            "tipo": "conectar",
            "modo": "titulo",
            "valor": "Inbox - Luis - Outlook",
            "titulos_alternativos": ["Inbox - Luis - Outlook", "Sent Items - Luis - Outlook"],
        },
        {"tipo": "click", "texto": "Archive", "control_tipo": "TreeItem"},
    ]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)

    import re as re_mod

    linea = next(l for l in codigo.split("\n") if "conectar_por_titulo" in l)
    valor = linea.split("conectar_por_titulo(", 1)[1].rsplit(")", 1)[0]
    patron = eval(valor)  # noqa: S307 - literal de cadena controlado por la prueba
    assert re_mod.match(patron, "Inbox - Luis - Outlook")
    assert re_mod.match(patron, "Sent Items - Luis - Outlook")
    assert not re_mod.match(patron, "Drafts - Luis - Outlook")


def test_generar_codigo_un_solo_titulo_no_usa_alternancia() -> None:
    """Con un solo titulo visto (caso normal, sin cambios), el patron
    generado sigue siendo el titulo exacto escapado -- sin el '|' de
    alternancia, para no aflojar el match sin necesidad."""
    pasos = [{"tipo": "conectar", "modo": "titulo", "valor": "Notepad", "titulos_alternativos": ["Notepad"]}]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)
    linea = next(l for l in codigo.split("\n") if "conectar_por_titulo" in l)
    assert "|" not in linea


def test_detener_captura_el_titulo_final_no_observado_por_ningun_click_posterior() -> None:
    """El titulo resultante del ULTIMO click nunca se observa durante la
    grabacion (se lee al INICIO del siguiente click, y no hay uno
    despues del ultimo) -- detener() debe capturarlo tambien, para que
    conectar_por_titulo reconozca el estado en el que quedo la app."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch.object(
        GrabadoraEscritorio, "_control_en", return_value=("Sent Items", "TreeItem", False)
    ):
        w.WindowFromPoint.return_value = 111
        w.GetAncestor.return_value = 111
        w.GetWindowText.return_value = "Inbox - Luis - Outlook"
        w.ScreenToClient.return_value = (10, 10)

        grabadora._al_click(10, 10, None, True)  # fija 111, titulo "Inbox - ..." (el unico observado)

        # tras el click, la app "navega" a Sent Items -- el titulo YA
        # cambio en la ventana real, pero ningun click lo observa.
        w.GetWindowText.return_value = "Sent Items - Luis - Outlook"
        grabadora.detener()

    conectar = [p for p in grabadora.pasos if p["tipo"] == "conectar"]
    assert conectar[0]["titulos_alternativos"] == ["Inbox - Luis - Outlook", "Sent Items - Luis - Outlook"]


def test_grabadora_rebind_no_se_confunde_con_cambio_de_titulo() -> None:
    """Un rebind genuino (hwnd distinto, ventana anterior cerrada) sigue
    emitiendo un 'conectar' NUEVO y separado -- el mecanismo de titulos
    alternativos (misma ventana, titulo distinto) no debe interferir."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch.object(
        GrabadoraEscritorio, "_control_en", side_effect=[("A", "Button", False), ("B", "Button", False)]
    ):
        w.WindowFromPoint.side_effect = [111, 222]
        w.GetAncestor.side_effect = [111, 222]
        w.IsWindow.return_value = False  # 111 ya no existe -> rebind genuino a 222
        w.GetWindowText.side_effect = ["Ventana A", "Ventana B"]
        w.ScreenToClient.return_value = (10, 10)

        grabadora._al_click(10, 10, None, True)
        grabadora._al_click(50, 50, None, True)

    conectar = [p for p in grabadora.pasos if p["tipo"] == "conectar"]
    assert len(conectar) == 2  # rebind SI genera un conectar nuevo y separado
    assert "titulos_alternativos" not in conectar[0]
    assert conectar[1]["tras_rebind"] is True


# ---------- teclas de navegacion (moverse entre correos/filas/resultados) ----------


def test_grabadora_flecha_abajo_genera_paso_de_navegacion() -> None:
    """Forma SEGURA de grabar 'muevete entre correos/filas/resultados':
    solo se guarda QUE TECLA se presiono, nunca el contenido/asunto del
    item que quedo seleccionado."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True
    grabadora._hwnd_objetivo = 111

    with patch("engine.actions.desktop_recorder.win32gui") as w:
        w.GetForegroundWindow.return_value = 111

        from pynput.keyboard import Key

        grabadora._al_tecla(Key.down)

    assert grabadora.pasos == [{"tipo": "tecla_navegacion", "tecla": "DOWN"}]


def test_grabadora_navegacion_funciona_sin_click_editable_previo() -> None:
    """A diferencia del tecleo normal, la navegacion NO depende de
    _ultimo_click_editable -- moverse en una lista/arbol no es 'escribir
    en un campo'."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True
    grabadora._hwnd_objetivo = 111
    grabadora._ultimo_click_editable = False

    with patch("engine.actions.desktop_recorder.win32gui") as w:
        w.GetForegroundWindow.return_value = 111

        from pynput.keyboard import Key

        grabadora._al_tecla(Key.up)

    assert grabadora.pasos == [{"tipo": "tecla_navegacion", "tecla": "UP"}]


def test_grabadora_navegacion_ignora_fuera_de_la_ventana_objetivo() -> None:
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True
    grabadora._hwnd_objetivo = 111

    with patch("engine.actions.desktop_recorder.win32gui") as w:
        w.GetForegroundWindow.return_value = 222  # otra ventana tiene el foco

        from pynput.keyboard import Key

        grabadora._al_tecla(Key.down)

    assert grabadora.pasos == []


def test_depurar_pasos_junta_navegacion_consecutiva_de_la_misma_tecla() -> None:
    pasos = [
        {"tipo": "tecla_navegacion", "tecla": "DOWN"},
        {"tipo": "tecla_navegacion", "tecla": "DOWN"},
        {"tipo": "tecla_navegacion", "tecla": "DOWN"},
        {"tipo": "tecla_navegacion", "tecla": "UP"},
    ]
    limpios = _depurar_pasos(pasos)
    assert limpios == [
        {"tipo": "tecla_navegacion", "tecla": "DOWN", "veces": 3},
        {"tipo": "tecla_navegacion", "tecla": "UP"},
    ]


def test_generar_codigo_tecla_navegacion_una_vez() -> None:
    pasos = [{"tipo": "conectar", "modo": "titulo", "valor": "Outlook"}, {"tipo": "tecla_navegacion", "tecla": "DOWN"}]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)
    assert 'self.escritorio.atajo("{DOWN}")' in codigo


def test_generar_codigo_tecla_navegacion_repetida() -> None:
    pasos = [
        {"tipo": "conectar", "modo": "titulo", "valor": "Outlook"},
        {"tipo": "tecla_navegacion", "tecla": "DOWN", "veces": 5},
    ]
    codigo = generar_codigo_escritorio("mi_prueba", pasos)
    _compila_sin_error(codigo)
    assert 'self.escritorio.atajo("{DOWN 5}")' in codigo


# ---------- modo "multiple" (grabar cualquier click, bajo consentimiento explicito) ----------


def test_modo_ventana_invalido_lanza_valueerror() -> None:
    with pytest.raises(ValueError):
        GrabadoraEscritorio(_LoggerFalso(), modo_ventana="lo_que_sea")


def test_modo_multiple_es_default_unica() -> None:
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    assert grabadora.modo_ventana == "unica"


def test_modo_multiple_acepta_clicks_de_cualquier_ventana() -> None:
    """El usuario pidio explicitamente grabar TODO lo que haga, sin
    importar la ventana -- en modo 'multiple' un click en una ventana
    DISTINTA (con la anterior todavia abierta) debe aceptarse y
    conectarse, no ignorarse."""
    grabadora = GrabadoraEscritorio(_LoggerFalso(), modo_ventana="multiple")
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch.object(
        GrabadoraEscritorio, "_control_en", side_effect=[("A", "Button", False), ("B", "Button", False)]
    ):
        w.WindowFromPoint.side_effect = [111, 222]
        w.GetAncestor.side_effect = [111, 222]
        w.IsWindow.return_value = True  # la ventana 111 SIGUE abierta -- en modo unica esto se ignoraria
        w.GetWindowText.side_effect = ["Ventana A", "Ventana B"]
        w.ScreenToClient.return_value = (10, 10)

        grabadora._al_click(10, 10, None, True)
        grabadora._al_click(50, 50, None, True)

    assert grabadora._hwnd_objetivo == 222
    assert grabadora._clicks_ignorados_fuera_de_ventana == 0
    assert grabadora._ventanas_revinculadas == 0  # el cambio de ventana no cuenta como revinculacion
    conectar = [p for p in grabadora.pasos if p["tipo"] == "conectar"]
    assert [p["valor"] for p in conectar] == ["Ventana A", "Ventana B"]
    clicks = [p for p in grabadora.pasos if p["tipo"] == "click"]
    assert [c["texto"] for c in clicks] == ["A", "B"]


def test_modo_multiple_no_llama_iswindow() -> None:
    """En modo multiple no hace falta verificar si la ventana anterior
    sigue viva -- el cambio siempre se acepta."""
    grabadora = GrabadoraEscritorio(_LoggerFalso(), modo_ventana="multiple")
    grabadora._grabando = True

    with patch("engine.actions.desktop_recorder.win32gui") as w, patch.object(
        GrabadoraEscritorio, "_control_en", side_effect=[("A", "Button", False), ("B", "Button", False)]
    ):
        w.WindowFromPoint.side_effect = [111, 222]
        w.GetAncestor.side_effect = [111, 222]
        w.GetWindowText.side_effect = ["Ventana A", "Ventana B"]
        w.ScreenToClient.return_value = (10, 10)

        grabadora._al_click(10, 10, None, True)
        grabadora._al_click(50, 50, None, True)

    w.IsWindow.assert_not_called()
