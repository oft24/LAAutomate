from __future__ import annotations

import importlib
import ast
import re
import shutil
import sys
from pathlib import Path
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from app.resources.tokens import COLORES, ESPACIADO, TIPO
from app.widgets.empty_state import EmptyState
from app.widgets.page_header import PageHeader
from app.widgets.code_editor import CodeEditor
from app.widgets.python_highlighter import PythonHighlighter
from app.workers import AutomationWorker
from core.gemini_client import tiene_api_key
from core.config import BASE_DIR
from engine.autocorreccion import MAX_INTENTOS
from core.vault import Vault
from engine.registry import AutomationSpec, eliminar as eliminar_del_registro, listar, obtener

_PATRON_CREDENCIALES = re.compile(r"self\.credenciales\.(usuario|password|token)\b")
_CAMPOS_CREDENCIALES = ("usuario", "password", "token")


def _detectar_uso_credenciales(codigo: str) -> set[str]:
    """Que campos de self.credenciales referencia este codigo -- deteccion
    de texto simple (no AST), suficiente porque solo se usa para avisar en
    la UI, nunca para decidir algo de seguridad."""
    return set(_PATRON_CREDENCIALES.findall(codigo))


class AutomationsView(QWidget):
    def __init__(self, scheduler, on_finalizado=None) -> None:
        super().__init__()
        self.scheduler = scheduler
        self.runner = scheduler.runner
        self.on_finalizado = on_finalizado
        self._worker: AutomationWorker | None = None
        self._automatizacion_fallida = ""
        self._nombre_actual: str | None = None
        self._codigo_cargado = ""
        self._borradores: dict[str, tuple[str, str]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(ESPACIADO.md)

        layout.addWidget(
            PageHeader("Automatizaciones", "Elige una para ver, editar o correr su código")
        )

        fila_superior = QHBoxLayout()
        fila_superior.setSpacing(ESPACIADO.md)
        layout.addLayout(fila_superior, stretch=3)

        columna_lista = QVBoxLayout()
        columna_lista.addWidget(self._subtitulo("Registradas"))
        self.campo_busqueda = QLineEdit()
        self.campo_busqueda.setPlaceholderText("Buscar…")
        self.campo_busqueda.textChanged.connect(self._filtrar_lista)
        columna_lista.addWidget(self.campo_busqueda)
        self._contenedor_lista = QWidget()
        self._contenedor_lista.setMaximumWidth(260)
        self._pila_lista = QStackedLayout(self._contenedor_lista)
        self.lista = QListWidget()
        self.lista.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista.currentRowChanged.connect(self._cargar_codigo)
        self._vacio_lista = EmptyState(
            "Sin automatizaciones todavía",
            "Crea tu primera automatización dando tus clics reales en la Grabadora.",
            "Ir a la Grabadora",
            self._ir_a_grabadora,
        )
        self._pila_lista.addWidget(self.lista)
        self._pila_lista.addWidget(self._vacio_lista)
        columna_lista.addWidget(self._contenedor_lista)
        fila_superior.addLayout(columna_lista)

        columna_editor = QVBoxLayout()
        columna_editor.addWidget(self._subtitulo("Código (automation.py) — edítalo y ejecútalo aquí mismo"))
        self.info_boveda = QLabel("")
        self.info_boveda.setWordWrap(True)
        columna_editor.addWidget(self.info_boveda)
        self.editor = CodeEditor()
        self.editor.setObjectName("editorCodigo")
        self.editor.setPlaceholderText("Selecciona una automatización de la lista para ver y editar su código aquí.")
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.setTabStopDistance(28)
        self.editor.textChanged.connect(self._marcar_sin_guardar)
        self._resaltador = PythonHighlighter(self.editor.document())
        columna_editor.addWidget(self.editor)
        fila_superior.addLayout(columna_editor, stretch=1)

        # riel de acciones a la derecha: Ejecutar/Cancelar arriba (lo que
        # se usa a cada corrida), Guardar/Bóveda en medio, Eliminar
        # anclado abajo (para no confundirlo con un click accidental
        # entre los botones de uso frecuente).
        self._contenedor_acciones = QWidget()
        self._contenedor_acciones.setFixedWidth(150)
        columna_acciones = QVBoxLayout(self._contenedor_acciones)
        columna_acciones.setContentsMargins(0, 0, 0, 0)
        columna_acciones.setSpacing(ESPACIADO.sm)
        columna_acciones.addWidget(self._subtitulo("Ejecución"))

        self.boton_ejecutar = QPushButton("▶  Ejecutar")
        self.boton_ejecutar.setObjectName("primario")
        self.boton_ejecutar.clicked.connect(self._ejecutar_seleccionada)
        columna_acciones.addWidget(self.boton_ejecutar)

        self.boton_cancelar = QPushButton("■  Cancelar")
        self.boton_cancelar.setObjectName("peligro")
        self.boton_cancelar.setEnabled(False)
        self.boton_cancelar.clicked.connect(self._cancelar_ejecucion)
        columna_acciones.addWidget(self.boton_cancelar)

        columna_acciones.addSpacing(ESPACIADO.sm)
        columna_acciones.addWidget(self._subtitulo("Código"))

        # Aparece habilitado solo despues de un fallo. Corregir es una
        # decision del usuario, no algo que pase solo: el ciclo automatico
        # dejaba "Ejecutar" bloqueado varios minutos hablando con el
        # modelo, sin que nadie pudiera parar ni mirar el error.
        self.boton_corregir = QPushButton("Corregir código")
        self.boton_corregir.setEnabled(False)
        self.boton_corregir.setToolTip("Se habilita cuando una ejecución falla.")
        self.boton_corregir.clicked.connect(self._corregir_el_ultimo_fallo)
        columna_acciones.addWidget(self.boton_corregir)

        columna_acciones.addSpacing(ESPACIADO.sm)

        self.boton_guardar = QPushButton("Guardar")
        self.boton_guardar.setShortcut("Ctrl+S")
        self.boton_guardar.setToolTip("Guardar cambios (Ctrl+S). Comprueba cambios externos y sintaxis.")
        self.boton_guardar.clicked.connect(self._guardar_codigo)
        columna_acciones.addWidget(self.boton_guardar)

        self.boton_recargar = QPushButton("Recargar archivo")
        self.boton_recargar.setToolTip("Releer automation.py después de editarlo fuera de LaAutomate.")
        self.boton_recargar.clicked.connect(self._recargar_archivo)
        columna_acciones.addWidget(self.boton_recargar)
        columna_acciones.addWidget(self._subtitulo("Configuración"))

        self.boton_boveda = QPushButton("Bóveda")
        self.boton_boveda.clicked.connect(self._ir_a_boveda)
        columna_acciones.addWidget(self.boton_boveda)

        columna_acciones.addStretch()

        self.boton_eliminar = QPushButton("Eliminar")
        self.boton_eliminar.setObjectName("peligro")
        self.boton_eliminar.clicked.connect(self._eliminar_seleccionada)
        columna_acciones.addWidget(self.boton_eliminar)

        fila_superior.addWidget(self._contenedor_acciones)

        self.estado = QLabel("")
        self.estado.setWordWrap(True)
        layout.addWidget(self.estado)

        layout.addWidget(self._subtitulo("Salida en vivo"))
        self.consola = QPlainTextEdit(readOnly=True)
        self.consola.setObjectName("consola")
        self.consola.setPlaceholderText(
            "Selecciona una automatización y presiona “Ejecutar” para ver su log aquí."
        )
        self.consola.setMaximumBlockCount(2000)
        layout.addWidget(self.consola, stretch=2)

        self._llenar_lista()

    @staticmethod
    def _subtitulo(texto: str) -> QLabel:
        etiqueta = QLabel(texto)
        etiqueta.setObjectName("subtituloSeccion")
        return etiqueta

    def _ir_a_grabadora(self) -> None:
        ventana = self.window()
        if hasattr(ventana, "sidebar"):
            ventana.sidebar.establecer_vista("grabadora")

    def _ir_a_boveda(self) -> None:
        ventana = self.window()
        if hasattr(ventana, "sidebar"):
            ventana.sidebar.establecer_vista("boveda")

    def _filtrar_lista(self, texto: str) -> None:
        consulta = texto.strip().lower()
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            item.setHidden(bool(consulta) and consulta not in item.text().lower())

    # ---------- lista y carga de codigo ----------

    def refrescar(self, seleccionar: str | None = None) -> None:
        """Repuebla la lista desde el registry -- llamar despues de crear
        una automatizacion nueva (ej. desde la Grabadora) para que aparezca
        sin tener que reiniciar la app."""
        self._llenar_lista(seleccionar)

    def _llenar_lista(self, seleccionar: str | None = None) -> None:
        self._conservar_borrador()
        seleccionar = seleccionar or self._nombre_actual
        especificaciones = listar()
        self._pila_lista.setCurrentWidget(self._vacio_lista if not especificaciones else self.lista)

        self.lista.clear()
        indice_a_seleccionar = 0
        for i, spec in enumerate(especificaciones):
            self.lista.addItem(spec.nombre)
            self.lista.item(self.lista.count() - 1).setToolTip(
                f"{spec.nombre}\nCategoría: {spec.categoria}\nDisparador: {spec.disparador}"
            )
            if seleccionar and spec.nombre == seleccionar:
                indice_a_seleccionar = i
        if self.lista.count():
            self.lista.setCurrentRow(indice_a_seleccionar)

    def _ruta_codigo(self, spec: AutomationSpec) -> Path:
        return BASE_DIR / "automations" / spec.nombre / "automation.py"

    def _conservar_borrador(self) -> None:
        if self._nombre_actual and self.editor.toPlainText() != self._codigo_cargado:
            self._borradores[self._nombre_actual] = (self.editor.toPlainText(), self._codigo_cargado)
        elif self._nombre_actual:
            self._borradores.pop(self._nombre_actual, None)

    def _recargar_archivo(self) -> None:
        if self._worker is not None or not self._nombre_actual:
            return
        if self.editor.toPlainText() != self._codigo_cargado:
            decision = QMessageBox.question(
                self, "Recargar archivo", "¿Descartar los cambios del editor y leer la versión del archivo?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if decision != QMessageBox.StandardButton.Yes:
                return
        self._borradores.pop(self._nombre_actual, None)
        self._nombre_actual = None
        self._cargar_codigo(self.lista.currentRow())

    def _actualizar_controles(self) -> None:
        seleccion = self._nombre_actual is not None
        libre = self._worker is None
        for boton in (self.boton_ejecutar, self.boton_guardar, self.boton_recargar,
                      self.boton_eliminar, self.boton_boveda):
            boton.setEnabled(seleccion and libre)
        self.editor.setReadOnly(not seleccion or not libre)
        self.lista.setEnabled(libre)
        self.campo_busqueda.setEnabled(libre)
        self.boton_corregir.setEnabled(libre and seleccion and self._automatizacion_fallida == self._nombre_actual)

    def _cargar_codigo(self, indice: int) -> None:
        self._conservar_borrador()
        especificaciones = listar()
        if indice < 0 or indice >= len(especificaciones):
            self._nombre_actual = None
            self._codigo_cargado = ""
            self.editor.clear()
            self.info_boveda.setText("")
            self._actualizar_controles()
            return

        spec = especificaciones[indice]
        ruta = self._ruta_codigo(spec)
        try:
            codigo = ruta.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self._nombre_actual = None
            self._actualizar_controles()
            self._mostrar_error_recarga(f"No se pudo leer {ruta.name}: {exc}")
            return
        self._nombre_actual = spec.nombre
        borrador, base = self._borradores.get(spec.nombre, (codigo, codigo))
        self._codigo_cargado = base
        self.editor.blockSignals(True)
        self.editor.setPlainText(borrador)
        self.editor.blockSignals(False)
        self.estado.setText("")
        self._actualizar_info_boveda(spec.nombre, codigo)
        self._actualizar_controles()
        if self.editor.toPlainText() != codigo:
            self._marcar_sin_guardar()

    def _actualizar_info_boveda(self, nombre: str, codigo: str) -> None:
        campos_usados = _detectar_uso_credenciales(codigo)
        if not campos_usados:
            self.info_boveda.setText("No usa self.credenciales (no depende de la Bóveda).")
            self.info_boveda.setStyleSheet(f"color: {COLORES.grafito}; font-size: {TIPO.t_caption}px;")
            return

        try:
            credenciales = Vault().credenciales_para(nombre)
        except Exception:
            self.info_boveda.setText("No se pudo consultar la Bóveda. Comprueba tus credenciales antes de ejecutar.")
            return
        guardado_por_campo = {
            "usuario": credenciales.usuario is not None,
            "password": credenciales.password is not None,
            "token": credenciales.token is not None,
        }
        partes = [
            f"{campo} {'guardada' if guardado_por_campo[campo] else 'FALTA'}"
            for campo in _CAMPOS_CREDENCIALES
            if campo in campos_usados
        ]
        falta_algo = any(not guardado_por_campo[campo] for campo in campos_usados)
        self.info_boveda.setText("Usa self.credenciales — " + ", ".join(partes))
        color = COLORES.oxido if falta_algo else COLORES.musgo
        self.info_boveda.setStyleSheet(f"color: {color}; font-size: {TIPO.t_caption}px; font-weight: 600;")

    def _marcar_sin_guardar(self) -> None:
        if "sin guardar" not in self.estado.text():
            self.estado.setText("cambios sin guardar")
            self.estado.setStyleSheet(f"color: {COLORES.grafito}; font-weight: 600;")

    # ---------- guardar / recargar / ejecutar ----------

    def _guardar_codigo(self) -> bool:
        indice = self.lista.currentRow()
        if indice < 0 or self._worker is not None:
            return False

        spec = listar()[indice]
        codigo = self.editor.toPlainText()
        ruta = self._ruta_codigo(spec)
        try:
            externo = ruta.read_text(encoding="utf-8")
            if externo != self._codigo_cargado:
                if codigo == self._codigo_cargado:
                    self._nombre_actual = None
                    self._cargar_codigo(indice)
                    self.estado.setText("Archivo actualizado externamente; revísalo y vuelve a ejecutar.")
                else:
                    self._mostrar_error_recarga("El archivo cambió fuera de LaAutomate. Tu borrador sigue aquí; copia tus cambios y usa Recargar archivo para comparar.")
                return False
            arbol = ast.parse(codigo)
            compile(arbol, str(ruta), "exec")
            nombres = [kw.value.value for nodo in arbol.body if isinstance(nodo, ast.ClassDef)
                       for dec in nodo.decorator_list if isinstance(dec, ast.Call) and getattr(dec.func, "id", "") == "registrar"
                       for kw in dec.keywords if kw.arg == "nombre" and isinstance(kw.value, ast.Constant)]
            if nombres != [spec.nombre]:
                raise ValueError(f'Conserva @registrar(nombre="{spec.nombre}") para mantener su identidad e historial.')
            self.scheduler.validar_disparador_codigo(codigo)
            ruta.write_text(codigo, encoding="utf-8")
        except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
            self._mostrar_error_recarga(f"No se guardó el código: {exc}")
            return False
        self._codigo_cargado = codigo
        self._borradores.pop(spec.nombre, None)
        try:
            self._recargar_modulo(spec.nombre)
            self.scheduler.actualizar(obtener(spec.nombre))
        except Exception as exc:
            self._mostrar_error_recarga(f"Archivo guardado, pero no se pudo activar su código/horario: {exc}. Corrígelo antes de ejecutar.")
            return False
        self.estado.setText("Guardado")
        self.estado.setStyleSheet(f"color: {COLORES.grafito}; font-weight: 600;")
        self._actualizar_info_boveda(spec.nombre, codigo)
        return True

    def _recargar_modulo(self, nombre: str) -> None:
        modulo = importlib.import_module(f"automations.{nombre}.automation")
        importlib.reload(modulo)

    def _ejecutar_seleccionada(self) -> None:
        indice = self.lista.currentRow()
        if indice < 0 or self._worker is not None:
            return

        nombre_original = listar()[indice].nombre
        if not self._guardar_codigo():
            return

        try:
            spec = obtener(nombre_original)
        except SyntaxError as exc:
            self._mostrar_error_recarga(f"Error de sintaxis: {exc}")
            return
        except KeyError:
            self._mostrar_error_recarga(
                "No encuentro la automatización tras recargar — "
                "¿cambiaste el nombre en @registrar(nombre=...)? Vuelve a seleccionarla en la lista."
            )
            self._llenar_lista()
            return
        except Exception as exc:  # noqa: BLE001 - cualquier error de import cuenta como fallo de recarga
            self._mostrar_error_recarga(f"Error al recargar el código: {exc}")
            return

        self.consola.clear()
        self.estado.setText(f"Ejecutando {spec.nombre}…")
        self.estado.setStyleSheet(f"color: {COLORES.ocre}; font-weight: 600;")
        self.boton_ejecutar.setEnabled(False)
        self.boton_cancelar.setEnabled(True)

        self.boton_corregir.setEnabled(False)
        self._automatizacion_fallida = ""

        # autocorregir=False: la ejecucion termina donde falla. Reparar es
        # lo que hace el boton "Corregir código", cuando el usuario quiere.
        self._worker = AutomationWorker(self.runner, spec, autocorregir=False)
        self._worker.log_line.connect(self.consola.appendPlainText)
        self._worker.finalizado.connect(lambda resultado: self._al_finalizar(spec.nombre, resultado))
        self._actualizar_controles()
        self._arrancar_worker()

    def _corregir_el_ultimo_fallo(self) -> None:
        """Arranca el ciclo de reparación sobre la automatización que falló.

        Es el ciclo de siempre —bitácora, captura de cada intento, las tres
        puertas del contrato, la práctica aprendida y la versión nueva del
        prompt—, solo que ahora lo pide una persona en vez de dispararse en
        cada fallo. Vuelve a ejecutarla desde cero a propósito: el
        diagnóstico necesita la bitácora de acciones, y una ejecución
        normal no la levanta.

        Sin API key no hay ciclo posible, así que se cae con elegancia al
        camino manual: el fallo cargado en el chat para corregirlo a mano.
        """
        nombre = self._automatizacion_fallida
        if not nombre or self._worker is not None:
            return

        if not tiene_api_key():
            self._corregir_a_mano(nombre, "no hay API key de Gemini configurada")
            return

        try:
            spec = obtener(nombre)
        except KeyError:
            self._mostrar_error_recarga(f"«{nombre}» ya no está registrada.")
            return

        self.consola.clear()
        self.estado.setText(f"Reparando {nombre} con IA (hasta {MAX_INTENTOS} intentos)…")
        self.estado.setStyleSheet(f"color: {COLORES.ocre}; font-weight: 600;")
        self.boton_ejecutar.setEnabled(False)
        self.boton_corregir.setEnabled(False)
        self.boton_cancelar.setEnabled(True)

        self._worker = AutomationWorker(
            self.runner, spec, autocorregir=True, max_intentos=MAX_INTENTOS
        )
        self._worker.log_line.connect(self.consola.appendPlainText)
        self._worker.reparado.connect(self._al_reparar)
        self._worker.finalizado.connect(lambda r: self._al_finalizar(nombre, r))
        self._actualizar_controles()
        self._arrancar_worker()

    def _arrancar_worker(self) -> None:
        from PySide6.QtCore import QThread
        if isinstance(self._worker, QThread):
            # finalizado puede llegar antes de que run() retorne. El padre
            # conserva el hilo hasta finished, aunque se libere _worker.
            self._worker.setParent(self)
            self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _corregir_a_mano(self, nombre: str, motivo: str) -> None:
        """El camino sin IA: el fallo cargado en el chat para revisarlo."""
        ventana = self.window()
        vista = getattr(ventana, "assistant_view", None)
        if vista is None:
            self._mostrar_error_recarga("No encuentro la vista del Asistente IA.")
            return

        hay_rastro = vista.preparar_correccion(nombre)
        if hasattr(ventana, "sidebar"):
            ventana.sidebar.establecer_vista("asistente")
        if not hay_rastro:
            self.estado.setText(f"{nombre}: no hay log ni captura del fallo todavía.")
            self.estado.setStyleSheet(f"color: {COLORES.ocre}; font-weight: 600;")
        else:
            self.estado.setText(f"{nombre}: {motivo}. Te dejé el fallo cargado en el chat.")
            self.estado.setStyleSheet(f"color: {COLORES.ocre}; font-weight: 600;")

    def _al_reparar(self, reparacion) -> None:
        """Recarga el código que dejó la reparación y lo cuenta en el chat.

        Recargar importa: si el ciclo cambió el archivo, el editor seguiría
        enseñando una versión que ya no está en disco, y el siguiente
        "Guardar" la pisaría —deshaciendo el arreglo sin que nadie se
        entere.
        """
        if any(i.aplicado for i in reparacion.intentos):
            self._borradores.pop(self._nombre_actual, None)
            self._nombre_actual = None
            self._cargar_codigo(self.lista.currentRow())

        vista = getattr(self.window(), "assistant_view", None)
        if vista is not None:
            vista.mostrar_reparacion(reparacion)

    def _cancelar_ejecucion(self) -> None:
        if self._worker is None:
            return
        reparando = getattr(self._worker, "autocorregir", False)
        self._worker.cancelar()
        self.boton_cancelar.setEnabled(False)
        self.estado.setText(
            # Durante una reparacion el hilo puede estar esperando la
            # respuesta del modelo, con hasta 2 min de timeout de lectura:
            # decir "unos segundos" ahi es mentir.
            "Cancelando… el modelo puede tardar hasta 2 minutos en responder; "
            "en cuanto conteste, se para."
            if reparando
            else "Cancelando… (puede tardar unos segundos en detenerse)"
        )
        self.estado.setStyleSheet(f"color: {COLORES.ocre}; font-weight: 600;")

    def _mostrar_error_recarga(self, mensaje: str) -> None:
        self.estado.setText(mensaje)
        self.estado.setStyleSheet(f"color: {COLORES.oxido}; font-weight: 600;")

    def _al_finalizar(self, nombre: str, resultado) -> None:
        self.boton_ejecutar.setEnabled(True)
        self.boton_cancelar.setEnabled(False)
        self._worker = None
        self.editor.setReadOnly(False)
        self.lista.setEnabled(True)
        self.campo_busqueda.setEnabled(True)
        for boton in (self.boton_guardar, self.boton_recargar, self.boton_eliminar, self.boton_boveda):
            boton.setEnabled(self._nombre_actual is not None)

        if resultado.success:
            # El mensaje del resultado se enseña: una automatización que
            # termina bien puede tener algo que decir ("creé la plantilla,
            # ábrela y llénala") y tragárselo deja al usuario sin saber
            # qué hacer a continuación.
            detalle = (resultado.message or "").strip()
            self.estado.setText(f"{nombre}: exitoso — {detalle}" if detalle else f"{nombre}: exitoso")
            self.estado.setStyleSheet(f"color: {COLORES.musgo}; font-weight: 600;")
            self.boton_corregir.setEnabled(False)
            self._automatizacion_fallida = ""
        else:
            self.estado.setText(f"{nombre}: falló — {resultado.message}")
            self.estado.setStyleSheet(f"color: {COLORES.oxido}; font-weight: 600;")
            self._automatizacion_fallida = nombre
            self.boton_corregir.setEnabled(True)

        if self.on_finalizado:
            self.on_finalizado()

    # ---------- eliminar ----------

    def _eliminar_seleccionada(self) -> None:
        indice = self.lista.currentRow()
        if indice < 0 or self._worker is not None:
            return

        spec = listar()[indice]
        respuesta = QMessageBox.question(
            self,
            "Eliminar automatización",
            f"¿Eliminar “{spec.nombre}” permanentemente?\n\n"
            "Esto borra su carpeta y código de disco -- no se puede deshacer. "
            "Si guardaste credenciales suyas en la Bóveda, esas NO se eliminan automáticamente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        nombre = spec.nombre
        carpeta = Path("automations") / nombre
        try:
            if carpeta.exists():
                shutil.rmtree(carpeta)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo al borrar se muestra, no se silencia
            self._mostrar_error_recarga(f"No se pudo eliminar “{nombre}”: {type(exc).__name__}: {exc}")
            return

        self.scheduler.desregistrar(nombre)
        eliminar_del_registro(nombre)
        for nombre_modulo in (f"automations.{nombre}.automation", f"automations.{nombre}"):
            sys.modules.pop(nombre_modulo, None)

        self.editor.clear()
        self.info_boveda.setText("")
        self.consola.clear()
        self._llenar_lista()
        self.estado.setText(f"“{nombre}” eliminada")
        self.estado.setStyleSheet(f"color: {COLORES.musgo}; font-weight: 600;")

        if self.on_finalizado:
            self.on_finalizado()
