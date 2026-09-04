"""Pruebas de DesktopActions que no requieren ninguna ventana real -- la
ventana conectada se reemplaza por un MagicMock para verificar la
SECUENCIA de llamadas (down, pausa, up) y los parametros exactos, sin
clickear nada de verdad."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from engine.actions.desktop import DesktopActions


class _LoggerFalso:
    def info(self, *a, **k):
        pass


def _acciones_con_ventana_falsa() -> tuple[DesktopActions, MagicMock]:
    acciones = DesktopActions(_LoggerFalso())
    ventana_falsa = MagicMock()
    acciones._ventana = ventana_falsa
    return acciones, ventana_falsa


def test_click_por_texto_hace_down_pausa_up_no_un_click_instantaneo() -> None:
    """Regresion del bug real: un click_input() instantaneo (sin pausa
    entre down y up) no lo registran apps modernas WinUI/XAML -- se
    confirmo contra la Calculadora de Windows 11."""
    acciones, ventana_falsa = _acciones_con_ventana_falsa()
    control_falso = MagicMock()
    ventana_falsa.child_window.return_value.wrapper_object.return_value = control_falso

    with patch("engine.actions.desktop.time.sleep") as sleep_falso:
        acciones.click_por_texto("Aceptar", pausa=0.08)

    ventana_falsa.child_window.assert_called_once_with(title="Aceptar")
    assert control_falso.click_input.call_args_list == [
        call(button_down=True, button_up=False),
        call(button_down=False, button_up=True),
    ]
    sleep_falso.assert_called_once_with(0.08)


def test_click_por_texto_con_control_type_lo_pasa_como_criterio_extra() -> None:
    """control_type es opcional: si se pasa, se agrega como criterio EXTRA
    de busqueda para reducir ambiguedad entre controles distintos que
    comparten el mismo texto visible (ej. dos botones "OK" en dialogos
    anidados)."""
    acciones, ventana_falsa = _acciones_con_ventana_falsa()
    control_falso = MagicMock()
    ventana_falsa.child_window.return_value.wrapper_object.return_value = control_falso

    with patch("engine.actions.desktop.time.sleep"):
        acciones.click_por_texto("OK", control_type="Button")

    ventana_falsa.child_window.assert_called_once_with(title="OK", control_type="Button")


def test_click_por_texto_con_found_index_elige_cual_control_usar() -> None:
    """found_index resuelve el caso en que texto+control_type siguen sin
    bastar (ej. el mismo ícono de una app repetido en la barra de tareas
    de cada monitor, con texto y tipo idénticos) -- regresion real:
    'UltraVNC Viewer' en Shell_SecondaryTrayWnd via ElementAmbiguousError
    con 2 controles Button identicos."""
    acciones, ventana_falsa = _acciones_con_ventana_falsa()
    control_falso = MagicMock()
    ventana_falsa.child_window.return_value.wrapper_object.return_value = control_falso

    with patch("engine.actions.desktop.time.sleep"):
        acciones.click_por_texto("UltraVNC Viewer", control_type="Button", found_index=1)

    ventana_falsa.child_window.assert_called_once_with(
        title="UltraVNC Viewer", control_type="Button", found_index=1
    )


def test_click_por_texto_ambiguo_da_un_error_claro_no_la_excepcion_cruda_de_pywinauto() -> None:
    """Regresion directa de un hallazgo real: child_window(title=texto)
    sin control_type puede matchear VARIOS controles (ej. dos botones
    'OK' en dialogos anidados) y pywinauto lanza ElementAmbiguousError --
    debe envolverse en un error legible, no dejarse pasar crudo."""
    from pywinauto.findwindows import ElementAmbiguousError

    acciones, ventana_falsa = _acciones_con_ventana_falsa()
    ventana_falsa.child_window.side_effect = ElementAmbiguousError("hay 2 controles con ese título")

    with pytest.raises(RuntimeError, match="no identifica un único control"):
        acciones.click_por_texto("OK")


def test_click_en_usa_client_to_screen_no_el_de_pywinauto() -> None:
    """Regresion de un bug real encontrado en validacion contra una app
    real: pywinauto.click_input(coords=.., absolute=False) traduce con su
    propio client_to_screen(), que suma sobre element_info.rectangle -- el
    rectangulo EXTERIOR completo (incluye barra de titulo/bordes), NO el
    area cliente. Eso desalineaba cada click en el alto de la barra de
    titulo respecto a como GrabadoraEscritorio grababa la coordenada (via
    win32gui.ScreenToClient). click_en debe usar win32gui.ClientToScreen
    -- la API espejo exacta -- y pasar absolute=True para que pywinauto
    NO vuelva a sumar su propio (incorrecto, para este caso) offset."""
    acciones, ventana_falsa = _acciones_con_ventana_falsa()
    ventana_falsa.handle = 4242

    win32gui_falso = MagicMock()
    win32gui_falso.ClientToScreen.return_value = (620, 440)  # simula el offset real de la ventana

    with patch.dict("sys.modules", {"win32gui": win32gui_falso}), patch("engine.actions.desktop.time.sleep") as sleep_falso:
        acciones.click_en(120, 340, pausa=0.05)

    win32gui_falso.ClientToScreen.assert_called_once_with(4242, (120, 340))
    assert ventana_falsa.click_input.call_args_list == [
        call(coords=(620, 440), absolute=True, button_down=True, button_up=False),
        call(coords=(620, 440), absolute=True, button_down=False, button_up=True),
    ]
    sleep_falso.assert_called_once_with(0.05)


def test_click_en_requiere_ventana_conectada() -> None:
    acciones = DesktopActions(_LoggerFalso())
    with pytest.raises(RuntimeError):
        acciones.click_en(10, 10)


def _modulos_falsos_click_por_imagen(offset_x: int = 0, offset_y: int = 0):
    """pyautogui.locateCenterOnScreen() en Windows solo ve el monitor
    PRIMARIO -- click_por_imagen ahora usa pyautogui.screenshot(allScreens=True)
    + pyscreeze.locate() directamente, con el offset real del escritorio
    virtual (GetSystemMetrics). Estos mocks reproducen esa cadena."""
    ctypes_falso = MagicMock()
    ctypes_falso.windll.user32.GetSystemMetrics.side_effect = lambda idx: {76: offset_x, 77: offset_y}[idx]

    pyautogui_falso = MagicMock()
    captura_falsa = MagicMock(name="captura")
    pyautogui_falso.screenshot.return_value = captura_falsa

    class _ImageNotFoundExceptionFalsa(Exception):
        pass

    pyscreeze_falso = MagicMock()
    pyscreeze_falso.ImageNotFoundException = _ImageNotFoundExceptionFalsa

    return ctypes_falso, pyautogui_falso, pyscreeze_falso, captura_falsa


def test_click_por_imagen_restringe_la_busqueda_al_area_de_la_ventana_conectada() -> None:
    """En una maquina con varios monitores, buscar una imagen en TODA la
    pantalla arriesga encontrar un parecido en la ventana equivocada --
    si hay una ventana conectada, la busqueda debe restringirse a su
    area (region, trasladada al sistema de coordenadas de la captura
    multi-monitor), no a la pantalla completa."""
    acciones, ventana_falsa = _acciones_con_ventana_falsa()
    rect_falso = MagicMock(left=2000, top=100)
    rect_falso.width.return_value = 800
    rect_falso.height.return_value = 600
    ventana_falsa.rectangle.return_value = rect_falso

    ctypes_falso, pyautogui_falso, pyscreeze_falso, captura_falsa = _modulos_falsos_click_por_imagen(
        offset_x=50, offset_y=20
    )
    pyscreeze_falso.locate.return_value = (100, 50, 30, 30)  # caja cualquiera en coords de la captura
    pyscreeze_falso.center.return_value = (150, 90)

    with patch.dict(
        "sys.modules", {"pyautogui": pyautogui_falso, "pyscreeze": pyscreeze_falso, "ctypes": ctypes_falso}
    ), patch("engine.actions.desktop.time.sleep"):
        acciones.click_por_imagen("boton.png", confianza=0.85)

    pyautogui_falso.screenshot.assert_called_once_with(allScreens=True)
    pyscreeze_falso.locate.assert_called_once_with(
        "boton.png", captura_falsa, confidence=0.85, region=(2000 - 50, 100 - 20, 800, 600)
    )
    pyautogui_falso.mouseDown.assert_called_once_with(150 + 50, 90 + 20)
    pyautogui_falso.mouseUp.assert_called_once_with(150 + 50, 90 + 20)


def test_click_por_imagen_busca_pantalla_completa_sin_ventana_conectada() -> None:
    """Sin ninguna ventana conectada (ej. un icono suelto del escritorio)
    se conserva el comportamiento anterior: buscar sin restringir region."""
    acciones = DesktopActions(_LoggerFalso())
    ctypes_falso, pyautogui_falso, pyscreeze_falso, captura_falsa = _modulos_falsos_click_por_imagen()
    pyscreeze_falso.locate.return_value = (10, 20, 5, 5)
    pyscreeze_falso.center.return_value = (12, 22)

    with patch.dict(
        "sys.modules", {"pyautogui": pyautogui_falso, "pyscreeze": pyscreeze_falso, "ctypes": ctypes_falso}
    ), patch("engine.actions.desktop.time.sleep"):
        acciones.click_por_imagen("icono.png")

    pyscreeze_falso.locate.assert_called_once_with("icono.png", captura_falsa, confidence=0.9, region=None)


def test_click_por_imagen_funciona_con_ventana_en_monitor_secundario() -> None:
    """Regresion directa del hallazgo real: si la ventana conectada esta
    en un monitor SECUNDARIO (offset negativo del escritorio virtual),
    la busqueda debe seguir encontrando la imagen -- antes esto siempre
    fallaba porque pyautogui.locateCenterOnScreen solo ve el primario."""
    acciones, ventana_falsa = _acciones_con_ventana_falsa()
    rect_falso = MagicMock(left=-1800, top=200)  # ventana en un monitor a la izquierda del primario
    rect_falso.width.return_value = 400
    rect_falso.height.return_value = 300
    ventana_falsa.rectangle.return_value = rect_falso

    ctypes_falso, pyautogui_falso, pyscreeze_falso, captura_falsa = _modulos_falsos_click_por_imagen(
        offset_x=-1920, offset_y=0
    )
    pyscreeze_falso.locate.return_value = (50, 50, 20, 20)
    pyscreeze_falso.center.return_value = (60, 60)

    with patch.dict(
        "sys.modules", {"pyautogui": pyautogui_falso, "pyscreeze": pyscreeze_falso, "ctypes": ctypes_falso}
    ), patch("engine.actions.desktop.time.sleep"):
        acciones.click_por_imagen("boton.png")

    pyscreeze_falso.locate.assert_called_once_with(
        "boton.png", captura_falsa, confidence=0.9, region=(-1800 - (-1920), 200 - 0, 400, 300)
    )
    pyautogui_falso.mouseDown.assert_called_once_with(60 + (-1920), 60 + 0)


def test_click_por_imagen_lanza_si_no_encuentra_la_imagen() -> None:
    acciones = DesktopActions(_LoggerFalso())
    ctypes_falso, pyautogui_falso, pyscreeze_falso, _ = _modulos_falsos_click_por_imagen()
    pyscreeze_falso.locate.side_effect = pyscreeze_falso.ImageNotFoundException("no encontrada")

    with patch.dict(
        "sys.modules", {"pyautogui": pyautogui_falso, "pyscreeze": pyscreeze_falso, "ctypes": ctypes_falso}
    ):
        with pytest.raises(LookupError):
            acciones.click_por_imagen("no_existe.png")


def test_conectar_por_clase_conecta_y_enfoca(monkeypatch) -> None:
    """El camino de siempre: buscar por class_name.

    Se desactiva el atajo por handle (`_conectar_rapido`, ver
    tests/test_conexion_rapida.py). Sin esto la prueba depende del equipo
    donde corre: en un Windows real hay exactamente una Shell_TrayWnd, el
    atajo se activaria y la conexion iria por handle -- correcto, pero no
    es el camino que esta prueba cubre.
    """
    monkeypatch.setattr("engine.actions.desktop._conectar_rapido", lambda *a, **k: None)

    acciones = DesktopActions(_LoggerFalso())
    app_falsa = MagicMock()
    ventana_falsa = MagicMock()
    app_falsa.connect.return_value = app_falsa  # pywinauto: Application.connect() devuelve self
    app_falsa.window.return_value = ventana_falsa

    aplicacion_falsa = MagicMock(return_value=app_falsa)
    with patch.dict("sys.modules", {"pywinauto": MagicMock(Application=aplicacion_falsa)}):
        resultado = acciones.conectar_por_clase("Shell_TrayWnd", tiempo_espera=5)

    aplicacion_falsa.assert_called_once_with(backend="uia")
    app_falsa.connect.assert_called_once_with(class_name="Shell_TrayWnd", timeout=5)
    app_falsa.window.assert_called_once_with(class_name="Shell_TrayWnd")
    ventana_falsa.set_focus.assert_called_once()
    assert resultado is ventana_falsa


def test_escribir_none_lanza_error_claro_en_vez_de_tipear_none() -> None:
    """Regresion del bug real: self.credenciales.password sin guardar en
    la Boveda es None, y sin este guard pywinauto tipeaba el texto literal
    "None" en el campo -- confuso y silencioso. Debe fallar con un mensaje
    que apunte a la causa real (falta guardar la credencial)."""
    acciones, ventana_falsa = _acciones_con_ventana_falsa()

    with pytest.raises(ValueError, match="Bóveda de credenciales"):
        acciones.escribir(None)

    ventana_falsa.type_keys.assert_not_called()
