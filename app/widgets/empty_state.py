"""Estado vacio con instruccion accionable: que es esta pantalla, por que
esta vacia, y un boton -- ninguna vista debe quedarse en blanco sin decir
nada."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app.resources.tokens import COLORES, ESPACIADO


class EmptyState(QWidget):
    def __init__(
        self,
        titulo: str,
        descripcion: str,
        texto_boton: str | None = None,
        on_click: callable = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(ESPACIADO.sm)
        layout.setContentsMargins(ESPACIADO.xxxl, ESPACIADO.xxxl, ESPACIADO.xxxl, ESPACIADO.xxxl)

        titulo_lbl = QLabel(titulo)
        titulo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titulo_lbl.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {COLORES.tinta};")
        layout.addWidget(titulo_lbl)

        desc_lbl = QLabel(descripcion)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {COLORES.grafito}; font-size: 13px;")
        desc_lbl.setMaximumWidth(420)
        layout.addWidget(desc_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

        if texto_boton and on_click:
            boton = QPushButton(texto_boton)
            boton.setObjectName("primario")
            boton.clicked.connect(on_click)
            layout.addSpacing(ESPACIADO.sm)
            layout.addWidget(boton, alignment=Qt.AlignmentFlag.AlignHCenter)
