"""Conectar con una ventana por HANDLE en vez de por título.

`Application(backend="uia").connect(title_re=...)` hace que UI Automation
recorra el escritorio entero. Medido en un equipo real con 389 ventanas de
nivel superior:

    connect(handle=hwnd)             0.0 s
    connect(title_re="Calculadora")  no volvió en 2 minutos

No es "lento": se cuelga. Y el botón Cancelar de la interfaz no puede
sacarte de ahí, porque inyecta la excepción con PyThreadState_SetAsyncExc
y eso solo surte efecto en el siguiente bytecode de Python -- dentro de
una llamada C larga, nunca (ver app/workers.py).

Aquí se prueba la SELECCIÓN de ventana, que es donde está toda la lógica:
Win32 ve más ventanas que pywinauto, y elegir mal significaría teclear en
la ventana equivocada.
"""
from __future__ import annotations

import pytest

from engine.actions import desktop
from engine.actions.desktop import _conectar_rapido, _hwnds_que_coinciden


class _Ventana:
    def __init__(self, hwnd, titulo="", clase="", visible=True, habilitada=True, padre=0):
        self.hwnd, self.titulo, self.clase = hwnd, titulo, clase
        self.visible, self.habilitada, self.padre = visible, habilitada, padre


@pytest.fixture
def escritorio_falso(monkeypatch):
    """Sustituye las llamadas a Win32 por una lista de ventanas de mentira."""

    def _instalar(*ventanas: _Ventana):
        por_hwnd = {v.hwnd: v for v in ventanas}

        def enum(callback, extra):
            for v in ventanas:
                callback(v.hwnd, extra)

        monkeypatch.setattr(desktop.win32gui, "EnumWindows", enum)
        monkeypatch.setattr(desktop.win32gui, "GetWindowText", lambda h: por_hwnd[h].titulo)
        monkeypatch.setattr(desktop.win32gui, "GetClassName", lambda h: por_hwnd[h].clase)
        monkeypatch.setattr(desktop.win32gui, "IsWindowVisible", lambda h: por_hwnd[h].visible)
        monkeypatch.setattr(desktop.win32gui, "IsWindowEnabled", lambda h: por_hwnd[h].habilitada)
        monkeypatch.setattr(desktop.win32gui, "GetParent", lambda h: por_hwnd[h].padre)

    return _instalar


# ------------------------------------------------- selección de ventana


def test_el_titulo_se_compara_como_regex_igual_que_pywinauto(escritorio_falso) -> None:
    escritorio_falso(
        _Ventana(1, titulo="Calculadora"),
        _Ventana(2, titulo="Bloc de notas"),
    )
    assert _hwnds_que_coinciden("Calculadora") == [1]
    assert _hwnds_que_coinciden(r"^Bloc") == [2]
    assert _hwnds_que_coinciden("Excel") == []


def test_sin_filtro_se_ven_las_ventanas_invisibles_a_proposito(escritorio_falso) -> None:
    """`_despertar_ventana` necesita justamente las que UIA no ve: una
    ventana minimizada o 'cloaked' sigue existiendo y hay que restaurarla."""
    escritorio_falso(_Ventana(1, titulo="Calculadora", visible=False))

    assert _hwnds_que_coinciden("Calculadora") == [1]
    assert _hwnds_que_coinciden("Calculadora", solo_visibles=True) == []


def test_solo_visibles_descarta_fantasmas_y_ventanas_hijas(escritorio_falso) -> None:
    """Caso real de la Calculadora: sin filtrar salían tres "Calculadora"
    -- la buena, una invisible y la CoreWindow hija que la app UWP cuelga
    de su ApplicationFrameWindow con el mismo título."""
    escritorio_falso(
        _Ventana(10, titulo="Calculadora", clase="ApplicationFrameWindow"),
        _Ventana(11, titulo="Calculadora", clase="ApplicationFrameWindow", visible=False),
        _Ventana(12, titulo="Calculadora", clase="Windows.UI.Core.CoreWindow", padre=10),
        _Ventana(13, titulo="Calculadora", clase="ApplicationFrameWindow", habilitada=False),
    )
    assert _hwnds_que_coinciden("Calculadora", solo_visibles=True) == [10]


def test_se_puede_buscar_por_clase_para_ventanas_sin_titulo(escritorio_falso) -> None:
    escritorio_falso(
        _Ventana(1, titulo="", clase="Shell_TrayWnd"),
        _Ventana(2, titulo="Otra", clase="Chrome_WidgetWin_1"),
    )
    assert _hwnds_que_coinciden(clase="Shell_TrayWnd") == [1]


# ----------------------------------------------------- el atajo en sí


def test_con_una_sola_ventana_se_conecta_por_handle(escritorio_falso, monkeypatch) -> None:
    escritorio_falso(_Ventana(42, titulo="Calculadora"))
    llamadas = []

    class _App:
        def connect(self, **kwargs):
            llamadas.append(kwargs)
            return self

    # `_conectar_rapido` importa pywinauto DENTRO de la función, así que se
    # sustituye el módulo entero: es el único punto por el que pasa.
    import sys

    monkeypatch.setitem(
        sys.modules, "pywinauto", type("_modulo", (), {"Application": lambda **k: _App()})
    )

    resultado = _conectar_rapido("Calculadora")

    assert resultado is not None
    _app, hwnd = resultado
    assert hwnd == 42
    assert llamadas == [{"handle": 42, "timeout": 5}], "debe ir por handle, nunca por title_re"


def test_con_varias_ventanas_declina_en_vez_de_elegir_una(escritorio_falso) -> None:
    """Con dos ventanas que coinciden no hay forma segura de saber en cuál
    quería teclear el usuario. Se devuelve None y el camino de siempre
    lanza el ElementAmbiguousError de pywinauto, como antes -- elegir por
    nuestra cuenta significaría escribir en la ventana equivocada."""
    escritorio_falso(
        _Ventana(1, titulo="Calculadora"),
        _Ventana(2, titulo="Calculadora"),
    )
    assert _conectar_rapido("Calculadora") is None


def test_sin_ninguna_ventana_declina(escritorio_falso) -> None:
    escritorio_falso(_Ventana(1, titulo="Bloc de notas"))
    assert _conectar_rapido("Calculadora") is None


# ------------------------------- no lanzar una segunda copia de la app


def test_iniciar_o_conectar_no_abre_otra_copia_si_la_app_ya_esta_abierta(
    escritorio_falso, monkeypatch
) -> None:
    """Con dos ventanas que coinciden el atajo declina -- pero la app está
    abierta, así que hay que conectar, no lanzar otra instancia. Sin esta
    comprobación el atajo convertía "conecta si está abierta" en "abre una
    segunda copia", peor que el problema que resuelve.
    """
    from unittest.mock import MagicMock, patch

    from engine.actions.desktop import DesktopActions

    escritorio_falso(_Ventana(1, titulo="Bloc de notas"), _Ventana(2, titulo="Bloc de notas"))

    lanzamientos = []
    monkeypatch.setattr(desktop.subprocess, "Popen", lambda *a, **k: lanzamientos.append(a))

    app_falsa = MagicMock()
    app_falsa.connect.return_value = app_falsa
    acciones = DesktopActions(type("L", (), {"info": lambda *a: None})())

    with patch.dict(
        "sys.modules", {"pywinauto": MagicMock(Application=MagicMock(return_value=app_falsa))}
    ):
        acciones.iniciar_o_conectar("notepad.exe", "Bloc de notas", tiempo_espera=1)

    assert lanzamientos == [], "no debe lanzar la app: ya estaba abierta"
    app_falsa.connect.assert_called_once_with(title_re="Bloc de notas", timeout=1)


# --------------------------------- ventana dormida: despertar y reintentar


def _acciones():
    from engine.actions.desktop import DesktopActions

    return DesktopActions(type("L", (), {"info": lambda *a: None})())


def test_una_ventana_minimizada_se_despierta_y_se_conecta_por_handle(
    escritorio_falso, monkeypatch
) -> None:
    """Antes había que esperar a que `connect(title_re=)` agotara su
    timeout -- o se colgara del todo -- solo para llegar a despertarla."""
    escritorio_falso(_Ventana(7, titulo="Calculadora", visible=False))

    despertadas = []

    def _despertar(titulo_regex=None, clase=None):
        despertadas.append(titulo_regex or clase)
        return 7

    from unittest.mock import MagicMock

    monkeypatch.setattr(desktop, "_despertar_ventana", _despertar)
    app_falsa = MagicMock()
    monkeypatch.setattr(desktop, "_conectar_rapido", lambda *a, **k: (app_falsa, 7))

    acciones = _acciones()
    assert acciones._atajo_tras_despertar(titulo_regex="Calculadora") is True
    assert despertadas == ["Calculadora"]
    app_falsa.window.assert_called_once_with(handle=7), "la ventana se toma por handle"


def test_no_se_despierta_nada_si_ya_hay_ventanas_visibles(escritorio_falso, monkeypatch) -> None:
    """Con dos visibles el atajo declinó por AMBIGÜEDAD, no porque nada se
    vea. Despertar una escondida sería elegir por nuestra cuenta cuál
    usar, justo lo que se quiere evitar."""
    escritorio_falso(
        _Ventana(1, titulo="Calculadora"),
        _Ventana(2, titulo="Calculadora"),
        _Ventana(3, titulo="Calculadora", visible=False),
    )
    monkeypatch.setattr(
        desktop, "_despertar_ventana", lambda **k: pytest.fail("no debía despertar nada")
    )

    assert _acciones()._atajo_tras_despertar(titulo_regex="Calculadora") is False


def test_si_la_app_no_existe_no_se_inventa_una_conexion(escritorio_falso, monkeypatch) -> None:
    escritorio_falso(_Ventana(1, titulo="Otra cosa"))
    monkeypatch.setattr(desktop, "_despertar_ventana", lambda **k: None)

    assert _acciones()._atajo_tras_despertar(titulo_regex="Calculadora") is False
