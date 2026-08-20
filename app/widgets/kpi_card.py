"""Tarjeta de KPI: valor grande + etiqueta + delta opcional."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from app.resources.tokens import COLORES, ESPACIADO


class KpiCard(QFrame):
    def __init__(self, etiqueta: str, valor: str, delta: str | None = None, positivo: bool = True) -> None:
        super().__init__()
        self.setObjectName("tarjeta")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ESPACIADO.lg, ESPACIADO.md, ESPACIADO.lg, ESPACIADO.md)
        layout.setSpacing(4)

        self._etiqueta = QLabel(etiqueta)
        self._etiqueta.setObjectName("kpiEtiqueta")
        layout.addWidget(self._etiqueta)

        fila_valor = QVBoxLayout()
        fila_valor.setSpacing(0)
        self._valor = QLabel(valor)
        self._valor.setObjectName("kpiValor")
        fila_valor.addWidget(self._valor)
        layout.addLayout(fila_valor)

        if delta:
            self._delta = QLabel(delta)
            self._delta.setObjectName("kpiDelta")
            color = COLORES.musgo if positivo else COLORES.oxido
            self._delta.setStyleSheet(f"color: {color}; font-weight: 600; font-size: 12px;")
            layout.addWidget(self._delta)

    def actualizar_valor(self, valor: str) -> None:
        self._valor.setText(valor)
