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

import importlib
import sys
from pathlib import Path

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
from app.widgets.page_header import PageHeader
from app.widgets.toast import mostrar_toast
from core.logger import get_logger
from core.vault import Vault
from engine.actions.desktop_recorder import GrabadoraEscritorio, generar_codigo_escritorio
from engine.actions.recorder import GrabadoraWeb, generar_codigo, nombre_de_clase, validar_nombre
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


class _EmisorHotkeyF5(QObject):
    """El listener de F5 corre en un hilo de pynput (fuera de Qt) --
    emitir una señal es la forma segura de avisarle a la UI desde ahí:
    Qt encola la entrega en el hilo principal en vez de tocar widgets
    directamente desde otro hilo."""

    presionado = Signal()


class _ListenerHotkeyF5(QThread):
    """Escucha F5 globalmente (sin importar que ventana tenga el foco)
    mientras el modo Escritorio esté abierto -- permite iniciar/detener
    la grabación aunque LAAutomate no sea la ventana activa (la
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


class RecorderView(QWidget):
    def __init__(self, on_automatizacion_creada=None) -> None:
        super().__init__()
        self.on_automatizacion_creada = on_automatizacion_creada
        self._modo = "web"  # "web" | "escritorio" -- solo uno grabando a la vez
        self._grabadora: GrabadoraWeb | GrabadoraEscritorio | None = None
        self._worker: _AbrirNavegadorWorker | _IniciarGrabacionEscritorioWorker | None = None
        self._worker_detener: _DetenerGrabacionWorker | _DetenerGrabacionEscritorioWorker | None = None

        # sondeo en vivo de clicks ignorados (modo escritorio): el candado
        # de una sola ventana ignora TODO click fuera de ella -- en un
        # flujo tipo "login -> se abre una ventana de sesión nueva" (ej.
        # VNC), eso significa que todos los clicks posteriores se pierden
        # en silencio. Antes solo se sabía al terminar, revisando el log.
        self._timer_estado_escritorio = QTimer(self)
        self._timer_estado_escritorio.setInterval(500)
        self._timer_estado_escritorio.timeout.connect(self._refrescar_estado_escritorio)

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
        self.boton_modo_web = QPushButton("Web")
        self.boton_modo_escritorio = QPushButton("Escritorio")
        self._grupo_modo = QButtonGroup(self)
        self._grupo_modo.setExclusive(True)
        for boton, modo in ((self.boton_modo_web, "web"), (self.boton_modo_escritorio, "escritorio")):
            boton.setObjectName("modoToggle")
            boton.setCheckable(True)
            boton.setFixedWidth(110)
            self._grupo_modo.addButton(boton)
            boton.clicked.connect(lambda _checked=False, m=modo: self._cambiar_modo(m))
            fila_modo.addWidget(boton)
        self.boton_modo_web.setChecked(True)
        fila_modo.addStretch()
        v_controles.addLayout(fila_modo)

        self.paginas_form = QStackedWidget()

        pagina_web = QWidget()
        fila_form = QHBoxLayout(pagina_web)
        fila_form.setContentsMargins(0, 0, 0, 0)
        fila_form.setSpacing(ESPACIADO.sm)
        fila_form.addWidget(QLabel("Nombre:"))
        self.campo_nombre_web = QLineEdit()
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

        self.estado = QLabel("")
        fila_botones.addWidget(self.estado)
        fila_botones.addStretch()
        v_controles.addLayout(fila_botones)

        layout.addWidget(tarjeta_controles)

        layout.addWidget(self._subtitulo("Código generado"))
        self.vista_codigo = QPlainTextEdit(readOnly=True)
        self.vista_codigo.setObjectName("editorCodigo")
        self.vista_codigo.setPlaceholderText(
            "Aquí vas a ver el código generado en cuanto detengas la grabación."
        )
        layout.addWidget(self.vista_codigo, stretch=1)

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
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        self.boton_iniciar.setEnabled(False)
        self._alternar_toggle_modo(False)
        self.estado.setText("Abriendo navegador…")
        self.estado.setStyleSheet(f"color: {COLORES.grafito}; font-weight: 600;")

        self._worker = _AbrirNavegadorWorker(url)
        self._worker.listo.connect(self._al_iniciar_listo)
        self._worker.error.connect(self._al_iniciar_error)
        self._worker.start()

    def _al_iniciar_listo(self, grabadora: GrabadoraWeb) -> None:
        self._grabadora = grabadora
        self._worker = None  # el worker de arranque ya cumplio (ver _al_iniciar_escritorio_listo)
        self.estado.setText("Grabando… da clicks en el navegador, luego presiona “Detener”")
        self.estado.setStyleSheet(f"color: {COLORES.ocre}; font-weight: 600;")
        self.boton_detener.setEnabled(True)

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

        self.boton_iniciar.setEnabled(False)
        self._alternar_toggle_modo(False)
        self.check_cualquier_ventana.setEnabled(False)
        modo_ventana = "multiple" if self.check_cualquier_ventana.isChecked() else "unica"
        self.estado.setText("Iniciando grabación…")
        self.estado.setStyleSheet(f"color: {COLORES.grafito}; font-weight: 600;")

        self._worker = _IniciarGrabacionEscritorioWorker(modo_ventana=modo_ventana)
        self._worker.listo.connect(self._al_iniciar_escritorio_listo)
        self._worker.error.connect(self._al_iniciar_error)
        self._worker.start()

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
        self._timer_estado_escritorio.start()

    def _refrescar_estado_escritorio(self) -> None:
        if not isinstance(self._grabadora, GrabadoraEscritorio):
            return
        # revinculaciones tiene prioridad y se muestra de forma PERSISTENTE
        # mientras sea > 0 (no solo en el instante en que cambia): es la
        # decisión más consecuente (la grabación empezó a confiar en una
        # ventana distinta a la original) y debe seguir visible durante el
        # resto de la grabación, no solo parpadear un tick.
        revinculadas = self._grabadora.ventanas_revinculadas
        if revinculadas:
            self.estado.setText(
                f"Grabando… (la ventana objetivo cambió {revinculadas} vez/veces porque la anterior "
                "se cerró — si esto no era lo que esperabas, detén la grabación)"
            )
            self.estado.setStyleSheet(f"color: {COLORES.ocre}; font-weight: 600;")
            return

        ignorados = self._grabadora.clicks_ignorados
        if ignorados:
            self.estado.setText(
                f"Grabando… ({ignorados} click(s) ignorados por caer en otra ventana que sigue "
                "abierta — si fue un click tuyo por accidente, ignóralo)"
            )
            self.estado.setStyleSheet(f"color: {COLORES.ocre}; font-weight: 600;")

    def _al_iniciar_error(self, mensaje: str) -> None:
        self._worker = None  # si no se libera, F5 no podria reintentar tras un fallo
        self.boton_iniciar.setEnabled(True)
        self._alternar_toggle_modo(True)
        self.check_cualquier_ventana.setEnabled(True)
        prefijo = "No se pudo abrir el navegador" if self._modo == "web" else "No se pudo iniciar la grabación"
        self._marcar_error(f"{prefijo}: {mensaje}")

    def _detener(self) -> None:
        if self._grabadora is None or self._worker_detener is not None:
            return

        self.boton_detener.setEnabled(False)
        self.estado.setText("Deteniendo grabación…")
        self.estado.setStyleSheet(f"color: {COLORES.grafito}; font-weight: 600;")

        if self._modo == "web":
            self._worker_detener = _DetenerGrabacionWorker(self._grabadora)
        else:
            self._worker_detener = _DetenerGrabacionEscritorioWorker(self._grabadora)
        self._worker_detener.listo.connect(self._al_detener_listo)
        self._worker_detener.error.connect(self._al_detener_error)
        self._worker_detener.start()

    def _al_detener_listo(self, pasos: list) -> None:
        self._timer_estado_escritorio.stop()
        self._grabadora = None
        self._worker_detener = None
        self.boton_iniciar.setEnabled(True)
        self._alternar_toggle_modo(True)
        self.check_cualquier_ventana.setEnabled(True)

        campo_nombre = self.campo_nombre_web if self._modo == "web" else self.campo_nombre_escritorio
        nombre = campo_nombre.text().strip()
        try:
            codigo = generar_codigo(nombre, pasos) if self._modo == "web" else generar_codigo_escritorio(nombre, pasos)
        except ValueError as exc:
            self._marcar_error(str(exc))
            return

        self.vista_codigo.setPlainText(codigo)

        try:
            self._guardar_automatizacion(nombre, codigo)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo al registrar se muestra, no se silencia
            self._marcar_error(
                f"Se generó el código pero no se pudo registrar la automatización: "
                f"{type(exc).__name__}: {exc}"
            )
            return

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
        self._timer_estado_escritorio.stop()
        self._grabadora = None
        self._worker_detener = None
        self.boton_iniciar.setEnabled(True)
        self._alternar_toggle_modo(True)
        self.check_cualquier_ventana.setEnabled(True)
        self._marcar_error(f"Error al detener la grabación: {mensaje}")

    def _guardar_automatizacion(self, nombre: str, codigo: str) -> None:
        carpeta = Path("automations") / nombre
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "automation.py").write_text(codigo, encoding="utf-8")

        clase = nombre_de_clase(nombre)
        (carpeta / "__init__.py").write_text(
            f"from automations.{nombre}.automation import {clase}\n\n__all__ = [{clase!r}]\n",
            encoding="utf-8",
        )

        nombre_modulo = f"automations.{nombre}.automation"
        if nombre_modulo in sys.modules:
            importlib.reload(sys.modules[nombre_modulo])
        else:
            importlib.import_module(nombre_modulo)

    def _marcar_error(self, mensaje: str) -> None:
        self.estado.setText(mensaje)
        self.estado.setStyleSheet(f"color: {COLORES.oxido}; font-weight: 600;")
