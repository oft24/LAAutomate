"""Badge de estado: punto de color + etiqueta -- reemplaza el texto plano
'Exitoso'/'Falló' en cualquier tabla o lista de la app."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from app.resources.tokens import COLORES, ESPACIADO

ESTADOS = {
    "completado": ("Completado", COLORES.musgo, COLORES.musgo_suave),
    "en_curso": ("En curso", COLORES.acento, COLORES.acento_suave),
    "con_error": ("Con error", COLORES.oxido, COLORES.oxido_suave),
    "cancelado": ("Cancelado", COLORES.grafito, COLORES.reticula),
    "programado": ("Programado", COLORES.acento, COLORES.acento_suave),
    "manual": ("Manual", COLORES.grafito, COLORES.reticula),
}


class StatusBadge(QFrame):
    def __init__(self, estado: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBadge")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(ESPACIADO.sm, 2, ESPACIADO.sm, 2)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        etiqueta, color, color_suave = ESTADOS.get(estado, (estado.capitalize(), COLORES.grafito, COLORES.reticula))

        self._punto = QLabel("●")
        self._punto.setStyleSheet(f"color: {color}; font-size: 9px;")
        layout.addWidget(self._punto)

        self._texto = QLabel(etiqueta)
        self._texto.setStyleSheet(f"color: {color}; font-weight: 600; font-size: 12px; background: transparent;")
        layout.addWidget(self._texto)

        self.setStyleSheet(f"QFrame#statusBadge {{ background-color: {color_suave}; border-radius: 10px; }}")
        self.setFixedHeight(22)

    @staticmethod
    def desde_exito(exito: bool | None) -> str:
        if exito is None:
            return "en_curso"
        return "completado" if exito else "con_error"
