"""Tabla de ejecuciones: columnas flexibles (nombre crece), estado como
badge, fecha legible con relativa debajo, error con tipo en negrita y
detalle completo en un panel lateral al hacer click -- nunca truncado sin
forma de leerlo. Menu de acciones por fila.

Decision: NO se habilita QTableWidget.setSortingEnabled(True). Con celdas
que usan setCellWidget (badge, fecha, menu), el ordenamiento de
QTableWidget desincroniza el widget visual de la fila logica (problema
conocido de Qt) -- reintroducirlo bien requeriria QAbstractTableModel +
QSortFilterProxyModel, un cambio de arquitectura de tabla, no solo visual.
Se deja como mejora futura; por ahora el orden es siempre mas reciente
primero (igual que ya devolvia core.database.historial())."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.resources.tokens import COLORES, DENSIDAD, ESPACIADO
from app.widgets.status_badge import StatusBadge

_MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


@dataclass
class FilaEjecucion:
    automatizacion: str
    exito: bool
    mensaje: str | None
    iniciado_en: str | None
    finalizado_en: str | None
    ruta_captura: Path | None = None
    ruta_log: Path | None = None


class DataTable(QWidget):
    reintentar_solicitado = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._filas: list[FilaEjecucion] = []
        # Que fila esta abierta en el panel lateral. Inicializado a None
        # a proposito: los tres botones del panel lo leen, y sin esta
        # linea existia solo despues del primer _mostrar_detalle -- un
        # AttributeError esperando a cualquier cambio que ensenara el
        # panel por otro camino.
        self._indice_detalle_actual: int | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ESPACIADO.md)

        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(["Automatización", "Estado", "Cuándo", "Duración", "Error", ""])
        self.tabla.verticalHeader().hide()
        self.tabla.verticalHeader().setDefaultSectionSize(DENSIDAD.alto_fila)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.tabla.setShowGrid(False)
        self.tabla.itemSelectionChanged.connect(self._al_seleccionar)

        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        # Fixed, no ResizeToContents: un cell widget (el badge de estado) no
        # siempre reporta su sizeHint real a tiempo para el calculo
        # automatico de ancho -- resultaba en "Completado" cortado a
        # "Completa". Un ancho fijo generoso evita ese corte.
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tabla.setColumnWidth(1, 130)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.tabla, stretch=1)

        self.panel_detalle = self._construir_panel_detalle()
        self.panel_detalle.hide()
        layout.addWidget(self.panel_detalle)

    # ---------- construccion del panel lateral ----------

    def _construir_panel_detalle(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("tarjeta")
        panel.setFixedWidth(300)
        v = QVBoxLayout(panel)
        v.setContentsMargins(ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg, ESPACIADO.lg)
        v.setSpacing(ESPACIADO.sm)

        fila_cierre = QHBoxLayout()
        self._panel_titulo = QLabel("Detalle")
        self._panel_titulo.setStyleSheet("font-weight: 600; font-size: 14px;")
        fila_cierre.addWidget(self._panel_titulo)
        fila_cierre.addStretch()
        boton_cerrar = QPushButton("✕")
        boton_cerrar.setFixedSize(24, 24)
        boton_cerrar.clicked.connect(lambda: panel.hide())
        fila_cierre.addWidget(boton_cerrar)
        v.addLayout(fila_cierre)

        self._panel_estado = QWidget()
        v.addWidget(self._panel_estado)

        self._panel_mensaje = QLabel("")
        self._panel_mensaje.setWordWrap(True)
        self._panel_mensaje.setStyleSheet(f"color: {COLORES.tinta}; font-size: 13px;")
        v.addWidget(self._panel_mensaje)

        v.addStretch()

        self._boton_captura = QPushButton("Ver captura de pantalla")
        self._boton_captura.clicked.connect(self._abrir_captura_actual)
        v.addWidget(self._boton_captura)

        self._boton_log = QPushButton("Abrir log completo")
        self._boton_log.clicked.connect(self._abrir_log_actual)
        v.addWidget(self._boton_log)

        self._boton_reintentar = QPushButton("Reintentar")
        self._boton_reintentar.setObjectName("primario")
        self._boton_reintentar.clicked.connect(self._reintentar_actual)
        v.addWidget(self._boton_reintentar)

        return panel

    # ---------- llenado de filas ----------

    def establecer_filas(self, filas: list[FilaEjecucion]) -> None:
        self._filas = filas
        self.tabla.setRowCount(len(filas))
        for i, fila in enumerate(filas):
            self._pintar_fila(i, fila)
        self.panel_detalle.hide()
        self._indice_detalle_actual = None

    def mostrar_fila(self, indice: int) -> None:
        """API publica para que otro widget (ej. StepTrack) pida abrir el
        panel de detalle de una fila por indice."""
        self._mostrar_detalle(indice)

    def _pintar_fila(self, i: int, fila: FilaEjecucion) -> None:
        item_nombre = QTableWidgetItem(fila.automatizacion)
        item_nombre.setToolTip(fila.automatizacion)
        self.tabla.setItem(i, 0, item_nombre)

        self.tabla.setCellWidget(i, 1, self._centrado(StatusBadge(StatusBadge.desde_exito(fila.exito))))

        self.tabla.setCellWidget(i, 2, self._widget_cuando(fila.iniciado_en))

        item_duracion = QTableWidgetItem(self._formatear_duracion(fila.iniciado_en, fila.finalizado_en))
        item_duracion.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabla.setItem(i, 3, item_duracion)

        tipo, _detalle = self._separar_error(fila.mensaje)
        item_error = QTableWidgetItem(tipo)
        fuente = item_error.font()
        fuente.setBold(True)
        item_error.setFont(fuente)
        item_error.setToolTip(fila.mensaje or "")
        if not fila.exito:
            item_error.setForeground(QColor(COLORES.oxido))
        self.tabla.setItem(i, 4, item_error)

        self.tabla.setCellWidget(i, 5, self._boton_menu(i))

        if not fila.exito:
            # La fila entera se tiñe apenas. El badge de estado ya dice
            # "Con error", pero en una tabla de veinte filas hay que LEER
            # esa columna para encontrarlo; el tinte se ve sin leer nada.
            # COLORES.fila_error es mas claro que oxido_suave a proposito
            # (ver tokens.py) y no se toca el color del texto: la fila
            # sigue siendo legible, no un bloque rojo.
            for columna in (0, 3, 4):
                celda = self.tabla.item(i, columna)
                if celda is not None:
                    celda.setBackground(QColor(COLORES.fila_error))

    @staticmethod
    def _centrado(widget: QWidget) -> QWidget:
        envoltorio = QWidget()
        l = QHBoxLayout(envoltorio)
        l.setContentsMargins(0, 0, 0, 0)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(widget)
        return envoltorio

    def _widget_cuando(self, iniciado_en: str | None) -> QWidget:
        envoltorio = QWidget()
        v = QVBoxLayout(envoltorio)
        v.setContentsMargins(ESPACIADO.sm, 2, ESPACIADO.sm, 2)
        v.setSpacing(0)

        dt = self._parsear_fecha(iniciado_en)
        if dt is None:
            v.addWidget(QLabel("—"))
            return envoltorio

        absoluto = QLabel(self._formatear_absoluta(dt))
        absoluto.setStyleSheet(f"font-size: 12px; color: {COLORES.tinta};")
        v.addWidget(absoluto)

        relativo = QLabel(self._formatear_relativa(dt))
        relativo.setStyleSheet(f"font-size: 11px; color: {COLORES.grafito};")
        v.addWidget(relativo)
        return envoltorio

    def _boton_menu(self, indice_fila: int) -> QToolButton:
        boton = QToolButton()
        boton.setText("⋯")
        boton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        boton.setFixedSize(28, 28)

        menu = QMenu(boton)
        menu.addAction("Ver detalle", lambda: self._mostrar_detalle(indice_fila))
        menu.addAction("Reintentar", lambda: self.reintentar_solicitado.emit(self._filas[indice_fila].automatizacion))
        accion_captura = menu.addAction("Ver captura", lambda: self._abrir_ruta(self._filas[indice_fila].ruta_captura))
        accion_log = menu.addAction("Abrir log", lambda: self._abrir_ruta(self._filas[indice_fila].ruta_log))
        fila = self._filas[indice_fila] if indice_fila < len(self._filas) else None
        if fila:
            accion_captura.setEnabled(bool(fila.ruta_captura and fila.ruta_captura.exists()))
            accion_log.setEnabled(bool(fila.ruta_log and fila.ruta_log.exists()))
        boton.setMenu(menu)
        return boton

    # ---------- panel de detalle ----------

    def _al_seleccionar(self) -> None:
        filas_seleccionadas = self.tabla.selectionModel().selectedRows()
        if filas_seleccionadas:
            self._mostrar_detalle(filas_seleccionadas[0].row())

    def _mostrar_detalle(self, indice: int) -> None:
        if indice < 0 or indice >= len(self._filas):
            return
        self._indice_detalle_actual = indice
        fila = self._filas[indice]

        self._panel_titulo.setText(fila.automatizacion)
        self._panel_mensaje.setText(fila.mensaje or "Sin mensaje adicional.")

        layout_estado = QHBoxLayout()
        layout_estado.setContentsMargins(0, 0, 0, 0)
        badge = StatusBadge(StatusBadge.desde_exito(fila.exito))
        nuevo_estado = QWidget()
        QHBoxLayout(nuevo_estado).addWidget(badge)
        nuevo_estado.layout().setContentsMargins(0, 0, 0, 0)
        nuevo_estado.layout().setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._panel_estado.setParent(None)
        self._panel_estado = nuevo_estado
        self.panel_detalle.layout().insertWidget(1, self._panel_estado)

        self._boton_captura.setEnabled(bool(fila.ruta_captura and fila.ruta_captura.exists()))
        self._boton_log.setEnabled(bool(fila.ruta_log and fila.ruta_log.exists()))

        self.panel_detalle.show()

    def _fila_del_panel(self) -> FilaEjecucion | None:
        """La fila que el panel lateral esta mostrando, o None.

        Devuelve None tambien cuando el indice guardado ya no existe:
        `establecer_filas` (el refresco automatico del panel cada 10 s)
        reemplaza la lista entera, y el indice de antes puede quedar
        apuntando fuera o a OTRA automatizacion -- reintentar la
        equivocada es peor que no hacer nada."""
        indice = self._indice_detalle_actual
        if indice is None or not (0 <= indice < len(self._filas)):
            return None
        return self._filas[indice]

    def _abrir_captura_actual(self) -> None:
        fila = self._fila_del_panel()
        if fila:
            self._abrir_ruta(fila.ruta_captura)

    def _abrir_log_actual(self) -> None:
        fila = self._fila_del_panel()
        if fila:
            self._abrir_ruta(fila.ruta_log)

    def _reintentar_actual(self) -> None:
        fila = self._fila_del_panel()
        if fila:
            self.reintentar_solicitado.emit(fila.automatizacion)

    @staticmethod
    def _abrir_ruta(ruta: Path | None) -> None:
        if ruta and ruta.exists():
            os.startfile(str(ruta))  # noqa: S606 - abrir con la app predeterminada de Windows

    # ---------- formato ----------

    @staticmethod
    def _parsear_fecha(valor: str | None) -> datetime | None:
        if not valor:
            return None
        try:
            dt = datetime.fromisoformat(valor)
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    @staticmethod
    def _formatear_absoluta(dt: datetime) -> str:
        local = dt.astimezone()
        return f"{local.day} {_MESES_ES[local.month - 1]} {local.year}, {local.hour:02d}:{local.minute:02d}"

    @staticmethod
    def _formatear_relativa(dt: datetime) -> str:
        segundos = (datetime.now(timezone.utc) - dt).total_seconds()
        if segundos < 60:
            return "justo ahora"
        minutos = int(segundos // 60)
        if minutos < 60:
            return f"hace {minutos} min"
        horas = minutos // 60
        if horas < 24:
            return f"hace {horas} h"
        dias = horas // 24
        return f"hace {dias} d"

    @classmethod
    def _formatear_duracion(cls, iniciado_en: str | None, finalizado_en: str | None) -> str:
        inicio = cls._parsear_fecha(iniciado_en)
        fin = cls._parsear_fecha(finalizado_en)
        if inicio is None or fin is None:
            return "—"
        segundos = (fin - inicio).total_seconds()
        if segundos < 1:
            return f"{int(segundos * 1000)} ms"
        if segundos < 60:
            return f"{segundos:.1f} s"
        return f"{int(segundos // 60)} min {int(segundos % 60)} s"

    @staticmethod
    def _separar_error(mensaje: str | None) -> tuple[str, str]:
        if not mensaje:
            return "", ""
        if ": " in mensaje:
            tipo, _, detalle = mensaje.partition(": ")
            return tipo, detalle
        return mensaje, ""
