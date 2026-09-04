from __future__ import annotations

import importlib
import re
import shutil
import sys
from pathlib import Path

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
from app.widgets.python_highlighter import PythonHighlighter
from app.workers import AutomationWorker
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
        self.editor = QPlainTextEdit()
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
        columna_acciones.addWidget(self._subtitulo("Acciones"))

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

        self.boton_guardar = QPushButton("Guardar")
        self.boton_guardar.clicked.connect(self._guardar_codigo)
        columna_acciones.addWidget(self.boton_guardar)

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
        especificaciones = listar()
        self._pila_lista.setCurrentWidget(self._vacio_lista if not especificaciones else self.lista)

        self.lista.clear()
        indice_a_seleccionar = 0
        for i, spec in enumerate(especificaciones):
            self.lista.addItem(f"{spec.nombre}  ·  {spec.categoria}  ·  {spec.disparador}")
            if seleccionar and spec.nombre == seleccionar:
                indice_a_seleccionar = i
        if self.lista.count():
            self.lista.setCurrentRow(indice_a_seleccionar)

    def _ruta_codigo(self, spec: AutomationSpec) -> Path:
        return Path("automations") / spec.nombre / "automation.py"

    def _cargar_codigo(self, indice: int) -> None:
        especificaciones = listar()
        if indice < 0 or indice >= len(especificaciones):
            self.editor.clear()
            self.info_boveda.setText("")
            return

        spec = especificaciones[indice]
        ruta = self._ruta_codigo(spec)
        codigo = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
        self.editor.blockSignals(True)
        self.editor.setPlainText(codigo)
        self.editor.blockSignals(False)
        self.estado.setText("")
        self._actualizar_info_boveda(spec.nombre, codigo)

    def _actualizar_info_boveda(self, nombre: str, codigo: str) -> None:
        campos_usados = _detectar_uso_credenciales(codigo)
        if not campos_usados:
            self.info_boveda.setText("No usa self.credenciales (no depende de la Bóveda).")
            self.info_boveda.setStyleSheet(f"color: {COLORES.grafito}; font-size: {TIPO.t_caption}px;")
            return

        credenciales = Vault().credenciales_para(nombre)
        guardado_por_campo = {
            "usuario": credenciales.usuario is not None,
            "password": credenciales.password is not None,
            "token": credenciales.token is not None,
        }
        partes = [
            f"{campo} {'✓' if guardado_por_campo[campo] else '✗ falta guardarla'}"
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
        if indice < 0:
            return False

        spec = listar()[indice]
        codigo = self.editor.toPlainText()
        ruta = self._ruta_codigo(spec)
        ruta.write_text(codigo, encoding="utf-8")
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
        self._guardar_codigo()

        try:
            self._recargar_modulo(nombre_original)
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

        self._worker = AutomationWorker(self.runner, spec)
        self._worker.log_line.connect(self.consola.appendPlainText)
        self._worker.reparado.connect(self._al_reparar)
        self._worker.finalizado.connect(lambda resultado: self._al_finalizar(spec.nombre, resultado))
        self._worker.start()

    def _al_reparar(self, reparacion) -> None:
        """Recarga el codigo que la reparacion dejo y lo cuenta en el chat.

        Recargar importa: si el autocorrector cambio el archivo, el editor
        estaria enseniando una version que ya no es la que hay en disco --
        y el siguiente "Guardar" la pisaria con la vieja, deshaciendo el
        arreglo sin que nadie se entere.
        """
        if any(i.aplicado for i in reparacion.intentos):
            self._cargar_codigo(self.lista.currentRow())

        ventana = self.window()
        vista = getattr(ventana, "assistant_view", None)
        if vista is not None:
            vista.mostrar_reparacion(reparacion)

    def _cancelar_ejecucion(self) -> None:
        if self._worker is None:
            return
        self._worker.cancelar()
        self.boton_cancelar.setEnabled(False)
        self.estado.setText("Cancelando… (puede tardar unos segundos en detenerse)")
        self.estado.setStyleSheet(f"color: {COLORES.ocre}; font-weight: 600;")

    def _mostrar_error_recarga(self, mensaje: str) -> None:
        self.estado.setText(mensaje)
        self.estado.setStyleSheet(f"color: {COLORES.oxido}; font-weight: 600;")

    def _al_finalizar(self, nombre: str, resultado) -> None:
        self.boton_ejecutar.setEnabled(True)
        self.boton_cancelar.setEnabled(False)
        self._worker = None

        if resultado.success:
            self.estado.setText(f"{nombre}: exitoso")
            self.estado.setStyleSheet(f"color: {COLORES.musgo}; font-weight: 600;")
        else:
            self.estado.setText(f"{nombre}: falló — {resultado.message}")
            self.estado.setStyleSheet(f"color: {COLORES.oxido}; font-weight: 600;")

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
