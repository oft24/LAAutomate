"""Encabezado de pagina: titulo + subtitulo de una linea + acciones
primarias a la derecha. Ninguna vista debe mostrar un titulo flotando solo."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.resources.tokens import ESPACIADO


class PageHeader(QWidget):
    def __init__(
        self,
        titulo: str,
        subtitulo: str,
        acciones: list[tuple[str, callable]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, ESPACIADO.lg)
        layout.setSpacing(ESPACIADO.lg)

        columna_texto = QVBoxLayout()
        columna_texto.setSpacing(3)
        contexto_lbl = QLabel(f"//  {titulo.upper()}")
        contexto_lbl.setObjectName("pageEyebrow")
        columna_texto.addWidget(contexto_lbl)
        titulo_lbl = QLabel(titulo)
        titulo_lbl.setObjectName("pageTitle")
        columna_texto.addWidget(titulo_lbl)
        subtitulo_lbl = QLabel(subtitulo)
        subtitulo_lbl.setObjectName("pageSubtitle")
        subtitulo_lbl.setWordWrap(True)
        subtitulo_lbl.setMinimumWidth(0)
        columna_texto.addWidget(subtitulo_lbl)
        layout.addLayout(columna_texto, stretch=1)

        self.botones: dict[str, QPushButton] = {}
        for i, (etiqueta, callback) in enumerate(acciones or []):
            boton = QPushButton(etiqueta)
            if i == len(acciones) - 1:
                boton.setObjectName("primario")
            boton.clicked.connect(callback)
            layout.addWidget(boton)
            self.botones[etiqueta] = boton
