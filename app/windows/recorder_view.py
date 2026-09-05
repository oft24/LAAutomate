"""Vista de la Grabadora: dos modos.

Modo Web: abre un navegador real, el usuario da clicks y escribe
manualmente para validar cada paso, y al detener se genera el codigo
Python de la automatizacion (self.web.ir_a/click/escribir). Logica de
_AbrirNavegadorWorker / _DetenerGrabacionWorker / GrabadoraWeb identica a
la version anterior.

Modo Escritorio: sin URL ni nada -- el usuario da su primer click en
CUALQUIER ventana de escritorio abierta y esa ventana queda fijada para
el resto de la grabacion (ver GrabadoraEscritorio para el porque de este
diseno). Genera codigo para self.escritorio."""
from __future__ import annotations
from urllib.parse import urlsplit

import os

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.resources.tokens import COLORES, ESPACIADO
from app.widgets.grabacion import EstadoGrabacion, PasosGrabados
from app.widgets.page_header import PageHeader
from app.widgets.python_highlighter import PythonHighlighter
from app.widgets.toast import mostrar_toast
from core.config import LOGS_DIR
from core.logger import get_logger
from core.vault import Vault
from engine.actions.desktop_recorder import GrabadoraEscritorio, generar_codigo_escritorio
from engine.actions.recorder import GrabadoraWeb, generar_codigo, validar_nombre
from engine.almacen import guardar_automatizacion
from engine.actions.web import WebActions


class _DialogoGuardarPassword(QDialog):
    """Se detecto un click en un campo de password durante la grabacion --
    su valor NUNCA se capturo (ver GrabadoraEscritorio: ni siquiera
    transitoriamente en memoria, porque un campo de password de una app
    ajena no garantiza que su texto venga enmascarado). Se le pide al
    usuario que lo escriba aqui, en un campo de password de ESTA app, la
    unica fuente en la que se puede confiar -- y se guarda cifrado en la
    Boveda, nunca en el .py generado."""

    def __init__(self, nombre_automatizacion: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guardar contraseña")
        self.setModal(True)
        self.setMinimumWidth(420)

        v = QVBoxLayout(self)
        v.setContentsMargins(ESPACIADO.xl, ESPACIADO.xl, ESPACIADO.xl, ESPACIADO.xl)
        v.setSpacing(ESPACIADO.md)

        texto = QLabel(
            f"Detectamos un click en un campo de contraseña durante la grabación de "
            f"“{nombre_automatizacion}”. Por seguridad nunca copiamos lo que escribiste ahí -- "
            "ingrésala aquí para guardarla cifrada en la Bóveda de credenciales."
        )
        texto.setWordWrap(True)
        v.addWidget(texto)

        self.campo_password = QLineEdit()
        self.campo_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_password.setPlaceholderText("Contraseña")
        v.addWidget(self.campo_password)

        fila_botones = QHBoxLayout()
        fila_botones.addStretch()
        boton_omitir = QPushButton("Omitir por ahora")
        boton_omitir.clicked.connect(self.reject)
        fila_botones.addWidget(boton_omitir)

        boton_guardar = QPushButton("Guardar en la Bóveda")
        boton_guardar.setObjectName("primario")
        boton_guardar.clicked.connect(self.accept)
        fila_botones.addWidget(boton_guardar)
        v.addLayout(fila_botones)

    def password(self) -> str:
        return self.campo_password.text()


class _DialogoLogGrabadora(QDialog):
    """El log de la grabadora, sin salir de la vista ni esperar a terminar.

    La vista Registros muestra el log MAS RECIENTE de cualquier
    automatización -- que durante una grabación casi nunca es el de la
    grabadora. Y los avisos que importan aquí (clicks ignorados por caer
    en otra ventana, teclas descartadas por foco, revinculaciones) solo
    viven en ese archivo. Se refresca solo cada segundo para poder
    dejarlo abierto en un segundo monitor mientras se graba."""

    _REFRESCO_MS = 1000
    _MAX_CARACTERES = 200_000  # un log largo no debe congelar el diálogo

    def __init__(self, modo: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ruta = LOGS_DIR / ("grabadora_escritorio.log" if modo == "escritorio" else "grabadora.log")
        self.setWindowTitle(f"Registro de la grabadora — {self.ruta.name}")
        self.resize(880, 520)

        v = QVBoxLayout(self)
        v.setContentsMargins(ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg)
        v.setSpacing(ESPACIADO.sm)

        self.texto = QPlainTextEdit(readOnly=True)
        self.texto.setObjectName("consola")
        v.addWidget(self.texto, stretch=1)

        fila = QHBoxLayout()
        self.etiqueta_ruta = QLabel(str(self.ruta))
        self.etiqueta_ruta.setStyleSheet(f"color: {COLORES.grafito};")
        fila.addWidget(self.etiqueta_ruta)
        fila.addStretch()
        boton_carpeta = QPushButton("Abrir carpeta")
        boton_carpeta.clicked.connect(self._abrir_carpeta)
        fila.addWidget(boton_carpeta)
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.setObjectName("primario")
        boton_cerrar.clicked.connect(self.accept)
        fila.addWidget(boton_cerrar)
        v.addLayout(fila)

        self._timer = QTimer(self)
        self._timer.setInterval(self._REFRESCO_MS)
        self._timer.timeout.connect(self._cargar)
        self._timer.start()
        self._cargar()

    def _cargar(self) -> None:
        # se conserva la posición del scroll: si el usuario subió a leer
        # algo, un refresco automático no debe arrastrarlo al final.
        barra = self.texto.verticalScrollBar()
        estaba_al_final = barra.value() >= barra.maximum() - 4
        posicion = barra.value()
        try:
            contenido = self.ruta.read_text(encoding="utf-8", errors="ignore")
        except FileNotFoundError:
            contenido = (
                f"Todavía no existe {self.ruta.name}.\n\n"
                "Se crea en cuanto inicies una grabación en este modo."
            )
        except OSError as exc:
            contenido = f"No se pudo leer {self.ruta}: {type(exc).__name__}: {exc}"
        if len(contenido) > self._MAX_CARACTERES:
            contenido = "[…recortado…]\n" + contenido[-self._MAX_CARACTERES :]
        if contenido == self.texto.toPlainText():
            return
        self.texto.setPlainText(contenido)
        barra.setValue(barra.maximum() if estaba_al_final else min(posicion, barra.maximum()))

    def _abrir_carpeta(self) -> None:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(LOGS_DIR))  # noqa: S606 - abrir con el explorador de Windows

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)


class _EmisorHotkeyF5(QObject):
    """El listener de F5 corre en un hilo de pynput (fuera de Qt) --
    emitir una señal es la forma segura de avisarle a la UI desde ahí:
    Qt encola la entrega en el hilo principal en vez de tocar widgets
    directamente desde otro hilo."""

    presionado = Signal()


class _ListenerHotkeyF5(QThread):
    """Escucha F5 globalmente (sin importar que ventana tenga el foco)
    mientras el modo Escritorio esté abierto -- permite iniciar/detener
    la grabación aunque LaAutomate no sea la ventana activa (la
    grabadora en sí ya requiere eso: casi siempre se está grabando OTRA
    app, no esta)."""

    def __init__(self, emisor: _EmisorHotkeyF5) -> None:
        super().__init__()
        self.emisor = emisor
        self._listener = None

    def run(self) -> None:
        from pynput import keyboard

        def _al_presionar(key) -> None:
            if key == keyboard.Key.f5:
                self.emisor.presionado.emit()

        self._listener = keyboard.Listener(on_press=_al_presionar)
        self._listener.start()
        self._listener.join()

    def detener(self) -> None:
        if self._listener is not None:
            self._listener.stop()
        self.wait(2000)


class _AbrirNavegadorWorker(QThread):
    listo = Signal(object)
    error = Signal(str)

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    def run(self) -> None:
        try:
            logger = get_logger("grabadora")
            web = WebActions(logger, headless=False)
            grabadora = GrabadoraWeb(web, logger)
            grabadora.iniciar(self.url)
            self.listo.emit(grabadora)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo al abrir el navegador se reporta a la UI
            self.error.emit(f"{type(exc).__name__}: {exc}")


class _DetenerGrabacionWorker(QThread):
    """Corre detener()+cerrar() fuera del hilo de la GUI: si la pagina
    quedo con un dialogo nativo abierto (alert/confirm) esas llamadas
    pueden tardar o bloquearse, y no queremos congelar toda la ventana
    mientras eso pasa."""

    listo = Signal(list)
    error = Signal(str)

    def __init__(self, grabadora: GrabadoraWeb) -> None:
        super().__init__()
        self.grabadora = grabadora

    def run(self) -> None:
        try:
            pasos = self.grabadora.detener()
            if self.grabadora.detencion_limpia:
                try:
                    self.grabadora.web.cerrar()
                except Exception as exc:
                    self.grabadora.logger.debug("Error cerrando el navegador: %s", exc)
            else:
                self.grabadora.logger.warning(
                    "No se cerró el navegador automáticamente porque el hilo de sondeo seguía "
                    "activo -- cierra la ventana manualmente si quedó abierta."
                )
            self.listo.emit(pasos)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo al detener se reporta a la UI
            self.error.emit(f"{type(exc).__name__}: {exc}")


class _IniciarGrabacionEscritorioWorker(QThread):
    listo = Signal(object)
    error = Signal(str)

    def __init__(self, modo_ventana: str = "unica") -> None:
        super().__init__()
        self.modo_ventana = modo_ventana

    def run(self) -> None:
        try:
            logger = get_logger("grabadora_escritorio")
            grabadora = GrabadoraEscritorio(logger, modo_ventana=self.modo_ventana)
            grabadora.iniciar()
            self.listo.emit(grabadora)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo al iniciar se reporta a la UI
            self.error.emit(f"{type(exc).__name__}: {exc}")


class _DetenerGrabacionEscritorioWorker(QThread):
    listo = Signal(list)
    error = Signal(str)

    def __init__(self, grabadora: GrabadoraEscritorio) -> None:
        super().__init__()
        self.grabadora = grabadora

    def run(self) -> None:
        try:
            pasos = self.grabadora.detener()
            self.listo.emit(pasos)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo al detener se reporta a la UI
            self.error.emit(f"{type(exc).__name__}: {exc}")


class _CancelarGrabacionWorker(QThread):
    """Cancelar corre fuera del hilo de la GUI por el mismo motivo que
    detener: en modo Web cierra el navegador, y esa llamada puede tardar
    o bloquearse si la página dejó un diálogo nativo abierto. Sirve para
    ambos modos porque las dos grabadoras exponen cancelar()."""

    listo = Signal(int)
    error = Signal(str)

    def __init__(self, grabadora: GrabadoraWeb | GrabadoraEscritorio) -> None:
        super().__init__()
        self.grabadora = grabadora

    def run(self) -> None:
        try:
            self.listo.emit(self.grabadora.cancelar())
        except Exception as exc:  # noqa: BLE001 - cualquier fallo al cancelar se reporta a la UI
            self.error.emit(f"{type(exc).__name__}: {exc}")


class RecorderView(QWidget):
    def __init__(self, on_automatizacion_creada=None) -> None:
        super().__init__()
        self.on_automatizacion_creada = on_automatizacion_creada
        self._modo = "web"  # "web" | "escritorio" -- solo uno grabando a la vez
        self._grabadora: GrabadoraWeb | GrabadoraEscritorio | None = None
        self._worker: _AbrirNavegadorWorker | _IniciarGrabacionEscritorioWorker | None = None
        self._worker_detener: _DetenerGrabacionWorker | _DetenerGrabacionEscritorioWorker | None = None
        self._worker_cancelar: _CancelarGrabacionWorker | None = None
        self._dialogo_log: _DialogoLogGrabadora | None = None

        # sondeo en vivo de clicks ignorados (modo escritorio): el candado
        # de una sola ventana ignora TODO click fuera de ella -- en un
        # flujo tipo "login -> se abre una ventana de sesión nueva" (ej.
        # VNC), eso significa que todos los clicks posteriores se pierden
        # en silencio. Antes solo se sabía al terminar, revisando el log.
        self._timer_estado = QTimer(self)
        self._timer_estado.setInterval(500)
        self._timer_estado.timeout.connect(self._refrescar_estado)

        # F5 inicia/detiene la grabación de escritorio sin importar qué
        # ventana tenga el foco (casi siempre va a ser OTRA app, no esta) --
        # activo solo mientras el modo Escritorio esté abierto.
        self._emisor_f5 = _EmisorHotkeyF5()
        self._emisor_f5.presionado.connect(self._al_presionar_f5)
        self._listener_f5: _ListenerHotkeyF5 | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(ESPACIADO.md)

        layout.addWidget(
            PageHeader(
                "Grabadora",
                "Graba una app web o una app de escritorio dando los clicks tú mismo — al terminar se genera el código",
            )
        )

        tarjeta_controles = QFrame()
        tarjeta_controles.setObjectName("tarjeta")
        v_controles = QVBoxLayout(tarjeta_controles)
        v_controles.setContentsMargins(ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg)
        v_controles.setSpacing(ESPACIADO.md)

        fila_modo = QHBoxLayout()
        fila_modo.setSpacing(ESPACIADO.xs)
        selector_modo = QFrame()
        selector_modo.setObjectName("selectorModo")
        opciones_modo = QHBoxLayout(selector_modo)
        opciones_modo.setContentsMargins(4, 4, 4, 4)
        opciones_modo.setSpacing(4)
        self.boton_modo_web = QPushButton("Web")
        self.boton_modo_escritorio = QPushButton("Escritorio")
        self._grupo_modo = QButtonGroup(self)
        self._grupo_modo.setExclusive(True)
        for boton, modo in ((self.boton_modo_web, "web"), (self.boton_modo_escritorio, "escritorio")):
            boton.setObjectName("modoToggle")
            boton.setCheckable(True)
            boton.setFixedWidth(110)
            boton.setFixedHeight(32)
            self._grupo_modo.addButton(boton)
            boton.clicked.connect(lambda _checked=False, m=modo: self._cambiar_modo(m))
            opciones_modo.addWidget(boton)
        self.boton_modo_web.setChecked(True)
        fila_modo.addWidget(selector_modo)
        fila_modo.addStretch()
        v_controles.addLayout(fila_modo)

        self.paginas_form = QStackedWidget()

        pagina_web = QWidget()
        fila_form = QHBoxLayout(pagina_web)
        fila_form.setContentsMargins(0, 0, 0, 0)
        fila_form.setSpacing(ESPACIADO.sm)
        fila_form.addWidget(QLabel("Nombre:"))
        self.campo_nombre_web = QLineEdit()
        self.campo_nombre_web.setMinimumWidth(220)
        self.campo_nombre_web.setPlaceholderText("mi_proceso_web")
        fila_form.addWidget(self.campo_nombre_web)
        fila_form.addWidget(QLabel("URL inicial:"))
        self.campo_url = QLineEdit()
        self.campo_url.setPlaceholderText("https://...")
        fila_form.addWidget(self.campo_url, stretch=1)
        self.paginas_form.addWidget(pagina_web)

        pagina_escritorio = QWidget()
        fila_form_escritorio = QHBoxLayout(pagina_escritorio)
        fila_form_escritorio.setContentsMargins(0, 0, 0, 0)
        fila_form_escritorio.setSpacing(ESPACIADO.sm)
        fila_form_escritorio.addWidget(QLabel("Nombre:"))
        self.campo_nombre_escritorio = QLineEdit()
        self.campo_nombre_escritorio.setPlaceholderText("mi_proceso_escritorio")
        fila_form_escritorio.addWidget(self.campo_nombre_escritorio)
        self.check_cualquier_ventana = QCheckBox("Cualquier ventana (sin candado) — F5 inicia/detiene")
        self.check_cualquier_ventana.setToolTip(
            "Por defecto solo se graba UNA ventana (la del primer click) -- activa esto SOLO si vas a "
            "dar los clicks tú mismo entre varias apps de tu propio flujo; no lo actives si vas a "
            "simular clicks por código, para no arriesgar capturar contenido de una ventana ajena."
        )
        fila_form_escritorio.addWidget(self.check_cualquier_ventana)
        etiqueta_ayuda = QLabel("Sin URL: al iniciar, da tu primer click en la ventana que quieras grabar")
        etiqueta_ayuda.setStyleSheet(f"color: {COLORES.grafito};")
        fila_form_escritorio.addWidget(etiqueta_ayuda, stretch=1)
        self.paginas_form.addWidget(pagina_escritorio)

        v_controles.addWidget(self.paginas_form)

        fila_botones = QHBoxLayout()
        fila_botones.setSpacing(ESPACIADO.sm)
        self.boton_iniciar = QPushButton("Iniciar grabación")
        self.boton_iniciar.setObjectName("primario")
        self.boton_iniciar.clicked.connect(self._iniciar)
        fila_botones.addWidget(self.boton_iniciar)

        self.boton_detener = QPushButton("Detener y generar código")
        self.boton_detener.setEnabled(False)
        self.boton_detener.clicked.connect(self._detener)
        fila_botones.addWidget(self.boton_detener)

        # Detener genera un borrador; Guardar lo registra. Cancelar descarta
        # la captura sin generar ni escribir código.
        self.boton_cancelar = QPushButton("Cancelar")
        self.boton_cancelar.setEnabled(False)
        self.boton_cancelar.setToolTip(
            "Aborta la grabación y descarta lo capturado -- no genera código ni registra nada."
        )
        self.boton_cancelar.clicked.connect(self._cancelar)
        fila_botones.addWidget(self.boton_cancelar)

        self.boton_logs = QPushButton("Ver registro")
        fila_botones.addStretch()
        self.boton_logs.setToolTip(
            "Abre el log de la grabadora (clicks ignorados, teclas descartadas, revinculaciones). "
            "Se puede dejar abierto mientras grabas."
        )
        self.boton_logs.clicked.connect(self._ver_logs)
        fila_botones.addWidget(self.boton_logs)

        self.estado = QLabel("Lista para grabar · configura el nombre y el destino.")
        self.estado.setWordWrap(True)
        v_controles.addLayout(fila_botones)
        v_controles.addWidget(self.estado)
        self._pendiente_guardar = None
        self._pasos_pendientes = []

        layout.addWidget(tarjeta_controles)

        # Franja de estado en vivo: sustituye a la frase suelta que antes
        # tenia que elegir QUE contar (si avisaba de una revinculacion, los
        # clicks ignorados desaparecian del mensaje). Oculta fuera de una
        # grabacion, donde no hay nada que informar.
        self.panel_estado = EstadoGrabacion()
        self.panel_estado.setVisible(False)
        layout.addWidget(self.panel_estado)

        fila_resultado = QHBoxLayout()
        fila_resultado.setSpacing(ESPACIADO.md)

        columna_pasos = QVBoxLayout()
        columna_pasos.setSpacing(ESPACIADO.sm)
        self.titulo_pasos = self._subtitulo("Pasos capturados")
        columna_pasos.addWidget(self.titulo_pasos)
        tarjeta_pasos = QFrame()
        tarjeta_pasos.setObjectName("tarjeta")
        v_pasos = QVBoxLayout(tarjeta_pasos)
        v_pasos.setContentsMargins(2, 2, 2, 2)
        self.lista_pasos = PasosGrabados()
        v_pasos.addWidget(self.lista_pasos)
        columna_pasos.addWidget(tarjeta_pasos, stretch=1)
        self.contenedor_pasos = QWidget()
        self.contenedor_pasos.setLayout(columna_pasos)
        self.contenedor_pasos.setFixedWidth(340)
        self.contenedor_pasos.setVisible(False)
        fila_resultado.addWidget(self.contenedor_pasos)

        columna_codigo = QVBoxLayout()
        columna_codigo.setSpacing(ESPACIADO.sm)
        cabecera_codigo = QHBoxLayout()
        cabecera_codigo.addWidget(self._subtitulo("Código generado"))
        cabecera_codigo.addStretch()
        columna_codigo.addLayout(cabecera_codigo)
        self.vista_codigo = QPlainTextEdit()
        self.vista_codigo.setReadOnly(True)
        self.vista_codigo.setObjectName("editorCodigo")
        self._resaltador_codigo = PythonHighlighter(self.vista_codigo.document())
        self.vista_codigo.setPlaceholderText(
            "Aquí vas a ver el código generado en cuanto detengas la grabación."
        )
        columna_codigo.addWidget(self.vista_codigo, stretch=1)
        self.boton_guardar = QPushButton("Guardar automatización")
        self.boton_guardar.setFixedWidth(204)
        self.boton_guardar.setToolTip("Disponible después de detener y generar el código. Revisa el borrador antes de guardarlo.")
        self.boton_guardar.setObjectName("primario")
        self.boton_guardar.setEnabled(False)
        self.boton_guardar.clicked.connect(self._guardar_resultado)
        cabecera_codigo.addWidget(self.boton_guardar)
        fila_resultado.addLayout(columna_codigo, stretch=1)

        layout.addLayout(fila_resultado, stretch=1)

    @staticmethod
    def _subtitulo(texto: str) -> QLabel:
        etiqueta = QLabel(texto)
        etiqueta.setObjectName("subtituloSeccion")
        return etiqueta

    def _cambiar_modo(self, modo: str) -> None:
        self._modo = modo
        self.paginas_form.setCurrentIndex(0 if modo == "web" else 1)
        self.estado.setText("")
        if modo == "escritorio":
            self._iniciar_listener_f5()
        else:
            self._detener_listener_f5()

    def _iniciar_listener_f5(self) -> None:
        if self._listener_f5 is not None:
            return
        self._listener_f5 = _ListenerHotkeyF5(self._emisor_f5)
        self._listener_f5.start()

    def _detener_listener_f5(self) -> None:
        if self._listener_f5 is None:
            return
        self._listener_f5.detener()
        self._listener_f5 = None

    def _al_presionar_f5(self) -> None:
        if self._modo != "escritorio":
            return  # F5 solo aplica en modo escritorio
        if self._grabadora is not None:
            self._detener()
        elif self._worker is None and self.boton_iniciar.isEnabled():
            self._iniciar_escritorio()

    def _alternar_toggle_modo(self, habilitado: bool) -> None:
        self.boton_modo_web.setEnabled(habilitado)
        self.boton_modo_escritorio.setEnabled(habilitado)
        for campo in (self.campo_nombre_web, self.campo_nombre_escritorio, self.campo_url):
            campo.setEnabled(habilitado)

    def _iniciar(self) -> None:
        if self._modo == "web":
            self._iniciar_web()
        else:
            self._iniciar_escritorio()

    def _iniciar_web(self) -> None:
        nombre = self.campo_nombre_web.text().strip()
        url = self.campo_url.text().strip()

        if not nombre or not url:
            self._marcar_error("Escribe un nombre y una URL antes de iniciar.")
            return
        try:
            validar_nombre(nombre)
        except ValueError as exc:
            self._marcar_error(str(exc))
            return
        if "://" in url and not url.lower().startswith(("http://", "https://")):
            self._marcar_error("Solo se permiten URLs http:// o https://.")
            return
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        try:
            partes = urlsplit(url)
            if partes.scheme not in ("http", "https") or not partes.hostname or any(c.isspace() for c in url) or partes.username or partes.password:
                raise ValueError("Usa una URL http/https válida, sin usuario ni contraseña.")
            _ = partes.port
        except ValueError as exc:
            self._marcar_error(str(exc))
            return
        if not self._preparar_nueva_grabacion(nombre):
            return

        self.boton_iniciar.setEnabled(False)
        self._alternar_toggle_modo(False)
        self.estado.setText("Abriendo navegador…")
        self.estado.setStyleSheet(f"color: {COLORES.grafito}; font-weight: 600;")

        self._worker = _AbrirNavegadorWorker(url)
        self._worker.listo.connect(self._al_iniciar_listo)
        self._worker.error.connect(self._al_iniciar_error)
        self._arrancar_worker(self._worker)

    def _al_iniciar_listo(self, grabadora: GrabadoraWeb) -> None:
        self._grabadora = grabadora
        self._worker = None  # el worker de arranque ya cumplio (ver _al_iniciar_escritorio_listo)
        self.estado.setText("Grabando… da clicks en el navegador, luego presiona “Detener”")
        self.estado.setStyleSheet(f"color: {COLORES.ocre}; font-weight: 600;")
        self.boton_detener.setEnabled(True)
        self.boton_cancelar.setEnabled(True)
        self._mostrar_panel_en_vivo(True)
        self._timer_estado.start()

    def _iniciar_escritorio(self) -> None:
        nombre = self.campo_nombre_escritorio.text().strip()
        if not nombre:
            self._marcar_error("Escribe un nombre antes de iniciar.")
            return
        try:
            validar_nombre(nombre)
        except ValueError as exc:
            self._marcar_error(str(exc))
            return

        if not self._preparar_nueva_grabacion(nombre):
            return

        self.boton_iniciar.setEnabled(False)
        self._alternar_toggle_modo(False)
        self.check_cualquier_ventana.setEnabled(False)
        modo_ventana = "multiple" if self.check_cualquier_ventana.isChecked() else "unica"
        self.estado.setText("Iniciando grabación…")
        self.estado.setStyleSheet(f"color: {COLORES.grafito}; font-weight: 600;")

        self._worker = _IniciarGrabacionEscritorioWorker(modo_ventana=modo_ventana)
        self._worker.listo.connect(self._al_iniciar_escritorio_listo)
        self._worker.error.connect(self._al_iniciar_error)
        self._arrancar_worker(self._worker)

    def _al_iniciar_escritorio_listo(self, grabadora: GrabadoraEscritorio) -> None:
        self._grabadora = grabadora
        # el worker de arranque ya cumplio: si no se libera, _al_presionar_f5
        # (que exige self._worker is None) solo podria iniciar la PRIMERA
        # grabación de la sesión y F5 quedaba muerto de ahí en adelante.
        self._worker = None
        if grabadora.modo_ventana == "multiple":
            self.estado.setText("Grabando cualquier ventana… da tus clicks — presiona F5 o “Detener” para terminar")
        else:
            self.estado.setText("Grabando… da tu PRIMER click en la ventana que quieras grabar (F5 para detener)")
        self.estado.setStyleSheet(f"color: {COLORES.ocre}; font-weight: 600;")
        self.boton_detener.setEnabled(True)
        self.boton_cancelar.setEnabled(True)
        self._mostrar_panel_en_vivo(True)
        self._timer_estado.start()

    def _refrescar_estado(self) -> None:
        """Sondeo de 500 ms. Ya no arma una frase: alimenta la franja de
        estado y la lista de pasos, que tienen un sitio fijo para cada
        dato. La frase tenia que ELEGIR que contar -- si avisaba de una
        revinculacion, los clicks ignorados desaparecian del mensaje."""
        if self._grabadora is None:
            return
        if isinstance(self._grabadora, GrabadoraEscritorio):
            self.panel_estado.actualizar_escritorio(self._grabadora)
        else:
            self.panel_estado.actualizar_web(self._grabadora)

        pasos = self._grabadora.instantanea_de_pasos()
        self.lista_pasos.establecer_pasos(pasos)
        self.titulo_pasos.setText(f"Pasos capturados ({len(pasos)})")


    def _al_iniciar_error(self, mensaje: str) -> None:
        self._worker = None  # si no se libera, F5 no podria reintentar tras un fallo
        self.boton_iniciar.setEnabled(True)
        self._alternar_toggle_modo(True)
        self.check_cualquier_ventana.setEnabled(True)
        prefijo = "No se pudo abrir el navegador" if self._modo == "web" else "No se pudo iniciar la grabación"
        self._marcar_error(f"{prefijo}: {mensaje}")

    def _ver_logs(self) -> None:
        # no modal, y reutilizando el mismo diálogo: la idea es dejarlo
        # abierto mientras se graba, no interrumpir la grabación.
        if self._dialogo_log is not None and self._dialogo_log.isVisible():
            self._dialogo_log.raise_()
            self._dialogo_log.activateWindow()
            return
        self._dialogo_log = _DialogoLogGrabadora(self._modo, self)
        self._dialogo_log.setModal(False)
        self._dialogo_log.show()

    def _cancelar(self) -> None:
        if self._grabadora is None or self._worker_detener is not None or self._worker_cancelar is not None:
            return

        self.boton_detener.setEnabled(False)
        self.boton_cancelar.setEnabled(False)
        self._timer_estado.stop()
        self.estado.setText("Cancelando grabación…")
        self.estado.setStyleSheet(f"color: {COLORES.grafito}; font-weight: 600;")

        self._worker_cancelar = _CancelarGrabacionWorker(self._grabadora)
        self._worker_cancelar.listo.connect(self._al_cancelar_listo)
        self._worker_cancelar.error.connect(self._al_cancelar_error)
        self._arrancar_worker(self._worker_cancelar)

    def _al_cancelar_listo(self, descartados: int) -> None:
        self._restablecer_controles()
        self.estado.setText(
            f"Grabación cancelada — {descartados} paso(s) descartados, no se creó ninguna automatización"
        )
        self.estado.setStyleSheet(f"color: {COLORES.grafito}; font-weight: 600;")

    def _al_cancelar_error(self, mensaje: str) -> None:
        # aunque cancelar falle, la grabadora ya no sirve: se sueltan los
        # controles igual para no dejar la vista trabada sin salida.
        self._restablecer_controles()
        self._marcar_error(f"Error al cancelar la grabación: {mensaje}")

    def _mostrar_panel_en_vivo(self, visible: bool) -> None:
        """La franja y la lista solo existen mientras se graba: fuera de
        una grabacion no informan nada y le robarian alto al codigo
        generado, que es lo que se revisa al terminar."""
        self.panel_estado.setVisible(visible)
        self.contenedor_pasos.setVisible(visible)
        if visible:
            self.panel_estado.reiniciar()
            self.lista_pasos.establecer_pasos([])
            self.titulo_pasos.setText("Pasos capturados (0)")

    def _restablecer_controles(self) -> None:
        """Deja la vista como antes de grabar. Un solo lugar: cada salida
        (detener, cancelar, error) tenía que acordarse de las mismas seis
        líneas y era fácil olvidar una y dejar un botón trabado."""
        self._timer_estado.stop()
        self._mostrar_panel_en_vivo(False)
        self._grabadora = None
        self._worker_detener = None
        self._worker_cancelar = None
        self.boton_iniciar.setEnabled(True)
        self.boton_detener.setEnabled(False)
        self.boton_cancelar.setEnabled(False)
        self._alternar_toggle_modo(True)
        self.check_cualquier_ventana.setEnabled(True)

    def _detener(self) -> None:
        if self._grabadora is None or self._worker_detener is not None or self._worker_cancelar is not None:
            return

        self.boton_detener.setEnabled(False)
        self.boton_cancelar.setEnabled(False)
        self.estado.setText("Deteniendo grabación…")
        self.estado.setStyleSheet(f"color: {COLORES.grafito}; font-weight: 600;")

        if self._modo == "web":
            self._worker_detener = _DetenerGrabacionWorker(self._grabadora)
        else:
            self._worker_detener = _DetenerGrabacionEscritorioWorker(self._grabadora)
        self._worker_detener.listo.connect(self._al_detener_listo)
        self._worker_detener.error.connect(self._al_detener_error)
        self._arrancar_worker(self._worker_detener)

    def _arrancar_worker(self, worker) -> None:
        if isinstance(worker, QThread):
            worker.setParent(self)
            worker.finished.connect(worker.deleteLater)
        worker.start()

    def _al_detener_listo(self, pasos: list) -> None:
        self._restablecer_controles()

        campo_nombre = self.campo_nombre_web if self._modo == "web" else self.campo_nombre_escritorio
        nombre = campo_nombre.text().strip()
        if not pasos:
            self._marcar_error("No se capturaron acciones. Inicia otra grabación y realiza el flujo antes de detener.")
            return
        try:
            codigo = generar_codigo(nombre, pasos) if self._modo == "web" else generar_codigo_escritorio(nombre, pasos)
        except ValueError as exc:
            self._marcar_error(str(exc))
            return

        self.vista_codigo.setPlainText(codigo)
        self.vista_codigo.setReadOnly(False)
        self._pendiente_guardar = nombre
        self._pasos_pendientes = pasos
        self.boton_guardar.setEnabled(True)
        self.estado.setText(f"Código generado · {len(pasos)} paso(s). Revísalo y pulsa Guardar automatización.")
        self.estado.setStyleSheet(f"color: {COLORES.musgo}; font-weight: 600;")

    def _preparar_nueva_grabacion(self, nombre: str) -> bool:
        from core.config import BASE_DIR
        if (BASE_DIR / "automations" / nombre).exists():
            self._marcar_error("Ese nombre ya existe. Elige otro para conservar la automatización anterior.")
            return False
        if self._pendiente_guardar:
            from PySide6.QtWidgets import QMessageBox
            if QMessageBox.question(self, "Código pendiente", "¿Descartar el código pendiente y comenzar otra grabación?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return False
        self._pendiente_guardar = None
        self._pasos_pendientes = []
        self.boton_guardar.setEnabled(False)
        self.vista_codigo.clear()
        self.vista_codigo.setReadOnly(True)
        return True

    def _guardar_resultado(self) -> None:
        from core.config import BASE_DIR
        if not self._pendiente_guardar:
            return
        nombre = self._pendiente_guardar
        codigo = self.vista_codigo.toPlainText()
        pasos = self._pasos_pendientes
        if (BASE_DIR / "automations" / nombre).exists():
            self._marcar_error("El nombre ya existe en disco. No se sobrescribió. Copia el código para conservarlo.")
            return

        try:
            from engine.scheduler import Scheduler
            import ast
            arbol = ast.parse(codigo)
            compile(arbol, "automation.py", "exec")
            nombres = [kw.value.value for nodo in ast.walk(arbol) if isinstance(nodo, ast.Call)
                       and getattr(nodo.func, "id", "") == "registrar" for kw in nodo.keywords
                       if kw.arg == "nombre" and isinstance(kw.value, ast.Constant)]
            if nombres != [nombre]:
                raise ValueError(f'Conserva @registrar(nombre="{nombre}").')
            Scheduler.validar_disparador_codigo(codigo)
            self._guardar_automatizacion(nombre, codigo)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo al registrar se muestra, no se silencia
            self._marcar_error(
                f"Se generó el código pero no se pudo registrar la automatización: "
                f"{type(exc).__name__}: {exc}"
            )
            return

        self._pendiente_guardar = None
        self.boton_guardar.setEnabled(False)
        self.vista_codigo.setReadOnly(True)

        self.estado.setText(f"“{nombre}” creada con {len(pasos)} paso(s) capturados — revísala en Automatizaciones")
        self.estado.setStyleSheet(f"color: {COLORES.musgo}; font-weight: 600;")

        if self.on_automatizacion_creada:
            self.on_automatizacion_creada(nombre)

        if any(paso.get("tipo") == "click_password" for paso in pasos):
            self._ofrecer_guardar_password(nombre)

    def _ofrecer_guardar_password(self, nombre: str) -> None:
        dialogo = _DialogoGuardarPassword(nombre, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        password = dialogo.password()
        if not password:
            mostrar_toast(self, "No se guardó ninguna contraseña (campo vacío).", "error")
            return

        try:
            Vault().guardar_password(nombre, password)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo al guardar se muestra, no se silencia
            mostrar_toast(self, f"No se pudo guardar la contraseña: {type(exc).__name__}: {exc}", "error")
            return

        mostrar_toast(self, f"Contraseña guardada en la Bóveda para “{nombre}”.", "exito")

    def _al_detener_error(self, mensaje: str) -> None:
        self._restablecer_controles()
        self._marcar_error(f"Error al detener la grabación: {mensaje}")

    def _guardar_automatizacion(self, nombre: str, codigo: str) -> None:
        # Escribir la carpeta, el __init__.py y recargar el modulo vive
        # en engine.almacen: el __init__.py se genera leyendo del codigo
        # QUE clase exportar, en vez de suponer que se llama igual que la
        # carpeta en CamelCase -- cuando no coincide, la automatizacion
        # muere con ImportError al recargar, no al guardar.
        guardar_automatizacion(nombre, codigo)

    def _marcar_error(self, mensaje: str) -> None:
        self.estado.setText(mensaje)
        self.estado.setStyleSheet(f"color: {COLORES.oxido}; font-weight: 600;")
