"""Validación de extremo a extremo de la Grabadora de escritorio: se
simula una sesión completa (clicks, tecleo, botones) contra un escritorio
falso y se comprueba QUE CÓDIGO SALE. Nada toca el mouse, el teclado ni
UI Automation reales.

Las pruebas de test_desktop_recorder.py cubren piezas sueltas. Estas
recorren el camino entero -- _al_click / _al_tecla -> _depurar_pasos ->
generar_codigo_escritorio -- porque los defectos que motivaron este
archivo vivían justo en las costuras entre esas piezas y cada una pasaba
sus propias pruebas.
"""
from __future__ import annotations

import py_compile
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pynput.keyboard import Key, KeyCode

from engine.actions.desktop import DesktopActions, escapar_para_type_keys
from engine.actions.desktop_recorder import GrabadoraEscritorio, generar_codigo_escritorio


class _LoggerFalso:
    def info(self, *a, **k):
        pass

    def debug(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass


class _EscritorioFalso:
    """Un escritorio de mentira con UNA ventana y controles conocidos.

    `controles` mapea coordenada de pantalla -> (texto, control_type,
    es_password), que es exactamente lo que devuelve _control_en() al
    consultar UI Automation."""

    HWND = 4242

    def __init__(self, titulo: str, controles: dict[tuple[int, int], tuple[str, str, bool]]) -> None:
        self.titulo = titulo
        self.controles = controles

    def _control_en(self, x: int, y: int):
        return self.controles[(x, y)]


def _sesion(escritorio: _EscritorioFalso):
    """Contexto que hace creer a la grabadora que `escritorio` es real."""
    parche_win32 = patch("engine.actions.desktop_recorder.win32gui")
    parche_control = patch.object(GrabadoraEscritorio, "_control_en", side_effect=escritorio._control_en)
    # sin ambiguedad: cada texto identifica un solo control en la ventana
    parche_indice = patch.object(GrabadoraEscritorio, "_indice_entre_coincidencias", return_value=(None, 1))

    win32 = parche_win32.start()
    parche_control.start()
    parche_indice.start()

    win32.WindowFromPoint.return_value = escritorio.HWND
    win32.GetAncestor.return_value = escritorio.HWND
    win32.GetForegroundWindow.return_value = escritorio.HWND
    win32.GetWindowText.return_value = escritorio.titulo
    win32.IsWindow.return_value = True
    win32.ScreenToClient.side_effect = lambda _hwnd, punto: punto
    win32process = patch("engine.actions.desktop_recorder.win32process").start()
    win32process.GetWindowThreadProcessId.return_value = (0, 999999)  # nunca es la propia app

    try:
        yield
    finally:
        patch.stopall()


def _grabar(escritorio: _EscritorioFalso, acciones) -> list[dict]:
    """Corre `acciones` (una lista de callables) sobre una grabadora recién
    arrancada y devuelve los pasos capturados."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    generador = _sesion(escritorio)
    next(generador)
    try:
        for accion in acciones:
            accion(grabadora)
    finally:
        for _ in generador:
            pass

    grabadora._flush_texto()
    return grabadora.pasos


def _click(x: int, y: int):
    return lambda g: g._al_click(x, y, None, True)


def _teclear(texto: str):
    def accion(g):
        for caracter in texto:
            g._al_tecla(KeyCode.from_char(caracter) if caracter != " " else Key.space)

    return accion


def _tecla(key):
    return lambda g: g._al_tecla(key)


def _codigo_de(pasos: list[dict], nombre: str = "flujo_de_prueba") -> str:
    codigo = generar_codigo_escritorio(nombre, pasos)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(codigo)
        ruta = tmp.name
    try:
        py_compile.compile(ruta, doraise=True)  # el .py generado siempre debe compilar
    finally:
        Path(ruta).unlink(missing_ok=True)
    return codigo


def _cuerpo(codigo: str) -> list[str]:
    """Las llamadas del ejecutar() generado, sin los comentarios al final
    de linea (son ayuda para quien lea el .py, no parte del flujo)."""
    return [
        linea.strip().split("  # ", 1)[0]
        for linea in codigo.splitlines()
        if linea.startswith("        self.escritorio.")
    ]


# --------------------------------------------------------------------------
# 1. Puede dar clicks
# --------------------------------------------------------------------------


def test_graba_un_click_sobre_un_control_con_texto() -> None:
    escritorio = _EscritorioFalso("Panel", {(100, 200): ("Buscar cliente", "Text", False)})
    pasos = _grabar(escritorio, [_click(100, 200)])

    assert _cuerpo(_codigo_de(pasos)) == [
        "self.escritorio.conectar_por_titulo('Panel')",
        "self.escritorio.click_por_texto('Buscar cliente', control_type='Text')",
    ]


def test_graba_un_click_sin_texto_como_coordenada() -> None:
    """El lienzo de un cliente VNC: UI Automation no ve controles, solo un
    Pane sin texto. Debe quedar como click por coordenada, nunca como
    click_por_texto('') -- que haria match con CUALQUIER control sin titulo."""
    escritorio = _EscritorioFalso("Sesion remota", {(640, 480): ("", "Pane", False)})
    pasos = _grabar(escritorio, [_click(640, 480)])

    assert "self.escritorio.click_en(640, 480)" in _codigo_de(pasos)
    assert "click_por_texto('')" not in _codigo_de(pasos)


# --------------------------------------------------------------------------
# 2. Puede enviar textos
# --------------------------------------------------------------------------


def test_graba_texto_con_espacios() -> None:
    """Regresión del defecto principal: en Windows pynput entrega la barra
    espaciadora como Key.space, cuyo .char es None. El filtro
    `if not caracter: return` la descartaba, y TODO texto con espacios se
    grababa pegado ('Rep dia' -> 'Repdia')."""
    escritorio = _EscritorioFalso("Editor", {(50, 60): ("", "Edit", False)})
    pasos = _grabar(escritorio, [_click(50, 60), _teclear("reporte diario de fallas")])

    assert "self.escritorio.escribir('reporte diario de fallas')" in _codigo_de(pasos)


def test_backspace_corrige_lo_tecleado() -> None:
    escritorio = _EscritorioFalso("Editor", {(50, 60): ("", "Edit", False)})
    pasos = _grabar(
        escritorio,
        [_click(50, 60), _teclear("holaa"), _tecla(Key.backspace), _teclear(" mundo")],
    )

    assert "self.escritorio.escribir('hola mundo')" in _codigo_de(pasos)


def test_tab_entre_campos_conserva_los_dos_valores_y_mueve_el_foco() -> None:
    """El otro defecto de fondo: Tab hacía flush pero no emitía paso, así
    que los dos "escribir" quedaban adyacentes y _depurar_pasos colapsaba
    campos DISTINTOS -- llenar un login con Tab conservaba solo el último.
    Y al reproducir nadie movía el foco, así que el segundo valor se
    tecleaba encima del primero."""
    escritorio = _EscritorioFalso("Ingreso", {(30, 40): ("", "Edit", False)})
    pasos = _grabar(
        escritorio,
        [_click(30, 40), _teclear("luis ortiz"), _tecla(Key.tab), _teclear("sucursal 7")],
    )

    # El click en un campo de texto se localiza por TIPO, no por
    # coordenada: el texto visible de un Edit es su CONTENIDO (no un
    # nombre) y una coordenada deja de apuntar al campo si la ventana
    # se mueve o cambia de tamaño. click_por_tipo sobrevive a las dos cosas.
    assert _cuerpo(_codigo_de(pasos)) == [
        "self.escritorio.conectar_por_titulo('Ingreso')",
        "self.escritorio.click_por_tipo('Edit')",
        "self.escritorio.escribir('luis ortiz')",
        'self.escritorio.atajo("{TAB}")',
        "self.escritorio.escribir('sucursal 7')",
    ]


def test_graba_texto_sobre_un_lienzo_sin_tipo_editable() -> None:
    """Antes solo se grababa tecleo tras un click en Edit/ComboBox/Document.
    Dentro de una sesión VNC el lienzo es un 'Pane', así que TODO lo que se
    escribiera en el escritorio remoto se perdía en silencio."""
    escritorio = _EscritorioFalso("Sesion remota", {(640, 480): ("", "Pane", False)})
    pasos = _grabar(escritorio, [_click(640, 480), _teclear("dir c:")])

    assert "self.escritorio.escribir('dir c:')" in _codigo_de(pasos)


def test_no_graba_tecleo_sobre_un_boton() -> None:
    """El otro lado de la moneda: pulsar la barra espaciadora con un botón
    enfocado lo ACTIVA, no escribe. No debe salir un escribir(' ')."""
    escritorio = _EscritorioFalso("Panel", {(10, 20): ("Aceptar", "Button", False)})
    pasos = _grabar(escritorio, [_click(10, 20), _teclear(" ")])

    assert not [p for p in pasos if p["tipo"] == "escribir"]


def test_atajos_de_teclado_no_ensucian_el_texto() -> None:
    """Ctrl+C llega como carácter de control ('\\x03'), no como 'c'."""
    escritorio = _EscritorioFalso("Editor", {(50, 60): ("", "Edit", False)})
    pasos = _grabar(
        escritorio,
        [_click(50, 60), _teclear("nota"), lambda g: g._al_tecla(KeyCode.from_char("\x03"))],
    )

    assert "self.escritorio.escribir('nota')" in _codigo_de(pasos)


# --------------------------------------------------------------------------
# 3. Puede mandar botones (Enter y navegación)
# --------------------------------------------------------------------------


def test_enter_tras_escribir_queda_como_paso_propio() -> None:
    escritorio = _EscritorioFalso("Buscador", {(80, 90): ("", "Edit", False)})
    pasos = _grabar(escritorio, [_click(80, 90), _teclear("factura 2026"), _tecla(Key.enter)])

    # El click en un campo de texto se localiza por TIPO, no por
    # coordenada: el texto visible de un Edit es su CONTENIDO (no un
    # nombre) y una coordenada deja de apuntar al campo si la ventana
    # se mueve o cambia de tamaño. click_por_tipo sobrevive a las dos cosas.
    assert _cuerpo(_codigo_de(pasos)) == [
        "self.escritorio.conectar_por_titulo('Buscador')",
        "self.escritorio.click_por_tipo('Edit')",
        "self.escritorio.escribir('factura 2026')",
        'self.escritorio.atajo("{ENTER}")',
    ]


def test_flechas_repetidas_se_juntan_en_un_solo_atajo() -> None:
    escritorio = _EscritorioFalso("Bandeja", {(10, 10): ("Correos", "List", False)})
    pasos = _grabar(escritorio, [_click(10, 10)] + [_tecla(Key.down)] * 3)

    assert 'self.escritorio.atajo("{DOWN 3}")' in _codigo_de(pasos)


def test_flujo_de_login_completo() -> None:
    """La secuencia real que motivó todo esto: conectar, llenar usuario y
    contraseña, pulsar el botón. La contraseña nunca aparece en el código."""
    escritorio = _EscritorioFalso(
        "Ingreso al sistema",
        {
            (300, 100): ("", "Edit", False),  # usuario
            (300, 150): ("", "Edit", True),  # contraseña
            (300, 220): ("Entrar", "Button", False),
        },
    )
    pasos = _grabar(
        escritorio,
        [
            _click(300, 100),
            _teclear("luis ortiz"),
            _click(300, 150),
            _teclear("secreto real"),
            _click(300, 220),
        ],
    )
    codigo = _codigo_de(pasos, "login_de_prueba")

    # El click en un campo de texto se localiza por TIPO, no por
    # coordenada: el texto visible de un Edit es su CONTENIDO (no un
    # nombre) y una coordenada deja de apuntar al campo si la ventana
    # se mueve o cambia de tamaño. click_por_tipo sobrevive a las dos cosas.
    assert _cuerpo(codigo) == [
        "self.escritorio.conectar_por_titulo('Ingreso\\\\ al\\\\ sistema')",
        "self.escritorio.click_por_tipo('Edit')",
        "self.escritorio.escribir('luis ortiz')",
        "self.escritorio.click_en(300, 150)",
        "self.escritorio.escribir(self.credenciales.password)",
        "self.escritorio.click_por_texto('Entrar', control_type='Button')",
    ]
    assert "secreto real" not in codigo


# --------------------------------------------------------------------------
# 4. Lo grabado se teclea LITERAL al reproducir
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    ["usuario^admin", "clave%2026", "a(b)c", "pass~word", "Repor+te", "llave{ENTER}", "sin nada raro"],
)
def test_escribir_no_interpreta_el_texto_como_atajos(texto: str) -> None:
    """type_keys() de pywinauto habla SendKeys: ^ es Ctrl, % es Alt, + es
    Shift, ~ es Enter y ( ) { } agrupan. Sin escapar, escribir(
    'usuario^admin') disparaba Ctrl+A (seleccionar todo) y lo siguiente
    BORRABA el campo; 'pass~word' enviaba el formulario a media
    contraseña; los paréntesis desaparecían sin aviso."""
    from pywinauto.keyboard import parse_keys

    acciones = DesktopActions(_LoggerFalso())
    acciones._ventana = MagicMock()
    acciones.escribir(texto)

    enviado = acciones._ventana.type_keys.call_args.args[0]
    tecleado = "".join(str(k).strip("<>") for k in parse_keys(enviado, with_spaces=True))
    assert tecleado == texto


def test_atajo_sigue_recibiendo_sintaxis_sendkeys_cruda() -> None:
    """El escape es solo de escribir() -- atajo() SÍ recibe sintaxis
    SendKeys a propósito, y escaparla ahí lo rompería todo."""
    acciones = DesktopActions(_LoggerFalso())
    acciones._ventana = MagicMock()
    acciones.atajo("^e")

    assert acciones._ventana.type_keys.call_args.args[0] == "^e"


# --------------------------------------------------------------------------
# 5. Cancelar
# --------------------------------------------------------------------------


def test_cancelar_descarta_todo_lo_grabado() -> None:
    escritorio = _EscritorioFalso("Panel", {(10, 20): ("Aceptar", "Button", False)})
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    grabadora._grabando = True

    generador = _sesion(escritorio)
    next(generador)
    try:
        grabadora._al_click(10, 20, None, True)
        assert grabadora.pasos, "precondición: algo se grabó"
        descartados = grabadora.cancelar()
    finally:
        for _ in generador:
            pass

    assert descartados == 2  # conectar + click
    assert grabadora.pasos == []
    assert grabadora._grabando is False
    assert grabadora._hwnd_objetivo is None


def test_cancelar_vacia_la_lista_en_el_lugar() -> None:
    """El hilo de desambiguación recibió ESA MISMA lista por argumento y
    sigue con permiso de tocarla. Si cancelar rebindeara self.pasos a una
    lista nueva, el hilo escribiría en la vieja y los pasos descartados
    reaparecerían en la siguiente grabación."""
    grabadora = GrabadoraEscritorio(_LoggerFalso())
    lista_original = grabadora.pasos
    grabadora.pasos.append({"tipo": "click", "texto": "x", "control_tipo": "Button"})

    grabadora.cancelar()

    assert grabadora.pasos is lista_original
    assert lista_original == []
