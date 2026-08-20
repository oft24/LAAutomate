"""Notificacion no bloqueante que aparece flotando sobre una vista y se
cierra sola -- para resultados de acciones sin interrumpir al usuario con
un QMessageBox modal."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.resources.tokens import COLORES, ESPACIADO

_TIPOS = {
    "exito": (COLORES.musgo, COLORES.musgo_suave),
    "error": (COLORES.oxido, COLORES.oxido_suave),
    "info": (COLORES.acento, COLORES.acento_suave),
}


class Toast(QWidget):
    """Se ancla en la esquina inferior derecha del `parent` dado."""

    def __init__(self, parent: QWidget, mensaje: str, tipo: str = "info", duracion_ms: int = 3500) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        color, color_suave = _TIPOS.get(tipo, _TIPOS["info"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(ESPACIADO.md, ESPACIADO.sm, ESPACIADO.md, ESPACIADO.sm)
        etiqueta = QLabel(mensaje)
        etiqueta.setStyleSheet(f"color: {color}; font-weight: 600; font-size: 13px;")
        layout.addWidget(etiqueta)

        self.setStyleSheet(
            f"background-color: {color_suave}; border: 1px solid {color}; border-radius: 8px;"
        )

        self.adjustSize()
        self._posicionar(parent)
        self.show()

        QTimer.singleShot(duracion_ms, self.close)

    def _posicionar(self, parent: QWidget) -> None:
        punto = parent.mapToGlobal(parent.rect().bottomRight())
        self.move(punto.x() - self.width() - 24, punto.y() - self.height() - 24)


def mostrar_toast(parent: QWidget, mensaje: str, tipo: str = "info") -> Toast:
    return Toast(parent, mensaje, tipo)
