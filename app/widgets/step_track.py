"""Elemento firma: pista de ejecuciones en plano tecnico. Cada nodo
numerado es UNA ejecucion (no un paso dentro de ella -- ver nota de
arquitectura mas abajo), coloreado por resultado, conectado por lineas
ortogonales estilo linea de metro. Click en un nodo -> abre su detalle.

Nota de arquitectura: la version original del elemento firma imaginaba un
nodo por CADA llamada (self.web.click, escribir...) dentro de una sola
ejecucion -- eso habria requerido instrumentar engine/actions/*.py para
grabar cada llamada, un cambio a la logica que se pidio no tocar. Esta
version usa el mismo lenguaje visual pero con el dato que YA existe: un
nodo por ejecucion completa (de core.database.historial()), mas
ejecuciones recientes a la derecha."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget
from app.i18n import QLabel, QPushButton

from app.resources.tokens import COLORES, ESPACIADO, TIPO
from app.widgets.data_table import FilaEjecucion

MAX_NODOS = 12


class StepTrack(QWidget):
    nodo_clickeado = Signal(int)  # indice dentro de la lista de filas original

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, ESPACIADO.sm, 0, ESPACIADO.sm)
        self._layout.setSpacing(6)
        self.establecer_filas([])

    def establecer_filas(self, filas: list[FilaEjecucion]) -> None:
        self._vaciar()

        if not filas:
            vacio = QLabel("Sin ejecuciones todavía — corre una automatización para ver su pista aquí.")
            vacio.setStyleSheet(f"color: {COLORES.grafito}; font-size: 12px;")
            self._layout.addWidget(vacio)
            self._layout.addStretch()
            return

        recientes = list(enumerate(filas[:MAX_NODOS]))
        recientes.reverse()  # mas vieja de este lote primero (izquierda), mas nueva al final (derecha)

        for numero, (indice_original, fila) in enumerate(recientes, start=1):
            self._layout.addWidget(self._crear_nodo(numero, fila, indice_original))
            if numero < len(recientes):
                self._layout.addWidget(self._crear_conector())
        self._layout.addStretch()

    def _vaciar(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _crear_nodo(self, numero: int, fila: FilaEjecucion, indice_original: int) -> QPushButton:
        color = COLORES.musgo if fila.exito else COLORES.oxido
        fondo = COLORES.musgo_suave if fila.exito else COLORES.oxido_suave
        boton = QPushButton(f"{numero:02d}")
        boton.setFixedSize(38, 36)
        estado_texto = "Completado" if fila.exito else "Con error"
        boton.setToolTip(f"{fila.automatizacion} — {estado_texto}")
        boton.setCursor(Qt.CursorShape.PointingHandCursor)
        boton.setStyleSheet(
            f"QPushButton {{ background-color: {fondo}; color: {color}; padding: 0; "
            f"font-family: {TIPO.familia_mono}; font-weight: 600; font-size: 11px; "
            f"border: 1px solid {color}; border-radius: 8px; }}"
            f"QPushButton:hover {{ background-color: {color}; color: {COLORES.papel}; }}"
            f"QPushButton:focus {{ border: 2px solid {COLORES.tinta}; }}"
        )
        boton.clicked.connect(lambda checked=False, i=indice_original: self.nodo_clickeado.emit(i))
        return boton

    @staticmethod
    def _crear_conector() -> QFrame:
        linea = QFrame()
        linea.setFixedSize(14, 2)
        linea.setStyleSheet(f"background-color: {COLORES.borde_fuerte};")
        return linea
