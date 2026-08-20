"""Grabadora de acciones de escritorio: a diferencia de la Grabadora web
(que necesita una URL), esta escucha clicks y tecleo del sistema -- sin
URL ni nada -- e identifica el control bajo el cursor via UI Automation,
para generar codigo Python listo para correr con self.escritorio
(DesktopActions).

Requiere pynput (listener de mouse/teclado) + pywinauto/pywin32
(identificar el control y la ventana bajo el cursor).

SEGURIDAD / DISENO: el primer click tras iniciar() fija la "ventana
objetivo" de la grabacion (por HWND, no por titulo -- el titulo puede
cambiar). Todo click o tecla fuera de esa ventana, MIENTRAS la ventana
objetivo siga abierta, se IGNORA por completo -- ni se identifica el
control, ni se lee su texto. Esto no es un detalle menor: una version
anterior escuchaba clicks realmente globales (en cualquier ventana del
sistema) y, al probarla, un click mal calculado en una pantalla con
multiples monitores y escalado DPI cayo sobre una ventana de Edge
completamente distinta, capturando texto sensible de otra aplicacion.
Limitar la grabacion a una sola ventana elegida por el primer click
hace que eso sea estructuralmente imposible, no solo improbable.

REVINCULACION: si la ventana objetivo se CIERRA durante la grabacion
(ej. un dialogo de login/busqueda que se cierra y abre una ventana de
sesion nueva, tipico de un cliente VNC/RDP), el siguiente click SI se
acepta y la grabacion se revincula a esa ventana nueva -- porque una
ventana cerrada ya no puede ser el objetivo de un click mal calculado
del incidente original (ese incidente ocurria con la ventana objetivo
TODAVIA abierta). Esto es deliberado y necesario para que la grabadora
sea util en flujos "buscar/lanzar -> abrir app -> interactuar", pero
sigue siendo una decision que vale la pena poder abortar: cada
revinculacion se cuenta en ventanas_revinculadas y se avisa en vivo en
la UI exactamente igual que clicks_ignorados, para que un humano pueda
notar y detener una revinculacion que no esperaba.
"""
from __future__ import annotations

import os
import queue
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import win32con
import win32gui
import win32process

from engine.actions.recorder import nombre_de_clase, validar_nombre  # reusa la misma validacion

_TIPOS_EDITABLES = {"Edit", "ComboBox", "Document"}

# Tope al buscar cuantos controles comparten el mismo (texto, tipo) dentro
# de la ventana grabada. Es solo para desambiguar un click; si hubiera mas
# coincidencias que esto, el texto ya no es un localizador util y se cae a
# coordenadas. Evita recorrer una lista enorme (ej. una tabla con cientos
# de celdas del mismo valor) en cada click.
_MAX_COINCIDENCIAS_A_REVISAR = 12

# Cuanto espera detener() a que el hilo de desambiguacion termine lo que
# tenga pendiente antes de entregar los pasos. Si se agota, se entregan
# igual (los pasos sin desambiguar siguen siendo validos, solo sin
# found_index) -- nunca se cuelga la UI por esto.
_ESPERA_DESAMBIGUACION_AL_DETENER = 8.0

# nombres pynput -> codigo SendKeys de pywinauto, para teclas de
# NAVEGACION (mover la seleccion en una lista/arbol -- ej. moverse entre
# correos en Outlook, filas de Excel, resultados de una busqueda). Se
# capturan SIEMPRE, sin depender de _ultimo_click_editable (navegar una
# lista no es "escribir en un campo"), y sin importar el CONTENIDO de lo
# que se este seleccionando: solo se guarda QUE TECLA se presiono, nunca
# el texto/asunto/remitente del item que quedo seleccionado. Es la forma
# segura de grabar "muevete entre correos" sin que el .py generado
# termine con datos reales de correspondencia.
_NOMBRES_TECLAS_NAVEGACION = {
    "up": "UP",
    "down": "DOWN",
    "left": "LEFT",
    "right": "RIGHT",
    "page_up": "PGUP",
    "page_down": "PGDN",
    "home": "HOME",
    "end": "END",
}


@dataclass
class ResultadoGrabacionEscritorio:
    tipo: str  # "pasos" | "error"
    pasos: list[dict] = field(default_factory=list)
    detalle: dict[str, Any] = field(default_factory=dict)


class GrabadoraEscritorio:
    """Graba clicks/tecleo. Dos modos:

    - "unica" (default, seguro): SOLO la ventana que reciba el primer
      click tras iniciar() -- todo click/tecla en otra ventana, MIENTRAS
      esa primera siga abierta, se ignora por completo (ver el docstring
      del modulo para el incidente real que motiva esto).
    - "multiple" (bajo consentimiento explicito del usuario): graba
      CUALQUIER click, sin importar en que ventana caiga -- cada cambio
      de ventana se trata como una transicion legitima (se conecta a la
      ventana nueva), nunca como un click ignorado. Este modo existe
      porque el candado de una sola ventana protege contra un click
      SIMULADO/programatico mal calculado (el incidente real fue asi);
      un humano real dando clicks con su propio mouse, a proposito,
      entre varias ventanas de su propio flujo de trabajo, no tiene ese
      riesgo -- el usuario debe pedirlo explicitamente para activarlo."""

    def __init__(self, logger, modo_ventana: str = "unica") -> None:
        if modo_ventana not in ("unica", "multiple"):
            raise ValueError(f"modo_ventana debe ser 'unica' o 'multiple', no {modo_ventana!r}")
        self.modo_ventana = modo_ventana
        self.logger = logger
        self.pasos: list[dict] = []
        self._lock = threading.Lock()
        self._grabando = False
        self._listener_mouse = None
        self._listener_teclado = None
        self._hwnd_objetivo: int | None = None
        self._ventana_actual: str | None = None
        self._buffer_texto = ""
        self._ultimo_click_editable = False
        self._ultimo_click_es_password = False
        self._se_tecleo_password = False
        self._clicks_ignorados_fuera_de_ventana = 0
        self._ventanas_revinculadas = 0
        self._marca_conectar_tras_rebind = False
        self._necesita_conectar = False
        self._paso_conectar_actual: dict | None = None
        self._titulos_alternativos: list[str] = []
        self._cola_desambiguacion: queue.Queue = queue.Queue()
        self._hilo_desambiguacion: threading.Thread | None = None

    def iniciar(self) -> None:
        from pynput import keyboard, mouse

        self.pasos = []
        self._hwnd_objetivo = None
        self._ventana_actual = None
        self._buffer_texto = ""
        self._ultimo_click_editable = False
        self._ultimo_click_es_password = False
        self._se_tecleo_password = False
        self._clicks_ignorados_fuera_de_ventana = 0
        self._ventanas_revinculadas = 0
        self._marca_conectar_tras_rebind = False
        self._necesita_conectar = False
        self._paso_conectar_actual = None
        self._titulos_alternativos = []
        self._grabando = True

        # Hilo aparte para desambiguar controles homonimos: esa consulta
        # cuesta cientos de ms de UI Automation y NO puede correr en el
        # callback de pynput. En Windows, pynput despacha el callback en el
        # MISMO hilo que instala el hook de bajo nivel (WH_MOUSE_LL) y que
        # debe seguir bombeando mensajes; si ese hilo se bloquea, Windows
        # deja de entregarle eventos al hook (LowLevelHooksTimeout, 300 ms
        # por defecto) y la grabación se muere en silencio.
        self._cola_desambiguacion = queue.Queue()
        # La cola se le pasa al hilo como ARGUMENTO, no se lee de
        # self._cola_desambiguacion dentro del bucle: si un detener()
        # agota su tope de espera, ese hilo sigue vivo, y al iniciar otra
        # grabacion se pondria a consumir la cola NUEVA -- robandole
        # tareas al hilo nuevo y escribiendo pasos de una grabacion en la
        # otra. Atado a su propia cola, un hilo rezagado solo puede
        # terminar lo suyo.
        self._hilo_desambiguacion = threading.Thread(
            target=self._bucle_desambiguacion,
            args=(self._cola_desambiguacion, self.pasos),
            name="desambiguacion-grabadora",
            daemon=True,
        )
        self._hilo_desambiguacion.start()

        self._listener_mouse = mouse.Listener(on_click=self._al_click)
        self._listener_teclado = keyboard.Listener(on_press=self._al_tecla)
        self._listener_mouse.start()
        self._listener_teclado.start()
        if self.modo_ventana == "multiple":
            self.logger.info(
                "Grabación de escritorio iniciada -- modo múltiples ventanas: se grabará cualquier click, "
                "sin importar en qué ventana caiga"
            )
        else:
            self.logger.info(
                "Grabación de escritorio iniciada -- el primer click define la ventana a grabar; "
                "todo lo demás se ignora"
            )

    def detener(self) -> list[dict]:
        self._grabando = False
        self._flush_texto()
        if self._listener_mouse is not None:
            self._listener_mouse.stop()
        if self._listener_teclado is not None:
            self._listener_teclado.stop()
        self._capturar_titulo_final()
        # Se espera a que la desambiguacion pendiente termine ANTES de
        # copiar los pasos: list(self.pasos) es una copia superficial (los
        # dicts son los mismos), asi que una mutacion posterior tocaria los
        # pasos que ya se estan traduciendo a codigo.
        self._esperar_desambiguacion()
        with self._lock:
            pasos = [dict(p) for p in self.pasos]
        if self._clicks_ignorados_fuera_de_ventana:
            self.logger.info(
                "Se ignoraron %d click(s) fuera de la ventana grabada", self._clicks_ignorados_fuera_de_ventana
            )
        if self._ventanas_revinculadas:
            self.logger.info(
                "La ventana objetivo se revinculó %d vez/veces durante la grabación",
                self._ventanas_revinculadas,
            )
        self.logger.info("Grabación de escritorio detenida: %d paso(s) capturados", len(pasos))
        return pasos

    def _capturar_titulo_final(self) -> None:
        """El titulo de una ventana se observa a partir del SIGUIENTE
        click (es el estado vigente cuando ese click llega, resultado de
        la accion anterior) -- asi que el titulo resultante del ULTIMO
        click de la grabacion nunca se observa, porque no hay un click
        posterior que lo capture. Sin esto, ese ultimo estado (ej. la
        carpeta de Outlook con la que termino la grabacion) queda fuera
        de titulos_alternativos y conectar_por_titulo podria no
        reconocerlo si el usuario vuelve a correr la automatizacion
        estando la app en ese mismo estado."""
        if (
            self._hwnd_objetivo is None
            or self._paso_conectar_actual is None
            or self._paso_conectar_actual.get("modo") != "titulo"
        ):
            return
        try:
            titulo_final = win32gui.GetWindowText(self._hwnd_objetivo) or None
        except Exception:
            return
        if titulo_final and titulo_final not in self._titulos_alternativos:
            with self._lock:
                self._titulos_alternativos.append(titulo_final)
                self._paso_conectar_actual["titulos_alternativos"] = list(self._titulos_alternativos)

    @property
    def clicks_ignorados(self) -> int:
        """Cuantos clicks se han ignorado hasta ahora por caer fuera de la
        ventana objetivo -- antes solo se sabia al TERMINAR la grabación
        (via el log), demasiado tarde para que el usuario ajustara su
        flujo. Expuesto para que la UI pueda avisar EN VIVO -- util sobre
        todo en apps donde una ventana de login se cierra y abre una
        ventana de sesión nueva (ej. un cliente VNC): esos clicks
        posteriores se ignoran todos y sin esto el usuario no se entera
        hasta revisar el código generado."""
        return self._clicks_ignorados_fuera_de_ventana

    @property
    def ventanas_revinculadas(self) -> int:
        """Cuantas veces la ventana objetivo se revinculó a una ventana
        nueva porque la anterior ya no existía (ej. un diálogo de login
        que se cierra y abre una ventana de sesión, típico de VNC/RDP).
        Expuesta con el MISMO criterio que clicks_ignorados: una
        revinculación es una decisión tan consecuente como un click
        ignorado -- el usuario debe poder verla EN VIVO y abortar la
        grabación si no era lo que esperaba."""
        return self._ventanas_revinculadas

    # ---------- callbacks de pynput (corren en el hilo del listener) ----------

    def _al_click(self, x: int, y: int, button, pressed: bool) -> None:
        if not pressed or not self._grabando:
            return

        try:
            hwnd = win32gui.WindowFromPoint((x, y))
            hwnd_raiz = win32gui.GetAncestor(hwnd, win32con.GA_ROOT) or hwnd
        except Exception as exc:
            self.logger.debug("No se pudo identificar la ventana en (%s, %s): %s", x, y, exc)
            return

        if self._es_ventana_propia(hwnd_raiz):
            # Un click sobre la propia app LAAutomate (tipico: el boton
            # "Detener y generar código" que el usuario presiona para
            # TERMINAR la grabación) nunca debe grabarse como parte de la
            # automatización -- ni fijar la ventana objetivo, ni disparar
            # un reenlace, ni contar como click ignorado. Simplemente no
            # existió para la grabadora. Bug real: sin este guard, si la
            # ventana objetivo se cerraba justo antes (ej. una sesión VNC
            # que termina), el siguiente click legítimo del usuario para
            # detener la grabación se reenlazaba a LAAutomate mismo y
            # quedaba como el último paso grabado -- irreproducible, porque
            # ese botón está deshabilitado fuera de una grabación en curso.
            return

        if self._hwnd_objetivo is None:
            self._hwnd_objetivo = hwnd_raiz
            self._necesita_conectar = True
            self.logger.info("Ventana fijada para esta grabación: hwnd=%s", hwnd_raiz)
        elif hwnd_raiz != self._hwnd_objetivo:
            if self.modo_ventana == "multiple":
                # El usuario pidio EXPLICITAMENTE grabar cualquier click,
                # sin importar la ventana -- este modo solo se activa a
                # peticion directa (nunca por default), precisamente
                # porque el candado de "unica" existe para un riesgo
                # distinto (un click SIMULADO/programatico mal calculado,
                # no un humano clickeando de verdad su propio flujo entre
                # varias ventanas). Se cambia de ventana objetivo sin
                # marcarlo como click ignorado ni como revinculacion (esas
                # metricas son para el modo "unica").
                self._hwnd_objetivo = hwnd_raiz
                self._ventana_actual = None
                self._necesita_conectar = True
            else:
                try:
                    objetivo_sigue_vivo = win32gui.IsWindow(self._hwnd_objetivo)
                except Exception as exc:
                    self.logger.debug("No se pudo verificar si la ventana objetivo sigue viva: %s", exc)
                    objetivo_sigue_vivo = True  # ante la duda, comportamiento actual (ignorar)

                if objetivo_sigue_vivo:
                    # la ventana objetivo SIGUE abierta y este click cae en
                    # otra -- este es el incidente original que el candado
                    # existe para impedir: se ignora por completo.
                    self._clicks_ignorados_fuera_de_ventana += 1
                    return

                # La ventana objetivo ya NO EXISTE (se cerró) -- a diferencia
                # del caso anterior, esto es una transicion legitima de flujo
                # (ej. un dialogo de login/busqueda que se cierra y abre una
                # ventana nueva, como un cliente VNC) y no un click mal
                # calculado con la ventana original todavia ahi. Se revincula
                # a la ventana nueva, pero SIEMPRE de forma visible:
                # ventanas_revinculadas se expone en vivo en la UI con el
                # mismo criterio que clicks_ignorados, para que un humano
                # pueda notar y abortar una revinculacion que no esperaba.
                self.logger.warning(
                    "La ventana objetivo (hwnd=%s) ya no existe -- revinculando a hwnd=%s",
                    self._hwnd_objetivo,
                    hwnd_raiz,
                )
                self._hwnd_objetivo = hwnd_raiz
                self._ventana_actual = None
                self._ventanas_revinculadas += 1
                self._marca_conectar_tras_rebind = True
                self._necesita_conectar = True

        self._flush_texto()

        try:
            titulo_ventana = win32gui.GetWindowText(hwnd_raiz) or None
            # No toda ventana tiene titulo (ej. la barra de tareas de
            # Windows, clase "Shell_TrayWnd", siempre reporta titulo
            # vacio) -- sin este respaldo, esas grabaciones nunca emitian
            # un paso "conectar" y el codigo generado fallaba en
            # tiempo de reproduccion con "llama iniciar_o_conectar()
            # antes...". El nombre de clase de Win32 SIEMPRE existe.
            modo = "titulo" if titulo_ventana else "clase"
            identificador = titulo_ventana or win32gui.GetClassName(hwnd_raiz)
            texto_control, tipo_control, es_password = self._control_en(x, y)
            # coordenadas relativas al AREA CLIENTE de la ventana objetivo
            # (no de la pantalla): se calculan aqui, con la MISMA API de
            # Win32 que reproduccion usara (ScreenToClient / pywinauto
            # client_to_screen), para no repetir el desfase de coordenadas
            # entre librerias distintas que ya causo problemas antes.
            x_rel, y_rel = win32gui.ScreenToClient(hwnd_raiz, (x, y))
        except Exception as exc:  # noqa: BLE001 - un click que no se puede identificar simplemente no se graba
            self.logger.debug("No se pudo identificar el control en (%s, %s): %s", x, y, exc)
            return

        paso_click_con_texto: dict | None = None

        with self._lock:
            if identificador and self._necesita_conectar:
                # SOLO se emite un "conectar" nuevo cuando la ventana
                # OBJETIVO recien se fijo (primer click) o se revinculo
                # (hwnd genuinamente distinto) -- nunca por un simple
                # cambio de titulo dentro de la MISMA ventana.
                paso_conectar = {"tipo": "conectar", "modo": modo, "valor": identificador}
                if self._marca_conectar_tras_rebind:
                    # se marca aqui (no en la rama de rebind) porque esa
                    # rama puede mutar _hwnd_objetivo y retornar de una
                    # llamada FALLIDA antes de llegar a este punto (ver
                    # el try/except de arriba) -- la bandera sobrevive
                    # como atributo de instancia hasta que el "conectar"
                    # real se logra emitir, en la primera llamada exitosa
                    # subsecuente.
                    paso_conectar["tras_rebind"] = True
                    self._marca_conectar_tras_rebind = False
                self.pasos.append(paso_conectar)
                self._paso_conectar_actual = paso_conectar
                self._titulos_alternativos = [identificador] if modo == "titulo" else []
                self._ventana_actual = identificador
                self._necesita_conectar = False
            elif (
                identificador
                and modo == "titulo"
                and identificador != self._ventana_actual
                and self._paso_conectar_actual is not None
                and self._paso_conectar_actual.get("modo") == "titulo"
                and identificador not in self._titulos_alternativos
            ):
                # La MISMA ventana (mismo hwnd, sin rebind) cambio de
                # titulo -- ej. Outlook pone el nombre de la carpeta que
                # se esta viendo en el titulo. No hace falta reconectar
                # (self._ventana ya sigue apuntando a la ventana
                # correcta), pero el patron de conexion YA GRABADO
                # quedaria demasiado especifico (solo coincidiria con el
                # titulo de la primera vez) -- se amplia para aceptar
                # CUALQUIERA de los titulos vistos durante esta
                # grabacion, mutando en el lugar el mismo paso "conectar"
                # ya agregado a self.pasos (no se agrega uno nuevo).
                self._titulos_alternativos.append(identificador)
                self._paso_conectar_actual["titulos_alternativos"] = list(self._titulos_alternativos)
                self._ventana_actual = identificador
            if es_password:
                # CurrentIsPassword solo le dice a lectores de pantalla que
                # no lo anuncien -- NO garantiza que window_text() venga
                # enmascarado (muchos Edit nativos Win32/MFC devuelven el
                # valor real igual). Por eso el click en SI sobre un campo
                # de password nunca debe llevar texto_control, ni siquiera
                # si el campo ya tenia algo escrito (typo a corregir,
                # password recordado): solo se guarda el tipo de control.
                # Las COORDENADAS si se guardan (no son secretas, solo la
                # posicion de un campo en pantalla) -- sin esto, el codigo
                # generado nunca hacia click real en el campo de password
                # antes de escribir la credencial, y el tecleo caia sobre
                # el ultimo control que si tuvo foco (ej. el campo de
                # usuario justo antes), escribiendo la contraseña ahi.
                self.pasos.append(
                    {"tipo": "click_password", "control_tipo": tipo_control, "x": x_rel, "y": y_rel}
                )
            elif texto_control:
                # Se agrega YA, sin found_index: resolver la ambiguedad
                # cuesta cientos de ms de consultas UIA y no puede ir antes
                # de comprometer el paso ni las banderas de abajo (ver el
                # bloque de desambiguacion despues de este with).
                paso_click_con_texto = {
                    "tipo": "click",
                    "texto": texto_control,
                    "control_tipo": tipo_control,
                }
                self.pasos.append(paso_click_con_texto)
            else:
                # sin texto identificable (ej. un lienzo/canvas de escritorio
                # remoto en un cliente VNC, o un "Pane" generico) --
                # click_por_texto('') intentaria matchear CUALQUIER control
                # sin titulo; en su lugar se graba un click por coordenada,
                # relativo a esta ventana.
                self.pasos.append(
                    {"tipo": "click_coordenada", "x": x_rel, "y": y_rel, "control_tipo": tipo_control}
                )

        self._ultimo_click_editable = tipo_control in _TIPOS_EDITABLES
        self._ultimo_click_es_password = es_password

        # La desambiguacion (cientos de ms de consultas UIA) se delega al
        # hilo aparte: aqui NO se puede bloquear (ver el comentario de
        # iniciar() sobre el hook de bajo nivel de Windows).
        if paso_click_con_texto is not None:
            self._cola_desambiguacion.put(
                (paso_click_con_texto, hwnd_raiz, texto_control, tipo_control, x, y, x_rel, y_rel)
            )

    # ---------- desambiguacion de controles homonimos (hilo aparte) ----------

    def _bucle_desambiguacion(self, cola: queue.Queue, pasos: list[dict]) -> None:
        """`cola` y `pasos` llegan por argumento (no via self) para que un
        hilo rezagado de una grabacion anterior no toque los de la
        grabacion nueva -- ver el comentario en iniciar()."""
        while True:
            tarea = cola.get()
            try:
                if tarea is None:  # centinela de detener()
                    return
                self._resolver_ambiguedad(pasos, *tarea)
            except Exception as exc:  # noqa: BLE001 - un fallo aqui jamas debe matar el hilo
                self.logger.debug("Fallo desambiguando un click: %s", exc)
            finally:
                cola.task_done()

    def _resolver_ambiguedad(
        self,
        pasos: list[dict],
        paso: dict,
        hwnd_raiz: int,
        texto: str,
        tipo: str,
        x: int,
        y: int,
        x_rel: int,
        y_rel: int,
    ) -> None:
        """Corrige EN EL LUGAR el paso ya grabado cuando su (texto, tipo)
        no identifica un unico control. El paso ya esta en self.pasos desde
        el callback (para no alterar el orden de la secuencia ni retrasar
        las banderas de tecleo); aqui solo se completa."""
        try:
            indice, total = self._indice_entre_coincidencias(hwnd_raiz, texto, tipo, x, y)
        except Exception as exc:  # noqa: BLE001 - si no se puede desambiguar, queda como estaba
            self.logger.debug("No se pudo calcular found_index para %r: %s", texto, exc)
            return
        if total <= 1:
            # total==1: el texto ya identifica un solo control.
            # total==0: NO se degrada a coordenadas. Esta consulta corre en
            # el hilo aparte, cientos de ms DESPUES del click, cuando la app
            # ya reacciono: un boton que alterna su texto ("Conectar" ->
            # "Desconectar") o un panel que se reemplaza dan total=0 aunque
            # el control SI existia al clickear -- y volvera a existir al
            # reproducir, que llega con la app en el estado PRE-click.
            # Degradar aqui convertia un click_por_texto correcto en
            # coordenadas, de forma no determinista (la misma grabacion
            # daba un resultado u otro segun cuanto tardara la app).
            return

        if indice is not None:
            # varios controles comparten texto+tipo (caso real: el icono de
            # una app anclada aparece duplicado en la barra de tareas de un
            # segundo monitor) -- se graba CUAL se clickeo.
            nuevo = {**paso, "found_index": indice}
        else:
            # hay varias coincidencias y no se supo cual -- grabar el texto
            # produciria codigo que revienta al reproducir con
            # ElementAmbiguousError, asi que este paso se convierte a click
            # por coordenada, que siempre identifica un solo punto.
            self.logger.debug(
                "Texto %r ambiguo (%d coincidencias) sin índice claro -- se graba por coordenada",
                texto,
                total,
            )
            nuevo = {"tipo": "click_coordenada", "x": x_rel, "y": y_rel, "control_tipo": tipo}

        # Se REEMPLAZA el elemento de la lista en vez de mutar el dict en
        # el lugar: quien ya tenga una referencia al dict viejo (ej. una
        # copia de detener() que se este traduciendo a codigo) sigue viendo
        # un paso completo y coherente, nunca uno a medio actualizar.
        with self._lock:
            for i, p in enumerate(pasos):
                if p is paso:
                    pasos[i] = nuevo
                    break

    def _esperar_desambiguacion(self) -> None:
        """Deja que el hilo termine lo pendiente antes de entregar los
        pasos. Con tope: si algo se atora, se entregan igual (un paso sin
        found_index sigue siendo valido) en vez de colgar la UI."""
        hilo = self._hilo_desambiguacion
        if hilo is None:
            return
        self._cola_desambiguacion.put(None)  # centinela: termina el bucle
        hilo.join(timeout=_ESPERA_DESAMBIGUACION_AL_DETENER)
        if hilo.is_alive():
            self.logger.warning(
                "La desambiguación de controles no terminó a tiempo -- algunos clicks pueden "
                "quedar sin found_index en el código generado."
            )
        self._hilo_desambiguacion = None

    def _al_tecla(self, key) -> None:
        if not self._grabando or self._hwnd_objetivo is None:
            return

        # el foco de teclado tambien se restringe a la ventana objetivo
        try:
            hwnd_activo = win32gui.GetForegroundWindow()
        except Exception:
            return
        if hwnd_activo != self._hwnd_objetivo:
            return

        from pynput.keyboard import Key

        if key in (Key.enter, Key.tab):
            # Enter suele ser la accion que CONFIRMA/DISPARA el paso (enviar
            # un login, lanzar el resultado seleccionado en el buscador de
            # Windows) -- sin esto, se grababa el texto tecleado pero nunca
            # el Enter que lo confirma, y el flujo grabado quedaba
            # incompleto en tiempo de reproduccion. Tab solo sigue siendo
            # un delimitador de campo (mover el foco ya queda implicito en
            # los siguientes clicks/tecleo).
            editable_antes_del_flush = self._ultimo_click_editable
            self._flush_texto()
            if key == Key.enter and editable_antes_del_flush:
                with self._lock:
                    self.pasos.append({"tipo": "tecla_enter"})
            return

        codigo_navegacion = _NOMBRES_TECLAS_NAVEGACION.get(getattr(key, "name", None))
        if codigo_navegacion:
            self._flush_texto()
            with self._lock:
                self.pasos.append({"tipo": "tecla_navegacion", "tecla": codigo_navegacion})
            return

        caracter = getattr(key, "char", None)
        if not caracter or not self._ultimo_click_editable:
            return

        if self._ultimo_click_es_password:
            # NUNCA se guarda la contraseña real, ni siquiera en memoria
            # mas alla de este callback: solo se marca que se tecleo algo,
            # para que _flush_texto grabe un paso que use la Boveda de
            # credenciales en vez del texto literal.
            with self._lock:
                self._se_tecleo_password = True
            return

        with self._lock:
            self._buffer_texto += caracter

    def _flush_texto(self) -> None:
        with self._lock:
            if self._se_tecleo_password:
                self.pasos.append({"tipo": "escribir_credencial"})
                self._se_tecleo_password = False
            if self._buffer_texto:
                self.pasos.append({"tipo": "escribir", "valor": self._buffer_texto})
                self._buffer_texto = ""

    @staticmethod
    def _es_ventana_propia(hwnd: int) -> bool:
        """True si `hwnd` pertenece a ESTE proceso (la propia app
        LAAutomate) -- comparar por PID, no por título, para que
        cualquier ventana propia (la principal, un diálogo, un toast)
        quede excluida, no solo la ventana principal por su título
        exacto."""
        try:
            _, pid_ventana = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return False
        return pid_ventana == os.getpid()

    @staticmethod
    def _indice_entre_coincidencias(
        hwnd_raiz: int, texto: str, tipo: str, x: int, y: int
    ) -> tuple[int | None, int]:
        """Devuelve (indice_del_control_clickeado, total_de_coincidencias)
        para los controles de la ventana que comparten el mismo
        (texto, tipo). Si solo hay uno, devuelve (None, 1) y quien llama no
        graba found_index -- el localizador por texto ya es unico.

        El indice se calcula recorriendo EXACTAMENTE el mismo camino que
        usa la reproduccion (child_window(..., found_index=i)
        .wrapper_object() de pywinauto), no una enumeracion propia: es la
        unica forma de garantizar que el indice grabado apunte al MISMO
        control al reproducir, porque pywinauto no promete que otras vias
        (ej. descendants()) devuelvan los elementos en el mismo orden.

        Caso real que motiva esto: el icono de una app anclada aparece
        DUPLICADO en la barra de tareas de un segundo monitor
        (Shell_SecondaryTrayWnd), con texto y control_type identicos, y el
        codigo grabado reventaba al reproducir con ElementAmbiguousError."""
        from pywinauto import Application, findwindows

        criterios: dict = {"title": texto}
        if tipo:
            criterios["control_type"] = tipo

        aplicacion = Application(backend="uia").connect(handle=hwnd_raiz, timeout=2)
        ventana = aplicacion.window(handle=hwnd_raiz).wrapper_object()

        # UNA sola consulta con find_elements, en vez de resolver
        # child_window(found_index=i) doce veces. Es la MISMA lista
        # ordenada sobre la que la reproduccion aplica found_index (es el
        # ultimo filtro que aplica find_elements), asi que el indice i de
        # aqui equivale al found_index=i de alla, y visible_only queda en
        # su default True igual que en reproduccion.
        #
        # Antes esto era un bucle que bajaba Timings.window_find_timeout a
        # 0 para no pagar 5 s en la llamada fallida que lo cortaba. Ese
        # timeout es GLOBAL del proceso: si una automatizacion corria en
        # paralelo (cron del Programador o "Ejecutar ahora"), su
        # click_por_texto dejaba de reintentar y reventaba con
        # ElementNotFoundError en vez de esperar a que apareciera su
        # control. Con una sola consulta no hace falta tocar nada global.
        coincidencias = findwindows.find_elements(
            parent=ventana.element_info,
            top_level_only=False,
            backend="uia",
            **criterios,
        )[:_MAX_COINCIDENCIAS_A_REVISAR]

        total = len(coincidencias)
        indice_clickeado: int | None = None
        for i, info in enumerate(coincidencias):
            rect = info.rectangle
            if rect.left <= x <= rect.right and rect.top <= y <= rect.bottom:
                indice_clickeado = i
                break

        return (indice_clickeado if total > 1 else None), total

    # ---------- identificacion del control bajo el cursor (UI Automation) ----------

    @staticmethod
    def _control_en(x: int, y: int) -> tuple[str, str, bool]:
        from pywinauto import Desktop

        elemento = Desktop(backend="uia").from_point(x, y)
        texto = (elemento.window_text() or "").strip()
        tipo = elemento.element_info.control_type or ""
        try:
            # Propiedad estandar de UI Automation (IsPasswordProperty):
            # confirmado contra un QLineEdit real con echoMode Password.
            # Si un click aterriza en un campo asi, lo tecleado despues NO
            # debe terminar como texto plano en el .py generado.
            es_password = bool(elemento.element_info.element.CurrentIsPassword)
        except Exception:
            es_password = False
        return texto, tipo, es_password


def _depurar_pasos(pasos: list[dict]) -> list[dict]:
    """Igual criterio que la Grabadora web: sin 'conectar' repetidos
    consecutivos a la misma ventana, y con el ultimo valor tecleado por
    campo (no cada tecla)."""
    limpios: list[dict] = []
    for paso in pasos:
        if paso["tipo"] == "conectar":
            if (
                limpios
                and limpios[-1]["tipo"] == "conectar"
                and limpios[-1]["valor"] == paso["valor"]
                and limpios[-1]["modo"] == paso["modo"]
            ):
                continue
            limpios.append(paso)
        elif paso["tipo"] == "escribir":
            if limpios and limpios[-1]["tipo"] == "escribir":
                limpios[-1] = paso
            else:
                limpios.append(paso)
        elif paso["tipo"] == "escribir_credencial":
            if not (limpios and limpios[-1]["tipo"] == "escribir_credencial"):
                limpios.append(paso)
        elif paso["tipo"] == "tecla_navegacion":
            # pulsaciones CONSECUTIVAS de la MISMA tecla de navegacion
            # (ej. Down x5 para bajar 5 correos) se juntan en un solo
            # paso con un contador -- mas legible en el codigo generado
            # que 5 lineas idénticas.
            if (
                limpios
                and limpios[-1]["tipo"] == "tecla_navegacion"
                and limpios[-1]["tecla"] == paso["tecla"]
            ):
                limpios[-1] = {**limpios[-1], "veces": limpios[-1].get("veces", 1) + 1}
            else:
                limpios.append(paso)
        elif paso["tipo"] in ("click", "click_coordenada", "click_password", "tecla_enter"):
            limpios.append(paso)
    return limpios


_SALTOS_DE_LINEA = re.compile(r"[\r\n]+")


def generar_codigo_escritorio(nombre_automatizacion: str, pasos: list[dict]) -> str:
    """Traduce los pasos grabados a un automation.py que usa
    self.escritorio -- TODO valor capturado (titulo de ventana, texto de
    control, texto tecleado) se inserta con repr(), nunca crudo: viene de
    una app arbitraria y no se puede confiar en que no traiga comillas,
    backslashes o saltos de linea que rompan el archivo generado."""
    validar_nombre(nombre_automatizacion)
    clase = nombre_de_clase(nombre_automatizacion)

    lineas_cuerpo = []
    for paso in _depurar_pasos(pasos):
        if paso["tipo"] == "conectar":
            # tras un rebind (la ventana anterior se cerro durante la
            # grabacion, ej. login -> sesion VNC), la ventana nueva puede
            # ser un proceso recien lanzado que tarde en aparecer -- se le
            # da mas margen que al conectar inicial (que ya deberia estar
            # abierto). Application(...).connect(timeout=...) de pywinauto
            # ya reintenta internamente durante ese tiempo.
            kwarg_espera = ", tiempo_espera=30" if paso.get("tras_rebind") else ""
            if paso["modo"] == "clase":
                # la ventana no tenia titulo (ej. la barra de tareas) --
                # se conecta por su nombre de clase de Win32 en su lugar.
                lineas_cuerpo.append(f"        self.escritorio.conectar_por_clase({paso['valor']!r}{kwarg_espera})")
            else:
                titulos_alternativos = paso.get("titulos_alternativos")
                if titulos_alternativos and len(titulos_alternativos) > 1:
                    # esta ventana cambio de titulo durante la grabacion
                    # sin cerrarse (ej. Outlook segun la carpeta abierta)
                    # -- se acepta cualquiera de los titulos vistos, no
                    # solo el de la primera vez, para no depender de que
                    # la app este exactamente en el mismo estado al
                    # reproducir.
                    patron = "|".join(re.escape(t) for t in titulos_alternativos)
                else:
                    # re.escape: el titulo se trata como texto literal, no
                    # como regex -- una ventana con parentesis o corchetes en
                    # el titulo (comun, ej. "Documento (recuperado)") no
                    # deberia requerir que el usuario sepa que
                    # conectar_por_titulo espera un patron de regex.
                    patron = re.escape(paso["valor"])
                lineas_cuerpo.append(f"        self.escritorio.conectar_por_titulo({patron!r}{kwarg_espera})")
        elif paso["tipo"] == "click":
            tipo_control = _SALTOS_DE_LINEA.sub(" ", paso.get("control_tipo") or "")
            # control_type como argumento REAL (no solo comentario): acota
            # la busqueda cuando dos controles DISTINTOS comparten el mismo
            # texto visible (ej. dos botones "OK" en dialogos anidados),
            # que de otro modo revienta con un ElementAmbiguousError crudo
            # de pywinauto en tiempo de reproduccion. found_index va cuando
            # ni texto+tipo bastan (ej. el mismo icono repetido en la barra
            # de tareas de un segundo monitor): dice CUAL de los que hacen
            # match se clickeo al grabar.
            argumentos = [repr(paso["texto"])]
            if tipo_control:
                argumentos.append(f"control_type={tipo_control!r}")
            if paso.get("found_index") is not None:
                argumentos.append(f"found_index={paso['found_index']!r}")
            lineas_cuerpo.append(f"        self.escritorio.click_por_texto({', '.join(argumentos)})")
        elif paso["tipo"] == "click_coordenada":
            tipo_control = _SALTOS_DE_LINEA.sub(" ", paso.get("control_tipo") or "")
            comentario = f"  # {tipo_control}, sin texto identificable" if tipo_control else "  # sin texto identificable"
            lineas_cuerpo.append(f"        self.escritorio.click_en({paso['x']!r}, {paso['y']!r}){comentario}")
        elif paso["tipo"] == "click_password":
            # el VALOR del campo nunca se grabo (ver _al_click) -- ni
            # siquiera con repr(), porque simplemente no se captura: es la
            # unica forma de garantizar que una contraseña ya escrita (o
            # recordada/autocompletada) jamas llegue a este archivo. Las
            # coordenadas del click si son reales (no son secretas), asi
            # que este click_en() se ejecuta de verdad -- si fuera solo un
            # comentario, el tecleo de la credencial (linea siguiente)
            # caeria sobre el ultimo campo con foco real, no sobre este.
            tipo_control = _SALTOS_DE_LINEA.sub(" ", paso.get("control_tipo") or "")
            comentario = f"  # campo de {tipo_control or 'password'} -- su valor no se grabó por seguridad"
            lineas_cuerpo.append(f"        self.escritorio.click_en({paso['x']!r}, {paso['y']!r}){comentario}")
        elif paso["tipo"] == "tecla_enter":
            lineas_cuerpo.append('        self.escritorio.atajo("{ENTER}")')
        elif paso["tipo"] == "tecla_navegacion":
            veces = paso.get("veces", 1)
            # tecla ya viene de _NOMBRES_TECLAS_NAVEGACION (valores fijos
            # en codigo, ej. "DOWN") -- nunca texto externo, no hace
            # falta repr()/escape.
            atajo = f"{{{paso['tecla']} {veces}}}" if veces > 1 else f"{{{paso['tecla']}}}"
            lineas_cuerpo.append(f'        self.escritorio.atajo("{atajo}")')
        elif paso["tipo"] == "escribir":
            lineas_cuerpo.append(f"        self.escritorio.escribir({paso['valor']!r})")
        elif paso["tipo"] == "escribir_credencial":
            lineas_cuerpo.append(
                "        self.escritorio.escribir(self.credenciales.password)"
                "  # TODO: guarda esta contraseña en la Bóveda de credenciales (no se grabó en texto plano)"
            )

    if not lineas_cuerpo:
        lineas_cuerpo.append("        pass  # no se capturó ningún paso durante la grabación")

    cuerpo = "\n".join(lineas_cuerpo)

    return (
        '"""Automatizacion generada por la Grabadora de escritorio.\n\n'
        "Revisa cada paso antes de confiar en ella: los controles se "
        "identifican por su texto visible, y pueden necesitar ajuste si "
        'la app cambia de version o de idioma.\n"""\n'
        "from __future__ import annotations\n\n"
        "from engine.automation_base import AutomationResult, BaseAutomation\n"
        "from engine.registry import registrar\n\n\n"
        f'@registrar(nombre={nombre_automatizacion!r}, disparador="manual", categoria="grabada")\n'
        f"class {clase}(BaseAutomation):\n"
        "    def ejecutar(self) -> AutomationResult:\n"
        f"{cuerpo}\n"
        "        return AutomationResult(success=True)\n"
    )
