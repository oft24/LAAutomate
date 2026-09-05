"""Automatizacion de apps de escritorio via clics/teclado (pywinauto +
pyautogui) -- abre o conecta con la ventana de una app real y la controla
como lo haria una persona, sin pasar por ninguna API/COM de esa app."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import re
import subprocess
import time
from pathlib import Path

import win32con
import win32gui

# DWMWA_CLOAKED: Windows "encoge" (cloak) las ventanas de las apps UWP
# suspendidas en segundo plano. La ventana sigue existiendo y hasta
# IsWindowVisible() devuelve 1, pero UI Automation deja de enumerarla por
# completo -- Desktop(backend="uia").windows() devuelve una lista vacia y
# cualquier connect() se queda esperando hasta el timeout. Se comprobo con
# la Calculadora de Windows abierta y en segundo plano: cloaked=2
# (DWM_CLOAKED_SHELL) y connect(title_re="^Calculadora$") fallaba con
# TimeoutError pese a que la app estaba ahi. La unica salida es
# restaurarla primero; ver _despertar_ventana.
_DWMWA_CLOAKED = 14

SCREENSHOTS_DIR = Path("logs/screenshots")

# type_keys() de pywinauto no recibe texto literal, recibe un MINI-LENGUAJE:
# {} delimita teclas especiales, ^ + % son Ctrl/Shift/Alt, ~ es Enter y ()
# agrupa. Escribir un mensaje normal sin escapar esto lo destruye en
# silencio: se comprobo mandando
#   "prueba (LaAutomate) 100% ~ok~ +1 ^arriba^"
# a la caja de mensajes de Discord y lo que quedo escrito fue "rriba" --
# los parentesis se comieron su contenido, % y ^ se tomaron como
# modificadores y ~ como un Enter. Por eso escribir() escapa SIEMPRE.
_ESCAPES_TYPE_KEYS = {
    "{": "{{}",
    "}": "{}}",
    "^": "{^}",
    "+": "{+}",
    "%": "{%}",
    "~": "{~}",
    "(": "{(}",
    ")": "{)}",
}


def escapar_para_type_keys(texto: str) -> str:
    """Convierte texto literal en algo que type_keys() escribe tal cual."""
    return "".join(_ESCAPES_TYPE_KEYS.get(caracter, caracter) for caracter in texto)


def _esta_dormida(hwnd: int) -> bool:
    """True si la ventana esta minimizada o 'cloaked' por el shell."""
    try:
        estilo = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        if estilo & win32con.WS_MINIMIZE:
            return True
        oculta = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), _DWMWA_CLOAKED, ctypes.byref(oculta), ctypes.sizeof(oculta)
        )
        return bool(oculta.value)
    except Exception:
        return False


def _hwnds_que_coinciden(
    titulo_regex: str | None = None, clase: str | None = None, solo_visibles: bool = False
) -> list[int]:
    """HWNDs cuyo titulo/clase hacen match, via EnumWindows de Win32.

    EnumWindows es instantaneo y ve todas las ventanas, incluidas las
    minimizadas y las 'cloaked' que UI Automation esconde. El titulo se
    compara con re.match, igual que el `title_re` de pywinauto.

    `solo_visibles` acota a lo que pywinauto consideraria; sin el salen
    fantasmas y las CoreWindow hijas de una app UWP. Medido con la
    Calculadora: 3 coincidencias sin filtrar, 1 con filtro.
    `_despertar_ventana` no lo usa a proposito: ahi el objetivo es
    justamente la ventana que ya nadie ve.
    """
    candidatas: list[int] = []

    def _revisar(hwnd, _):
        try:
            if solo_visibles and not (
                win32gui.IsWindowVisible(hwnd)
                and win32gui.IsWindowEnabled(hwnd)
                and not win32gui.GetParent(hwnd)
            ):
                return True
            if titulo_regex is not None:
                if not re.match(titulo_regex, win32gui.GetWindowText(hwnd) or ""):
                    return True
            if clase is not None and win32gui.GetClassName(hwnd) != clase:
                return True
            if titulo_regex is None and clase is None:
                return True
            candidatas.append(hwnd)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_revisar, None)
    except Exception:
        return []
    return candidatas


def _conectar_rapido(titulo_regex: str | None = None, clase: str | None = None):
    """Conecta por HANDLE en vez de por titulo/clase, cuando se puede.

    `connect(title_re=...)` hace que UIA recorra el escritorio entero. Con
    muchas ventanas abiertas no es lento: se cuelga. Medido con 389
    ventanas de nivel superior:

        connect(handle=hwnd)             0.0 s
        connect(title_re="Calculadora")  no volvio en 2 minutos

    Y el cuelgue no se puede cancelar: "Cancelar" inyecta la excepcion en
    el siguiente bytecode, que nunca llega dentro de una llamada C larga
    (ver app/workers.py).

    El atajo solo se toma con EXACTAMENTE una coincidencia. Con varias se
    sigue el camino de siempre, para que pywinauto lance su
    ElementAmbiguousError en vez de que este codigo elija por su cuenta.
    Devuelve None si no puede.
    """
    from pywinauto import Application

    candidatas = _hwnds_que_coinciden(titulo_regex, clase, solo_visibles=True)
    if len(candidatas) != 1:
        return None
    try:
        return Application(backend="uia").connect(handle=candidatas[0], timeout=5), candidatas[0]
    except Exception:
        return None


def _despertar_ventana(titulo_regex: str | None = None, clase: str | None = None) -> int | None:
    """Restaura una ventana que UI Automation no puede ver y devuelve su HWND.

    La busqueda se hace con EnumWindows de Win32, que SI ve las ventanas
    minimizadas y cloaked que UIA esconde. Si la encuentra dormida, la
    restaura y la trae al frente para que UIA vuelva a enumerarla.

    Devuelve None si no hay ninguna ventana que haga match -- ahi el
    problema no es que este dormida, es que la app no esta abierta.
    """
    candidatas = _hwnds_que_coinciden(titulo_regex, clase)
    if not candidatas:
        return None

    # se prefiere una que este dormida: es la que hay que despertar
    hwnd = next((h for h in candidatas if _esta_dormida(h)), candidatas[0])
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        # SetForegroundWindow falla si otro proceso tiene el bloqueo de
        # primer plano; el SW_RESTORE ya suele bastar para descloakear.
        pass
    time.sleep(0.6)
    return hwnd


class DesktopActions:
    def __init__(self, logger) -> None:
        self.logger = logger
        self._app = None
        self._ventana = None

    def iniciar_o_conectar(self, comando: str, titulo_regex: str, tiempo_espera: int = 20):
        """Conecta con una ventana ya abierta que haga match con `titulo_regex`;
        si no la encuentra, lanza `comando` y espera a que aparezca."""
        from pywinauto import Application

        if self._intentar_atajo(titulo_regex=titulo_regex):
            self.logger.info("Conectado a ventana existente (%s)", titulo_regex)
            return self._ventana

        if _hwnds_que_coinciden(titulo_regex, solo_visibles=True):
            # El atajo declino (hay varias ventanas que coinciden, o el
            # connect por handle fallo) pero la app SI esta abierta: hay
            # que conectar, no lanzar otra instancia. Sin esta comprobacion
            # el atajo convertiria "conecta si esta abierta" en "abre una
            # segunda copia", que es peor que el problema que resuelve.
            self.logger.info("Ya está abierta (%s); conectando por título", titulo_regex)
            self._app = Application(backend="uia").connect(
                title_re=titulo_regex, timeout=tiempo_espera
            )
            self._ventana = self._app.window(title_re=titulo_regex)
            self._ventana.set_focus()
            return self._ventana

        self.logger.info("No estaba abierta, iniciando: %s", comando)
        subprocess.Popen(comando, shell=True)
        # Tras lanzarla se reintenta el atajo unos segundos: la ventana
        # nueva aparece en EnumWindows antes de que UIA la indexe.
        fin = time.time() + tiempo_espera
        while time.time() < fin:
            if self._intentar_atajo(titulo_regex=titulo_regex):
                return self._ventana
            time.sleep(0.5)

        self._app = Application(backend="uia").connect(title_re=titulo_regex, timeout=tiempo_espera)
        self._ventana = self._app.window(title_re=titulo_regex)
        self._ventana.set_focus()
        return self._ventana

    def _intentar_atajo(self, titulo_regex: str | None = None, clase: str | None = None) -> bool:
        """Conecta por handle si se puede; deja self._app/_ventana listos.

        Devuelve False sin tocar nada cuando no aplica (ninguna ventana
        coincide, o coinciden varias) -- ahi el que llama sigue por el
        camino de siempre. Ver `_conectar_rapido` para por que existe.
        """
        rapido = _conectar_rapido(titulo_regex, clase)
        if rapido is None:
            return False
        app, hwnd = rapido
        self._app = app
        # window(handle=...) y no window(title_re=...): la especificacion
        # perezosa por titulo volveria a lanzar la busqueda lenta la
        # primera vez que alguien la resuelva, deshaciendo el atajo.
        self._ventana = app.window(handle=hwnd)
        try:
            self._ventana.set_focus()
        except Exception:
            # set_focus falla si otro proceso tiene el bloqueo de primer
            # plano; la conexion es valida igual y los clicks siguen yendo
            # a las coordenadas correctas de esa ventana.
            self.logger.info("No se pudo enfocar la ventana; se sigue igualmente")
        return True

    def _atajo_tras_despertar(self, titulo_regex: str | None = None, clase: str | None = None) -> bool:
        """Despierta una ventana dormida y reintenta el atajo por handle.

        Cubre el caso que este modulo ya documentaba (ventana minimizada o
        'cloaked' por el shell, invisible para UI Automation) sin pasar por
        la busqueda lenta: antes habia que esperar a que `connect(title_re=)`
        agotara su timeout -- o se colgara del todo, ver `_conectar_rapido`
        -- solo para llegar a `_despertar_ventana`.

        Solo actua cuando NO hay ninguna ventana visible que coincida: si
        las hay, el atajo ya declino por ambiguedad y despertar una
        escondida elegiria por su cuenta cual usar.
        """
        if _hwnds_que_coinciden(titulo_regex, clase, solo_visibles=True):
            return False
        if _despertar_ventana(titulo_regex=titulo_regex, clase=clase) is None:
            return False
        if not self._intentar_atajo(titulo_regex=titulo_regex, clase=clase):
            return False
        self.logger.info("Ventana estaba dormida -- restaurada y conectada por handle")
        return True

    def conectar_por_titulo(self, titulo_regex: str, tiempo_espera: int = 10):
        """Conecta SOLO con una ventana ya abierta (no la lanza si no
        existe) -- para reproducir una grabacion donde la app ya estaba
        abierta cuando se grabo, sin necesitar el comando de lanzamiento."""
        from pywinauto import Application

        if self._intentar_atajo(titulo_regex=titulo_regex):
            self.logger.info("Conectado a ventana existente (%s)", titulo_regex)
            return self._ventana
        if self._atajo_tras_despertar(titulo_regex=titulo_regex):
            return self._ventana

        try:
            self._app = Application(backend="uia").connect(
                title_re=titulo_regex, timeout=tiempo_espera
            )
        except Exception:
            # Segundo intento tras despertar la ventana: una app UWP
            # suspendida (o cualquier ventana minimizada) es invisible para
            # UI Automation aunque exista -- ver el comentario de
            # _DWMWA_CLOAKED. Sin esto, automatizar una app que el usuario
            # dejo en segundo plano fallaba con un TimeoutError sin pistas.
            if _despertar_ventana(titulo_regex=titulo_regex) is None:
                raise
            self.logger.info("Ventana %s estaba dormida -- restaurada", titulo_regex)
            self._app = Application(backend="uia").connect(
                title_re=titulo_regex, timeout=tiempo_espera
            )
        self._ventana = self._app.window(title_re=titulo_regex)
        self._ventana.set_focus()
        self.logger.info("Conectado a ventana existente (%s)", titulo_regex)
        return self._ventana

    def conectar_por_clase(self, clase: str, tiempo_espera: int = 10):
        """Conecta con una ventana ya abierta por su nombre de clase de
        Win32 en vez de su titulo -- para ventanas SIN titulo (ej. la
        barra de tareas, clase 'Shell_TrayWnd') donde conectar_por_titulo
        no tiene con que hacer match."""
        from pywinauto import Application

        if self._intentar_atajo(clase=clase):
            self.logger.info("Conectado a ventana existente por clase (%s)", clase)
            return self._ventana
        if self._atajo_tras_despertar(clase=clase):
            return self._ventana

        try:
            self._app = Application(backend="uia").connect(class_name=clase, timeout=tiempo_espera)
        except Exception:
            if _despertar_ventana(clase=clase) is None:
                raise
            self.logger.info("Ventana de clase %s estaba dormida -- restaurada", clase)
            self._app = Application(backend="uia").connect(class_name=clase, timeout=tiempo_espera)
        self._ventana = self._app.window(class_name=clase)
        self._ventana.set_focus()
        self.logger.info("Conectado a ventana existente por clase (%s)", clase)
        return self._ventana

    def atajo(self, teclas: str) -> None:
        """Envia un atajo de teclado a la ventana conectada, ej. atajo('^e') para Ctrl+E."""
        self._requiere_ventana()
        self._ventana.type_keys(teclas, pause=0.05)

    def escribir(self, texto: str) -> None:
        if texto is None:
            # el caso mas comun: self.credenciales.usuario/password sin
            # guardar en la Boveda todavia -- sin este check, pywinauto
            # tipea el texto literal "None" en el campo (silencioso y
            # confuso) en vez de avisar claramente que falta la credencial.
            raise ValueError(
                "escribir(None): probablemente self.credenciales.usuario o .password no tiene valor "
                "-- guarda las credenciales de esta automatización en la Bóveda de credenciales."
            )
        self._requiere_ventana()
        # escapado: `texto` es un DATO (lo que el usuario tecleo al grabar,
        # o una credencial de la Boveda), nunca una secuencia de atajos --
        # para eso esta atajo(), que si recibe sintaxis SendKeys cruda.
        self._ventana.type_keys(
            escapar_para_type_keys(texto), with_spaces=True, with_newlines=True, pause=0.02
        )

    def esperar(self, segundos: float) -> None:
        time.sleep(segundos)

    def leer_items_lista(self, control_type: str = "ListItem") -> list[str]:
        """Lee el texto visible de los items de una lista/resultados (arbol
        de accesibilidad UIA) -- para saber cuantos/cuales resultados hay
        sin necesitar OCR ni una captura de pantalla."""
        self._requiere_ventana()
        return [item.window_text() for item in self._ventana.descendants(control_type=control_type)]

    def _resolver_control(self, **criterios):
        """Punto unico de busqueda de un control dentro de la ventana
        conectada -- envuelve ElementAmbiguousError (pywinauto) en un
        error que explica la causa real: el criterio no identifica un
        unico control (ej. dos botones "OK" en dialogos anidados, o una
        lista con items repetidos), y no hay forma segura de saber cual
        click se queria dar. Sin esto, ese caso revienta con una
        excepcion cruda de pywinauto dificil de diagnosticar -- y ademas
        es un fallo dependiente del estado: puede grabarse bien (un solo
        match visible en ese momento) y reventar despues en produccion."""
        from pywinauto.findwindows import ElementAmbiguousError

        self._requiere_ventana()
        try:
            return self._ventana.child_window(**criterios).wrapper_object()
        except ElementAmbiguousError as exc:
            raise RuntimeError(
                f"El criterio {criterios!r} no identifica un único control -- hay varios "
                "controles visibles que hacen match (ej. dos botones \"OK\" en diálogos "
                "anidados, o el mismo ícono repetido en una barra de tareas secundaria de un "
                "segundo monitor). Pasa control_type para acotar la búsqueda, found_index=0 "
                "(o 1, 2...) para elegir cuál de los que hacen match, o usa "
                "self.escritorio.click_en(x, y) si el control no tiene texto ni tipo únicos."
            ) from exc

    def click_por_texto(
        self,
        texto: str,
        control_type: str | None = None,
        found_index: int | None = None,
        pausa: float = 0.08,
    ) -> None:
        """Click con una pausa real entre el mouse-down y el mouse-up.

        Las apps WinUI/XAML (la Calculadora de Windows 11) descartan un
        `click_input()` de pywinauto porque manda los dos eventos
        demasiado rapido. Sin la pausa el click no hace nada, aunque
        aterrice en el pixel correcto.

        `control_type` (ej. "Button") es un criterio extra para evitar
        ElementAmbiguousError cuando dos controles distintos comparten el
        texto visible. `found_index` elige entre los que aun asi empatan;
        hay que probar cual, porque pywinauto no garantiza que su orden
        coincida con el visual."""
        criterios: dict = {"title": texto}
        if control_type:
            criterios["control_type"] = control_type
        if found_index is not None:
            criterios["found_index"] = found_index
        control = self._resolver_control(**criterios)
        control.click_input(button_down=True, button_up=False)
        time.sleep(pausa)
        control.click_input(button_down=False, button_up=True)

    def click_por_tipo(
        self, control_type: str, found_index: int | None = None, pausa: float = 0.08
    ) -> None:
        """Click en un control por su TIPO, sin mirar su texto.

        Existe para los controles donde el "texto visible" no es una
        etiqueta sino el CONTENIDO: en un campo de texto, window_text()
        devuelve lo que hay escrito dentro. Usarlo como localizador da un
        codigo que solo funciona mientras el campo tenga exactamente ese
        valor -- y deja de funcionar en cuanto esta vacio o dice otra cosa.

        Caso real: la caja de mensajes de Discord es un unico Edit cuyo
        window_text() es su propio contenido ('\\ufeff\\n' vacia). La
        grabacion guardaba ese valor como localizador y al reproducir
        reventaba con ElementNotFoundError. Por tipo se resuelve sola,
        porque en esa ventana hay exactamente un Edit.

        `found_index` (0, 1, 2...) elige cual usar si hay varios del mismo
        tipo."""
        criterios: dict = {"control_type": control_type}
        if found_index is not None:
            criterios["found_index"] = found_index
        control = self._resolver_control(**criterios)
        control.click_input(button_down=True, button_up=False)
        time.sleep(pausa)
        control.click_input(button_down=False, button_up=True)

    def click_en(self, x: int, y: int, pausa: float = 0.08) -> None:
        """Click en coordenadas relativas al AREA CLIENTE de la ventana ya
        conectada (lo mismo que graba GrabadoraEscritorio via
        win32gui.ScreenToClient) -- para controles sin texto identificable
        (ej. el lienzo de un escritorio remoto en un cliente VNC, donde no
        hay "botones" reales que UI Automation pueda enumerar, solo una
        imagen de pixeles).

        IMPORTANTE: NO se usa pywinauto.click_input(coords=(x, y),
        absolute=False) -- su client_to_screen() interno suma sobre
        element_info.rectangle, que es el rectangulo EXTERIOR completo de
        la ventana (incluye barra de titulo y bordes), no el area cliente.
        Eso desalinea sistematicamente cada click en el alto de la barra
        de titulo respecto a como se grabo (confirmado con una app real).
        Se usa en su lugar win32gui.ClientToScreen, la API espejo exacta
        de win32gui.ScreenToClient que usa la grabadora -- ambos lados
        quedan en el MISMO sistema de coordenadas, sin mezclar con ninguna
        otra libreria (evitando el tipo de desfase que ya causo problemas
        de click en este proyecto). Misma pausa real entre down/up que
        click_por_texto, por el mismo motivo."""
        import win32gui

        self._requiere_ventana()
        x_pantalla, y_pantalla = win32gui.ClientToScreen(self._ventana.handle, (x, y))
        self._ventana.click_input(coords=(x_pantalla, y_pantalla), absolute=True, button_down=True, button_up=False)
        time.sleep(pausa)
        self._ventana.click_input(coords=(x_pantalla, y_pantalla), absolute=True, button_down=False, button_up=True)

    def click_por_imagen(self, ruta_imagen: str, confianza: float = 0.9, pausa: float = 0.08) -> None:
        """Busca la imagen SOLO dentro del area de la ventana ya conectada,
        si hay una -- buscar en la pantalla completa arriesga encontrar un
        parecido en la ventana equivocada. Si no hay ventana conectada,
        busca en toda la pantalla (para clicks fuera de cualquier ventana
        conocida, ej. un icono del escritorio). Pausa real entre down/up
        por el mismo motivo que click_por_texto.

        pyautogui.locateCenterOnScreen() en Windows SOLO captura el
        monitor PRIMARIO (pyscreeze._screenshot_win32 usa allScreens=False
        y ni locateOnScreen ni locateCenterOnScreen lo exponen) -- si la
        ventana conectada esta en un monitor secundario, la busqueda
        SIEMPRE fallaria aunque la imagen sea visible. Por eso aqui se
        captura explicitamente con allScreens=True y se localiza con
        pyscreeze.locate sobre esa captura completa, traduciendo la
        region/el punto encontrado usando el offset real del escritorio
        virtual (SM_XVIRTUALSCREEN/SM_YVIRTUALSCREEN)."""
        import ctypes

        import pyautogui
        import pyscreeze

        SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
        offset_x = ctypes.windll.user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        offset_y = ctypes.windll.user32.GetSystemMetrics(SM_YVIRTUALSCREEN)

        region = None
        if self._ventana is not None:
            rect = self._ventana.rectangle()
            region = (rect.left - offset_x, rect.top - offset_y, rect.width(), rect.height())

        captura = pyautogui.screenshot(allScreens=True)
        try:
            caja = pyscreeze.locate(ruta_imagen, captura, confidence=confianza, region=region)
        except pyscreeze.ImageNotFoundException:
            caja = None
        if caja is None:
            raise LookupError(f"No se encontro la imagen {ruta_imagen} en pantalla")

        cx, cy = pyscreeze.center(caja)
        x, y = cx + offset_x, cy + offset_y

        pyautogui.mouseDown(x, y)
        time.sleep(pausa)
        pyautogui.mouseUp(x, y)

    def capturar_pantalla(self, nombre: str) -> Path:
        import pyautogui

        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        ruta = SCREENSHOTS_DIR / f"{nombre}.png"
        pyautogui.screenshot(str(ruta))
        self.logger.info("Screenshot de escritorio guardado en %s", ruta)
        return ruta

    def _requiere_ventana(self) -> None:
        if self._ventana is None:
            raise RuntimeError("Llama iniciar_o_conectar() antes de interactuar con la ventana")
